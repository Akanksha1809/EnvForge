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

from app.models.application import Application
from app.models.enums import EnvironmentState, EventTrigger, JobStatus, JobType
from app.models.environment import Environment, EnvironmentEvent
from app.models.job import Job
from app.models.team import Team
from app.services import lifecycle, task_dispatch
from app.services.teams import count_active_environments_for_team


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
    if team is not None:
        active_count = await count_active_environments_for_team(db, team.id)
        if active_count >= team.max_active_environments:
            raise QuotaExceededError(
                f"Team '{team.slug}' is at its active environment quota "
                f"({active_count}/{team.max_active_environments})"
            )

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

    base = environment.ttl_expires_at or datetime.now(UTC)
    environment.ttl_expires_at = base + timedelta(hours=additional_hours)
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
