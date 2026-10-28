from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import JobStatus, JobType
from app.models.job import Job
from app.services import task_dispatch

_TASK_NAME_BY_JOB_TYPE: dict[str, str] = {
    JobType.PROVISION.value: "envforge.provision_environment",
    JobType.CLEANUP.value: "envforge.destroy_environment",
}


class JobError(Exception):
    pass


async def get_job(db: AsyncSession, job_id: str) -> Job | None:
    return await db.get(Job, job_id)


async def retry_job(db: AsyncSession, job: Job) -> Job:
    """Resets a FAILED job to PENDING and re-dispatches the same Celery
    task. Re-dispatch is safe regardless of what state the job's
    Environment ended up in: the provisioning task transitions it to
    PROVISIONING from wherever it currently is (QUEUED or FAILED are both
    valid sources — see app/services/lifecycle.py), and the destroy task
    simply retries `terraform destroy` against the same workspace, which
    is itself idempotent."""
    if job.status != JobStatus.FAILED.value:
        raise JobError(f"Only failed jobs can be retried (current status: '{job.status}')")
    if job.attempts >= job.max_attempts:
        raise JobError(f"Job has exhausted its {job.max_attempts} retry attempts")

    task_name = _TASK_NAME_BY_JOB_TYPE.get(job.job_type)
    if task_name is None:
        raise JobError(f"Don't know how to retry a job of type '{job.job_type}'")

    job.status = JobStatus.PENDING.value
    job.error_message = None
    db.add(job)
    await db.commit()
    await db.refresh(job)

    task_id = task_dispatch.enqueue(task_name, job_id=job.id)
    if task_id:
        job.status = JobStatus.QUEUED.value
        job.celery_task_id = task_id
        db.add(job)
        await db.commit()
        await db.refresh(job)

    return job
