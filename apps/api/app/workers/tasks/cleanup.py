"""The cleanup engine: TTL expiration, orphan detection, and stale-job
detection, run on Celery beat's schedule (see app/workers/celery_app.py).

Each sweep is independently idempotent and safe to run concurrently with
itself (e.g. if a previous run is still finishing) — every action it takes
goes through the same lifecycle/provisioning code paths the API and the
provisioning task use, so there is exactly one way any of this happens.
"""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.enums import EnvironmentState, EventTrigger, JobStatus
from app.models.environment import Environment
from app.models.job import Job
from app.services import audit, environments, provisioning
from app.services.environments import get_environment
from app.workers.celery_app import celery_app
from app.workers.db import task_db_session

logger = get_logger("envforge.worker.cleanup")

_TERMINAL_OR_DELETING = {
    EnvironmentState.DELETED.value,
    EnvironmentState.EXPIRED.value,
    EnvironmentState.DELETING.value,
}


@celery_app.task(name="envforge.sweep_expired_environments")
def sweep_expired_environments_task() -> None:
    asyncio.run(_sweep_expired_environments())


@celery_app.task(name="envforge.detect_orphaned_namespaces")
def detect_orphaned_namespaces_task() -> None:
    asyncio.run(_detect_orphaned_namespaces())


@celery_app.task(name="envforge.detect_stale_jobs")
def detect_stale_jobs_task() -> None:
    asyncio.run(_detect_stale_jobs())


async def _sweep_expired_environments() -> None:
    async with task_db_session() as db:
        now = datetime.now(UTC)
        result = await db.execute(
            select(Environment).where(
                Environment.ttl_expires_at.is_not(None),
                Environment.ttl_expires_at < now,
                Environment.state.not_in(_TERMINAL_OR_DELETING),
            )
        )
        expired = result.scalars().all()

        for environment in expired:
            logger.info(
                "cleanup.ttl_expired",
                environment_id=environment.id,
                ttl_expires_at=str(environment.ttl_expires_at),
            )
            await environments.expire_environment(db, environment, trigger=EventTrigger.TTL)
            await audit.record(
                db,
                action="environment.ttl_expired",
                resource_type="environment",
                resource_id=environment.id,
                actor_label="cleanup-engine",
            )

        if expired:
            logger.info("cleanup.ttl_sweep_complete", expired_count=len(expired))


async def _detect_orphaned_namespaces() -> None:
    async with task_db_session() as db:
        managed = await asyncio.to_thread(provisioning.list_managed_namespaces)
        if not managed:
            return

        for ns in managed:
            namespace_name, environment_id = ns["name"], ns["environment_id"]
            environment = await get_environment(db, environment_id) if environment_id else None

            if environment is not None and environment.state not in (
                EnvironmentState.DELETED.value,
                EnvironmentState.EXPIRED.value,
            ):
                continue  # genuinely still owned by an active environment

            logger.warning(
                "cleanup.orphaned_namespace_detected",
                namespace=namespace_name,
                environment_id=environment_id or None,
                environment_state=environment.state if environment else None,
            )
            try:
                if environment is not None:
                    # A real Environment row exists but it's terminal —
                    # destroy() through Terraform if its workspace/state
                    # is still around, so state stays consistent.
                    await asyncio.to_thread(provisioning.destroy_environment, environment)
                else:
                    await asyncio.to_thread(provisioning.delete_namespace_directly, namespace_name)
            except provisioning.ProvisioningError as exc:
                logger.error(
                    "cleanup.orphan_cleanup_failed", namespace=namespace_name, error=str(exc)
                )
                continue

            await audit.record(
                db,
                action="namespace.orphan_cleaned_up",
                resource_type="namespace",
                resource_id=namespace_name,
                actor_label="cleanup-engine",
                metadata={"environment_id": environment_id or None},
            )


async def _detect_stale_jobs() -> None:
    settings = get_settings()
    cutoff = datetime.now(UTC) - timedelta(minutes=settings.stale_job_timeout_minutes)

    async with task_db_session() as db:
        result = await db.execute(
            select(Job).where(
                Job.status == JobStatus.RUNNING.value,
                Job.started_at.is_not(None),
                Job.started_at < cutoff,
            )
        )
        stale_jobs = result.scalars().all()

        for job in stale_jobs:
            logger.warning(
                "cleanup.stale_job_detected", job_id=job.id, started_at=str(job.started_at)
            )
            job.status = JobStatus.FAILED.value
            job.error_message = (
                f"Job exceeded {settings.stale_job_timeout_minutes} minutes in RUNNING state — "
                "the worker process that owned it is presumed crashed. "
                "Retry via POST /jobs/{id}/retry."
            )
            job.finished_at = datetime.now(UTC)
            db.add(job)

            if job.environment_id:
                environment = await get_environment(db, job.environment_id)
                if environment is not None and environment.state not in (
                    EnvironmentState.DELETED.value,
                    EnvironmentState.EXPIRED.value,
                ):
                    from app.services import lifecycle

                    try:
                        await lifecycle.transition(
                            db,
                            environment,
                            target=EnvironmentState.FAILED,
                            trigger=EventTrigger.SYSTEM,
                            job_id=job.id,
                            error_message="Associated job went stale (worker crash presumed)",
                            commit=False,
                        )
                    except lifecycle.InvalidTransitionError:
                        pass  # already FAILED or otherwise can't — job update above still stands

            await db.commit()
            await audit.record(
                db,
                action="job.marked_stale",
                resource_type="job",
                resource_id=job.id,
                actor_label="cleanup-engine",
            )

        if stale_jobs:
            logger.info("cleanup.stale_job_sweep_complete", stale_count=len(stale_jobs))
