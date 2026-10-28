"""Resource quota enforcement — active-environment counts per user, per
team, and per application. CPU/memory/storage limits are enforced at the
Kubernetes level instead (each environment's namespace gets a real
ResourceQuota — see infrastructure/terraform/modules/environment-namespace,
built in Phase 3); this module is specifically about *how many*
environments can exist at once, not how big any one of them is.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.application import Application
from app.models.enums import EnvironmentState
from app.models.environment import Environment
from app.models.team import Team

TERMINAL_STATES = {
    EnvironmentState.DELETED.value,
    EnvironmentState.EXPIRED.value,
    EnvironmentState.FAILED.value,
}


class QuotaExceededError(Exception):
    def __init__(self, scope: str, label: str, current: int, limit: int) -> None:
        self.scope = scope
        self.label = label
        self.current = current
        self.limit = limit
        super().__init__(
            f"{scope} '{label}' is at its active environment quota ({current}/{limit})"
        )


async def count_active_environments_for_user(db: AsyncSession, user_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Environment)
        .where(
            Environment.requested_by_user_id == user_id,
            Environment.state.not_in(TERMINAL_STATES),
        )
    )
    return result.scalar_one()


async def count_active_environments_for_application(db: AsyncSession, application_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Environment)
        .where(
            Environment.application_id == application_id,
            Environment.state.not_in(TERMINAL_STATES),
        )
    )
    return result.scalar_one()


async def count_active_environments_for_team(db: AsyncSession, team_id: str) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Environment)
        .join(Application, Application.id == Environment.application_id)
        .where(Application.team_id == team_id, Environment.state.not_in(TERMINAL_STATES))
    )
    return result.scalar_one()


async def check_all_quotas(
    db: AsyncSession, *, user_id: str | None, application: Application, team: Team | None
) -> None:
    """Raises QuotaExceededError on the first exceeded quota, checked in
    user -> application -> team order (narrowest to widest scope, though
    any order is equally correct since all three must pass)."""
    settings = get_settings()

    if user_id is not None:
        user_count = await count_active_environments_for_user(db, user_id)
        if user_count >= settings.max_active_environments_per_user:
            raise QuotaExceededError(
                "user", user_id, user_count, settings.max_active_environments_per_user
            )

    if application.max_active_environments is not None:
        app_count = await count_active_environments_for_application(db, application.id)
        if app_count >= application.max_active_environments:
            raise QuotaExceededError(
                "application", application.slug, app_count, application.max_active_environments
            )

    if team is not None:
        team_count = await count_active_environments_for_team(db, team.id)
        if team_count >= team.max_active_environments:
            raise QuotaExceededError("team", team.slug, team_count, team.max_active_environments)
