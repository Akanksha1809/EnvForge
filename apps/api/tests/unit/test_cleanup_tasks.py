from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState, JobStatus, JobType
from app.models.environment import Environment
from app.models.job import Job
from app.workers.tasks import cleanup


def _fake_task_db_session(db_session: AsyncSession):
    @asynccontextmanager
    async def _ctx():
        yield db_session

    return _ctx()


async def _make_app(db_session: AsyncSession) -> Application:
    app = Application(name="App", slug="app", team_id="team-1")
    db_session.add(app)
    await db_session.flush()
    return app


@pytest.mark.asyncio
async def test_sweep_expires_only_environments_past_ttl(db_session: AsyncSession) -> None:
    app = await _make_app(db_session)
    expired = Environment(
        application_id=app.id,
        name="expired-env",
        state=EnvironmentState.READY.value,
        ttl_expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    not_expired = Environment(
        application_id=app.id,
        name="fresh-env",
        state=EnvironmentState.READY.value,
        ttl_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add_all([expired, not_expired])
    await db_session.commit()

    with patch(
        "app.workers.tasks.cleanup.task_db_session", return_value=_fake_task_db_session(db_session)
    ):
        with patch("app.services.task_dispatch.enqueue", return_value=None):
            await cleanup._sweep_expired_environments()

    await db_session.refresh(expired)
    await db_session.refresh(not_expired)
    assert expired.state == EnvironmentState.DELETED.value  # expired, then deleted (no real infra)
    assert not_expired.state == EnvironmentState.READY.value


@pytest.mark.asyncio
async def test_detect_stale_jobs_marks_old_running_jobs_failed(db_session: AsyncSession) -> None:
    app = await _make_app(db_session)
    environment = Environment(
        application_id=app.id, name="stuck-env", state=EnvironmentState.PROVISIONING.value
    )
    db_session.add(environment)
    await db_session.flush()

    stale_job = Job(
        job_type=JobType.PROVISION.value,
        status=JobStatus.RUNNING.value,
        environment_id=environment.id,
        started_at=datetime.now(UTC) - timedelta(minutes=60),
    )
    fresh_job = Job(
        job_type=JobType.PROVISION.value,
        status=JobStatus.RUNNING.value,
        environment_id=environment.id,
        started_at=datetime.now(UTC) - timedelta(minutes=2),
    )
    db_session.add_all([stale_job, fresh_job])
    await db_session.commit()

    with patch(
        "app.workers.tasks.cleanup.task_db_session", return_value=_fake_task_db_session(db_session)
    ):
        await cleanup._detect_stale_jobs()

    await db_session.refresh(stale_job)
    await db_session.refresh(fresh_job)
    await db_session.refresh(environment)
    assert stale_job.status == JobStatus.FAILED.value
    assert "crashed" in stale_job.error_message
    assert fresh_job.status == JobStatus.RUNNING.value
    assert environment.state == EnvironmentState.FAILED.value


@pytest.mark.asyncio
async def test_detect_orphaned_namespaces_deletes_namespace_with_no_matching_environment(
    db_session: AsyncSession,
) -> None:
    with (
        patch(
            "app.workers.tasks.cleanup.provisioning.list_managed_namespaces",
            return_value=[{"name": "envforge-ghost-1234", "environment_id": "nonexistent-id"}],
        ),
        patch("app.workers.tasks.cleanup.provisioning.delete_namespace_directly") as mock_delete,
        patch(
            "app.workers.tasks.cleanup.task_db_session",
            return_value=_fake_task_db_session(db_session),
        ),
    ):
        await cleanup._detect_orphaned_namespaces()

    mock_delete.assert_called_once_with("envforge-ghost-1234")


@pytest.mark.asyncio
async def test_detect_orphaned_namespaces_skips_namespace_with_active_environment(
    db_session: AsyncSession,
) -> None:
    app = await _make_app(db_session)
    environment = Environment(
        application_id=app.id, name="active-env", state=EnvironmentState.READY.value
    )
    db_session.add(environment)
    await db_session.commit()

    with (
        patch(
            "app.workers.tasks.cleanup.provisioning.list_managed_namespaces",
            return_value=[{"name": "envforge-active-env", "environment_id": environment.id}],
        ),
        patch("app.workers.tasks.cleanup.provisioning.delete_namespace_directly") as mock_delete,
        patch("app.workers.tasks.cleanup.provisioning.destroy_environment") as mock_destroy,
        patch(
            "app.workers.tasks.cleanup.task_db_session",
            return_value=_fake_task_db_session(db_session),
        ),
    ):
        await cleanup._detect_orphaned_namespaces()

    mock_delete.assert_not_called()
    mock_destroy.assert_not_called()
