from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.environment_template import EnvironmentTemplate
    from app.models.team import Team


class Application(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A registered application EnvForge knows how to provision environments
    for. Deployment/infra/resource/health-check config is stored as JSON
    rather than normalized columns because its shape is template-dependent
    and versioned independently (see EnvironmentTemplate)."""

    __tablename__ = "applications"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)

    github_repo: Mapped[str | None] = mapped_column(String(512), nullable=True)
    default_branch: Mapped[str] = mapped_column(String(255), default="main", nullable=False)

    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    environment_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("environment_templates.id", ondelete="SET NULL"), nullable=True
    )
    environment_template_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    deployment_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    infrastructure_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    resource_requirements: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, nullable=False
    )
    health_check_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    env_vars: Mapped[dict[str, str]] = mapped_column(JSON, default=dict, nullable=False)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)

    environment_ttl_hours: Mapped[int] = mapped_column(Integer, default=48, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    team: Mapped["Team"] = relationship()
    environment_template: Mapped["EnvironmentTemplate | None"] = relationship()
