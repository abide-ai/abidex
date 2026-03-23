from __future__ import annotations
import asyncio
from typing import Any, Callable
from abidex.otel_setup import get_tracer
GEN_AI_FRAMEWORK = 'gen_ai.framework'
GEN_AI_WORKFLOW_NAME = 'gen_ai.workflow.name'
MAX_STR = 200

def _wrap_async_execution(original: Callable[..., Any], method_name: str) -> Callable[..., Any]:

    async def wrapped(*args: Any, **kwargs: Any) -> Any:
        workflow_id = kwargs.get('workflow_id') or (args[1] if len(args) > 1 else None)
        name = str(workflow_id)[:MAX_STR] if workflow_id else 'n8n_workflow'
        span_name = f'Workflow: n8n {method_name}'
        tracer = get_tracer('n8n_sdk_python')
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_FRAMEWORK, 'n8n')
            if workflow_id is not None:
                span.set_attribute(GEN_AI_WORKFLOW_NAME, str(workflow_id))
            return await original(*args, **kwargs)
    return wrapped

def _wrap_sync_execution(original: Callable[..., Any], method_name: str) -> Callable[..., Any]:

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        workflow_id = kwargs.get('workflow_id') or (args[1] if len(args) > 1 else None)
        name = str(workflow_id)[:MAX_STR] if workflow_id else 'n8n_workflow'
        span_name = f'Workflow: n8n {method_name}'
        tracer = get_tracer('n8n_sdk_python')
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute(GEN_AI_FRAMEWORK, 'n8n')
            if workflow_id is not None:
                span.set_attribute(GEN_AI_WORKFLOW_NAME, str(workflow_id))
            return original(*args, **kwargs)
    return wrapped

def _patch_client(client_cls: Any) -> bool:
    patched = False
    for method_name in ('execute_workflow', 'run_workflow', 'run', 'trigger_workflow', 'trigger_execution'):
        method = getattr(client_cls, method_name, None)
        if method is None or getattr(method, '_patched', False):
            continue
        try:
            if asyncio.iscoroutinefunction(method):
                setattr(client_cls, method_name, _wrap_async_execution(method, method_name))
            else:
                setattr(client_cls, method_name, _wrap_sync_execution(method, method_name))
            getattr(client_cls, method_name)._patched = True
            patched = True
        except Exception:
            continue
    return patched

def apply_n8n_sdk_python_patch() -> bool:
    try:
        from n8n_sdk_python import N8nClient
    except ImportError:
        return False
    return _patch_client(N8nClient)