"""Structured logging setup.

Every log entry carries service name, level, timestamp and whatever
contextvars are bound for the current request/job (request_id, environment_id,
job_id) — bound in middleware / task wrappers, not scattered through call sites.
"""

import logging
import sys

import structlog

from app.core.config import get_settings

_SERVICE_NAME = "envforge-api"


def configure_logging(service_name: str = _SERVICE_NAME) -> None:
    settings = get_settings()
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _bind_service_name(service_name),
    ]

    renderer = (
        structlog.processors.JSONRenderer()
        if settings.log_format == "json"
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.log_level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def _bind_service_name(service_name: str):
    def processor(logger, method_name, event_dict):
        event_dict["service"] = service_name
        return event_dict

    return processor


def get_logger(name: str = _SERVICE_NAME) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
