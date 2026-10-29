from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.application import Application
from app.models.environment import Environment
from app.models.team import Team
from app.services import cost_engine


def _application(**overrides) -> Application:
    defaults = dict(id="app-1", name="App", slug="app", team_id="team-1", resource_requirements={})
    defaults.update(overrides)
    return Application(**defaults)


def _environment(*, created_at, destroyed_at=None) -> Environment:
    return Environment(
        id="env-1",
        application_id="app-1",
        name="env",
        state="ready",
        created_at=created_at,
        destroyed_at=destroyed_at,
    )


def test_estimate_is_simulated_when_no_resource_requirements_configured() -> None:
    app = _application(resource_requirements={})
    env = _environment(created_at=datetime.now(UTC) - timedelta(hours=1))

    result = cost_engine.estimate_environment_cost(env, app)

    assert result["basis"] == "simulated"
    assert result["cpu_cores"] == cost_engine._DEFAULT_CPU_CORES
    assert result["memory_gb"] == cost_engine._DEFAULT_MEMORY_GB


def test_estimate_is_estimated_when_resource_requirements_configured() -> None:
    app = _application(resource_requirements={"cpu": "500m", "memory": "1Gi"})
    env = _environment(created_at=datetime.now(UTC) - timedelta(hours=2))

    result = cost_engine.estimate_environment_cost(env, app)

    assert result["basis"] == "estimated"
    assert result["cpu_cores"] == pytest.approx(0.5)
    assert result["memory_gb"] == pytest.approx(1.0)


def test_estimate_cost_matches_configured_pricing(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "cost_cpu_core_hour_usd", 0.1)
    monkeypatch.setattr(settings, "cost_memory_gb_hour_usd", 0.01)

    app = _application(resource_requirements={"cpu": "1", "memory": "2Gi"})
    env = _environment(created_at=datetime.now(UTC) - timedelta(hours=10))

    result = cost_engine.estimate_environment_cost(env, app)

    # 1 core * $0.1/hr * 10h + 2GB * $0.01/hr * 10h = 1.0 + 0.2 = 1.2
    assert result["estimated_cost_usd"] == pytest.approx(1.2, abs=0.01)
    assert result["hours_active"] == pytest.approx(10, abs=0.01)


def test_destroyed_environment_stops_accruing_cost() -> None:
    created = datetime.now(UTC) - timedelta(hours=10)
    destroyed = created + timedelta(hours=2)
    app = _application()
    env = _environment(created_at=created, destroyed_at=destroyed)

    result = cost_engine.estimate_environment_cost(env, app)

    assert result["hours_active"] == pytest.approx(2, abs=0.01)
    assert result["is_still_active"] is False


@pytest.mark.parametrize(
    ("value", "expected_cores"),
    [("500m", 0.5), ("2", 2.0), (1.5, 1.5), (None, None), ("not-a-number", None)],
)
def test_parse_cpu_cores(value, expected_cores) -> None:
    result = cost_engine._parse_cpu_cores(value)
    if expected_cores is None:
        assert result is None
    else:
        assert result == pytest.approx(expected_cores)


@pytest.mark.parametrize(
    ("value", "expected_gb"),
    [("1Gi", 1.0), ("512Mi", 0.5), ("1G", 1_000_000_000 / 1024**3), (None, None)],
)
def test_parse_memory_gb(value, expected_gb) -> None:
    result = cost_engine._parse_memory_gb(value)
    if expected_gb is None:
        assert result is None
    else:
        assert result == pytest.approx(expected_gb, rel=1e-3)


@pytest.mark.asyncio
async def test_estimate_cost_summary_groups_by_team_and_application(
    db_session: AsyncSession,
) -> None:
    team = Team(name="T", slug="t", max_active_environments=10)
    db_session.add(team)
    await db_session.flush()

    app = Application(name="App", slug="app", team_id=team.id, resource_requirements={})
    db_session.add(app)
    await db_session.flush()

    db_session.add_all(
        [
            Environment(
                application_id=app.id,
                name="env-1",
                state="ready",
                created_at=datetime.now(UTC) - timedelta(hours=1),
            ),
            Environment(
                application_id=app.id,
                name="env-2",
                state="ready",
                created_at=datetime.now(UTC) - timedelta(hours=1),
            ),
        ]
    )
    await db_session.commit()

    summary = await cost_engine.estimate_cost_summary(db_session)

    assert summary["basis"] == "simulated"
    assert len(summary["by_team"]) == 1
    assert summary["by_team"][0]["slug"] == "t"
    assert summary["by_application"][0]["slug"] == "app"
    assert summary["total_estimated_cost_usd"] > 0
