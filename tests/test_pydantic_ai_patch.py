"""Unit tests for pydantic_ai patch wrappers (sync vs async originals)."""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import MagicMock

import pytest

from abidex.patches import pydantic_ai as pa


@pytest.fixture
def mock_tracer(monkeypatch: pytest.MonkeyPatch) -> tuple[MagicMock, MagicMock]:
    span = MagicMock()
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=span)
    cm.__exit__ = MagicMock(return_value=None)
    tracer = MagicMock()
    tracer.start_as_current_span = MagicMock(return_value=cm)
    monkeypatch.setattr(pa, "get_tracer", lambda _: tracer)
    return tracer, span


class _FakeAgent:
    name = "test-agent"
    system_prompt = "be helpful"


async def _async_run(self: object, x: int) -> int:
    return x + 1


def _sync_run(self: object, x: int) -> int:
    return x + 2


async def _async_run_sync(self: object, x: int) -> int:
    return x + 3


def _sync_run_sync(self: object, x: int) -> int:
    return x + 4


def test_wrap_run_async_uses_await(mock_tracer: tuple[MagicMock, MagicMock]) -> None:
    tracer, span = mock_tracer
    wrapped = pa._wrap_run(_async_run)
    assert inspect.iscoroutinefunction(wrapped)
    agent = _FakeAgent()
    assert asyncio.run(wrapped(agent, 40)) == 41
    tracer.start_as_current_span.assert_called_once()
    span.set_attribute.assert_called()


def test_wrap_run_sync_path(mock_tracer: tuple[MagicMock, MagicMock]) -> None:
    tracer, span = mock_tracer
    wrapped = pa._wrap_run(_sync_run)
    assert not inspect.iscoroutinefunction(wrapped)
    agent = _FakeAgent()
    assert wrapped(agent, 1) == 3
    tracer.start_as_current_span.assert_called_once()
    span.set_attribute.assert_called()


def test_wrap_run_sync_async_original(mock_tracer: tuple[MagicMock, MagicMock]) -> None:
    tracer, span = mock_tracer
    wrapped = pa._wrap_run_sync(_async_run_sync)
    assert inspect.iscoroutinefunction(wrapped)
    agent = _FakeAgent()
    assert asyncio.run(wrapped(agent, 10)) == 13
    tracer.start_as_current_span.assert_called_once()
    span.set_attribute.assert_called()


def test_wrap_run_sync_sync_original(mock_tracer: tuple[MagicMock, MagicMock]) -> None:
    tracer, span = mock_tracer
    wrapped = pa._wrap_run_sync(_sync_run_sync)
    assert not inspect.iscoroutinefunction(wrapped)
    agent = _FakeAgent()
    assert wrapped(agent, 2) == 6
    tracer.start_as_current_span.assert_called_once()
    span.set_attribute.assert_called()


def test_apply_pydantic_ai_if_package_installed() -> None:
    pytest.importorskip("pydantic_ai")
    assert pa.apply_pydantic_ai_patch() is True
