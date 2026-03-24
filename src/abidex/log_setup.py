"""OpenTelemetry logs with agentic (gen_ai.*) enrichment from current span."""
import logging
import os
from typing import Optional

from opentelemetry import trace
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler, LogRecordProcessor
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from abidex.config import get_service_name, ABIDEX_LOGS_ENABLED, ABIDEX_LOGS_BUFFER_ENABLED
from abidex import log_buffer

_initialized = False


def _agentic_attributes_from_span(span) -> dict[str, str]:
    """Extract gen_ai.* attributes from the current span for log enrichment."""
    out = {}
    try:
        attrs = getattr(span, "attributes", None)
        if not attrs:
            return out
        for k, v in attrs.items():
            if isinstance(k, str) and k.startswith("gen_ai.") and v is not None:
                out[k] = str(v)
    except Exception:
        pass
    return out


class AgenticLogEnricherProcessor(LogRecordProcessor):
    """Adds gen_ai.* attributes from the current span to each log record."""

    def emit(self, log_data) -> None:
        span = trace.get_current_span()
        if span.is_recording() and hasattr(span, "attributes"):
            attrs = _agentic_attributes_from_span(span)
            if attrs:
                rec = log_data.log_record
                for k, v in attrs.items():
                    try:
                        rec.attributes[k] = v
                    except Exception:
                        pass

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def _get_log_exporter():
    """Console exporter for logs; OTLP if endpoint set."""
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if endpoint:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(endpoint if "//" in endpoint else f"//{endpoint}")
            use_http = parsed.port == 4318
            if use_http:
                from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
            else:
                from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
            return OTLPLogExporter()
        except ImportError:
            pass
    from opentelemetry.sdk._logs.export import ConsoleLogExporter
    return ConsoleLogExporter()


def init_logs(service_name: Optional[str] = None) -> None:
    global _initialized
    if _initialized or not ABIDEX_LOGS_ENABLED:
        return
    from opentelemetry._logs import set_logger_provider

    resource = Resource.create({
        "service.name": service_name or get_service_name() or "abidex",
    })
    provider = LoggerProvider(resource=resource)
    provider.add_log_record_processor(AgenticLogEnricherProcessor())
    provider.add_log_record_processor(BatchLogRecordProcessor(_get_log_exporter()))
    if ABIDEX_LOGS_BUFFER_ENABLED:
        provider.add_log_record_processor(log_buffer.BufferLogProcessor())
    set_logger_provider(provider)

    handler = LoggingHandler(logger_provider=provider)
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET or root.level > logging.INFO:
        root.setLevel(logging.INFO)
    _initialized = True
