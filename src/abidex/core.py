import os
import importlib
import sys
from typing import List
from abidex.config import get_service_name, ABIDEX_VERBOSE
from abidex import otel_setup
from abidex import log_setup
_FRAMEWORKS = ('crewai', 'langgraph', 'pydantic_ai', 'llama_index', 'n8n_sdk_python')
_FRAMEWORK_LABELS = {'crewai': 'CrewAI', 'langgraph': 'LangGraph', 'pydantic_ai': 'Pydantic AI', 'llama_index': 'LlamaIndex', 'n8n_sdk_python': 'n8n'}

def init(auto_patch: bool=True) -> List[str]:
    otel_setup.init_otel(service_name=get_service_name())
    log_setup.init_logs(service_name=get_service_name())
    # Set before any framework import so CrewAI doesn't override our TracerProvider
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
    if not auto_patch:
        return []
    if ABIDEX_VERBOSE:
        return _patch_all_detected_verbose()
    return patch_all_detected()

def _patch_all_detected_verbose() -> List[str]:
    from rich.console import Console
    console = Console()
    patched: List[str] = []
    for fw in _FRAMEWORKS:
        label = _FRAMEWORK_LABELS.get(fw, fw)
        try:
            if fw not in sys.modules:
                importlib.import_module(fw)
            mod = importlib.import_module(f'abidex.patches.{fw}')
            fn = getattr(mod, f'apply_{fw}_patch', None)
            if fn is not None and fn():
                patched.append(fw)
                console.print(f'[green]Patched {label} successfully[/green]')
            else:
                console.print(f'[dim]{label} not detected[/dim]')
        except Exception:
            console.print(f'[dim]{label} not detected[/dim]')
    if patched:
        console.print(f"[dim]Patched frameworks: {', '.join(patched)}[/dim]")
    if not os.environ.get('OTEL_EXPORTER_OTLP_ENDPOINT'):
        console.print('[dim]To see persistent traces, run SigNoz and set OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317[/dim]')
    return patched

def patch_all_detected() -> List[str]:
    patched: List[str] = []
    for fw in _FRAMEWORKS:
        try:
            if fw not in sys.modules:
                importlib.import_module(fw)
            mod = importlib.import_module(f'abidex.patches.{fw}')
            fn = getattr(mod, f'apply_{fw}_patch', None)
            if fn is not None and fn():
                patched.append(fw)
        except Exception:
            continue
    return patched