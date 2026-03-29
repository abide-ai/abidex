from typing import Any, Callable
from abidex.otel_setup import get_tracer
GEN_AI_FRAMEWORK = 'gen_ai.framework'
GEN_AI_AGENT_NAME = 'gen_ai.agent.name'
GEN_AI_INSTRUCTIONS = 'gen_ai.instructions'
MAX_STR = 200

def _trunc(s: Any, max_len: int=MAX_STR) -> str:
    if s is None:
        return ''
    t = str(s).strip()
    return t[:max_len] + '...' if len(t) > max_len else t

def _agent_name(agent: Any) -> str:
    if hasattr(agent, 'name') and agent.name:
        return str(agent.name).strip()
    return getattr(agent, '__class__', type(agent)).__name__ or 'Unnamed'

def _wrap_run(original: Callable[..., Any]) -> Callable[..., Any]:

    def run(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get('self')
        name = _agent_name(self)
        span_name = f'Agent: {name}'
        tracer = get_tracer('pydantic_ai')
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_FRAMEWORK, 'pydantic-ai')
            span.set_attribute(GEN_AI_AGENT_NAME, name)
            instructions = getattr(self, 'system_prompt', None) or getattr(self, 'instructions', None)
            if instructions:
                span.set_attribute(GEN_AI_INSTRUCTIONS, _trunc(instructions))
            return original(*args, **kwargs)
    return run

def _wrap_run_sync(original: Callable[..., Any]) -> Callable[..., Any]:

    def run_sync(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get('self')
        name = _agent_name(self)
        span_name = f'Agent: {name}'
        tracer = get_tracer('pydantic_ai')
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_FRAMEWORK, 'pydantic-ai')
            span.set_attribute(GEN_AI_AGENT_NAME, name)
            instructions = getattr(self, 'system_prompt', None) or getattr(self, 'instructions', None)
            if instructions:
                span.set_attribute(GEN_AI_INSTRUCTIONS, _trunc(instructions))
            return original(*args, **kwargs)
    return run_sync

def apply_pydantic_ai_patch() -> bool:
    try:
        from pydantic_ai import Agent
    except ImportError:
        return False
    if hasattr(Agent, 'run') and (not getattr(Agent.run, '_patched', False)):
        Agent.run = _wrap_run(Agent.run)
        Agent.run._patched = True
    if hasattr(Agent, 'run_sync') and (not getattr(Agent.run_sync, '_patched', False)):
        Agent.run_sync = _wrap_run_sync(Agent.run_sync)
        Agent.run_sync._patched = True
    return True