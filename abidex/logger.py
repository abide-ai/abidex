"""
Telemetry-integrated logging for the Abide AgentKit SDK.

This module provides a logger that integrates with the telemetry system,
automatically creating events for log messages while maintaining compatibility
with Python's standard logging interface.
"""

import logging
import time
from typing import Any, Dict, Optional, Union
from contextlib import contextmanager

from .client import TelemetryClient, Event, EventType, get_client


class TelemetryLogHandler(logging.Handler):
    """
    Logging handler that sends log records to telemetry.
    """
    
    def __init__(
        self,
        client: Optional[TelemetryClient] = None,
        level: Union[int, str] = logging.NOTSET,
        include_stack_info: bool = False,
        max_message_length: int = 1000
    ):
        super().__init__(level)
        self.client = client or get_client()
        self.include_stack_info = include_stack_info
        self.max_message_length = max_message_length
    
    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record as a telemetry event."""
        try:
            # Map logging levels to telemetry levels
            level_map = {
                logging.DEBUG: "debug",
                logging.INFO: "info", 
                logging.WARNING: "warn",
                logging.ERROR: "error",
                logging.CRITICAL: "error"
            }
            
            level = level_map.get(record.levelno, "info")
            
            # Truncate long messages
            message = record.getMessage()
            if len(message) > self.max_message_length:
                message = message[:self.max_message_length] + "..."
            
            # Create event data
            data = {
                "message": message,
                "logger_name": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
                "thread": record.thread,
                "process": record.process
            }
            
            # Add exception info if present
            if record.exc_info:
                data["exception"] = {
                    "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                    "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                    "traceback": self.format(record) if self.include_stack_info else None
                }
            
            # Add extra fields from the log record
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in {
                    'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                    'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                    'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                    'thread', 'threadName', 'processName', 'process', 'message'
                }:
                    extra_fields[key] = value
            
            if extra_fields:
                data["extra"] = extra_fields
            
            # Create and emit telemetry event
            event = Event(
                event_type=EventType.LOG,
                level=level,
                tags={"source": "python_logging", "logger": record.name}
            )
            # Set timestamp and metadata
            event.telemetry.timestamp_start = record.created
            event.metadata = data
            
            self.client.emit(event)
            
        except Exception:
            # Don't let telemetry errors break logging
            self.handleError(record)


class TelemetryLogger:
    """
    Logger that integrates with telemetry while providing a familiar interface.
    """
    
    def __init__(
        self,
        name: str,
        client: Optional[TelemetryClient] = None,
        level: Union[int, str] = logging.INFO,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None
    ):
        self.name = name
        self.client = client or get_client()
        self.run_id = run_id
        self.span_id = span_id
        
        # Create standard logger
        self._logger = logging.getLogger(f"telemetry.{name}")
        self._logger.setLevel(level)
        
        # Add telemetry handler if not already present
        handler_exists = any(
            isinstance(h, TelemetryLogHandler) for h in self._logger.handlers
        )
        if not handler_exists:
            handler = TelemetryLogHandler(client)
            self._logger.addHandler(handler)
    
    def _create_event(
        self,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        error: Optional[Exception] = None
    ) -> Event:
        """Create a telemetry event for logging."""
        event = Event(
            event_type=EventType.LOG,
            level=level,
            run_id=self.run_id,
            span_id=self.span_id,
            tags={
                "source": "telemetry_logger",
                "logger": self.name,
                **(tags or {})
            }
        )
        # Set metadata (Event uses metadata, not data)
        event.metadata = {
            "message": message,
            "logger_name": self.name,
            **(data or {})
        }
        
        if error:
            event.success = False
            event.error = str(error)
            event.metadata["exception"] = {
                "type": type(error).__name__,
                "message": str(error)
            }
        
        return event
    
    def debug(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log a debug message."""
        event = self._create_event("debug", message, data, tags)
        self.client.emit(event)
        self._logger.debug(message, **kwargs)
    
    def info(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log an info message."""
        event = self._create_event("info", message, data, tags)
        self.client.emit(event)
        self._logger.info(message, **kwargs)
    
    def warning(
        self,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log a warning message."""
        event = self._create_event("warn", message, data, tags)
        self.client.emit(event)
        self._logger.warning(message, **kwargs)
    
    def warn(self, *args, **kwargs) -> None:
        """Alias for warning."""
        self.warning(*args, **kwargs)
    
    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log an error message."""
        event = self._create_event("error", message, data, tags, error)
        self.client.emit(event)
        self._logger.error(message, **kwargs)
    
    def exception(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log an exception with traceback."""
        event = self._create_event("error", message, data, tags, error)
        self.client.emit(event)
        self._logger.exception(message, **kwargs)
    
    def critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> None:
        """Log a critical message."""
        event = self._create_event("error", message, data, tags, error)
        self.client.emit(event)
        self._logger.critical(message, **kwargs)
    
    def with_context(
        self,
        run_id: Optional[str] = None,
        span_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None
    ) -> 'TelemetryLogger':
        """Create a new logger with additional context."""
        new_logger = TelemetryLogger(
            name=self.name,
            client=self.client,
            run_id=run_id or self.run_id,
            span_id=span_id or self.span_id
        )
        
        if tags:
            new_logger.client.default_tags.update(tags)
        
        return new_logger
    
    @contextmanager
    def span_context(self, span_id: str):
        """Context manager for temporary span context."""
        old_span_id = self.span_id
        self.span_id = span_id
        try:
            yield self
        finally:
            self.span_id = old_span_id


class AgentLogger(TelemetryLogger):
    """
    Specialized logger for AI agents with additional agent-specific methods.
    """
    
    def __init__(
        self,
        agent_name: str,
        client: Optional[TelemetryClient] = None,
        agent_role: Optional[str] = None,
        **kwargs
    ):
        super().__init__(f"agent.{agent_name}", client, **kwargs)
        self.agent_name = agent_name
        self.agent_role = agent_role
    
    def _create_event(
        self,
        level: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        tags: Optional[Dict[str, str]] = None,
        error: Optional[Exception] = None
    ) -> Event:
        """Create a telemetry event for logging with agent information."""
        event = super()._create_event(level, message, data, tags, error)
        
        # Set agent information in the event's agent field
        event.set_agent_info(
            name=self.agent_name,
            role=self.agent_role
        )
        
        return event
    
    def thinking(
        self,
        thought: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log agent thinking/reasoning."""
        self.debug(
            f"Agent thinking: {thought}",
            data={"thought": thought, "context": context or {}},
            tags={"event_type": "thinking", "agent": self.agent_name},
            **kwargs
        )
    
    def action(
        self,
        action: str,
        details: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log agent action."""
        self.info(
            f"Agent action: {action}",
            data={"action": action, "details": details or {}},
            tags={"event_type": "action", "agent": self.agent_name},
            **kwargs
        )
    
    def decision(
        self,
        decision: str,
        reasoning: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> None:
        """Log agent decision."""
        self.info(
            f"Agent decision: {decision}",
            data={
                "decision": decision,
                "reasoning": reasoning,
                "options": options or {}
            },
            tags={"event_type": "decision", "agent": self.agent_name},
            **kwargs
        )
    
    def observation(
        self,
        observation: str,
        source: Optional[str] = None,
        confidence: Optional[float] = None,
        **kwargs
    ) -> None:
        """Log agent observation."""
        self.info(
            f"Agent observation: {observation}",
            data={
                "observation": observation,
                "source": source,
                "confidence": confidence
            },
            tags={"event_type": "observation", "agent": self.agent_name},
            **kwargs
        )


def get_logger(
    name: str,
    client: Optional[TelemetryClient] = None,
    **kwargs
) -> TelemetryLogger:
    """
    Get a telemetry logger instance.
    
    Args:
        name: Logger name
        client: Telemetry client (uses default if None)
        **kwargs: Additional arguments for TelemetryLogger
    
    Returns:
        TelemetryLogger instance
    """
    return TelemetryLogger(name, client, **kwargs)


def get_agent_logger(
    agent_name: str,
    client: Optional[TelemetryClient] = None,
    role: Optional[str] = None,
    **kwargs
) -> AgentLogger:
    """
    Get an agent-specific logger.
    
    Args:
        agent_name: Name of the agent
        client: Telemetry client (uses default if None)
        role: Agent role (e.g., "decision-maker", "data-processor", "notification")
        **kwargs: Additional arguments for AgentLogger
    
    Returns:
        AgentLogger instance
    """
    return AgentLogger(agent_name, client, agent_role=role, **kwargs)


def setup_telemetry_logging(
    client: Optional[TelemetryClient] = None,
    level: Union[int, str] = logging.INFO,
    logger_names: Optional[list] = None
) -> None:
    """
    Set up telemetry logging for standard Python loggers.
    
    Args:
        client: Telemetry client to use
        level: Logging level
        logger_names: List of logger names to instrument (None = root logger)
    """
    handler = TelemetryLogHandler(client, level)
    
    if logger_names:
        for name in logger_names:
            logger = logging.getLogger(name)
            logger.addHandler(handler)
    else:
        # Add to root logger
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(level)
