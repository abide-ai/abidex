"""
Context managers for tracking agent runs, model calls, and tool executions.
"""

import time
from contextlib import contextmanager
from typing import Any, Dict, Optional, Generator, Union
from uuid import uuid4

from .client import TelemetryClient, Event, EventType, get_client


class SpanContext:
    """Base context for tracking spans."""
    
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
    
    def start(self) -> None:
        """Start the span."""
        self.start_time = time.time()
        
        # Emit start event using new structured schema
        start_event = self.client.new_event(
            event_type=self._get_start_event_type(),
            conversation_id=self.run_id,
            tags=self.tags
        )
        
        start_event.run_id = self.run_id
        start_event.parent_id = self.parent_id
        start_event.span_id = self.span_id
        
        # Set action info for the span
        start_event.set_action_info(
            action_type=self.span_type,
            name=self.name,
            input_data=self.data
        )
        
        # If this is a model call, also set model call info
        if self.span_type == "model_call" and hasattr(self, 'model') and hasattr(self, 'provider'):
            start_event.set_model_call_info(
                backend=self.provider,
                model=self.model
            )
        
        self.client.emit(start_event)
    
    def end(self, error: Optional[Exception] = None) -> None:
        """End the span."""
        self.end_time = time.time()
        self.error = error
        
        # Calculate duration
        duration = self.end_time - self.start_time if self.start_time else 0
        
        # Emit end event using new structured schema
        end_event = self.client.new_event(
            event_type=self._get_end_event_type(),
            conversation_id=self.run_id,
            tags=self.tags
        )
        
        end_event.run_id = self.run_id
        end_event.parent_id = self.parent_id
        end_event.span_id = self.span_id
        end_event.level = "error" if error else "info"
        
        # Set timing info
        end_event.telemetry.timestamp_start = self.start_time
        end_event.telemetry.timestamp_end = self.end_time
        end_event.telemetry.latency_ms = duration * 1000.0
        
        # Set action info with result
        end_event.set_action_info(
            action_type=self.span_type,
            name=self.name,
            output_data=self.data if not error else None
        )
        
        # Set success status
        if end_event.action:
            end_event.action.success = error is None
            if error:
                end_event.action.output = f"Error: {str(error)}"
        
        # If this is a model call, also set model call info in end event
        if self.span_type == "model_call" and hasattr(self, 'model') and hasattr(self, 'provider'):
            end_event.set_model_call_info(
                backend=self.provider,
                model=self.model
            )
        
        if error:
            end_event.success = False
            end_event.error = str(error)
        
        self.client.emit(end_event)
        
        # Also emit error event if there was an error
        if error:
            self.client.error(
                error=error,
                context={"span_id": self.span_id, "span_type": self.span_type},
                run_id=self.run_id,
                span_id=self.span_id
            )
    
    def _get_start_event_type(self) -> EventType:
        """Get the start event type for this span."""
        return EventType.LOG  # Override in subclasses
    
    def _get_end_event_type(self) -> EventType:
        """Get the end event type for this span."""
        return EventType.LOG  # Override in subclasses
    
    def add_data(self, key: str, value: Any) -> None:
        """Add data to the span."""
        self.data[key] = value
    
    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to the span."""
        self.tags[key] = value


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
                if isinstance(msg, dict) and "content" in msg:
                    prompt_text += f"{msg.get('role', '')}: {msg['content']}\n"
            
            # Update model call info with prompt
            if hasattr(self, '_event_context'):
                event = self._event_context
                if event.model_call:
                    event.model_call.prompt_preview = prompt_text[:500] + "..." if len(prompt_text) > 500 else prompt_text
        
        self.add_data("input", {
            "messages": messages,
            "parameters": kwargs
        })
    
    def set_output(self, response: Any, usage: Optional[Dict[str, Any]] = None) -> None:
        """Set the output for the model call."""
        # Extract completion text from response
        completion_text = str(response)
        
        # Update model call info with completion and tokens
        if hasattr(self, '_event_context'):
            event = self._event_context
            if event.model_call:
                event.model_call.completion_preview = completion_text[:500] + "..." if len(completion_text) > 500 else completion_text
                
                # Set token counts from usage
                if usage:
                    event.model_call.input_token_count = usage.get("input_tokens") or usage.get("prompt_tokens")
                    event.model_call.output_token_count = usage.get("output_tokens") or usage.get("completion_tokens")
        
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
