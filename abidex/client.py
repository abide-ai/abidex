"""
Core telemetry client using OpenTelemetry as the backend.

This module provides the TelemetryClient and related classes using OpenTelemetry
for distributed tracing, metrics, and logging.
"""

import json
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from dataclasses import dataclass, asdict, field
from uuid import uuid4
from contextlib import contextmanager

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader, ConsoleMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.metrics import Meter, Counter, Histogram


class EventType(str, Enum):
    """Types of telemetry events."""
    AGENT_RUN_START = "agent_run_start"
    AGENT_RUN_END = "agent_run_end"
    MODEL_CALL_START = "model_call_start"
    MODEL_CALL_END = "model_call_end"
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_END = "tool_call_end"
    ERROR = "error"
    METRIC = "metric"
    LOG = "log"


@dataclass
class AgentInfo:
    """Agent information structure."""
    name: Optional[str] = None
    role: Optional[str] = None
    version: Optional[str] = None


@dataclass
class ActionInfo:
    """Action/tool call information structure."""
    type: Optional[str] = None  # 'tool_call', 'api_call', etc.
    name: Optional[str] = None
    input: Optional[str] = None
    output: Optional[str] = None
    success: bool = True
    latency_ms: Optional[float] = None


@dataclass
class ModelCallInfo:
    """Model call information structure."""
    backend: Optional[str] = None
    model: Optional[str] = None
    prompt_preview: Optional[str] = None
    completion_preview: Optional[str] = None
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None


@dataclass
class TelemetryInfo:
    """Core telemetry timing and performance data."""
    timestamp_start: float = field(default_factory=time.time)
    timestamp_end: Optional[float] = None
    latency_ms: Optional[float] = None
    total_tokens: Optional[int] = None
    throughput_tokens_per_sec: Optional[float] = None


@dataclass
class Event:
    """
    Core event structure for telemetry data.
    
    This follows a structured schema with nested objects for different
    types of information (agent, action, model_call, telemetry, metadata).
    """
    
    # Core identifiers
    trace_id: str = field(default_factory=lambda: str(uuid4()))
    conversation_id: Optional[str] = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    event_type: EventType = EventType.LOG
    
    # Structured data sections
    agent: AgentInfo = field(default_factory=AgentInfo)
    action: Optional[ActionInfo] = None
    model_call: Optional[ModelCallInfo] = None
    telemetry: TelemetryInfo = field(default_factory=TelemetryInfo)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Legacy/compatibility fields
    run_id: Optional[str] = None
    parent_id: Optional[str] = None
    span_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)
    level: str = "info"
    success: bool = True
    error: Optional[str] = None
    sampled: bool = True
    
    def __post_init__(self):
        """Post-initialization to set up derived fields."""
        # Set conversation_id from run_id if not provided
        if not self.conversation_id and self.run_id:
            self.conversation_id = self.run_id
    
    @property
    def timestamp_start(self) -> float:
        """Backward compatibility property."""
        return self.telemetry.timestamp_start
    
    @property
    def timestamp_end(self) -> Optional[float]:
        """Backward compatibility property."""
        return self.telemetry.timestamp_end
    
    @property
    def latency_ms(self) -> Optional[float]:
        """Backward compatibility property."""
        return self.telemetry.latency_ms
    
    @property
    def timestamp(self) -> float:
        """Backward compatibility property."""
        return self.telemetry.timestamp_start
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary format matching the structured schema."""
        result = asdict(self)
        
        # Add ISO timestamps to telemetry section
        if 'telemetry' in result and result['telemetry']:
            result['telemetry']['timestamp_start_iso'] = datetime.fromtimestamp(
                self.telemetry.timestamp_start
            ).isoformat()
            if self.telemetry.timestamp_end:
                result['telemetry']['timestamp_end_iso'] = datetime.fromtimestamp(
                    self.telemetry.timestamp_end
                ).isoformat()
        
        # Clean up None values in nested structures
        for section in ['agent', 'action', 'model_call', 'telemetry']:
            if section in result and result[section]:
                result[section] = {k: v for k, v in result[section].items() if v is not None}
        
        # Remove action and model_call if they're empty/None
        if result.get('action') and not any(result['action'].values()):
            result['action'] = None
        if result.get('model_call') and not any(result['model_call'].values()):
            result['model_call'] = None
            
        return result
    
    def finish(self, error: Optional[Exception] = None) -> None:
        """Mark the event as finished and calculate performance metrics."""
        self.telemetry.timestamp_end = time.time()
        
        if self.telemetry.timestamp_start:
            self.telemetry.latency_ms = (
                self.telemetry.timestamp_end - self.telemetry.timestamp_start
            ) * 1000.0
        
        # Calculate throughput if we have token information
        if (self.telemetry.latency_ms and self.telemetry.latency_ms > 0 and 
            self.model_call and self.model_call.output_token_count):
            self.telemetry.throughput_tokens_per_sec = (
                self.model_call.output_token_count / (self.telemetry.latency_ms / 1000.0)
            )
        
        # Calculate total tokens
        if self.model_call:
            input_tokens = self.model_call.input_token_count or 0
            output_tokens = self.model_call.output_token_count or 0
            if input_tokens or output_tokens:
                self.telemetry.total_tokens = input_tokens + output_tokens
        
        # Set success status
        if error:
            self.success = False
            self.error = str(error)
            if self.action:
                self.action.success = False
        
        # Set action latency if action exists
        if self.action and self.telemetry.latency_ms:
            self.action.latency_ms = self.telemetry.latency_ms
    
    def set_agent_info(self, name: str, role: Optional[str] = None, version: Optional[str] = None) -> None:
        """Set agent information."""
        self.agent.name = name
        if role:
            self.agent.role = role
        if version:
            self.agent.version = version
    
    def set_action_info(
        self, 
        action_type: str, 
        name: str, 
        input_data: Optional[Any] = None, 
        output_data: Optional[Any] = None
    ) -> None:
        """Set action/tool call information."""
        if not self.action:
            self.action = ActionInfo()
        
        self.action.type = action_type
        self.action.name = name
        
        if input_data is not None:
            # Truncate long inputs for preview
            input_str = str(input_data)
            self.action.input = input_str[:200] + "..." if len(input_str) > 200 else input_str
        
        if output_data is not None:
            # Truncate long outputs for preview
            output_str = str(output_data)
            self.action.output = output_str[:500] + "..." if len(output_str) > 500 else output_str
    
    def set_model_call_info(
        self,
        backend: str,
        model: str,
        prompt: Optional[str] = None,
        completion: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None
    ) -> None:
        """Set model call information."""
        if not self.model_call:
            self.model_call = ModelCallInfo()
        
        self.model_call.backend = backend
        self.model_call.model = model
        
        if prompt is not None:
            # Create preview of prompt
            self.model_call.prompt_preview = prompt[:500] + "..." if len(prompt) > 500 else prompt
        
        if completion is not None:
            # Create preview of completion
            self.model_call.completion_preview = completion[:500] + "..." if len(completion) > 500 else completion
        
        if input_tokens is not None:
            self.model_call.input_token_count = input_tokens
        
        if output_tokens is not None:
            self.model_call.output_token_count = output_tokens
    
    def to_json(self) -> str:
        """Convert event to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class TelemetrySink(Protocol):
    """Protocol for telemetry sinks."""
    
    def send(self, event: Event) -> None:
        """Send an event to the sink."""
        ...
    
    def flush(self) -> None:
        """Flush any pending events."""
        ...
    
    def close(self) -> None:
        """Close the sink and cleanup resources."""
        ...


class TelemetryClient:
    """
    OpenTelemetry-based telemetry client.
    
    This client uses OpenTelemetry for distributed tracing, metrics, and logging.
    It maintains compatibility with the existing API while using OpenTelemetry as the backend.
    """
    
    def __init__(
        self, 
        agent_id: Optional[str] = None,
        sinks: Optional[List[TelemetrySink]] = None,
        default_tags: Optional[Dict[str, str]] = None,
        sample_rate: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        otlp_endpoint: Optional[str] = None,
        otlp_headers: Optional[Dict[str, str]] = None,
        service_name: Optional[str] = None,
        service_version: Optional[str] = None
    ):
        self.agent_id = agent_id or str(uuid4())
        self.sinks = sinks or []  # Keep for backward compatibility
        self.default_tags = default_tags or {}
        self.sample_rate = float(sample_rate)
        self.metadata = metadata or {}
        self._enabled = True
        
        # Set up OpenTelemetry resource
        service_name = service_name or agent_id or "abidex_service"
        service_version = service_version or "0.1.0"
        
        resource_attributes = {
            "service.name": service_name,
            "service.version": service_version,
            "agent.id": self.agent_id,
            **self.metadata
        }
        resource = Resource.create(resource_attributes)
        
        # Initialize TracerProvider
        self.tracer_provider = TracerProvider(resource=resource)
        
        # Set up span exporters
        if otlp_endpoint:
            span_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint + "/v1/traces",
                headers=otlp_headers or {}
            )
        else:
            span_exporter = ConsoleSpanExporter()
        
        self.tracer_provider.add_span_processor(
            BatchSpanProcessor(span_exporter)
        )
        
        # Set as global tracer provider
        trace.set_tracer_provider(self.tracer_provider)
        
        # Get tracer
        self.tracer: Tracer = trace.get_tracer(
            instrumenting_module_name="abidex",
            instrumenting_library_version=service_version
        )
        
        # Set up metric exporters
        metric_readers = []
        if otlp_endpoint:
            metric_exporter = OTLPMetricExporter(
                endpoint=otlp_endpoint + "/v1/metrics",
                headers=otlp_headers or {}
            )
            metric_readers.append(
                PeriodicExportingMetricReader(metric_exporter)
            )
        else:
            metric_exporter = ConsoleMetricExporter()
            metric_readers.append(
                PeriodicExportingMetricReader(metric_exporter)
            )
        
        # Initialize MeterProvider with metric readers
        self.meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers
        )
        
        # Set as global meter provider
        metrics.set_meter_provider(self.meter_provider)
        
        # Get meter
        self.meter: Meter = metrics.get_meter(
            name="abidex",
            version=service_version
        )
        
        # Create common metrics
        self._create_otel_metrics()
    
    def _create_otel_metrics(self):
        """Create OpenTelemetry metrics."""
        self.agent_runs_counter: Counter = self.meter.create_counter(
            name="abidex.agent.runs",
            description="Total number of agent runs"
        )
        self.model_calls_counter: Counter = self.meter.create_counter(
            name="abidex.model.calls",
            description="Total number of model calls"
        )
        self.model_tokens_counter: Counter = self.meter.create_counter(
            name="abidex.model.tokens",
            description="Total tokens used in model calls",
            unit="token"
        )
        self.model_latency_histogram: Histogram = self.meter.create_histogram(
            name="abidex.model.latency",
            description="Model call latency",
            unit="ms"
        )
        self.errors_counter: Counter = self.meter.create_counter(
            name="abidex.errors",
            description="Total number of errors"
        )
    
    def add_sink(self, sink: TelemetrySink) -> None:
        """Add a telemetry sink (kept for backward compatibility)."""
        self.sinks.append(sink)
    
    def remove_sink(self, sink: TelemetrySink) -> None:
        """Remove a telemetry sink."""
        if sink in self.sinks:
            self.sinks.remove(sink)
    
    def enable(self) -> None:
        """Enable telemetry collection."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable telemetry collection."""
        self._enabled = False
    
    def _should_sample(self) -> bool:
        """Determine if event should be sampled."""
        import random
        return random.random() < self.sample_rate
    
    def start_span(
        self,
        name: str,
        kind: trace.SpanKind = trace.SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Any]] = None,
        links: Optional[list] = None,
        start_time: Optional[int] = None
    ) -> Span:
        """Start a new OpenTelemetry span."""
        if not self._enabled:
            return trace.NoOpSpan()
        
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
        """Context manager for creating an OpenTelemetry span."""
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
    
    def new_event(
        self,
        event_type: EventType = EventType.LOG,
        agent_name: Optional[str] = None,
        agent_role: Optional[str] = None,
        agent_version: Optional[str] = None,
        conversation_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> Event:
        """Create a new event with default values using the structured schema."""
        event = Event(
            event_type=event_type,
            conversation_id=conversation_id,
            tags={**self.default_tags, **(tags or {})},
            sampled=self._should_sample()
        )
        
        # Set agent information
        if agent_name or self.agent_id:
            event.set_agent_info(
                name=agent_name or self.agent_id,
                role=agent_role,
                version=agent_version
            )
        
        # Add metadata
        event.metadata.update(self.metadata)
        
        return event
    
    def emit(self, event: Event) -> None:
        """Emit an event using OpenTelemetry spans and metrics."""
        if not self._enabled or not event.sampled:
            return
        
        # Set agent info if not already set
        if (not event.agent.name or event.agent.name == "") and self.agent_id:
            event.set_agent_info(name=self.agent_id)
        
        # Merge default tags
        event.tags = {**self.default_tags, **event.tags}
        
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
        
        # Create span based on event type
        span_name = event.event_type.value
        with self.span(name=span_name, attributes=attributes) as span:
            if event.error:
                span.set_status(Status(StatusCode.ERROR, event.error))
                span.record_exception(Exception(event.error))
                self.errors_counter.add(1, attributes=attributes)
            
            if event.telemetry.latency_ms:
                span.set_attribute("latency_ms", event.telemetry.latency_ms)
            
            # Record metrics based on event type
            if event.event_type == EventType.AGENT_RUN_START:
                self.agent_runs_counter.add(1, attributes=attributes)
            elif event.event_type == EventType.MODEL_CALL_START:
                self.model_calls_counter.add(1, attributes=attributes)
                if event.telemetry.latency_ms:
                    self.model_latency_histogram.record(
                        event.telemetry.latency_ms,
                        attributes=attributes
                    )
                if event.model_call and event.model_call.input_token_count:
                    self.model_tokens_counter.add(
                        event.model_call.input_token_count,
                        attributes=attributes
                    )
        
        # Also send to legacy sinks for backward compatibility
        for sink in self.sinks:
            try:
                sink.send(event)
            except Exception as e:
                print(f"Warning: Failed to send event to sink {sink}: {e}")
    
    def write(self, event: Event) -> None:
        """Alias for emit() for backward compatibility."""
        self.emit(event)
    
    def log(
        self, 
        message: str, 
        level: str = "info",
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ) -> None:
        """Log a message using OpenTelemetry span events."""
        if not self._enabled:
            return
        
        attributes = {
            "message": message,
            "level": level,
            **self.default_tags,
            **(tags or {}),
            **(data or {})
        }
        if run_id:
            attributes["run_id"] = run_id
        if span_id:
            attributes["span_id"] = span_id
        
        # Log as OpenTelemetry span event
        with self.span("log", attributes=attributes) as span:
            span.add_event(name=f"log.{level}", attributes=attributes)
        
        # Also emit as Event for backward compatibility
        event = Event(
            event_type=EventType.LOG,
            level=level,
            tags=tags or {},
            run_id=run_id,
            span_id=span_id
        )
        event.metadata.update({"message": message, **(data or {})})
        # Send to legacy sinks
        for sink in self.sinks:
            try:
                sink.send(event)
            except Exception:
                pass
    
    def metric(
        self,
        name: str,
        value: Union[int, float],
        unit: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ) -> None:
        """Record a metric using OpenTelemetry metrics API."""
        if not self._enabled:
            return
        
        attributes = {**self.default_tags, **(tags or {})}
        if run_id:
            attributes["run_id"] = run_id
        if span_id:
            attributes["span_id"] = span_id
        
        # Use OpenTelemetry histogram for numeric metrics
        histogram = self.meter.create_histogram(
            name=name,
            description=f"Metric: {name}",
            unit=unit or ""
        )
        histogram.record(value, attributes=attributes)
        
        # Also emit as Event for backward compatibility
        event = Event(
            event_type=EventType.METRIC,
            tags=tags or {},
            run_id=run_id,
            span_id=span_id
        )
        event.metadata.update({
            "metric_name": name,
            "value": value,
            "unit": unit
        })
        # Send to legacy sinks
        for sink in self.sinks:
            try:
                sink.send(event)
            except Exception:
                pass
    
    def error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ) -> None:
        """Record an error using OpenTelemetry."""
        if not self._enabled:
            return
        
        attributes = {
            "error_type": type(error).__name__,
            "error_message": str(error),
            **self.default_tags,
            **(tags or {}),
            **(context or {})
        }
        if run_id:
            attributes["run_id"] = run_id
        if span_id:
            attributes["span_id"] = span_id
        
        # Record error as OpenTelemetry span
        with self.span("error", attributes=attributes) as span:
            span.set_status(Status(StatusCode.ERROR, str(error)))
            span.record_exception(error)
            self.errors_counter.add(1, attributes=attributes)
        
        # Also emit as Event for backward compatibility
        event = Event(
            event_type=EventType.ERROR,
            level="error",
            tags=tags or {},
            run_id=run_id,
            span_id=span_id
        )
        event.error = str(error)
        event.success = False
        event.metadata.update({
            "error_type": type(error).__name__,
            "error_message": str(error),
            "context": context or {}
        })
        # Send to legacy sinks
        for sink in self.sinks:
            try:
                sink.send(event)
            except Exception:
                pass
    
    def flush(self) -> None:
        """Flush all sinks."""
        for sink in self.sinks:
            try:
                sink.flush()
            except Exception as e:
                print(f"Warning: Failed to flush sink {sink}: {e}")
    
    def close(self) -> None:
        """Close all sinks and shutdown OpenTelemetry providers."""
        for sink in self.sinks:
            try:
                sink.close()
            except Exception as e:
                print(f"Warning: Failed to close sink {sink}: {e}")
        self.sinks.clear()
        
        # Shutdown OpenTelemetry providers
        if self.tracer_provider:
            self.tracer_provider.shutdown()
        if self.meter_provider:
            self.meter_provider.shutdown()
    
    @contextmanager
    def infer(
        self,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        batch_size: int = 1,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Context manager for tracking inference/model calls using OpenTelemetry.
        
        Example:
            with client.infer("gpt-4", "openai") as span:
                response = model.generate(prompt)
                span.set_attribute("output_tokens", len(response))
        """
        if not self._enabled:
            yield trace.NoOpSpan()
            return
        
        attributes = {
            "model": model or "unknown",
            "backend": backend or "unknown",
            "batch_size": batch_size,
            **self.default_tags,
            **(tags or {})
        }
        
        start_time = time.time()
        with self.span("model.call", attributes=attributes) as span:
            try:
                yield span
            finally:
                latency_ms = (time.time() - start_time) * 1000
                span.set_attribute("latency_ms", latency_ms)
                self.model_latency_histogram.record(latency_ms, attributes=attributes)
                self.model_calls_counter.add(1, attributes=attributes)
    
    def record(
        self,
        model: Optional[str] = None,
        backend: Optional[str] = None,
        batch_size_arg: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ):
        """
        Decorator for automatically tracking function calls.
        
        Args:
            model: Model name
            backend: Backend/provider name
            batch_size_arg: Argument name to extract batch size from
            tags: Additional tags
        
        Example:
            @client.record(model="gpt-4", backend="openai")
            def generate_text(prompt):
                return model.generate(prompt)
        """
        import functools
        
        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                # Resolve batch size if arg name provided
                bs = batch_size_arg and kwargs.get(batch_size_arg)
                if bs is None and batch_size_arg and args:
                    # Try to get batch size from first arg if it's list-like
                    try:
                        bs = len(args[0])
                    except (TypeError, AttributeError):
                        bs = 1
                
                event = self.new_event(
                    event_type=EventType.MODEL_CALL_START,
                    tags=tags
                )
                
                # Set model call info
                event.set_model_call_info(backend=backend or "unknown", model=model or "unknown")
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Try to extract completion from result
                    if hasattr(result, '__len__'):
                        completion = str(result)
                        event.set_model_call_info(
                            backend=event.model_call.backend,
                            model=event.model_call.model,
                            completion=completion
                        )
                    
                    event.finish()
                    self.emit(event)
                    return result
                    
                except Exception as e:
                    event.finish(error=e)
                    self.emit(event)
                    raise
            
            return wrapper
        return decorator


class InferenceContext:
    """Context manager for tracking inference calls."""
    
    def __init__(
        self,
        client: TelemetryClient,
        model: Optional[str],
        backend: Optional[str],
        batch_size: int,
        tags: Optional[Dict[str, str]]
    ):
        self.client = client
        self.event = client.new_event(
            event_type=EventType.MODEL_CALL_START,
            tags=tags
        )
        
        # Set model call information
        self.event.set_model_call_info(
            backend=backend or "unknown",
            model=model or "unknown"
        )
    
    def __enter__(self) -> Event:
        return self.event
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_val:
            self.event.finish(error=exc_val)
        else:
            self.event.finish()
        
        self.client.emit(self.event)
        return False


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
