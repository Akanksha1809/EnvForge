import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EnvironmentState, EventTrigger
from app.models.environment import Environment, EnvironmentEvent
from app.services import lifecycle


def _env(state: EnvironmentState) -> Environment:
    return Environment(application_id="app-1", name="test-env", state=state.value)


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (EnvironmentState.REQUESTED, EnvironmentState.VALIDATING, True),
        (EnvironmentState.REQUESTED, EnvironmentState.READY, False),
        (EnvironmentState.VALIDATING, EnvironmentState.QUEUED, True),
        (EnvironmentState.QUEUED, EnvironmentState.PROVISIONING, True),
        (EnvironmentState.QUEUED, EnvironmentState.READY, False),
        (EnvironmentState.PROVISIONING, EnvironmentState.DEPLOYING, True),
        (EnvironmentState.DEPLOYING, EnvironmentState.HEALTH_CHECKING, True),
        (EnvironmentState.HEALTH_CHECKING, EnvironmentState.READY, True),
        (EnvironmentState.READY, EnvironmentState.DELETING, True),
        (EnvironmentState.READY, EnvironmentState.PROVISIONING, False),
        (EnvironmentState.FAILED, EnvironmentState.QUEUED, True),
        (EnvironmentState.DELETED, EnvironmentState.READY, False),
        (EnvironmentState.DELETED, EnvironmentState.DELETING, False),
        (EnvironmentState.EXPIRED, EnvironmentState.DELETING, True),
    ],
)
def test_is_valid_transition(
    current: EnvironmentState, target: EnvironmentState, expected: bool
) -> None:
    assert lifecycle.is_valid_transition(current, target) is expected


@pytest.mark.asyncio
async def test_transition_persists_event_and_updates_state(db_session: AsyncSession) -> None:
    env = _env(EnvironmentState.REQUESTED)
    db_session.add(env)
    await db_session.flush()

    updated = await lifecycle.transition(
        db_session, env, target=EnvironmentState.VALIDATING, trigger=EventTrigger.SYSTEM
    )
    assert updated.state == EnvironmentState.VALIDATING.value

    from sqlalchemy import select

    events = (
        (
            await db_session.execute(
                select(EnvironmentEvent).where(EnvironmentEvent.environment_id == env.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1
    assert events[0].previous_state == EnvironmentState.REQUESTED.value
    assert events[0].new_state == EnvironmentState.VALIDATING.value
    assert events[0].trigger == EventTrigger.SYSTEM.value


@pytest.mark.asyncio
async def test_transition_rejects_invalid_target(db_session: AsyncSession) -> None:
    env = _env(EnvironmentState.REQUESTED)
    db_session.add(env)
    await db_session.flush()

    with pytest.raises(lifecycle.InvalidTransitionError):
        await lifecycle.transition(
            db_session, env, target=EnvironmentState.READY, trigger=EventTrigger.SYSTEM
        )


@pytest.mark.asyncio
async def test_failed_transition_records_error_message(db_session: AsyncSession) -> None:
    env = _env(EnvironmentState.PROVISIONING)
    db_session.add(env)
    await db_session.flush()

    updated = await lifecycle.transition(
        db_session,
        env,
        target=EnvironmentState.FAILED,
        trigger=EventTrigger.SYSTEM,
        error_message="terraform apply failed",
    )
    assert updated.last_error == "terraform apply failed"
