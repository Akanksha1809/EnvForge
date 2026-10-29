from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.environment import Environment
from app.models.job import Job
from app.models.team import Team
from app.services import recommendations


@pytest.mark.asyncio
async def test_recommends_raising_quota_when_team_near_capacity(
    db_session: AsyncSession,
) -> None:
    team = Team(name="Busy Team", slug="busy-team", max_active_environments=5)
    db_session.add(team)
    await db_session.flush()

    app = Application(name="App", slug="app", team_id=team.id, resource_requirements={})
    db_session.add(app)
    await db_session.flush()

    db_session.add_all(
        [Environment(application_id=app.id, name=f"env-{i}", state="ready") for i in range(4)]
    )
    await db_session.commit()

    result = await recommendations.get_recommendations(db_session)

    quota_hits = [r for r in result if r["category"] == "quota" and r["resource_id"] == team.id]
    assert len(quota_hits) == 1
    assert quota_hits[0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_recommends_configuring_resource_requirements_and_template(
    db_session: AsyncSession,
) -> None:
    team = Team(name="T", slug="t", max_active_environments=10)
    db_session.add(team)
    await db_session.flush()

    app = Application(
        name="Bare App",
        slug="bare-app",
        team_id=team.id,
        resource_requirements={},
        environment_template_id=None,
        is_active=True,
    )
    db_session.add(app)
    await db_session.commit()

    result = await recommendations.get_recommendations(db_session)

    categories = {
        r["category"]
        for r in result
        if r["resource_type"] == "application" and r["resource_id"] == app.id
    }
    assert categories == {"cost_accuracy", "consistency"}


@pytest.mark.asyncio
async def test_recommends_reviewing_long_lived_active_environment(
    db_session: AsyncSession,
) -> None:
    team = Team(name="T2", slug="t2", max_active_environments=10)
    db_session.add(team)
    await db_session.flush()

    app = Application(name="App2", slug="app2", team_id=team.id, resource_requirements={"cpu": "1"})
    db_session.add(app)
    await db_session.flush()

    stale_env = Environment(
        application_id=app.id,
        name="stale-env",
        state="ready",
        created_at=datetime.now(UTC) - timedelta(days=10),
    )
    db_session.add(stale_env)
    await db_session.commit()

    result = await recommendations.get_recommendations(db_session)

    staleness_hits = [r for r in result if r["category"] == "staleness"]
    assert any(r["resource_id"] == stale_env.id for r in staleness_hits)


@pytest.mark.asyncio
async def test_recommends_investigating_exhausted_jobs(db_session: AsyncSession) -> None:
    job = Job(job_type="provision", status="failed", attempts=3, max_attempts=3)
    db_session.add(job)
    await db_session.commit()

    result = await recommendations.get_recommendations(db_session)

    failed_job_hits = [r for r in result if r["category"] == "failed_jobs"]
    assert len(failed_job_hits) == 1
    assert failed_job_hits[0]["resource_id"] is None


@pytest.mark.asyncio
async def test_no_recommendations_for_a_healthy_platform(db_session: AsyncSession) -> None:
    team = Team(name="Healthy", slug="healthy", max_active_environments=10)
    db_session.add(team)
    await db_session.flush()

    app = Application(
        name="Healthy App",
        slug="healthy-app",
        team_id=team.id,
        resource_requirements={"cpu": "1", "memory": "1Gi"},
        environment_template_id=None,
        is_active=False,
    )
    db_session.add(app)
    await db_session.commit()

    result = await recommendations.get_recommendations(db_session)

    assert result == []
