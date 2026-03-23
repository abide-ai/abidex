from typing import Any, Callable
from abidex.otel_setup import get_tracer
GEN_AI_FRAMEWORK = 'gen_ai.framework'
LANGGRAPH_NODE_KEY = 'langgraph_node'

def _span_name_and_attrs(method: str, config: Any) -> tuple[str, dict[str, str]]:
    name = f'Workflow: LangGraph {method.capitalize()}'
    attrs: dict[str, str] = {GEN_AI_FRAMEWORK: 'langgraph'}
    if config and isinstance(config, dict):
        metadata = config.get('configurable') or config.get('metadata') or {}
        if isinstance(metadata, dict):
            node = metadata.get(LANGGRAPH_NODE_KEY)
            if node:
                attrs[LANGGRAPH_NODE_KEY] = str(node)[:200]
            workflow = metadata.get('workflow_name') or metadata.get('name')
            if workflow:
                name = f'Workflow: {workflow}'
    return (name, attrs)

def _wrap_invoke(original: Callable[..., Any]) -> Callable[..., Any]:

    def invoke(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get('self')
        config = kwargs.get('config') or (args[1] if len(args) > 1 and isinstance(args[1], dict) else None)
        span_name, attrs = _span_name_and_attrs('invoke', config)
        tracer = get_tracer('langgraph')
        with tracer.start_as_current_span(span_name) as span:
            for k, v in attrs.items():
                span.set_attribute(k, v)
            return original(*args, **kwargs)
    return invoke

def _wrap_stream(original: Callable[..., Any]) -> Callable[..., Any]:

    def stream(*args: Any, **kwargs: Any) -> Any:
        self = args[0] if args else kwargs.get('self')
        config = kwargs.get('config') or (args[1] if len(args) > 1 and isinstance(args[1], dict) else None)
        span_name, attrs = _span_name_and_attrs('stream', config)
        tracer = get_tracer('langgraph')
        with tracer.start_as_current_span(span_name) as span:
            for k, v in attrs.items():
                span.set_attribute(k, v)
            return original(*args, **kwargs)
    return stream

def _patch_compiled_graph(graph_cls: type) -> None:
    if hasattr(graph_cls, 'invoke') and (not getattr(graph_cls.invoke, '_patched', False)):
        graph_cls.invoke = _wrap_invoke(graph_cls.invoke)
        graph_cls.invoke._patched = True
    if hasattr(graph_cls, 'stream') and (not getattr(graph_cls.stream, '_patched', False)):
        graph_cls.stream = _wrap_stream(graph_cls.stream)
        graph_cls.stream._patched = True

def apply_langgraph_patch() -> bool:
    try:
        from langgraph.graph.state import CompiledStateGraph
        _patch_compiled_graph(CompiledStateGraph)
        return True
    except ImportError:
        try:
            from langgraph.graph import CompiledGraph
            _patch_compiled_graph(CompiledGraph)
            return True
        except ImportError:
            return False