"""Shared enums persisted as plain strings (Postgres TEXT + CHECK via Pydantic
validation at the API boundary, rather than native enum types) so new values
never require a migration — only a widened Python enum + app-level validation."""

from enum import StrEnum


class PlatformRole(StrEnum):
    """Global role. Scoped (per-team / per-application) permissions are layered
    on top of this via TeamMembership — see app/services/rbac.py."""

    PLATFORM_ADMIN = "platform_admin"
    TEAM_ADMIN = "team_admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"


class TeamRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"
