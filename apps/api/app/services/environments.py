"""Environment creation/extend/refresh/delete business logic.

This module takes an environment through REQUESTED -> VALIDATING -> QUEUED
(all fast, synchronous checks) and creates the Job row a Celery task picks
up to actually provision or destroy infrastructure
(app/workers/tasks/provisioning.py). No endpoint here ever blocks on
infrastructure work, satisfying the spec's "API must not block on
provisioning" rule. Task dispatch is best-effort (see
app/services/task_dispatch.py): if the broker is unreachable the Job row
simply stays PENDING rather than the request failing.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.application import Application
from app.models.enums import EnvironmentState, EventTrigger, JobStatus, JobType
from app.models.environment import Environment, EnvironmentEvent
from app.models.job import Job
from app.models.team import Team
from app.services import lifecycle, quotas, task_dispatch


class EnvironmentError(Exception):
    pass


class QuotaExceededError(EnvironmentError):
    pass


async def _generate_environment_name(
    db: AsyncSession, application: Application, pr_number: int | None
) -> str:
    if pr_number is not None:
        base = f"{application.slug}-pr-{pr_number}"
    else:
        base = f"{application.slug}-manual"

    result = await db.execute(select(Environment).where(Environment.name.like(f"{base}%")))
    count = len(result.scalars().all())
    return base if count == 0 else f"{base}-{count + 1}"


async def create_environment(
    db: AsyncSession,
    *,
    application: Application,
    requested_by_user_id: str | None,
    name: str | None = None,
    pr_number: int | None = None,
    pr_branch: str | None = None,
    pr_commit_sha: str | None = None,
    config_overrides: dict[str, Any] | None = None,
    trigger: EventTrigger = EventTrigger.USER,
) -> Environment:
    if not application.is_active:
        raise EnvironmentError("Cannot create an environment for an inactive application")

    team = await db.get(Team, application.team_id)
    try:
        await quotas.check_all_quotas(
            db, user_id=requested_by_user_id, application=application, team=team
        )
    except quotas.QuotaExceededError as exc:
        raise QuotaExceededError(str(exc)) from exc

    resolved_name = name or await _generate_environment_name(db, application, pr_number)
    ttl_hours = application.environment_ttl_hours

    environment = Environment(
        application_id=application.id,
        requested_by_user_id=requested_by_user_id,
        template_id=application.environment_template_id,
        template_version=application.environment_template_version,
        name=resolved_name,
        state=EnvironmentState.REQUESTED.value,
        pr_number=pr_number,
        pr_branch=pr_branch,
        pr_commit_sha=pr_commit_sha,
        config_snapshot=config_overrides or {},
        ttl_expires_at=datetime.now(UTC) + timedelta(hours=ttl_hours),
    )
    db.add(environment)
    await db.flush()

    # Initial REQUESTED state needs its own event row since `transition()`
    # only records *changes* — there's no prior state to transition from.
    db.add(
        EnvironmentEvent(
            environment_id=environment.id,
            previous_state=EnvironmentState.REQUESTED.value,
            new_state=EnvironmentState.REQUESTED.value,
            trigger=trigger.value,
            actor_user_id=requested_by_user_id,
        )
    )

    # Fast synchronous validation — config shape, template compatibility —
    # happens here. There's nothing to validate yet beyond "app is active"
    # until templates are enforced more strictly in Phase 3.
    await lifecycle.transition(
        db, environment, target=EnvironmentState.VALIDATING, trigger=trigger, commit=False
    )
    await lifecycle.transition(
        db, environment, target=EnvironmentState.QUEUED, trigger=trigger, commit=False
    )

    job = Job(
        job_type=JobType.PROVISION.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
        payload={"application_id": application.id, "environment_id": environment.id},
    )
    db.add(job)
    await db.commit()
    await db.refresh(environment)
    await db.refresh(job)

    task_id = task_dispatch.enqueue("envforge.provision_environment", job_id=job.id)
    if task_id:
        job.status = JobStatus.QUEUED.value
        job.celery_task_id = task_id
        db.add(job)
        await db.commit()

    return environment


async def get_environment(db: AsyncSession, environment_id: str) -> Environment | None:
    return await db.get(Environment, environment_id)


_TERMINAL_STATES = {EnvironmentState.DELETED.value, EnvironmentState.EXPIRED.value}


async def get_active_environment_for_pr(
    db: AsyncSession, *, application_id: str, pr_number: int
) -> Environment | None:
    """The non-terminal environment for this (application, PR) pair, if
    any — used by the GitHub webhook handler to find the environment a
    `synchronize`/`closed` event applies to, and to avoid creating a
    second environment for a PR that already has one."""
    result = await db.execute(
        select(Environment)
        .where(
            Environment.application_id == application_id,
            Environment.pr_number == pr_number,
            Environment.state.not_in(_TERMINAL_STATES),
        )
        .order_by(Environment.created_at.desc())
    )
    return result.scalars().first()


async def redeploy_for_new_commit(
    db: AsyncSession,
    environment: Environment,
    *,
    commit_sha: str,
    trigger: EventTrigger,
) -> Environment:
    """A new commit was pushed to the PR this environment tracks. Reuses
    the same Environment row (never creates a second one for the same
    PR) and re-enters the provisioning pipeline from whatever state it's
    currently in — `terraform apply` against the existing workspace/state
    is idempotent, so this is a real redeploy, not a fresh provision."""
    current = EnvironmentState(environment.state)
    if current in (EnvironmentState.DELETED, EnvironmentState.DELETING, EnvironmentState.EXPIRED):
        raise EnvironmentError(f"Cannot redeploy an environment in state '{environment.state}'")

    environment.pr_commit_sha = commit_sha
    db.add(
        EnvironmentEvent(
            environment_id=environment.id,
            previous_state=environment.state,
            new_state=environment.state,
            trigger=trigger.value,
            metadata_json={"note": "new commit pushed", "commit_sha": commit_sha},
        )
    )
    db.add(environment)

    if current not in (EnvironmentState.READY, EnvironmentState.FAILED):
        # A provisioning run is already in flight for this environment —
        # its Terraform workspace uses unlocked local state, so running a
        # second `apply` concurrently against it is unsafe. The commit
        # SHA is already updated above; the in-flight run finishing (or
        # failing) is what the next redeploy, if any, will build on.
        await db.commit()
        await db.refresh(environment)
        return environment

    job = Job(
        job_type=JobType.PROVISION.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
        payload={"environment_id": environment.id, "commit_sha": commit_sha, "redeploy": True},
    )
    db.add(job)
    await db.commit()
    await db.refresh(environment)
    await db.refresh(job)

    task_id = task_dispatch.enqueue("envforge.provision_environment", job_id=job.id)
    if task_id:
        job.status = JobStatus.QUEUED.value
        job.celery_task_id = task_id
        db.add(job)
        await db.commit()

    return environment


async def extend_environment(
    db: AsyncSession, environment: Environment, *, additional_hours: int, actor_user_id: str | None
) -> Environment:
    if EnvironmentState(environment.state) in (
        EnvironmentState.DELETED,
        EnvironmentState.DELETING,
        EnvironmentState.EXPIRED,
        EnvironmentState.FAILED,
    ):
        raise EnvironmentError(f"Cannot extend an environment in state '{environment.state}'")

    settings = get_settings()
    base = environment.ttl_expires_at or datetime.now(UTC)
    requested_expiry = base + timedelta(hours=additional_hours)
    max_expiry = environment.created_at + timedelta(hours=settings.max_environment_lifetime_hours)
    if requested_expiry > max_expiry:
        raise EnvironmentError(
            f"Cannot extend beyond this platform's maximum environment lifetime "
            f"({settings.max_environment_lifetime_hours} hours from creation)"
        )

    environment.ttl_expires_at = requested_expiry
    db.add(
        EnvironmentEvent(
            environment_id=environment.id,
            previous_state=environment.state,
            new_state=environment.state,
            trigger=EventTrigger.USER.value,
            actor_user_id=actor_user_id,
            metadata_json={"extended_by_hours": additional_hours},
        )
    )
    db.add(environment)
    await db.commit()
    await db.refresh(environment)
    return environment


async def request_deletion(
    db: AsyncSession, environment: Environment, *, actor_user_id: str | None, trigger: EventTrigger
) -> Environment:
    current = EnvironmentState(environment.state)
    if current in (EnvironmentState.DELETED, EnvironmentState.DELETING):
        return environment
    if not lifecycle.is_valid_transition(current, EnvironmentState.DELETING):
        raise EnvironmentError(f"Cannot delete an environment in state '{environment.state}'")

    environment = await lifecycle.transition(
        db,
        environment,
        target=EnvironmentState.DELETING,
        trigger=trigger,
        actor_user_id=actor_user_id,
    )

    if not environment.namespace:
        # Nothing was ever actually provisioned (it never got past QUEUED,
        # or provisioning failed before creating a namespace) — there's no
        # infrastructure to tear down, so this completes immediately rather
        # than waiting on a Celery task that has nothing real to do.
        environment = await lifecycle.transition(
            db,
            environment,
            target=EnvironmentState.DELETED,
            trigger=trigger,
            actor_user_id=actor_user_id,
        )
        environment.destroyed_at = datetime.now(UTC)
        db.add(environment)
        await db.commit()
        await db.refresh(environment)
        return environment

    job = Job(
        job_type=JobType.CLEANUP.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
        payload={"environment_id": environment.id, "namespace": environment.namespace},
    )
    db.add(job)
    await db.commit()
    await db.refresh(environment)
    await db.refresh(job)

    task_id = task_dispatch.enqueue("envforge.destroy_environment", job_id=job.id)
    if task_id:
        job.status = JobStatus.QUEUED.value
        job.celery_task_id = task_id
        db.add(job)
        await db.commit()

    return environment


async def expire_environment(
    db: AsyncSession, environment: Environment, *, trigger: EventTrigger = EventTrigger.TTL
) -> Environment:
    """TTL ran out (or a platform admin force-expired it manually). Marks
    EXPIRED, then immediately requests deletion — expiring an environment
    always means tearing it down, there's no "expired but still running"
    state in this platform."""
    current = EnvironmentState(environment.state)
    if current in (EnvironmentState.DELETED, EnvironmentState.DELETING, EnvironmentState.EXPIRED):
        return environment

    environment = await lifecycle.transition(
        db, environment, target=EnvironmentState.EXPIRED, trigger=trigger
    )
    return await request_deletion(db, environment, actor_user_id=None, trigger=trigger)
