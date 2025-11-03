"""
Prometheus metrics sink for telemetry events.
"""

import time
from typing import Dict, Optional, Set, Any
from threading import Lock

from ..client import Event, EventType, TelemetrySink

try:
    from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False


class PrometheusSink:
    """
    Sink that exports telemetry events as Prometheus metrics.
    """
    
    def __init__(
        self,
        registry: Optional['CollectorRegistry'] = None,
        metric_prefix: str = "abide_agent",
        include_labels: Optional[Set[str]] = None,
        max_label_cardinality: int = 1000
    ):
        if not PROMETHEUS_AVAILABLE:
            raise ImportError("prometheus_client is required for PrometheusSink")
        
        self.registry = registry
        self.metric_prefix = metric_prefix
        self.include_labels = include_labels or {"agent_id", "event_type", "level"}
        self.max_label_cardinality = max_label_cardinality
        self._lock = Lock()
        self._label_counts: Dict[str, int] = {}
        
        # Initialize metrics
        self._init_metrics()
    
    def _init_metrics(self) -> None:
        """Initialize Prometheus metrics."""
        
        # Event counters
        self.event_counter = Counter(
            f'{self.metric_prefix}_events_total',
            'Total number of telemetry events',
            ['agent_id', 'event_type', 'level'],
            registry=self.registry
        )
        
        # Duration histograms for spans
        self.span_duration = Histogram(
            f'{self.metric_prefix}_span_duration_seconds',
            'Duration of spans in seconds',
            ['agent_id', 'span_type', 'success'],
            registry=self.registry
        )
        
        # Token usage metrics
        self.token_counter = Counter(
            f'{self.metric_prefix}_tokens_total',
            'Total number of tokens used',
            ['agent_id', 'model', 'token_type'],
            registry=self.registry
        )
        
        # Error counter
        self.error_counter = Counter(
            f'{self.metric_prefix}_errors_total',
            'Total number of errors',
            ['agent_id', 'error_type'],
            registry=self.registry
        )
        
        # Active runs gauge
        self.active_runs = Gauge(
            f'{self.metric_prefix}_active_runs',
            'Number of currently active agent runs',
            ['agent_id'],
            registry=self.registry
        )
        
        # Custom metrics gauge for arbitrary metrics
        self.custom_metrics = Gauge(
            f'{self.metric_prefix}_custom_metric',
            'Custom metrics from events',
            ['agent_id', 'metric_name', 'unit'],
            registry=self.registry
        )
    
    def _extract_labels(self, event: Event) -> Dict[str, str]:
        """Extract labels from an event."""
        labels = {}
        
        # Add standard labels
        if 'agent_id' in self.include_labels and event.agent_id:
            labels['agent_id'] = str(event.agent_id)
        
        if 'event_type' in self.include_labels:
            labels['event_type'] = event.event_type.value
        
        if 'level' in self.include_labels:
            labels['level'] = event.level
        
        # Add tags as labels
        for tag_key, tag_value in event.tags.items():
            if tag_key in self.include_labels:
                labels[tag_key] = str(tag_value)
        
        # Check label cardinality
        label_key = str(sorted(labels.items()))
        with self._lock:
            if label_key not in self._label_counts:
                if len(self._label_counts) >= self.max_label_cardinality:
                    # Skip this label combination to avoid high cardinality
                    return {'agent_id': labels.get('agent_id', 'unknown')}
                self._label_counts[label_key] = 0
            self._label_counts[label_key] += 1
        
        return labels
    
    def _handle_span_event(self, event: Event) -> None:
        """Handle span-related events."""
        if event.event_type in (EventType.AGENT_RUN_START, EventType.MODEL_CALL_START, EventType.TOOL_CALL_START):
            # Increment active runs for agent run starts
            if event.event_type == EventType.AGENT_RUN_START and event.agent_id:
                self.active_runs.labels(agent_id=event.agent_id).inc()
        
        elif event.event_type in (EventType.AGENT_RUN_END, EventType.MODEL_CALL_END, EventType.TOOL_CALL_END):
            # Handle span end events
            duration = event.data.get('duration_seconds', 0)
            
            # Use latency_ms from new Event schema if available
            if event.latency_ms is not None:
                duration = event.latency_ms / 1000.0
            
            success = str(event.success).lower()
            span_type = event.data.get('span_type', 'unknown')
            
            if duration > 0 and event.agent_id:
                self.span_duration.labels(
                    agent_id=event.agent_id,
                    span_type=span_type,
                    success=success
                ).observe(duration)
            
            # Decrement active runs for agent run ends
            if event.event_type == EventType.AGENT_RUN_END and event.agent_id:
                self.active_runs.labels(agent_id=event.agent_id).dec()
            
            # Track token usage from new Event schema fields
            if event.agent_id and event.model:
                if event.input_token_count:
                    self.token_counter.labels(
                        agent_id=event.agent_id,
                        model=event.model,
                        token_type='input_tokens'
                    ).inc(event.input_token_count)
                
                if event.output_token_count:
                    self.token_counter.labels(
                        agent_id=event.agent_id,
                        model=event.model,
                        token_type='output_tokens'
                    ).inc(event.output_token_count)
                
                if event.total_tokens:
                    self.token_counter.labels(
                        agent_id=event.agent_id,
                        model=event.model,
                        token_type='total_tokens'
                    ).inc(event.total_tokens)
    
    def _handle_error_event(self, event: Event) -> None:
        """Handle error events."""
        if event.agent_id:
            error_type = event.data.get('error_type', 'unknown')
            self.error_counter.labels(
                agent_id=event.agent_id,
                error_type=error_type
            ).inc()
    
    def _handle_metric_event(self, event: Event) -> None:
        """Handle metric events."""
        if event.agent_id:
            metric_name = event.data.get('metric_name', 'unknown')
            value = event.data.get('value', 0)
            unit = event.data.get('unit', '')
            
            try:
                self.custom_metrics.labels(
                    agent_id=event.agent_id,
                    metric_name=metric_name,
                    unit=unit
                ).set(float(value))
            except (ValueError, TypeError):
                pass  # Skip non-numeric values
    
    def send(self, event: Event) -> None:
        """Send an event to Prometheus metrics."""
        # Skip unsampled events
        if not event.sampled:
            return
            
        try:
            # Update event counter
            labels = self._extract_labels(event)
            if labels:
                self.event_counter.labels(**labels).inc()
            
            # Handle specific event types
            if event.event_type in (
                EventType.AGENT_RUN_START, EventType.AGENT_RUN_END,
                EventType.MODEL_CALL_START, EventType.MODEL_CALL_END,
                EventType.TOOL_CALL_START, EventType.TOOL_CALL_END
            ):
                self._handle_span_event(event)
            
            elif event.event_type == EventType.ERROR:
                self._handle_error_event(event)
            
            elif event.event_type == EventType.METRIC:
                self._handle_metric_event(event)
        
        except Exception as e:
            print(f"Error processing event in Prometheus sink: {e}")
    
    def flush(self) -> None:
        """Flush is not needed for Prometheus metrics."""
        pass
    
    def close(self) -> None:
        """Close the sink."""
        pass
    
    def get_metrics(self) -> str:
        """Get current metrics in Prometheus format."""
        if not PROMETHEUS_AVAILABLE:
            return ""
        
        if self.registry:
            return generate_latest(self.registry).decode('utf-8')
        else:
            return generate_latest().decode('utf-8')


class PrometheusHTTPSink(PrometheusSink):
    """
    Prometheus sink that also serves metrics via HTTP.
    """
    
    def __init__(self, port: int = 8000, **kwargs):
        super().__init__(**kwargs)
        self.port = port
        self._server = None
        self._start_server()
    
    def _start_server(self) -> None:
        """Start the HTTP server for metrics."""
        try:
            from prometheus_client import start_http_server
            self._server = start_http_server(self.port, registry=self.registry)
            print(f"Prometheus metrics server started on port {self.port}")
        except Exception as e:
            print(f"Failed to start Prometheus HTTP server: {e}")
    
    def close(self) -> None:
        """Close the sink and stop the HTTP server."""
        super().close()
        # Note: prometheus_client doesn't provide a way to stop the HTTP server
        # The server will continue running until the process exits


# Mock classes for when prometheus_client is not available
if not PROMETHEUS_AVAILABLE:
    class PrometheusSink:
        def __init__(self, *args, **kwargs):
            raise ImportError("prometheus_client is required for PrometheusSink")
    
    class PrometheusHTTPSink:
        def __init__(self, *args, **kwargs):
            raise ImportError("prometheus_client is required for PrometheusHTTPSink")
