from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import JobStatus, JobType


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: JobType
    status: JobStatus
    environment_id: str | None
    celery_task_id: str | None
    attempts: int
    max_attempts: int
    payload: dict[str, Any]
    result: dict[str, Any]
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
