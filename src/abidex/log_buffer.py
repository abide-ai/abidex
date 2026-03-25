"""Buffer for OTel logs; enables abidex logs last and export to logs/."""
import json
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from opentelemetry.sdk._logs import LogRecordProcessor
from opentelemetry.trace import format_span_id, format_trace_id

BUFFER_MAX = 1000
_buffer: deque[dict[str, Any]] = deque(maxlen=BUFFER_MAX)

DEFAULT_LOGS_DIR = Path("logs")


def _log_data_to_dict(log_data) -> dict[str, Any]:
    rec = getattr(log_data, "log_record", None)
    if rec is None:
        rec = log_data
    attrs = dict(rec.attributes) if rec.attributes else {}
    trace_id = f"0x{format_trace_id(rec.trace_id)}" if rec.trace_id else None
    span_id = f"0x{format_span_id(rec.span_id)}" if rec.span_id else None
    return {
        "body": str(rec.body) if rec.body is not None else None,
        "severity_text": rec.severity_text,
        "timestamp_ns": rec.timestamp,
        "trace_id": trace_id,
        "span_id": span_id,
        "attributes": {k: str(v) for k, v in attrs.items()},
    }


class BufferLogProcessor(LogRecordProcessor):
    def on_emit(self, log_record) -> None:
        _buffer.append(_log_data_to_dict(log_record))

    def emit(self, log_data) -> None:
        _buffer.append(_log_data_to_dict(log_data))

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def get_recent_logs(n: int = BUFFER_MAX) -> list[dict[str, Any]]:
    return list(_buffer)[-n:]


def export_to_jsonl(path: str | Path, n: int = BUFFER_MAX) -> Path:
    """Write last n logs to JSONL. Creates parent dir (e.g. logs/) if needed. Returns path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    logs = get_recent_logs(n)
    with open(path, "w") as f:
        for log in logs:
            f.write(json.dumps(log) + "\n")
    return path


def _timestamp_suffix() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def export_with_timestamp(output_dir: str | Path = "logs", n: int = BUFFER_MAX) -> Path:
    """Export logs to timestamped NDJSON in output_dir. Returns path."""
    output_dir = Path(output_dir)
    suffix = _timestamp_suffix()
    return export_to_jsonl(output_dir / f"logs_{suffix}.ndjson", n)


def clear_buffer() -> None:
    _buffer.clear()


def buffer_len() -> int:
    return len(_buffer)
