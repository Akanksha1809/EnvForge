"""OpenTelemetry tracing setup, shared by the API and the worker.

Exports to a real OTLP collector when `OTEL_EXPORTER_OTLP_ENDPOINT` is
configured; otherwise exports to the console, so spans are always real
and visible somewhere (`docker logs`) rather than silently dropped when
no collector is running — consistent with this project's rule that an
absent external dependency makes an integration a visible no-op, never a
faked success.
"""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter, SpanExporter

from app.core.config import get_settings

_configured = False


def configure_tracing(service_name: str) -> trace.Tracer:
    global _configured
    settings = get_settings()
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))

    if settings.otel_exporter_otlp_endpoint:
        exporter: SpanExporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint)
    else:
        exporter = ConsoleSpanExporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))

    if not _configured:
        trace.set_tracer_provider(provider)
        _configured = True

    return trace.get_tracer(service_name)
