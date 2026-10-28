from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState, EventTrigger
from app.models.environment import Environment
from app.services import environments as environments_service


async def _make_app(db_session: AsyncSession) -> Application:
    app = Application(name="App", slug="app", team_id="team-1")
    db_session.add(app)
    await db_session.flush()
    return app


@pytest.mark.asyncio
async def test_extend_environment_rejects_beyond_max_lifetime(db_session: AsyncSession) -> None:
    app = await _make_app(db_session)
    environment = Environment(
        application_id=app.id,
        name="env",
        state=EnvironmentState.READY.value,
        created_at=datetime.now(UTC) - timedelta(hours=1),
        ttl_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(environment)
    await db_session.commit()

    with patch("app.services.environments.get_settings") as mock_settings:
        mock_settings.return_value.max_environment_lifetime_hours = 10
        with pytest.raises(
            environments_service.EnvironmentError, match="maximum environment lifetime"
        ):
            await environments_service.extend_environment(
                db_session, environment, additional_hours=24, actor_user_id=None
            )


@pytest.mark.asyncio
async def test_extend_environment_allows_extension_within_max_lifetime(
    db_session: AsyncSession,
) -> None:
    app = await _make_app(db_session)
    environment = Environment(
        application_id=app.id,
        name="env",
        state=EnvironmentState.READY.value,
        created_at=datetime.now(UTC),
        ttl_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(environment)
    await db_session.commit()

    updated = await environments_service.extend_environment(
        db_session, environment, additional_hours=2, actor_user_id=None
    )
    assert updated.ttl_expires_at > environment.created_at + timedelta(hours=2)


@pytest.mark.asyncio
async def test_expire_environment_without_namespace_completes_synchronously(
    db_session: AsyncSession,
) -> None:
    app = await _make_app(db_session)
    environment = Environment(application_id=app.id, name="env", state=EnvironmentState.READY.value)
    db_session.add(environment)
    await db_session.commit()

    expired = await environments_service.expire_environment(
        db_session, environment, trigger=EventTrigger.TTL
    )
    assert expired.state == EnvironmentState.DELETED.value
    assert expired.destroyed_at is not None


@pytest.mark.asyncio
async def test_expire_environment_is_a_noop_for_already_terminal_environment(
    db_session: AsyncSession,
) -> None:
    app = await _make_app(db_session)
    environment = Environment(
        application_id=app.id, name="env", state=EnvironmentState.DELETED.value
    )
    db_session.add(environment)
    await db_session.commit()

    result = await environments_service.expire_environment(
        db_session, environment, trigger=EventTrigger.TTL
    )
    assert result.state == EnvironmentState.DELETED.value
