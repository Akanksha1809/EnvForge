"""The real provisioning pipeline: QUEUED -> PROVISIONING -> DEPLOYING ->
HEALTH_CHECKING -> READY (or FAILED at any step), driving actual Terraform
+ kubectl against the local kind cluster. See app/services/provisioning.py
for the Terraform orchestration and app/services/lifecycle.py for the
state machine every transition below goes through.
"""

import asyncio
from datetime import UTC, datetime

from app.core.logging import get_logger
from app.models.application import Application
from app.models.enums import EnvironmentState, EventTrigger, JobStatus
from app.models.environment import Environment
from app.models.job import Job
from app.services import github_client, lifecycle, provisioning
from app.services.applications import get_application
from app.services.environments import get_environment
from app.services.teams import get_team
from app.workers.celery_app import celery_app
from app.workers.db import task_db_session

logger = get_logger("envforge.worker.provisioning")


@celery_app.task(name="envforge.provision_environment", bind=True, max_retries=2)
def provision_environment_task(self, job_id: str) -> None:
    asyncio.run(_provision_environment(job_id))


@celery_app.task(name="envforge.destroy_environment", bind=True, max_retries=2)
def destroy_environment_task(self, job_id: str) -> None:
    asyncio.run(_destroy_environment(job_id))


async def _mark_job_failed(db, job: Job, message: str) -> None:
    job.status = JobStatus.FAILED.value
    job.error_message = message[:4000]
    job.finished_at = datetime.now(UTC)
    db.add(job)
    await db.commit()


async def _report_github_status(
    environment: Environment,
    application: Application,
    *,
    state: str,
    description: str,
    target_url: str | None = None,
    comment_on_success: bool = False,
) -> None:
    """No-ops quietly for manually-created (non-PR) environments or
    applications with no linked repo — see app.services.github_client for
    why an absent GITHUB_API_TOKEN also makes this a safe no-op."""
    if (
        environment.pr_number is None
        or not application.github_repo
        or not environment.pr_commit_sha
    ):
        return

    await github_client.post_commit_status(
        application.github_repo,
        environment.pr_commit_sha,
        state=state,
        description=description,
        target_url=target_url,
    )
    if comment_on_success and target_url:
        await github_client.post_pr_comment(
            application.github_repo,
            environment.pr_number,
            f"🚀 EnvForge preview environment is ready: {target_url}",
        )


async def _provision_environment(job_id: str) -> None:
    async with task_db_session() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.error("provision.job_not_found", job_id=job_id)
            return

        environment = await get_environment(db, job.environment_id) if job.environment_id else None
        if environment is None:
            await _mark_job_failed(db, job, "environment no longer exists")
            return

        application = await get_application(db, environment.application_id)
        if application is None:
            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.FAILED,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
                error_message="application no longer exists",
            )
            await _mark_job_failed(db, job, "application no longer exists")
            return

        team = await get_team(db, application.team_id)
        team_slug = team.slug if team else application.team_id

        job.status = JobStatus.RUNNING.value
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        db.add(job)
        await db.commit()

        try:
            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.PROVISIONING,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
            )

            outputs = await asyncio.to_thread(
                provisioning.apply_environment, environment, application, team_slug
            )

            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.DEPLOYING,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
                metadata={"note": "terraform apply blocks until the Deployment rollout completes"},
            )
            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.HEALTH_CHECKING,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
            )

            namespace = outputs.get("namespace_name")
            if not namespace:
                raise provisioning.ProvisioningError(
                    "terraform apply did not produce a namespace_name output"
                )
            healthy = await asyncio.to_thread(provisioning.wait_for_health, application, namespace)
            if not healthy:
                raise provisioning.ProvisioningError(
                    "Pods did not reach Ready within the health-check timeout"
                )

            is_first_time_ready = environment.namespace is None
            environment.namespace = namespace
            environment.preview_url = outputs.get("preview_url")
            db.add(environment)
            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.READY,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
            )

            job.status = JobStatus.SUCCEEDED.value
            job.result = outputs
            job.finished_at = datetime.now(UTC)
            db.add(job)
            await db.commit()
            logger.info("provision.succeeded", environment_id=environment.id, namespace=namespace)

            await _report_github_status(
                environment,
                application,
                state="success",
                description="EnvForge preview environment is ready",
                target_url=environment.preview_url,
                comment_on_success=is_first_time_ready,
            )

        except Exception as exc:
            logger.error(
                "provision.failed", job_id=job_id, environment_id=environment.id, error=str(exc)
            )
            await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.FAILED,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
                error_message=str(exc),
            )
            await _mark_job_failed(db, job, str(exc))
            await _report_github_status(
                environment,
                application,
                state="failure",
                description="EnvForge preview environment provisioning failed",
            )


async def _destroy_environment(job_id: str) -> None:
    async with task_db_session() as db:
        job = await db.get(Job, job_id)
        if job is None:
            logger.error("destroy.job_not_found", job_id=job_id)
            return

        environment = await get_environment(db, job.environment_id) if job.environment_id else None
        if environment is None:
            await _mark_job_failed(db, job, "environment no longer exists")
            return

        job.status = JobStatus.RUNNING.value
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        db.add(job)
        await db.commit()

        try:
            await asyncio.to_thread(provisioning.destroy_environment, environment)

            environment = await lifecycle.transition(
                db,
                environment,
                target=EnvironmentState.DELETED,
                trigger=EventTrigger.SYSTEM,
                job_id=job_id,
            )
            environment.destroyed_at = datetime.now(UTC)
            db.add(environment)

            job.status = JobStatus.SUCCEEDED.value
            job.finished_at = datetime.now(UTC)
            db.add(job)
            await db.commit()
            logger.info("destroy.succeeded", environment_id=environment.id)

        except Exception as exc:
            # Deliberately do NOT transition to DELETED on failure — the
            # spec requires that a failed teardown preserve state and
            # retry rather than falsely report deletion. The environment
            # stays in DELETING so it's visible to the cleanup engine's
            # retry loop (Phase 5) and to `POST /jobs/{id}/retry`.
            logger.error(
                "destroy.failed", job_id=job_id, environment_id=environment.id, error=str(exc)
            )
            await _mark_job_failed(db, job, str(exc))
