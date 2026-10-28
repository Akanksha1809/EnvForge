import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState
from app.models.environment import Environment
from app.models.team import Team
from app.services import quotas


async def _make_team(db_session: AsyncSession, *, max_active_environments: int = 10) -> Team:
    team = Team(name="T", slug="t", max_active_environments=max_active_environments)
    db_session.add(team)
    await db_session.flush()
    return team


async def _make_application(
    db_session: AsyncSession, team: Team, *, max_active_environments: int | None = None
) -> Application:
    app = Application(
        name="App", slug="app", team_id=team.id, max_active_environments=max_active_environments
    )
    db_session.add(app)
    await db_session.flush()
    return app


async def _make_environment(
    db_session: AsyncSession,
    application: Application,
    *,
    requested_by_user_id: str | None = None,
    state: EnvironmentState = EnvironmentState.READY,
) -> Environment:
    env = Environment(
        application_id=application.id,
        name=f"env-{application.slug}",
        state=state.value,
        requested_by_user_id=requested_by_user_id,
    )
    db_session.add(env)
    await db_session.flush()
    return env


@pytest.mark.asyncio
async def test_team_quota_counts_only_non_terminal_environments(db_session: AsyncSession) -> None:
    team = await _make_team(db_session)
    app = await _make_application(db_session, team)
    await _make_environment(db_session, app, state=EnvironmentState.READY)
    await _make_environment(db_session, app, state=EnvironmentState.DELETED)
    await _make_environment(db_session, app, state=EnvironmentState.FAILED)
    await db_session.commit()

    count = await quotas.count_active_environments_for_team(db_session, team.id)
    assert count == 1


@pytest.mark.asyncio
async def test_check_all_quotas_raises_when_team_quota_exceeded(db_session: AsyncSession) -> None:
    team = await _make_team(db_session, max_active_environments=1)
    app = await _make_application(db_session, team)
    await _make_environment(db_session, app, state=EnvironmentState.READY)
    await db_session.commit()

    with pytest.raises(quotas.QuotaExceededError) as exc_info:
        await quotas.check_all_quotas(db_session, user_id=None, application=app, team=team)
    assert exc_info.value.scope == "team"


@pytest.mark.asyncio
async def test_check_all_quotas_raises_when_application_quota_exceeded(
    db_session: AsyncSession,
) -> None:
    team = await _make_team(db_session, max_active_environments=100)
    app = await _make_application(db_session, team, max_active_environments=1)
    await _make_environment(db_session, app, state=EnvironmentState.READY)
    await db_session.commit()

    with pytest.raises(quotas.QuotaExceededError) as exc_info:
        await quotas.check_all_quotas(db_session, user_id=None, application=app, team=team)
    assert exc_info.value.scope == "application"


@pytest.mark.asyncio
async def test_check_all_quotas_raises_when_user_quota_exceeded(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_active_environments_per_user", 1)

    team = await _make_team(db_session, max_active_environments=100)
    app = await _make_application(db_session, team)
    await _make_environment(db_session, app, requested_by_user_id="user-1")
    await db_session.commit()

    with pytest.raises(quotas.QuotaExceededError) as exc_info:
        await quotas.check_all_quotas(db_session, user_id="user-1", application=app, team=team)
    assert exc_info.value.scope == "user"


@pytest.mark.asyncio
async def test_application_with_no_quota_override_is_unlimited(db_session: AsyncSession) -> None:
    team = await _make_team(db_session, max_active_environments=100)
    app = await _make_application(db_session, team, max_active_environments=None)
    for _ in range(5):
        await _make_environment(db_session, app)
    await db_session.commit()

    # Should not raise — no application-level cap configured.
    await quotas.check_all_quotas(db_session, user_id=None, application=app, team=team)
