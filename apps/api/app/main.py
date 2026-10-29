"""EnvForge API entrypoint."""

import time
import uuid
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.tracing import configure_tracing
from app.db.session import get_db
from app.services import metrics as metrics_service

settings = get_settings()
configure_logging("envforge-api")
logger = get_logger("envforge-api")
configure_tracing("envforge-api")

REQUEST_COUNT = Counter(
    "envforge_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status_code"],
)
REQUEST_LATENCY = Histogram(
    "envforge_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("api.startup", environment=settings.environment)
    yield
    logger.info("api.shutdown")


app = FastAPI(
    title=settings.app_name,
    description="Self-service ephemeral environment management platform",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next) -> Response:
    """Binds a request_id to every log line emitted while handling this
    request, and records Prometheus request metrics — the two pieces of
    observability every single request needs regardless of route."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=request_id)

    start = time.perf_counter()
    path = request.url.path
    try:
        response = await call_next(request)
    except Exception:
        REQUEST_COUNT.labels(method=request.method, path=path, status_code=500).inc()
        raise
    duration = time.perf_counter() - start

    REQUEST_COUNT.labels(method=request.method, path=path, status_code=response.status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, path=path).observe(duration)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("api.unhandled_exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
    )


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "service": settings.app_name, "environment": settings.environment}


@app.get("/metrics", tags=["system"])
async def metrics(db: AsyncSession = Depends(get_db)) -> Response:
    await metrics_service.refresh_gauges(db)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


app.include_router(api_router, prefix=settings.api_v1_prefix)
