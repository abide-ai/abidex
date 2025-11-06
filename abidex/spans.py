"""
Context managers for tracking agent runs, model calls, and tool executions.
Uses OpenTelemetry spans as the backend.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Generator, Union
from uuid import uuid4

from opentelemetry import trace
from opentelemetry.trace import Span, Status, StatusCode

from .client import TelemetryClient, Event, EventType, get_client


class SpanContext:
    """Base context for tracking spans using OpenTelemetry."""
    
    def __init__(
        self,
        span_type: str,
        name: str,
        client: Optional[TelemetryClient] = None,
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        self.span_id = str(uuid4())
        self.span_type = span_type
        self.name = name
        self.client = client or get_client()
        self.run_id = run_id
        self.parent_id = parent_id
        self.tags = tags or {}
        self.data = data or {}
        self.start_time = None
        self.end_time = None
        self.error = None
        self.otel_span: Optional[Span] = None
    
    def start(self) -> None:
        """Start the OpenTelemetry span."""
        self.start_time = time.time()
        
        # Create OpenTelemetry span
        attributes = {
            "span.type": self.span_type,
            "span.name": self.name,
            **self.tags,
            **self.data
        }
        if self.run_id:
            attributes["run_id"] = self.run_id
        if self.parent_id:
            attributes["parent_id"] = self.parent_id
        
        # If this is a model call, add model info
        if self.span_type == "model_call" and hasattr(self, 'model') and hasattr(self, 'provider'):
            attributes["model"] = self.model
            attributes["backend"] = self.provider
        
        self.otel_span = self.client.start_span(
            name=self.name,
            attributes=attributes
        )
    
    def end(self, error: Optional[Exception] = None) -> None:
        """End the OpenTelemetry span."""
        self.end_time = time.time()
        self.error = error
        
        if self.otel_span:
            # Calculate duration
            duration = self.end_time - self.start_time if self.start_time else 0
            self.otel_span.set_attribute("latency_ms", duration * 1000.0)
            
            # Update span with any additional data
            for key, value in self.data.items():
                if isinstance(value, (str, int, float, bool)):
                    self.otel_span.set_attribute(f"data.{key}", value)
            
            if error:
                self.otel_span.set_status(Status(StatusCode.ERROR, str(error)))
                self.otel_span.record_exception(error)
                # Also record error via client
                self.client.error(
                    error=error,
                    context={"span_id": self.span_id, "span_type": self.span_type},
                    run_id=self.run_id,
                    span_id=self.span_id
                )
            
            self.otel_span.end()
    
    def _get_start_event_type(self) -> EventType:
        """Get the start event type for this span."""
        return EventType.LOG  # Override in subclasses
    
    def _get_end_event_type(self) -> EventType:
        """Get the end event type for this span."""
        return EventType.LOG  # Override in subclasses
    
    def add_data(self, key: str, value: Any) -> None:
        """Add data to the span."""
        self.data[key] = value
        # Also update OpenTelemetry span if it exists
        if self.otel_span and isinstance(value, (str, int, float, bool)):
            self.otel_span.set_attribute(f"data.{key}", value)
    
    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the span."""
        self.tags[key] = value
        # Also update OpenTelemetry span if it exists
        if self.otel_span:
            self.otel_span.set_attribute(key, value)


class AgentRunContext(SpanContext):
    """Context for tracking agent runs."""
    
    def __init__(
        self,
        name: str,
        client: Optional[TelemetryClient] = None,
        tags: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        run_id = str(uuid4())
        super().__init__(
            span_type="agent_run",
            name=name,
            client=client,
            run_id=run_id,
            tags=tags,
            data=data
        )
    
    def _get_start_event_type(self) -> EventType:
        return EventType.AGENT_RUN_START
    
    def _get_end_event_type(self) -> EventType:
        return EventType.AGENT_RUN_END


class ModelCallContext(SpanContext):
    """Context for tracking model API calls."""
    
    def __init__(
        self,
        model: str,
        provider: str = "unknown",
        client: Optional[TelemetryClient] = None,
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            span_type="model_call",
            name=f"{provider}/{model}",
            client=client,
            run_id=run_id,
            parent_id=parent_id,
            tags=tags,
            data={
                "model": model,
                "provider": provider,
                **(data or {})
            }
        )
        
        # Store model info for use in set_input/set_output
        self.model = model
        self.provider = provider
    
    def _get_start_event_type(self) -> EventType:
        return EventType.MODEL_CALL_START
    
    def _get_end_event_type(self) -> EventType:
        return EventType.MODEL_CALL_END
    
    def set_input(self, messages: Any, **kwargs) -> None:
        """Set the input for the model call."""
        # Create prompt preview from messages
        if isinstance(messages, list) and messages:
            prompt_text = ""
            for msg in messages:
                if isinstance(msg, str):
                    prompt_text += msg + "\n"
                elif isinstance(msg, dict) and "content" in msg:
                    prompt_text += f"{msg.get('role', '')}: {msg['content']}\n"
            
            # Update OpenTelemetry span with prompt preview
            if self.otel_span:
                preview = prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text
                self.otel_span.set_attribute("prompt_preview", preview)
        
        self.add_data("input", {
            "messages": messages,
            "parameters": kwargs
        })
    
    def set_output(self, response: Any, usage: Optional[Dict[str, Any]] = None) -> None:
        """Set the output for the model call."""
        # Extract completion text from response
        completion_text = str(response)
        
        # Update OpenTelemetry span with completion and tokens
        if self.otel_span:
            preview = completion_text[:500] + "..." if len(completion_text) > 500 else completion_text
            self.otel_span.set_attribute("completion_preview", preview)
            
            # Set token counts from usage
            if usage:
                input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
                output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
                if input_tokens:
                    self.otel_span.set_attribute("input_token_count", input_tokens)
                if output_tokens:
                    self.otel_span.set_attribute("output_token_count", output_tokens)
                
                # Record tokens metric
                if input_tokens:
                    self.client.model_tokens_counter.add(input_tokens, attributes={"type": "input"})
                if output_tokens:
                    self.client.model_tokens_counter.add(output_tokens, attributes={"type": "output"})
        
        output_data = {"response": response}
        if usage:
            output_data["usage"] = usage
        self.add_data("output", output_data)


class ToolCallContext(SpanContext):
    """Context for tracking tool executions."""
    
    def __init__(
        self,
        tool_name: str,
        client: Optional[TelemetryClient] = None,
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        tags: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            span_type="tool_call",
            name=tool_name,
            client=client,
            run_id=run_id,
            parent_id=parent_id,
            tags=tags,
            data={
                "tool_name": tool_name,
                **(data or {})
            }
        )
    
    def _get_start_event_type(self) -> EventType:
        return EventType.TOOL_CALL_START
    
    def _get_end_event_type(self) -> EventType:
        return EventType.TOOL_CALL_END
    
    def set_input(self, **kwargs) -> None:
        """Set the input parameters for the tool call."""
        self.add_data("input", kwargs)
    
    def set_output(self, result: Any) -> None:
        """Set the output result for the tool call."""
        self.add_data("output", result)


@contextmanager
def AgentRun(
    name: str,
    client: Optional[TelemetryClient] = None,
    tags: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Generator[AgentRunContext, None, None]:
    """
    Context manager for tracking an agent run.
    
    Args:
        name: Name of the agent run
        client: Telemetry client to use
        tags: Additional tags for the span
        data: Additional data for the span
    
    Yields:
        AgentRunContext: The agent run context
    
    Example:
        with AgentRun("process_user_query") as run:
            run.add_data("user_id", "123")
            # ... agent logic ...
    """
    context = AgentRunContext(name, client, tags, data)
    context.start()
    
    try:
        yield context
    except Exception as e:
        context.end(error=e)
        raise
    else:
        context.end()


@contextmanager
def ModelCall(
    model: str,
    provider: str = "unknown",
    client: Optional[TelemetryClient] = None,
    run_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Generator[ModelCallContext, None, None]:
    """
    Context manager for tracking a model API call.
    
    Args:
        model: Name of the model
        provider: Model provider (e.g., "openai", "anthropic")
        client: Telemetry client to use
        run_id: ID of the parent agent run
        parent_id: ID of the parent span
        tags: Additional tags for the span
        data: Additional data for the span
    
    Yields:
        ModelCallContext: The model call context
    
    Example:
        with ModelCall("gpt-4", "openai", run_id=run.run_id) as call:
            call.set_input(messages=[{"role": "user", "content": "Hello"}])
            response = openai_client.chat.completions.create(...)
            call.set_output(response, usage=response.usage)
    """
    context = ModelCallContext(model, provider, client, run_id, parent_id, tags, data)
    context.start()
    
    try:
        yield context
    except Exception as e:
        context.end(error=e)
        raise
    else:
        context.end()


@contextmanager
def ToolCall(
    tool_name: str,
    client: Optional[TelemetryClient] = None,
    run_id: Optional[str] = None,
    parent_id: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None
) -> Generator[ToolCallContext, None, None]:
    """
    Context manager for tracking a tool execution.
    
    Args:
        tool_name: Name of the tool being called
        client: Telemetry client to use
        run_id: ID of the parent agent run
        parent_id: ID of the parent span
        tags: Additional tags for the span
        data: Additional data for the span
    
    Yields:
        ToolCallContext: The tool call context
    
    Example:
        with ToolCall("web_search", run_id=run.run_id) as tool:
            tool.set_input(query="Python tutorial")
            result = search_web("Python tutorial")
            tool.set_output(result)
    """
    context = ToolCallContext(tool_name, client, run_id, parent_id, tags, data)
    context.start()
    
    try:
        yield context
    except Exception as e:
        context.end(error=e)
        raise
    else:
        context.end()
