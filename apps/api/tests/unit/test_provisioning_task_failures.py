"""Failure-injection tests for the Celery provisioning pipeline
(app/workers/tasks/provisioning.py). These exercise the actual task
coroutines against a real (in-memory) database and lifecycle state
machine, with only the Terraform/kubectl calls mocked — everything else
(state transitions, job bookkeeping, error persistence) is real.

`task_db_session` creates its own engine from `settings.database_url`,
bypassing the FastAPI `get_db` override the other fixtures rely on, so it
is monkeypatched here to reuse the test's own `db_session`.
"""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState, JobStatus, JobType
from app.models.environment import Environment
from app.models.job import Job
from app.models.team import Team
from app.services import provisioning
from app.workers.tasks import provisioning as provisioning_tasks


def _patch_task_db_session(db_session: AsyncSession):
    @asynccontextmanager
    async def _factory():
        yield db_session

    return patch.object(provisioning_tasks, "task_db_session", _factory)


async def _make_team_and_app(db_session: AsyncSession) -> Application:
    team = Team(name="Failure Team", slug="failure-team")
    db_session.add(team)
    await db_session.flush()

    app = Application(
        name="Failure App",
        slug="failure-app",
        team_id=team.id,
        deployment_config={"image": "nginxdemos/hello:latest", "port": 80},
    )
    db_session.add(app)
    await db_session.flush()
    return app


async def _make_queued_environment(
    db_session: AsyncSession, application: Application
) -> Environment:
    environment = Environment(
        application_id=application.id,
        name="failure-env",
        state=EnvironmentState.QUEUED.value,
    )
    db_session.add(environment)
    await db_session.flush()
    return environment


async def _make_provision_job(db_session: AsyncSession, environment: Environment) -> Job:
    job = Job(
        job_type=JobType.PROVISION.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_provision_task_transitions_to_failed_when_terraform_apply_raises(
    db_session: AsyncSession,
) -> None:
    application = await _make_team_and_app(db_session)
    environment = await _make_queued_environment(db_session, application)
    job = await _make_provision_job(db_session, environment)

    with (
        _patch_task_db_session(db_session),
        patch.object(
            provisioning,
            "apply_environment",
            side_effect=provisioning.ProvisioningError("terraform apply failed: exit status 1"),
        ),
    ):
        await provisioning_tasks._provision_environment(job.id)

    await db_session.refresh(environment)
    await db_session.refresh(job)

    assert environment.state == EnvironmentState.FAILED.value
    assert environment.last_error is not None
    assert "terraform apply failed" in environment.last_error
    assert job.status == JobStatus.FAILED.value
    assert job.error_message is not None
    assert job.attempts == 1


@pytest.mark.asyncio
async def test_provision_task_transitions_to_failed_when_health_check_times_out(
    db_session: AsyncSession,
) -> None:
    application = await _make_team_and_app(db_session)
    environment = await _make_queued_environment(db_session, application)
    job = await _make_provision_job(db_session, environment)

    with (
        _patch_task_db_session(db_session),
        patch.object(
            provisioning,
            "apply_environment",
            return_value={"namespace_name": "envforge-failure-app-abc123"},
        ),
        patch.object(provisioning, "wait_for_health", return_value=False),
    ):
        await provisioning_tasks._provision_environment(job.id)

    await db_session.refresh(environment)
    await db_session.refresh(job)

    assert environment.state == EnvironmentState.FAILED.value
    assert "Ready" in environment.last_error
    assert job.status == JobStatus.FAILED.value
    # Namespace is never recorded for a health-check failure — the
    # environment never reached a state it should claim as provisioned.
    assert environment.namespace is None


@pytest.mark.asyncio
async def test_provision_task_reaches_ready_on_success(db_session: AsyncSession) -> None:
    application = await _make_team_and_app(db_session)
    environment = await _make_queued_environment(db_session, application)
    job = await _make_provision_job(db_session, environment)

    with (
        _patch_task_db_session(db_session),
        patch.object(
            provisioning,
            "apply_environment",
            return_value={
                "namespace_name": "envforge-failure-app-abc123",
                "preview_url": "http://failure-app.127.0.0.1.nip.io:18080",
            },
        ),
        patch.object(provisioning, "wait_for_health", return_value=True),
    ):
        await provisioning_tasks._provision_environment(job.id)

    await db_session.refresh(environment)
    await db_session.refresh(job)

    assert environment.state == EnvironmentState.READY.value
    assert environment.namespace == "envforge-failure-app-abc123"
    assert environment.preview_url == "http://failure-app.127.0.0.1.nip.io:18080"
    assert job.status == JobStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_destroy_task_stays_in_deleting_when_terraform_destroy_raises(
    db_session: AsyncSession,
) -> None:
    """A failed teardown must never be reported as DELETED — the
    environment stays in DELETING, visible to the cleanup engine's retry
    loop and to POST /jobs/{id}/retry, rather than lying about success."""
    application = await _make_team_and_app(db_session)
    environment = Environment(
        application_id=application.id,
        name="failure-env-delete",
        state=EnvironmentState.DELETING.value,
        namespace="envforge-failure-app-abc123",
    )
    db_session.add(environment)
    await db_session.flush()

    job = Job(
        job_type=JobType.CLEANUP.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with (
        _patch_task_db_session(db_session),
        patch.object(
            provisioning,
            "destroy_environment",
            side_effect=provisioning.ProvisioningError("kubectl delete namespace timed out"),
        ),
    ):
        await provisioning_tasks._destroy_environment(job.id)

    await db_session.refresh(environment)
    await db_session.refresh(job)

    assert environment.state == EnvironmentState.DELETING.value
    assert environment.destroyed_at is None
    assert job.status == JobStatus.FAILED.value
    assert "kubectl delete namespace timed out" in job.error_message


@pytest.mark.asyncio
async def test_destroy_task_succeeds_and_marks_deleted(db_session: AsyncSession) -> None:
    application = await _make_team_and_app(db_session)
    environment = Environment(
        application_id=application.id,
        name="failure-env-delete-ok",
        state=EnvironmentState.DELETING.value,
        namespace="envforge-failure-app-def456",
    )
    db_session.add(environment)
    await db_session.flush()

    job = Job(
        job_type=JobType.CLEANUP.value,
        status=JobStatus.PENDING.value,
        environment_id=environment.id,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    with (
        _patch_task_db_session(db_session),
        patch.object(provisioning, "destroy_environment", return_value=None),
    ):
        await provisioning_tasks._destroy_environment(job.id)

    await db_session.refresh(environment)
    await db_session.refresh(job)

    assert environment.state == EnvironmentState.DELETED.value
    assert environment.destroyed_at is not None
    assert job.status == JobStatus.SUCCEEDED.value
