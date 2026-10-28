from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WebhookDelivery(Base, TimestampMixin):
    """Tracks every processed GitHub webhook delivery by its unique
    `X-GitHub-Delivery` id, so a redelivered (retried) webhook is a safe
    no-op instead of creating a duplicate environment. GitHub redelivers
    on timeout/5xx, so this dedupe is not optional for correctness."""

    __tablename__ = "webhook_deliveries"

    delivery_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str | None] = mapped_column(String(64), nullable=True)
    repository_full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    environment_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
