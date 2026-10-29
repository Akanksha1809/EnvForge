"""Celery application shared by the worker process and (for task submission)
the API process. Task modules are registered in `include=` below as each
subsystem lands (provisioning in Phase 3, cleanup/github in Phases 4-5)."""

from celery import Celery
from celery.signals import worker_process_init

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging("envforge-worker")

celery_app = Celery(
    "envforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.provisioning", "app.workers.tasks.cleanup"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,
    task_soft_time_limit=25 * 60,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# Runs continuously in `celery -A app.workers.celery_app beat` (a separate
# process from the worker — see docker-compose.yml). Each sweep is
# independently idempotent, so overlapping runs under a slow sweep are safe.
celery_app.conf.beat_schedule = {
    "sweep-expired-environments": {
        "task": "envforge.sweep_expired_environments",
        "schedule": settings.ttl_sweep_interval_seconds,
    },
    "detect-orphaned-namespaces": {
        "task": "envforge.detect_orphaned_namespaces",
        "schedule": settings.orphan_sweep_interval_seconds,
    },
    "detect-stale-jobs": {
        "task": "envforge.detect_stale_jobs",
        "schedule": settings.orphan_sweep_interval_seconds,
    },
}


@celery_app.task(name="envforge.health_check")
def health_check() -> str:
    return "ok"


@worker_process_init.connect
def _init_worker_tracing(**_kwargs: object) -> None:
    """Only runs inside an actual `celery worker` process, never when this
    module is merely imported by the API process (e.g. via
    app.services.task_dispatch) — otherwise the API would mislabel its own
    traces as `envforge-worker` by racing to configure the global tracer
    provider first."""
    from opentelemetry.instrumentation.celery import CeleryInstrumentor

    from app.core.tracing import configure_tracing

    configure_tracing("envforge-worker")
    CeleryInstrumentor().instrument()
