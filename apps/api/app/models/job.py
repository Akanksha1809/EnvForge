from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import JobStatus


class Job(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A unit of asynchronous work (provision/deploy/health_check/cleanup/
    refresh). The API creates a Job row synchronously and returns
    immediately; a Celery task (wired up per-subsystem starting Phase 3)
    does the actual work and updates this row + the owning Environment via
    app.services.lifecycle."""

    __tablename__ = "jobs"

    job_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default=JobStatus.PENDING.value, nullable=False, index=True
    )
    environment_id: Mapped[str | None] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
