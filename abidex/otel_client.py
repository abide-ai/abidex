"""
OpenTelemetry-based telemetry client implementation.

This module provides the TelemetryClient and related classes using OpenTelemetry
as the backend instead of custom telemetry implementation.
"""

import time
from typing import Any, Dict, Optional
from contextlib import contextmanager
from uuid import uuid4

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

# Re-export OpenTelemetry types for compatibility
from opentelemetry.trace import Span, Status, StatusCode
from opentelemetry.metrics import Meter, Counter, Histogram, UpDownCounter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

# Import existing types for compatibility
from .client import (
    Event, EventType, AgentInfo, ActionInfo, ModelCallInfo, TelemetryInfo
)


class TelemetryClient:
    """
    OpenTelemetry-based telemetry client.
    
    This wraps OpenTelemetry's Tracer and Meter to provide the same API
    as the original TelemetryClient but using OpenTelemetry as the backend.
    """
    
    def __init__(
        self,
        agent_id: Optional[str] = None,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None,
        otlp_endpoint: Optional[str] = None,
        otlp_headers: Optional[Dict[str, str]] = None,
        sample_rate: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        default_tags: Optional[Dict[str, str]] = None,
        enabled: bool = True,
        otlp_traces_endpoint: Optional[str] = None,
        otlp_metrics_endpoint: Optional[str] = None
    ):
        """
        Initialize OpenTelemetry-based telemetry client.
        
        Args:
            agent_id: Agent identifier
            service_name: Service name for OpenTelemetry resource
            service_version: Service version
            otlp_endpoint: Base OTLP endpoint URL (e.g., "http://localhost:4318")
            otlp_headers: Headers for OTLP export
            otlp_traces_endpoint: Full OTLP traces endpoint URL (overrides base)
            otlp_metrics_endpoint: Full OTLP metrics endpoint URL (overrides base)
            sample_rate: Sampling rate (0.0 to 1.0)
            metadata: Additional metadata
            default_tags: Default tags/attributes
            enabled: Whether telemetry is enabled
        """
        self.agent_id = agent_id or str(uuid4())
        self.service_name = service_name or agent_id or "abidex_service"
        self.service_version = service_version or "0.1.0"
        self.sample_rate = sample_rate
        self.metadata = metadata or {}
        self.default_tags = default_tags or {}
        self.enabled = enabled
        
        # Set up OpenTelemetry resource
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self.service_version,
            "agent.id": self.agent_id,
            **self.metadata
        })
        
        # Initialize TracerProvider
        self.tracer_provider = TracerProvider(resource=resource)
        
        from .config import resolve_otlp_settings

        otlp_settings = resolve_otlp_settings(
            otlp_endpoint=otlp_endpoint,
            otlp_headers=otlp_headers,
            otlp_traces_endpoint=otlp_traces_endpoint,
            otlp_metrics_endpoint=otlp_metrics_endpoint,
        )
        otlp_headers = otlp_settings.headers or {}

        # Set up span exporters
        # Use SimpleSpanProcessor for console (no background threads) to avoid hanging
        # Use BatchSpanProcessor for OTLP (better performance with batching)
        if otlp_settings.traces_endpoint:
            span_exporter = OTLPSpanExporter(
                endpoint=otlp_settings.traces_endpoint,
                headers=otlp_headers
            )
            # Store reference to span processor for proper shutdown
            self.span_processor = BatchSpanProcessor(span_exporter)
        else:
            span_exporter = ConsoleSpanExporter()
            # Use SimpleSpanProcessor for console to avoid background threads
            self.span_processor = SimpleSpanProcessor(span_exporter)
        
        self.tracer_provider.add_span_processor(self.span_processor)
        
        # Set as global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer = trace.get_tracer(
            instrumenting_module_name="abidex",
            instrumenting_library_version=self.service_version
        )
        
        # Set up metric exporters
        # For console mode, don't use PeriodicExportingMetricReader to avoid background threads
        # Metrics can still be recorded but won't be exported (prevents hanging)
        metric_readers = []
        if otlp_settings.metrics_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=otlp_settings.metrics_endpoint,
                headers=otlp_headers
            )
            metric_reader = PeriodicExportingMetricReader(metric_exporter)
            metric_readers.append(metric_reader)
            # Store reference to metric reader for proper shutdown
            self.metric_reader = metric_reader
        else:
            # For console mode, don't export metrics (no background threads = no hanging)
            # Metrics can still be recorded but won't be exported
            self.metric_reader = None
        
        # Initialize MeterProvider with metric readers
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers
        )
        
        # Set as global meter provider
        metrics.set_meter_provider(self.meter_provider)
        
        # Get meter
        self.meter = metrics.get_meter(
            name="abidex",
            version=self.service_version
        )
        
        # Create common metrics
        self._create_metrics()
    
    def _create_metrics(self):
        """Create common OpenTelemetry metrics."""
        self.agent_runs_counter = self.meter.create_counter(
            name="abidex.agent.runs",
            description="Total number of agent runs"
        )
        self.model_calls_counter = self.meter.create_counter(
            name="abidex.model.calls",
            description="Total number of model calls"
        )
        self.model_tokens_counter = self.meter.create_counter(
            name="abidex.model.tokens",
            description="Total tokens used in model calls",
            unit="token"
        )
        self.model_latency_histogram = self.meter.create_histogram(
            name="abidex.model.latency",
            description="Model call latency",
            unit="ms"
        )
        self.errors_counter = self.meter.create_counter(
            name="abidex.errors",
            description="Total number of errors"
        )
    
    def start_span(
        self,
        name: str,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[list] = None,
        start_time: Optional[int] = None
    ) -> Span:
        """
        Start a new OpenTelemetry span.
        
        Args:
            name: Span name
            kind: Span kind
            attributes: Span attributes
            links: Span links
            start_time: Start time in nanoseconds
            
        Returns:
            OpenTelemetry Span
        """
        if not self.enabled:
            return trace.NoOpSpan()
        
        # Merge default tags with provided attributes
        span_attributes = {**self.default_tags, **(attributes or {})}
        
        return self.tracer.start_span(
            name=name,
            kind=kind,
            attributes=span_attributes,
            links=links,
            start_time=start_time
        )
    
    @contextmanager
    def span(
        self,
        name: str,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        set_status_on_exception: bool = True
    ):
        """
        Context manager for creating a span.
        
        Args:
            name: Span name
            kind: Span kind
            attributes: Span attributes
            set_status_on_exception: Whether to set error status on exception
        """
        span = self.start_span(name, kind, attributes)
        try:
            with trace.use_span(span):
                yield span
        except Exception as e:
            if set_status_on_exception:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
            raise
        finally:
            span.end()
    
    def record_metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Record a metric value.
        
        Args:
            name: Metric name
            value: Metric value
            unit: Metric unit
            attributes: Metric attributes
        """
        if not self.enabled:
            return
        
        # Merge default tags
        metric_attributes = {**self.default_tags, **(attributes or {})}
        
        # Use histogram for numeric values
        histogram = self.meter.create_histogram(
            name=name,
            description=f"Metric: {name}",
            unit=unit
        )
        histogram.record(value, attributes=metric_attributes)
    
    def increment_counter(
        self,
        name: str,
        value: int = 1,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Increment a counter metric.
        
        Args:
            name: Counter name
            value: Increment value
            attributes: Counter attributes
        """
        if not self.enabled:
            return
        
        metric_attributes = {**self.default_tags, **(attributes or {})}
        counter = self.meter.create_counter(
            name=name,
            description=f"Counter: {name}"
        )
        counter.add(value, attributes=metric_attributes)
    
    def log_event(
        self,
        message: str,
        level: str = "info",
        attributes: Optional[Dict[str, Any]] = None,
        span: Optional[Span] = None
    ):
        """
        Log an event as a span event.
        
        Args:
            message: Log message
            level: Log level
            attributes: Event attributes
            span: Optional span to add event to
        """
        if not self.enabled:
            return
        
        event_attributes = {
            "message": message,
            "level": level,
            **self.default_tags,
            **(attributes or {})
        }
        
        if span:
            span.add_event(name=f"log.{level}", attributes=event_attributes)
        else:
            # Create a new span for the log event
            with self.span("log", attributes=event_attributes) as log_span:
                log_span.add_event(name=f"log.{level}", attributes=event_attributes)
    
    # Compatibility methods to match original TelemetryClient API
    def emit(self, event: Event):
        """Emit an event (compatibility method)."""
        if not self.enabled:
            return
        
        # Convert Event to OpenTelemetry span
        attributes = {
            "event.type": event.event_type.value,
            "agent.name": event.agent.name or "",
            "agent.role": event.agent.role or "",
            **event.tags,
            **event.metadata
        }
        
        if event.agent.name:
            attributes["agent.name"] = event.agent.name
        if event.agent.role:
            attributes["agent.role"] = event.agent.role
        
        with self.span(
            name=event.event_type.value,
            attributes=attributes
        ) as span:
            if event.error:
                span.set_status(Status(StatusCode.ERROR, event.error))
                span.record_exception(Exception(event.error))
            
            if event.telemetry.latency_ms:
                span.set_attribute("latency_ms", event.telemetry.latency_ms)
    
    def log(
        self,
        message: str,
        level: str = "info",
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ):
        """Log a message (compatibility method)."""
        attributes = {**(data or {}), **(tags or {})}
        if run_id:
            attributes["run_id"] = run_id
        if span_id:
            attributes["span_id"] = span_id
        
        self.log_event(message, level, attributes)
    
    def metric(
        self,
        name: str,
        value: float,
        unit: str = "",
        tags: Optional[Dict[str, str]] = None
    ):
        """Record a metric (compatibility method)."""
        self.record_metric(name, value, unit, tags)
    
    def error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ):
        """Record an error (compatibility method)."""
        attributes = {**(context or {}), **(tags or {})}
        if run_id:
            attributes["run_id"] = run_id
        if span_id:
            attributes["span_id"] = span_id
        
        with self.span("error", attributes=attributes) as span:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
            self.errors_counter.add(1, attributes=attributes)
    
    @contextmanager
    def infer(self, model: str, backend: str, **kwargs):
        """Context manager for model inference (compatibility method)."""
        attributes = {
            "model": model,
            "backend": backend,
            **kwargs
        }
        
        with self.span("model.call", attributes=attributes) as span:
            start_time = time.time()
            try:
                yield span
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("latency_ms", latency_ms)
                self.model_latency_histogram.record(latency_ms, attributes=attributes)
                self.model_calls_counter.add(1, attributes=attributes)
    
    def add_sink(self, sink):
        """Add a sink (compatibility method - no-op for OpenTelemetry)."""
        # OpenTelemetry uses exporters, not sinks
        # This is kept for API compatibility
        pass
    
    def shutdown(self):
        """Shutdown OpenTelemetry providers."""
        import threading
        
        # Flush span processor before shutdown to ensure all spans are exported
        # SimpleSpanProcessor doesn't have force_flush (it's synchronous)
        if hasattr(self, 'span_processor') and self.span_processor:
            try:
                # Only flush if it's a BatchSpanProcessor
                if isinstance(self.span_processor, BatchSpanProcessor):
                    self.span_processor.force_flush(timeout_millis=2000)
            except Exception as e:
                print(f"Warning: Failed to flush span processor: {e}")
        
        # Shutdown metric reader first if it exists (only for OTLP mode)
        if hasattr(self, 'metric_reader') and self.metric_reader:
            try:
                shutdown_done = threading.Event()
                def shutdown_metric_reader():
                    try:
                        self.metric_reader.shutdown()
                    finally:
                        shutdown_done.set()
                
                thread = threading.Thread(target=shutdown_metric_reader, daemon=True)
                thread.start()
                shutdown_done.wait(timeout=1.0)  # 1 second timeout
            except Exception as e:
                print(f"Warning: Failed to shutdown metric reader: {e}")
        
        # Shutdown OpenTelemetry providers
        # SimpleSpanProcessor doesn't have background threads, so shutdown should be quick
        if self.tracer_provider:
            try:
                self.tracer_provider.shutdown()
            except Exception as e:
                print(f"Warning: Failed to shutdown tracer provider: {e}")
        if self.meter_provider:
            try:
                self.meter_provider.shutdown()
            except Exception as e:
                print(f"Warning: Failed to shutdown meter provider: {e}")


# Global default client instance
_default_client: Optional[TelemetryClient] = None


def get_client() -> TelemetryClient:
    """Get the global default telemetry client."""
    global _default_client
    if _default_client is None:
        _default_client = TelemetryClient()
    return _default_client


def set_client(client: TelemetryClient) -> None:
    """Set the global default telemetry client."""
    global _default_client
    _default_client = client

