from typing import Any

from sqlalchemy import JSON, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TemplateType


class EnvironmentTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A versioned environment template (basic-backend / fullstack /
    microservices / custom). `slug` identifies the template family;
    `version` is monotonically increasing per slug. Applications pin a
    specific (slug, version) pair so template edits never silently change
    an application's already-provisioned environments."""

    __tablename__ = "environment_templates"
    __table_args__ = (UniqueConstraint("slug", "version", name="uq_template_slug_version"),)

    slug: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    is_latest: Mapped[bool] = mapped_column(default=True, nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    template_type: Mapped[str] = mapped_column(
        String(32), default=TemplateType.CUSTOM.value, nullable=False
    )

    required_services: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    infrastructure_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    resource_limits: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    env_vars: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    deployment_strategy: Mapped[str] = mapped_column(String(64), default="rolling", nullable=False)
    health_checks: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    dependency_requirements: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cleanup_rules: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
