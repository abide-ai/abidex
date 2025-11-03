"""
Abide AgentKit - Telemetry and logging SDK for AI agents.

This package provides comprehensive telemetry collection for AI agents,
including spans for agent runs, model calls, and tool executions.
"""

from .client import (
    TelemetryClient, Event, EventType, 
    AgentInfo, ActionInfo, ModelCallInfo, TelemetryInfo
)
from .spans import AgentRun, ModelCall, ToolCall
from .logger import TelemetryLogger, AgentLogger, get_logger, get_agent_logger, setup_telemetry_logging
from . import instrumentation

__version__ = "0.1.0"
__all__ = [
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
