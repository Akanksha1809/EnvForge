"""Best-effort Celery dispatch.

If the broker is unreachable (no Redis — e.g. a test run, or a transient
outage), this logs and returns None rather than raising. The Job row stays
PENDING either way; a later retry (manual via `POST /jobs/{id}/retry`, or
automatic once the cleanup engine's reconciliation loop lands in Phase 5)
can pick it up once a worker/broker is available. This keeps environment
creation itself from ever failing just because the async side is down,
matching the spec's "failure handling and recovery" requirement.
"""

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger("envforge.dispatch")


def enqueue(task_name: str, *, job_id: str) -> str | None:
    try:
        result = celery_app.send_task(task_name, args=[job_id])
    except Exception as exc:  # kombu/redis connection errors, etc.
        logger.warning(
            "dispatch.enqueue_failed", task_name=task_name, job_id=job_id, error=str(exc)
        )
        return None
    return result.id
