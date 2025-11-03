"""
Automatic instrumentation utilities for popular AI/ML frameworks.

This module provides functions to automatically instrument various AI/ML
frameworks and libraries with telemetry tracking.
"""

import time
import functools
from typing import Any, Optional, Dict, Callable, List
import inspect

from .client import TelemetryClient, get_client, Event, EventType
from .utils.token_counter import count_tokens


def naive_token_count(text: str) -> int:
    """Simple whitespace-based token counting fallback."""
    if text is None:
        return 0
    return max(1, len(text.split()))


def instrument_openai_client(
    openai_client,
    telemetry_client: Optional[TelemetryClient] = None,
    model_key: str = 'model'
):
    """
    Instrument OpenAI client to automatically track API calls.
    
    Args:
        openai_client: OpenAI client instance
        telemetry_client: Telemetry client to use
        model_key: Key to extract model name from kwargs
    
    Returns:
        Instrumented client
    
    Example:
        import openai
        from abide_agentkit.instrumentation import instrument_openai_client
        
        client = openai.OpenAI(api_key="your-key")
        client = instrument_openai_client(client)
        
        # Now all calls are automatically tracked
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "Hello"}]
        )
    """
    client = telemetry_client or get_client()
    
    # For OpenAI v1.0+ (new client structure)
    if hasattr(openai_client, 'chat') and hasattr(openai_client.chat, 'completions'):
        original_create = openai_client.chat.completions.create
        
        def tracked_create(*args, **kwargs):
            model = kwargs.get(model_key, 'unknown')
            messages = kwargs.get('messages', [])
            
            event = client.new_event(
                event_type=EventType.MODEL_CALL_START,
                model=model,
                backend='openai'
            )
            
            # Set input data
            event.data['input'] = {'messages': messages, **kwargs}
            if messages:
                token_count = count_tokens(messages=messages, model=model)
                event.input_token_count = token_count.input_tokens
                event.prompt_char_length = sum(len(str(msg.get('content', ''))) for msg in messages)
            
            try:
                response = original_create(*args, **kwargs)
                
                # Extract usage and response data
                if hasattr(response, 'usage') and response.usage:
                    usage = response.usage
                    event.input_token_count = usage.prompt_tokens
                    event.output_token_count = usage.completion_tokens
                    event.total_tokens = usage.total_tokens
                
                if hasattr(response, 'choices') and response.choices:
                    content = response.choices[0].message.content
                    event.response_char_length = len(content) if content else 0
                    event.data['output'] = {'content': content}
                
                event.finish()
                client.emit(event)
                return response
                
            except Exception as e:
                event.finish(error=e)
                client.emit(event)
                raise
        
        openai_client.chat.completions.create = tracked_create
    
    # For legacy OpenAI versions
    elif hasattr(openai_client, 'ChatCompletion'):
        original_create = openai_client.ChatCompletion.create
        
        def tracked_create(*args, **kwargs):
            model = kwargs.get(model_key, 'unknown')
            
            event = client.new_event(
                event_type=EventType.MODEL_CALL_START,
                model=model,
                backend='openai'
            )
            
            try:
                response = original_create(*args, **kwargs)
                
                # Extract usage from response
                if 'usage' in response:
                    usage = response['usage']
                    event.input_token_count = usage.get('prompt_tokens')
                    event.output_token_count = usage.get('completion_tokens')
                    event.total_tokens = usage.get('total_tokens')
                
                event.finish()
                client.emit(event)
                return response
                
            except Exception as e:
                event.finish(error=e)
                client.emit(event)
                raise
        
        openai_client.ChatCompletion.create = tracked_create
    
    return openai_client


def instrument_anthropic_client(
    anthropic_client,
    telemetry_client: Optional[TelemetryClient] = None
):
    """
    Instrument Anthropic client to automatically track API calls.
    
    Args:
        anthropic_client: Anthropic client instance
        telemetry_client: Telemetry client to use
    
    Returns:
        Instrumented client
    """
    client = telemetry_client or get_client()
    
    if hasattr(anthropic_client, 'messages') and hasattr(anthropic_client.messages, 'create'):
        original_create = anthropic_client.messages.create
        
        def tracked_create(*args, **kwargs):
            model = kwargs.get('model', 'claude')
            messages = kwargs.get('messages', [])
            
            event = client.new_event(
                event_type=EventType.MODEL_CALL_START,
                model=model,
                backend='anthropic'
            )
            
            # Set input data
            event.data['input'] = {'messages': messages, **kwargs}
            if messages:
                token_count = count_tokens(messages=messages, model=model)
                event.input_token_count = token_count.input_tokens
            
            try:
                response = original_create(*args, **kwargs)
                
                # Extract usage and response data
                if hasattr(response, 'usage'):
                    usage = response.usage
                    event.input_token_count = usage.input_tokens
                    event.output_token_count = usage.output_tokens
                    event.total_tokens = usage.input_tokens + usage.output_tokens
                
                if hasattr(response, 'content') and response.content:
                    # Handle content blocks
                    text_content = ""
                    for block in response.content:
                        if hasattr(block, 'text'):
                            text_content += block.text
                    
                    event.response_char_length = len(text_content)
                    event.data['output'] = {'text': text_content}
                
                event.finish()
                client.emit(event)
                return response
                
            except Exception as e:
                event.finish(error=e)
                client.emit(event)
                raise
        
        anthropic_client.messages.create = tracked_create
    
    return anthropic_client


def instrument_huggingface_model(
    model,
    tokenizer=None,
    telemetry_client: Optional[TelemetryClient] = None,
    backend: str = 'huggingface'
):
    """
    Instrument HuggingFace model to track generate() calls.
    
    Args:
        model: HuggingFace model instance
        tokenizer: Optional tokenizer for better token counting
        telemetry_client: Telemetry client to use
        backend: Backend identifier
    
    Returns:
        Instrumented model
    """
    client = telemetry_client or get_client()
    
    if hasattr(model, 'generate'):
        original_generate = model.generate
        
        def tracked_generate(*args, **kwargs):
            model_name = getattr(model, 'name_or_path', 'unknown')
            
            event = client.new_event(
                event_type=EventType.MODEL_CALL_START,
                model=model_name,
                backend=backend
            )
            
            # Try to get input information
            input_ids = kwargs.get('input_ids')
            if input_ids is None and args:
                input_ids = args[0]
            
            if input_ids is not None and hasattr(input_ids, 'shape'):
                event.batch_size = input_ids.shape[0] if len(input_ids.shape) > 1 else 1
                event.input_token_count = input_ids.shape[-1] * event.batch_size
            
            try:
                output = original_generate(*args, **kwargs)
                
                # Try to compute output token count
                if hasattr(output, 'shape'):
                    if len(output.shape) > 1:
                        event.output_token_count = output.shape[-1] * output.shape[0]
                    else:
                        event.output_token_count = output.shape[-1]
                
                event.finish()
                client.emit(event)
                return output
                
            except Exception as e:
                event.finish(error=e)
                client.emit(event)
                raise
        
        model.generate = tracked_generate
    
    return model


class LangChainCallbackHandler:
    """
    LangChain callback handler for telemetry tracking.
    
    Example:
        from langchain.llms import OpenAI
        from abide_agentkit.instrumentation import LangChainCallbackHandler
        
        handler = LangChainCallbackHandler()
        llm = OpenAI(callbacks=[handler])
    """
    
    def __init__(self, telemetry_client: Optional[TelemetryClient] = None):
        self.client = telemetry_client or get_client()
        self._current_events: Dict[str, Event] = {}
    
    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs) -> None:
        """Handle LLM start event."""
        model_name = serialized.get('name', 'unknown')
        run_id = kwargs.get('run_id', str(time.time()))
        
        event = self.client.new_event(
            event_type=EventType.MODEL_CALL_START,
            model=model_name,
            backend='langchain',
            batch_size=len(prompts)
        )
        
        # Store prompt info (truncated)
        event.data['input'] = {
            'prompts': [p[:500] + '...' if len(p) > 500 else p for p in prompts]
        }
        
        # Estimate token count
        total_chars = sum(len(p) for p in prompts)
        event.prompt_char_length = total_chars
        event.input_token_count = naive_token_count(' '.join(prompts))
        
        self._current_events[run_id] = event
    
    def on_llm_end(self, response, run_id: str = None, **kwargs) -> None:
        """Handle LLM end event."""
        if run_id in self._current_events:
            event = self._current_events.pop(run_id)
            
            # Extract response text
            response_text = str(response)
            event.response_char_length = len(response_text)
            event.output_token_count = naive_token_count(response_text)
            event.data['output'] = {'text': response_text[:1000]}
            
            event.finish()
            self.client.emit(event)
    
    def on_llm_error(self, error: Exception, run_id: str = None, **kwargs) -> None:
        """Handle LLM error event."""
        if run_id in self._current_events:
            event = self._current_events.pop(run_id)
            event.finish(error=error)
            self.client.emit(event)


def create_instrumented_function(
    func: Callable,
    telemetry_client: Optional[TelemetryClient] = None,
    model: Optional[str] = None,
    backend: Optional[str] = None,
    extract_tokens: Optional[Callable] = None,
    extract_model: Optional[Callable] = None
) -> Callable:
    """
    Create an instrumented version of any function.
    
    Args:
        func: Function to instrument
        telemetry_client: Telemetry client to use
        model: Model name (or function to extract it)
        backend: Backend name
        extract_tokens: Function to extract token counts from result
        extract_model: Function to extract model name from args/kwargs
    
    Returns:
        Instrumented function
    """
    client = telemetry_client or get_client()
    
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Determine model name
        model_name = model
        if extract_model:
            try:
                model_name = extract_model(*args, **kwargs)
            except Exception:
                pass
        
        event = client.new_event(
            event_type=EventType.MODEL_CALL_START,
            model=model_name,
            backend=backend or func.__module__
        )
        
        # Store function signature info
        try:
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            event.data['function_args'] = {
                k: str(v)[:100] for k, v in bound_args.arguments.items()
            }
        except Exception:
            pass
        
        try:
            result = func(*args, **kwargs)
            
            # Extract token information if extractor provided
            if extract_tokens:
                try:
                    tokens = extract_tokens(result, *args, **kwargs)
                    if isinstance(tokens, dict):
                        event.input_token_count = tokens.get('input_tokens')
                        event.output_token_count = tokens.get('output_tokens')
                        event.total_tokens = tokens.get('total_tokens')
                    elif isinstance(tokens, (int, float)):
                        event.output_token_count = int(tokens)
                except Exception:
                    pass
            
            # Try to get response length
            if hasattr(result, '__len__'):
                try:
                    event.response_char_length = len(str(result))
                except Exception:
                    pass
            
            event.finish()
            client.emit(event)
            return result
            
        except Exception as e:
            event.finish(error=e)
            client.emit(event)
            raise
    
    return wrapper


def auto_instrument_module(
    module,
    telemetry_client: Optional[TelemetryClient] = None,
    function_patterns: Optional[List[str]] = None,
    backend: Optional[str] = None
):
    """
    Automatically instrument functions in a module based on naming patterns.
    
    Args:
        module: Module to instrument
        telemetry_client: Telemetry client to use
        function_patterns: List of function name patterns to match
        backend: Backend identifier
    
    Returns:
        Instrumented module
    """
    import re
    
    client = telemetry_client or get_client()
    patterns = function_patterns or ['generate', 'predict', 'infer', 'complete', 'chat']
    backend_name = backend or getattr(module, '__name__', 'unknown')
    
    for attr_name in dir(module):
        if any(pattern in attr_name.lower() for pattern in patterns):
            attr = getattr(module, attr_name)
            if callable(attr) and not attr_name.startswith('_'):
                instrumented = create_instrumented_function(
                    attr,
                    telemetry_client=client,
                    backend=backend_name
                )
                setattr(module, attr_name, instrumented)
    
    return module
