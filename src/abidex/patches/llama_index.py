from __future__ import annotations
import asyncio
from typing import Any, Callable
from abidex.otel_setup import get_tracer
GEN_AI_FRAMEWORK = 'gen_ai.framework'
GEN_AI_WORKFLOW_NAME = 'gen_ai.workflow.name'
MAX_STR = 200

def _workflow_name(wf: Any) -> str:
    if hasattr(wf, 'name') and wf.name:
        return str(wf.name).strip()
    return getattr(wf, '__class__', type(wf)).__name__ or 'Workflow'

def _wrap_run(original: Callable[..., Any]) -> Callable[..., Any]:

    async def run(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get('self')
        name = _workflow_name(self)
        span_name = f'Workflow: {name}'
        tracer = get_tracer('llama_index')
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_FRAMEWORK, 'llamaindex')
            span.set_attribute(GEN_AI_WORKFLOW_NAME, name[:MAX_STR])
            return await original(*args, **kwargs)
    return run

def apply_llama_index_patch() -> bool:
    try:
        from llama_index.core.workflow import Workflow
    except ImportError:
        try:
            from llama_index.workflow import Workflow
        except ImportError:
            return False
    if not hasattr(Workflow, 'run'):
        return False
    if getattr(Workflow.run, '_patched', False):
        return True
    Workflow.run = _wrap_run(Workflow.run)
    Workflow.run._patched = True
    return True