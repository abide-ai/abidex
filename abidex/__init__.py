"""
AbideX - OpenTelemetry-based telemetry and logging SDK for AI agents.

This package provides comprehensive telemetry collection for AI agents using
OpenTelemetry as the backend, including spans for agent runs, model calls, and tool executions.
"""

# OpenTelemetry imports - re-exported for direct use
from opentelemetry import trace, metrics
from opentelemetry.trace import Span, Status, StatusCode, Tracer
from opentelemetry.metrics import Meter, Counter, Histogram
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter

# AbideX client and types
from .client import (
    TelemetryClient, Event, EventType, 
    AgentInfo, ActionInfo, ModelCallInfo, TelemetryInfo
)
from .spans import AgentRun, ModelCall, ToolCall
from .logger import TelemetryLogger, AgentLogger, get_logger, get_agent_logger, setup_telemetry_logging
from . import instrumentation

__version__ = "0.1.0"
__all__ = [
    # OpenTelemetry exports
    "trace",
    "metrics",
    "Span",
    "Status",
    "StatusCode",
    "Tracer",
    "Meter",
    "Counter",
    "Histogram",
    "TracerProvider",
    "MeterProvider",
    "OTLPSpanExporter",
    "OTLPMetricExporter",
    # AbideX client and types
    "TelemetryClient",
    "Event", 
    "EventType",
    "AgentInfo",
    "ActionInfo", 
    "ModelCallInfo",
    "TelemetryInfo",
    "AgentRun",
    "ModelCall", 
    "ToolCall",
    "TelemetryLogger",
    "AgentLogger",
    "get_logger",
    "get_agent_logger",
    "setup_telemetry_logging",
    "instrumentation"
]
