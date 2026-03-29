import asyncio
import inspect
import sys
import types

from abidex.patches import pydantic_ai as pydantic_ai_patch


class DummySpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def set_attribute(self, *args, **kwargs):
        pass


class DummyTracer:
    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name):
        self.spans.append(name)
        return DummySpan()


def _install_dummy_module(monkeypatch):
    class Agent:
        def __init__(self):
            self.system_prompt = "system prompt"

        async def run(self, value):
            return f"async:{value}"

        def run_sync(self, value):
            return f"sync:{value}"

    module = types.ModuleType("pydantic_ai")
    module.Agent = Agent
    monkeypatch.setitem(sys.modules, "pydantic_ai", module)
    return Agent


def test_apply_patch_wraps_async_run(monkeypatch):
    agent_cls = _install_dummy_module(monkeypatch)
    dummy_tracer = DummyTracer()
    monkeypatch.setattr(pydantic_ai_patch, "get_tracer", lambda component=None: dummy_tracer)

    assert pydantic_ai_patch.apply_pydantic_ai_patch() is True

    assert inspect.iscoroutinefunction(agent_cls.run)
    assert not inspect.iscoroutinefunction(agent_cls.run_sync)

    result = asyncio.run(agent_cls().run("ok"))
    assert result == "async:ok"
    assert agent_cls().run_sync("ok") == "sync:ok"

    assert agent_cls.run._patched is True
    assert agent_cls.run_sync._patched is True
