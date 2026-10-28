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


class TemplateType(StrEnum):
    BASIC_BACKEND = "basic_backend"
    FULLSTACK = "fullstack"
    MICROSERVICES = "microservices"
    CUSTOM = "custom"


class EnvironmentState(StrEnum):
    """The lifecycle state machine. Valid transitions live in
    app/services/lifecycle.py — this enum only names the states."""

    REQUESTED = "requested"
    VALIDATING = "validating"
    QUEUED = "queued"
    PROVISIONING = "provisioning"
    DEPLOYING = "deploying"
    HEALTH_CHECKING = "health_checking"
    READY = "ready"
    FAILED = "failed"
    DELETING = "deleting"
    DELETED = "deleted"
    EXPIRED = "expired"


class EventTrigger(StrEnum):
    USER = "user"
    WEBHOOK = "webhook"
    SYSTEM = "system"
    TTL = "ttl"
    RETRY = "retry"


class JobType(StrEnum):
    PROVISION = "provision"
    DEPLOY = "deploy"
    HEALTH_CHECK = "health_check"
    CLEANUP = "cleanup"
    REFRESH = "refresh"


class JobStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RETRYING = "retrying"
