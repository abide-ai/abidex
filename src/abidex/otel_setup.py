import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter
from opentelemetry.sdk.resources import Resource

from abidex.config import get_service_name, ABIDEX_BUFFER_ENABLED
from abidex import trace_buffer

TRACER_NAME = "abidex"
_version = "0.1.0"
_initialized = False


def _get_exporter() -> SpanExporter:
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            return OTLPSpanExporter()
        except ImportError:
            pass
    from opentelemetry.sdk.trace.export import ConsoleSpanExporter
    return ConsoleSpanExporter()


def init_otel(
    *,
    service_name: Optional[str] = None,
) -> None:
    global _initialized
    if _initialized:
        return
    # Only skip if an SDK TracerProvider is already set. OTel default is ProxyTracerProvider
    # (or NoOpTracerProvider) — in both cases we should set ours.
    current = trace.get_tracer_provider()
    if isinstance(current, TracerProvider):
        _initialized = True
        return
    resource = Resource.create({
        "service.name": service_name or get_service_name() or "abidex",
    })
    provider = TracerProvider(resource=resource)
    exporter = _get_exporter()
    provider.add_span_processor(BatchSpanProcessor(exporter))
    if ABIDEX_BUFFER_ENABLED:
        provider.add_span_processor(trace_buffer.BufferSpanProcessor())
    trace.set_tracer_provider(provider)
    _initialized = True


def get_tracer(component: Optional[str] = None) -> trace.Tracer:
    init_otel()
    name = f"{TRACER_NAME}.{component}" if component else TRACER_NAME
    return trace.get_tracer(TRACER_NAME, _version, schema_url=None)


def get_trace_buffer() -> list:
    """Return all spans in the buffer (for CLI). Empty if buffer disabled."""
    return trace_buffer.get_recent_spans(trace_buffer.BUFFER_MAX)


def clear_trace_buffer() -> None:
    trace_buffer.clear_buffer()
