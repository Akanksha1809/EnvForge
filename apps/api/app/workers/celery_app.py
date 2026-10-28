"""Celery application shared by the worker process and (for task submission)
the API process. Task modules are registered in `include=` below as each
subsystem lands (provisioning in Phase 3, cleanup/github in Phases 4-5)."""

from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging("envforge-worker")

celery_app = Celery(
    "envforge",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.tasks.provisioning"],
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

# Populated incrementally: TTL sweep / orphan detection land in Phase 5.
celery_app.conf.beat_schedule = {}


@celery_app.task(name="envforge.health_check")
def health_check() -> str:
    return "ok"
