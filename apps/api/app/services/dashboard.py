"""Dashboard aggregates — every number here is a real query against the
same tables the rest of the API reads/writes, never a hand-maintained
counter that could drift. Cost figures are deliberately not included
here; that's the Phase 8 cost engine's job, and it will clearly label
estimated vs. simulated vs. (never, in this build) actual figures.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState, JobStatus, JobType
from app.models.environment import Environment
from app.models.job import Job
from app.models.team import Team

_PROVISIONING_STATES = [
    EnvironmentState.REQUESTED.value,
    EnvironmentState.VALIDATING.value,
    EnvironmentState.QUEUED.value,
    EnvironmentState.PROVISIONING.value,
    EnvironmentState.DEPLOYING.value,
    EnvironmentState.HEALTH_CHECKING.value,
]
_ACTIVE_STATES = [*_PROVISIONING_STATES, EnvironmentState.READY.value]


async def get_summary(db: AsyncSession, *, expiring_within_hours: int = 24) -> dict:
    total_environments = (
        await db.execute(select(func.count()).select_from(Environment))
    ).scalar_one()

    active_environments = (
        await db.execute(
            select(func.count())
            .select_from(Environment)
            .where(Environment.state.in_(_ACTIVE_STATES))
        )
    ).scalar_one()

    provisioning_environments = (
        await db.execute(
            select(func.count())
            .select_from(Environment)
            .where(Environment.state.in_(_PROVISIONING_STATES))
        )
    ).scalar_one()

    failed_environments = (
        await db.execute(
            select(func.count())
            .select_from(Environment)
            .where(Environment.state == EnvironmentState.FAILED.value)
        )
    ).scalar_one()

    expiring_cutoff = datetime.now(UTC) + timedelta(hours=expiring_within_hours)
    expiring_environments = (
        await db.execute(
            select(func.count())
            .select_from(Environment)
            .where(
                Environment.state == EnvironmentState.READY.value,
                Environment.ttl_expires_at.is_not(None),
                Environment.ttl_expires_at < expiring_cutoff,
            )
        )
    ).scalar_one()

    by_application_rows = (
        await db.execute(
            select(Application.name, Application.slug, func.count(Environment.id))
            .join(Environment, Environment.application_id == Application.id)
            .where(Environment.state.in_(_ACTIVE_STATES))
            .group_by(Application.id, Application.name, Application.slug)
            .order_by(func.count(Environment.id).desc())
        )
    ).all()
    by_application = [
        {"name": name, "slug": slug, "active_count": count}
        for name, slug, count in by_application_rows
    ]

    by_team_rows = (
        await db.execute(
            select(Team.name, Team.slug, func.count(Environment.id))
            .join(Application, Application.team_id == Team.id)
            .join(Environment, Environment.application_id == Application.id)
            .where(Environment.state.in_(_ACTIVE_STATES))
            .group_by(Team.id, Team.name, Team.slug)
            .order_by(func.count(Environment.id).desc())
        )
    ).all()
    by_team = [
        {"name": name, "slug": slug, "active_count": count} for name, slug, count in by_team_rows
    ]

    # Success rate + average provisioning duration, over completed
    # PROVISION jobs (SUCCEEDED or FAILED — anything still in flight
    # hasn't concluded yet and shouldn't count either way).
    provision_job_rows = (
        await db.execute(
            select(Job.status, Job.started_at, Job.finished_at).where(
                Job.job_type == JobType.PROVISION.value,
                Job.status.in_([JobStatus.SUCCEEDED.value, JobStatus.FAILED.value]),
            )
        )
    ).all()
    succeeded = [r for r in provision_job_rows if r[0] == JobStatus.SUCCEEDED.value]
    total_completed = len(provision_job_rows)
    success_rate = (len(succeeded) / total_completed) if total_completed else None

    durations = [
        (r[2] - r[1]).total_seconds() for r in succeeded if r[1] is not None and r[2] is not None
    ]
    avg_provisioning_seconds = (sum(durations) / len(durations)) if durations else None

    recent_jobs_rows = (
        (await db.execute(select(Job).order_by(Job.created_at.desc()).limit(10))).scalars().all()
    )

    return {
        "total_environments": total_environments,
        "active_environments": active_environments,
        "provisioning_environments": provisioning_environments,
        "failed_environments": failed_environments,
        "expiring_environments": expiring_environments,
        "environments_by_application": by_application,
        "environments_by_team": by_team,
        "provisioning_success_rate": success_rate,
        "average_provisioning_duration_seconds": avg_provisioning_seconds,
        "recent_jobs": recent_jobs_rows,
    }
