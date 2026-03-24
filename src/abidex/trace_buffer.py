import json
import os
import subprocess
import sys
from collections import deque
from pathlib import Path
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


def export_to_jsonl(path: str | Path, n: int = BUFFER_MAX, *, show_table: bool = True) -> Path:
    """Write the last n spans to a JSONL file. For cross-process CLI visibility, call from your app after a run.

    When show_table is True (default), prints a pretty table of spans to stdout after writing.
    Set show_table=False for headless/CI runs. Skipped automatically when run via `abidex run` (avoids duplicate table).
    Returns the path written.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    spans = get_recent_spans(n)
    with open(path, "w") as f:
        for s in spans:
            f.write(json.dumps(s) + "\n")

    skip_table = os.environ.get("ABIDEX_RUN_MODE") == "1"
    if show_table and not skip_table and spans:
        try:
            subprocess.run(
                [sys.executable, "-m", "abidex.cli", "trace", "last", "--file", str(Path(path).resolve())],
                check=False,
            )
        except Exception:
            pass  # Don't fail the run if table display fails
    return path


def _timestamp_suffix() -> str:
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def export_with_timestamp(output_dir: str | Path = "traces", n: int = BUFFER_MAX, *, show_table: bool = True) -> Path:
    """Export spans to timestamped file in output_dir. Creates dir if needed."""
    output_dir = Path(output_dir)
    path = output_dir / f"spans_{_timestamp_suffix()}.ndjson"
    return export_to_jsonl(path, n, show_table=show_table)


def clear_buffer() -> None:
    """Clear the in-memory span buffer."""
    _buffer.clear()


def buffer_len() -> int:
    """Current number of spans in the buffer."""
    return len(_buffer)
