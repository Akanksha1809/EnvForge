"""The environment lifecycle state machine.

This is the one place that knows which `EnvironmentState` transitions are
valid. Every code path that changes an environment's state — the API, the
Celery provisioning pipeline (Phase 3), the cleanup engine (Phase 5), the
GitHub webhook handler (Phase 4) — must go through `transition()` so an
invalid transition can never happen and every change is persisted as an
`EnvironmentEvent`.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import EnvironmentState, EventTrigger
from app.models.environment import Environment, EnvironmentEvent

# Valid transitions. Terminal states (DELETED, EXPIRED) have no outbound
# edges. FAILED can be retried back into QUEUED, or deleted. Every
# in-flight state can also be cancelled straight to DELETING — a user (or
# the cleanup engine) can tear down an environment mid-provisioning, not
# only once it's READY or FAILED.
_VALID_TRANSITIONS: dict[EnvironmentState, set[EnvironmentState]] = {
    EnvironmentState.REQUESTED: {
        EnvironmentState.VALIDATING,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.VALIDATING: {
        EnvironmentState.QUEUED,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.QUEUED: {
        EnvironmentState.PROVISIONING,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.PROVISIONING: {
        EnvironmentState.DEPLOYING,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.DEPLOYING: {
        EnvironmentState.HEALTH_CHECKING,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.HEALTH_CHECKING: {
        EnvironmentState.READY,
        EnvironmentState.FAILED,
        EnvironmentState.DELETING,
    },
    EnvironmentState.READY: {
        EnvironmentState.DELETING,
        # A new commit pushed to the PR redeploys in place — see
        # app.services.environments.redeploy_for_new_commit (Phase 4).
        EnvironmentState.PROVISIONING,
    },
    EnvironmentState.FAILED: {
        EnvironmentState.QUEUED,
        EnvironmentState.DELETING,
        EnvironmentState.PROVISIONING,
    },
    EnvironmentState.DELETING: {EnvironmentState.DELETED, EnvironmentState.FAILED},
    EnvironmentState.DELETED: set(),
    EnvironmentState.EXPIRED: {EnvironmentState.DELETING},
}

# Every non-terminal, non-DELETING state can also expire on its own TTL
# (the cleanup engine doesn't care whether an environment is READY or
# stuck mid-provisioning — if its time is up, it's up) — same rationale
# as every in-flight state already allowing a cancel straight to DELETING.
for _state, _targets in _VALID_TRANSITIONS.items():
    if _state not in (
        EnvironmentState.DELETING,
        EnvironmentState.DELETED,
        EnvironmentState.EXPIRED,
    ):
        _targets.add(EnvironmentState.EXPIRED)


class InvalidTransitionError(Exception):
    def __init__(self, current: EnvironmentState, target: EnvironmentState) -> None:
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition environment from {current.value} to {target.value}")


def is_valid_transition(current: EnvironmentState, target: EnvironmentState) -> bool:
    return target in _VALID_TRANSITIONS.get(current, set())


async def transition(
    db: AsyncSession,
    environment: Environment,
    *,
    target: EnvironmentState,
    trigger: EventTrigger,
    actor_user_id: str | None = None,
    job_id: str | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> Environment:
    current = EnvironmentState(environment.state)
    if not is_valid_transition(current, target):
        raise InvalidTransitionError(current, target)

    event = EnvironmentEvent(
        environment_id=environment.id,
        previous_state=current.value,
        new_state=target.value,
        trigger=trigger.value,
        actor_user_id=actor_user_id,
        job_id=job_id,
        error_message=error_message,
        metadata_json=metadata or {},
    )
    environment.state = target.value
    if target == EnvironmentState.FAILED and error_message:
        environment.last_error = error_message
    elif target in (EnvironmentState.VALIDATING, EnvironmentState.QUEUED, EnvironmentState.READY):
        environment.last_error = None

    db.add(event)
    db.add(environment)
    if commit:
        await db.commit()
        await db.refresh(environment)
    else:
        await db.flush()
    return environment
