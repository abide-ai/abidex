"""
Persistent trace visibility for Phase 1 CLI (trace last, export jsonl).
Global deque (max 1000 spans) filled by a SpanProcessor; optional via ABIDEX_BUFFER_ENABLED.
"""

import json
from collections import deque
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanProcessor

BUFFER_MAX = 1000
_buffer: deque[dict[str, Any]] = deque(maxlen=BUFFER_MAX)


def _span_to_dict(span: ReadableSpan) -> dict[str, Any]:
    attrs = dict(span.attributes) if span.attributes else {}
    return {
        "name": span.name,
        "start_time_ns": span.start_time,
        "end_time_ns": span.end_time,
        "attributes": {k: str(v) for k, v in attrs.items()},
        "status": str(span.status) if span.status else None,
    }


class BufferSpanProcessor(SpanProcessor):
    """Appends finished spans to the global deque; does not forward to exporter (otel_setup adds exporter separately)."""

    def on_start(self, span: Any, parent_context: Any = None) -> None:
        pass

    def on_end(self, span: ReadableSpan) -> None:
        _buffer.append(_span_to_dict(span))

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def get_recent_spans(n: int = BUFFER_MAX) -> list[dict[str, Any]]:
    """Return the last n spans from the buffer (newest last)."""
    return list(_buffer)[-n:]


def export_to_jsonl(path: str, n: int = BUFFER_MAX) -> None:
    """Write the last n spans to a JSONL file. For cross-process CLI visibility, call from your app after a run."""
    spans = get_recent_spans(n)
    with open(path, "w") as f:
        for s in spans:
            f.write(json.dumps(s) + "\n")


def clear_buffer() -> None:
    """Clear the in-memory span buffer."""
    _buffer.clear()


def buffer_len() -> int:
    """Current number of spans in the buffer."""
    return len(_buffer)
