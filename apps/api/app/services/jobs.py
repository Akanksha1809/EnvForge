from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus
from app.models.job import Job


class JobError(Exception):
    pass


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    return await db.get(Job, job_id)


async def retry_job(db: AsyncSession, job: Job) -> Job:
    if job.status not in (JobStatus.FAILED.value,):
        raise JobError(f"Only failed jobs can be retried (current status: '{job.status}')")
    if job.attempts >= job.max_attempts:
        raise JobError(f"Job has exhausted its {job.max_attempts} retry attempts")

    job.status = JobStatus.PENDING.value
    job.error_message = None
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job
