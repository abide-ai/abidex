"""
Adapter for integrating with Anthropic's Claude API.
"""

import time
from typing import Any, Dict, List, Optional, Union
from contextlib import contextmanager

from ..client import TelemetryClient, get_client
from ..spans import ModelCall
from ..utils.token_counter import count_tokens


class ClaudeAdapter:
    """
    Adapter for tracking Claude API calls and responses.
    """
    
    def __init__(self, client: Optional[TelemetryClient] = None):
        self.client = client or get_client()
        self.model_name = "claude"
        self.provider = "anthropic"
    
    @contextmanager
    def track_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ):
        """
        Context manager for tracking Claude completion calls.
        
        Args:
            model: Claude model name (e.g., "claude-3-opus-20240229")
            messages: List of messages for the conversation
            run_id: ID of the parent agent run
            parent_id: ID of the parent span
            **kwargs: Additional parameters passed to the API
        
        Yields:
            ModelCallContext for tracking the call
        
        Example:
            adapter = ClaudeAdapter()
            with adapter.track_completion("claude-3-opus-20240229", messages) as call:
                response = anthropic_client.messages.create(
                    model="claude-3-opus-20240229",
                    messages=messages,
                    max_tokens=1000
                )
                call.set_response(response)
        """
        with ModelCall(
            model=model,
            provider=self.provider,
            client=self.client,
            run_id=run_id,
            parent_id=parent_id,
            data={"api_call": "messages.create"}
        ) as call:
            # Set input data
            input_data = {
                "messages": messages,
                "model": model,
                **kwargs
            }
            call.set_input(messages, **kwargs)
            
            # Estimate input tokens
            token_count = count_tokens(messages=messages, model=model)
            call.add_data("estimated_input_tokens", token_count.input_tokens)
            
            yield ClaudeCallContext(call, model)
    
    def track_streaming_completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ):
        """
        Track a streaming Claude completion call.
        
        Args:
            model: Claude model name
            messages: List of messages
            run_id: ID of the parent agent run
            parent_id: ID of the parent span
            **kwargs: Additional API parameters
        
        Returns:
            ClaudeStreamingContext for tracking the streaming call
        """
        return ClaudeStreamingContext(
            self.client, model, messages, run_id, parent_id, **kwargs
        )


class ClaudeCallContext:
    """Context for a Claude API call."""
    
    def __init__(self, model_call_context, model: str):
        self.call = model_call_context
        self.model = model
        self._response_set = False
    
    def set_response(self, response: Any) -> None:
        """
        Set the response from Claude API.
        
        Args:
            response: Response object from Claude API
        """
        if self._response_set:
            return
        
        self._response_set = True
        
        # Extract response data
        response_data = self._extract_response_data(response)
        self.call.set_output(response_data)
        
        # Extract and set usage information
        usage = self._extract_usage(response)
        if usage:
            self.call.add_data("token_usage", usage)
    
    def _extract_response_data(self, response: Any) -> Dict[str, Any]:
        """Extract relevant data from Claude response."""
        data = {}
        
        if hasattr(response, 'content'):
            # Handle content blocks
            content = response.content
            if isinstance(content, list):
                data['content'] = [
                    {
                        'type': block.type,
                        'text': getattr(block, 'text', '')
                    } for block in content
                ]
                # Get full text
                data['text'] = ''.join(
                    getattr(block, 'text', '') for block in content
                    if hasattr(block, 'text')
                )
            else:
                data['content'] = content
                data['text'] = str(content)
        
        if hasattr(response, 'role'):
            data['role'] = response.role
        
        if hasattr(response, 'model'):
            data['model'] = response.model
        
        if hasattr(response, 'stop_reason'):
            data['stop_reason'] = response.stop_reason
        
        if hasattr(response, 'stop_sequence'):
            data['stop_sequence'] = response.stop_sequence
        
        return data
    
    def _extract_usage(self, response: Any) -> Optional[Dict[str, Any]]:
        """Extract token usage from Claude response."""
        if hasattr(response, 'usage'):
            usage = response.usage
            return {
                'input_tokens': getattr(usage, 'input_tokens', 0),
                'output_tokens': getattr(usage, 'output_tokens', 0),
                'total_tokens': getattr(usage, 'input_tokens', 0) + getattr(usage, 'output_tokens', 0)
            }
        return None


class ClaudeStreamingContext:
    """Context for tracking Claude streaming completions."""
    
    def __init__(
        self,
        client: TelemetryClient,
        model: str,
        messages: List[Dict[str, Any]],
        run_id: Optional[str] = None,
        parent_id: Optional[str] = None,
        **kwargs
    ):
        self.client = client
        self.model = model
        self.messages = messages
        self.run_id = run_id
        self.parent_id = parent_id
        self.kwargs = kwargs
        
        self._call_context = None
        self._accumulated_content = ""
        self._start_time = None
        self._usage_data = None
    
    def start(self) -> None:
        """Start tracking the streaming call."""
        self._start_time = time.time()
        
        # Create model call context
        self._call_context = ModelCall(
            model=self.model,
            provider="anthropic",
            client=self.client,
            run_id=self.run_id,
            parent_id=self.parent_id,
            data={"api_call": "messages.create", "streaming": True}
        ).__enter__()
        
        # Set input
        self._call_context.set_input(self.messages, **self.kwargs)
        
        # Estimate input tokens
        token_count = count_tokens(messages=self.messages, model=self.model)
        self._call_context.add_data("estimated_input_tokens", token_count.input_tokens)
    
    def on_content_delta(self, delta: str) -> None:
        """Handle content delta from streaming response."""
        self._accumulated_content += delta
    
    def on_usage(self, usage: Dict[str, Any]) -> None:
        """Handle usage information from streaming response."""
        self._usage_data = usage
    
    def finish(self, stop_reason: Optional[str] = None) -> None:
        """Finish tracking the streaming call."""
        if not self._call_context:
            return
        
        # Set output data
        response_data = {
            'text': self._accumulated_content,
            'content': [{'type': 'text', 'text': self._accumulated_content}],
            'role': 'assistant',
            'model': self.model
        }
        
        if stop_reason:
            response_data['stop_reason'] = stop_reason
        
        self._call_context.set_output(response_data)
        
        # Add usage data if available
        if self._usage_data:
            self._call_context.add_data("token_usage", self._usage_data)
        
        # Add streaming metrics
        if self._start_time:
            duration = time.time() - self._start_time
            chars_per_second = len(self._accumulated_content) / duration if duration > 0 else 0
            self._call_context.add_data("streaming_metrics", {
                "chars_per_second": chars_per_second,
                "total_chars": len(self._accumulated_content),
                "duration": duration
            })
        
        # End the context
        self._call_context.__exit__(None, None, None)
        self._call_context = None
    
    def error(self, error: Exception) -> None:
        """Handle error in streaming call."""
        if self._call_context:
            self._call_context.__exit__(type(error), error, error.__traceback__)
            self._call_context = None


def patch_anthropic_client(anthropic_client, adapter: Optional[ClaudeAdapter] = None):
    """
    Monkey patch an Anthropic client to automatically track calls.
    
    Args:
        anthropic_client: The Anthropic client instance to patch
        adapter: ClaudeAdapter instance (creates new one if None)
    
    Returns:
        The patched client
    
    Example:
        import anthropic
        from abide_agentkit.adapters import patch_anthropic_client
        
        client = anthropic.Anthropic(api_key="your-key")
        client = patch_anthropic_client(client)
        
        # Now all calls are automatically tracked
        response = client.messages.create(
            model="claude-3-opus-20240229",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """
    if adapter is None:
        adapter = ClaudeAdapter()
    
    # Store original methods
    original_create = anthropic_client.messages.create
    
    def tracked_create(*args, **kwargs):
        model = kwargs.get('model', 'claude')
        messages = kwargs.get('messages', [])
        
        with adapter.track_completion(model, messages, **kwargs) as call:
            response = original_create(*args, **kwargs)
            call.set_response(response)
            return response
    
    # Replace methods
    anthropic_client.messages.create = tracked_create
    
    return anthropic_client
