from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import TeamRole

if TYPE_CHECKING:
    from app.models.user import User


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teams"

    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Resource quota fields — enforced by app.services.quotas, see Phase 5.
    max_active_environments: Mapped[int] = mapped_column(default=10, nullable=False)

    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )


class TeamMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "team_memberships"
    __table_args__ = (UniqueConstraint("user_id", "team_id", name="uq_team_membership_user_team"),)

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default=TeamRole.MEMBER.value, nullable=False)

    user: Mapped["User"] = relationship(back_populates="team_memberships")
    team: Mapped["Team"] = relationship(back_populates="memberships")
