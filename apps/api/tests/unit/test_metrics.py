from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application
from app.models.enums import EnvironmentState, JobStatus, JobType
from app.models.environment import Environment
from app.models.job import Job
from app.services import metrics


async def _make_app(db_session: AsyncSession) -> Application:
    app = Application(name="App", slug="app", team_id="team-1")
    db_session.add(app)
    await db_session.flush()
    return app


@pytest.mark.asyncio
async def test_refresh_gauges_reflects_real_environment_counts(db_session: AsyncSession) -> None:
    app = await _make_app(db_session)
    db_session.add_all(
        [
            Environment(application_id=app.id, name="ready-1", state=EnvironmentState.READY.value),
            Environment(
                application_id=app.id, name="prov-1", state=EnvironmentState.PROVISIONING.value
            ),
            Environment(
                application_id=app.id, name="failed-1", state=EnvironmentState.FAILED.value
            ),
            Environment(
                application_id=app.id, name="deleted-1", state=EnvironmentState.DELETED.value
            ),
        ]
    )
    await db_session.commit()

    await metrics.refresh_gauges(db_session)

    assert metrics.environments_active._value.get() == 2  # ready + provisioning
    assert metrics.environments_provisioning._value.get() == 1
    assert metrics.environments_failed._value.get() == 1


@pytest.mark.asyncio
async def test_refresh_gauges_computes_success_rate_and_avg_duration(
    db_session: AsyncSession,
) -> None:
    await _make_app(db_session)
    started = datetime.now(UTC) - timedelta(seconds=20)
    finished = datetime.now(UTC)
    db_session.add_all(
        [
            Job(
                job_type=JobType.PROVISION.value,
                status=JobStatus.SUCCEEDED.value,
                environment_id=None,
                started_at=started,
                finished_at=finished,
            ),
            Job(
                job_type=JobType.PROVISION.value,
                status=JobStatus.FAILED.value,
                environment_id=None,
                started_at=started,
                finished_at=finished,
            ),
            Job(job_type=JobType.PROVISION.value, status=JobStatus.PENDING.value),
        ]
    )
    await db_session.commit()

    await metrics.refresh_gauges(db_session)

    assert metrics.provisioning_success_rate._value.get() == 0.5
    assert metrics.provisioning_duration_avg_seconds._value.get() == pytest.approx(20, abs=1)
    assert metrics.jobs_queued._value.get() == 1
    assert metrics.jobs_failed_total_gauge._value.get() == 1
