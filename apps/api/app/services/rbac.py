"""Centralized permission checks.

Every permission-sensitive endpoint depends on one of these functions rather
than inlining role comparisons, so the permission matrix in section 12 of the
spec (who can register apps / create or delete environments / manage
templates / manage teams / administer the platform) lives in exactly one
place and the backend never trusts frontend-side restrictions.
"""

from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlatformRole, TeamRole
from app.models.team import TeamMembership
from app.models.user import User


class Permission(StrEnum):
    APPLICATION_REGISTER = "application:register"
    APPLICATION_MANAGE = "application:manage"
    ENVIRONMENT_CREATE = "environment:create"
    ENVIRONMENT_DELETE = "environment:delete"
    ENVIRONMENT_EXTEND = "environment:extend"
    TEMPLATE_MANAGE = "template:manage"
    TEAM_MANAGE = "team:manage"
    PLATFORM_ADMINISTER = "platform:administer"


# Global (platform-role) permissions that don't require team-scoped checks.
_ROLE_PERMISSIONS: dict[PlatformRole, set[Permission]] = {
    PlatformRole.PLATFORM_ADMIN: set(Permission),
    PlatformRole.TEAM_ADMIN: {
        Permission.APPLICATION_REGISTER,
        Permission.APPLICATION_MANAGE,
        Permission.ENVIRONMENT_CREATE,
        Permission.ENVIRONMENT_DELETE,
        Permission.ENVIRONMENT_EXTEND,
        Permission.TEMPLATE_MANAGE,
        Permission.TEAM_MANAGE,
    },
    PlatformRole.DEVELOPER: {
        Permission.APPLICATION_REGISTER,
        Permission.ENVIRONMENT_CREATE,
        Permission.ENVIRONMENT_DELETE,
        Permission.ENVIRONMENT_EXTEND,
    },
    PlatformRole.VIEWER: set(),
}


def has_global_permission(user: User, permission: Permission) -> bool:
    role = PlatformRole(user.platform_role)
    return permission in _ROLE_PERMISSIONS.get(role, set())


def require_permission(user: User, permission: Permission) -> None:
    if not has_global_permission(user, permission):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.platform_role}' lacks permission '{permission.value}'",
        )


async def get_team_role(db: AsyncSession, *, user_id: str, team_id: str) -> TeamRole | None:
    result = await db.execute(
        select(TeamMembership.role).where(
            TeamMembership.user_id == user_id, TeamMembership.team_id == team_id
        )
    )
    row = result.scalar_one_or_none()
    return TeamRole(row) if row else None


async def require_team_membership(db: AsyncSession, *, user: User, team_id: str) -> TeamRole:
    if PlatformRole(user.platform_role) == PlatformRole.PLATFORM_ADMIN:
        return TeamRole.ADMIN
    role = await get_team_role(db, user_id=user.id, team_id=team_id)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this team"
        )
    return role


async def require_team_admin(db: AsyncSession, *, user: User, team_id: str) -> None:
    if PlatformRole(user.platform_role) == PlatformRole.PLATFORM_ADMIN:
        return
    role = await get_team_role(db, user_id=user.id, team_id=team_id)
    if role != TeamRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Requires team admin role"
        )
