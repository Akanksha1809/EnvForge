from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus, JobType
from app.models.job import Job
from app.services import jobs as jobs_service


async def _make_job(
    db_session: AsyncSession, *, job_type: str, status: str, attempts: int = 1
) -> Job:
    job = Job(job_type=job_type, status=status, attempts=attempts)
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)
    return job


@pytest.mark.asyncio
async def test_retry_job_redispatches_provision_task(db_session: AsyncSession) -> None:
    job = await _make_job(
        db_session, job_type=JobType.PROVISION.value, status=JobStatus.FAILED.value
    )

    with patch("app.services.jobs.task_dispatch.enqueue", return_value="task-123") as mock_enqueue:
        retried = await jobs_service.retry_job(db_session, job)

    mock_enqueue.assert_called_once_with("envforge.provision_environment", job_id=job.id)
    assert retried.status == JobStatus.QUEUED.value
    assert retried.celery_task_id == "task-123"
    assert retried.error_message is None


@pytest.mark.asyncio
async def test_retry_job_redispatches_cleanup_task(db_session: AsyncSession) -> None:
    job = await _make_job(db_session, job_type=JobType.CLEANUP.value, status=JobStatus.FAILED.value)

    with patch("app.services.jobs.task_dispatch.enqueue", return_value="task-456") as mock_enqueue:
        retried = await jobs_service.retry_job(db_session, job)

    mock_enqueue.assert_called_once_with("envforge.destroy_environment", job_id=job.id)
    assert retried.status == JobStatus.QUEUED.value


@pytest.mark.asyncio
async def test_retry_job_stays_pending_when_broker_unreachable(db_session: AsyncSession) -> None:
    job = await _make_job(
        db_session, job_type=JobType.PROVISION.value, status=JobStatus.FAILED.value
    )

    with patch("app.services.jobs.task_dispatch.enqueue", return_value=None):
        retried = await jobs_service.retry_job(db_session, job)

    assert retried.status == JobStatus.PENDING.value


@pytest.mark.asyncio
async def test_retry_job_rejects_non_failed_job(db_session: AsyncSession) -> None:
    job = await _make_job(
        db_session, job_type=JobType.PROVISION.value, status=JobStatus.SUCCEEDED.value
    )

    with pytest.raises(jobs_service.JobError):
        await jobs_service.retry_job(db_session, job)


@pytest.mark.asyncio
async def test_retry_job_rejects_when_attempts_exhausted(db_session: AsyncSession) -> None:
    job = await _make_job(
        db_session, job_type=JobType.PROVISION.value, status=JobStatus.FAILED.value, attempts=3
    )

    with pytest.raises(jobs_service.JobError):
        await jobs_service.retry_job(db_session, job)
