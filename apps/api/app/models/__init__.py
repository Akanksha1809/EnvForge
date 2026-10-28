"""Import every model module here so Alembic's autogenerate and
`Base.metadata.create_all` (used only in tests) see the full schema."""

from app.models.application import Application  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.environment import Environment, EnvironmentEvent  # noqa: F401
from app.models.environment_template import EnvironmentTemplate  # noqa: F401
from app.models.job import Job  # noqa: F401
from app.models.team import Team, TeamMembership  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.webhook_delivery import WebhookDelivery  # noqa: F401

__all__ = [
    "User",
    "Team",
    "TeamMembership",
    "AuditLog",
    "Application",
    "EnvironmentTemplate",
    "Environment",
    "EnvironmentEvent",
    "Job",
    "WebhookDelivery",
]
