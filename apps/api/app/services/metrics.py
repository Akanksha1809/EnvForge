"""Prometheus metrics that reflect live platform state (environment/job
counts), computed from the same tables the REST API reads — not a
separately-maintained counter that could drift from reality.

HTTP request metrics (envforge_http_requests_total, latency) are recorded
per-request in app/main.py's middleware instead, since those are genuinely
request-scoped events rather than point-in-time state.

Job/task duration and worker-side counters live in the Celery worker
process, which Prometheus can't scrape directly without a second exporter
process or multiprocess-mode coordination — out of scope for this build.
Instead, the gauges below are computed by querying the same `jobs` table
the worker writes to, at scrape time, which is simpler and avoids
cross-process metric state entirely.
"""

from prometheus_client import Gauge
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EnvironmentState, JobStatus, JobType
from app.models.environment import Environment
from app.models.job import Job

_PROVISIONING_STATES = [
    EnvironmentState.REQUESTED.value,
    EnvironmentState.VALIDATING.value,
    EnvironmentState.QUEUED.value,
    EnvironmentState.PROVISIONING.value,
    EnvironmentState.DEPLOYING.value,
    EnvironmentState.HEALTH_CHECKING.value,
]
_ACTIVE_STATES = [*_PROVISIONING_STATES, EnvironmentState.READY.value]
_QUEUED_JOB_STATUSES = [JobStatus.PENDING.value, JobStatus.QUEUED.value, JobStatus.RUNNING.value]

environments_active = Gauge(
    "envforge_environments_active", "Environments currently in a non-terminal state"
)
environments_provisioning = Gauge(
    "envforge_environments_provisioning", "Environments currently being provisioned"
)
environments_failed = Gauge("envforge_environments_failed", "Environments in the FAILED state")
jobs_queued = Gauge("envforge_jobs_queued", "Jobs pending, queued, or running")
jobs_failed_total_gauge = Gauge(
    "envforge_jobs_failed", "Jobs currently in the FAILED state (not yet retried)"
)
provisioning_success_rate = Gauge(
    "envforge_provisioning_success_rate",
    "Fraction of completed provisioning jobs that succeeded (0-1)",
)
provisioning_duration_avg_seconds = Gauge(
    "envforge_provisioning_duration_avg_seconds",
    "Average duration of successful provisioning jobs, in seconds",
)


async def refresh_gauges(db: AsyncSession) -> None:
    """Called once per `/metrics` scrape — cheap count queries, no
    different in cost from what the dashboard endpoint already runs on
    every page load."""
    environments_active.set(
        (
            await db.execute(
                select(func.count())
                .select_from(Environment)
                .where(Environment.state.in_(_ACTIVE_STATES))
            )
        ).scalar_one()
    )
    environments_provisioning.set(
        (
            await db.execute(
                select(func.count())
                .select_from(Environment)
                .where(Environment.state.in_(_PROVISIONING_STATES))
            )
        ).scalar_one()
    )
    environments_failed.set(
        (
            await db.execute(
                select(func.count())
                .select_from(Environment)
                .where(Environment.state == EnvironmentState.FAILED.value)
            )
        ).scalar_one()
    )
    jobs_queued.set(
        (
            await db.execute(
                select(func.count()).select_from(Job).where(Job.status.in_(_QUEUED_JOB_STATUSES))
            )
        ).scalar_one()
    )
    jobs_failed_total_gauge.set(
        (
            await db.execute(
                select(func.count()).select_from(Job).where(Job.status == JobStatus.FAILED.value)
            )
        ).scalar_one()
    )

    completed_rows = (
        await db.execute(
            select(Job.status, Job.started_at, Job.finished_at).where(
                Job.job_type == JobType.PROVISION.value,
                Job.status.in_([JobStatus.SUCCEEDED.value, JobStatus.FAILED.value]),
            )
        )
    ).all()
    if completed_rows:
        succeeded = [r for r in completed_rows if r[0] == JobStatus.SUCCEEDED.value]
        provisioning_success_rate.set(len(succeeded) / len(completed_rows))
        durations = [
            (r[2] - r[1]).total_seconds()
            for r in succeeded
            if r[1] is not None and r[2] is not None
        ]
        if durations:
            provisioning_duration_avg_seconds.set(sum(durations) / len(durations))
