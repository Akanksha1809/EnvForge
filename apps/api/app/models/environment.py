from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import EnvironmentState

if TYPE_CHECKING:
    from app.models.application import Application


class Environment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One ephemeral environment instance. `state` is always one of
    EnvironmentState and must only ever be changed via
    app.services.lifecycle.transition() — never assigned directly — so every
    change is validated and recorded as an EnvironmentEvent."""

    __tablename__ = "environments"

    application_id: Mapped[str] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    template_id: Mapped[str | None] = mapped_column(
        ForeignKey("environment_templates.id", ondelete="SET NULL"), nullable=True
    )
    template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    state: Mapped[str] = mapped_column(
        String(32), default=EnvironmentState.REQUESTED.value, nullable=False, index=True
    )

    # Set when this environment was created for a GitHub PR rather than
    # manually through the portal — null for manual environments.
    pr_number: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    pr_branch: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pr_commit_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    namespace: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    preview_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(4096), nullable=True)

    config_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    ttl_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    destroyed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    application: Mapped["Application"] = relationship()
    events: Mapped[list["EnvironmentEvent"]] = relationship(
        back_populates="environment",
        cascade="all, delete-orphan",
        order_by="EnvironmentEvent.created_at",
    )


class EnvironmentEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Append-only lifecycle transition log — see app/services/lifecycle.py.
    This is the audit trail the spec requires: previous/new state,
    timestamp, trigger, actor, job, and error when applicable."""

    __tablename__ = "environment_events"

    environment_id: Mapped[str] = mapped_column(
        ForeignKey("environments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    previous_state: Mapped[str] = mapped_column(String(32), nullable=False)
    new_state: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    job_id: Mapped[str | None] = mapped_column(
        ForeignKey("jobs.id", ondelete="SET NULL"), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)

    environment: Mapped["Environment"] = relationship(back_populates="events")
