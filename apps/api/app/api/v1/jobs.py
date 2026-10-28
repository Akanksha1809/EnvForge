from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.pagination import paginate
from app.db.session import get_db
from app.models.job import Job
from app.models.user import User
from app.schemas.common import Page, PageParams
from app.schemas.job import JobOut
from app.services import jobs as jobs_service
from app.services.audit import record as audit_record

router = APIRouter()


@router.get("", response_model=Page[JobOut])
async def list_jobs(
    status_filter: str | None = Query(default=None, alias="status"),
    job_type: str | None = Query(default=None),
    environment_id: str | None = Query(default=None),
    params: PageParams = Depends(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Page[JobOut]:
    stmt = select(Job)
    if status_filter:
        stmt = stmt.where(Job.status == status_filter)
    if job_type:
        stmt = stmt.where(Job.job_type == job_type)
    if environment_id:
        stmt = stmt.where(Job.environment_id == environment_id)

    return await paginate(db, stmt, params, JobOut, sortable_columns={"created_at": Job.created_at})


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    job = await jobs_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=JobOut)
async def retry_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Job:
    job = await jobs_service.get_job(db, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        job = await jobs_service.retry_job(db, job)
    except jobs_service.JobError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    await audit_record(
        db,
        action="job.retry",
        resource_type="job",
        resource_id=job_id,
        actor_user_id=current_user.id,
        actor_label=current_user.email,
    )
    return job
