import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from .cli_common import get_repo_root


DEFAULT_CONFIG_FILENAMES = ("abidex.json", ".abidex.json")
DEFAULT_COLLECTOR_HOST = "127.0.0.1"
DEFAULT_COLLECTOR_PORT = 8000


@dataclass(frozen=True)
class CollectorSettings:
    host: str
    port: int


@dataclass(frozen=True)
class OtlpSettings:
    traces_endpoint: Optional[str]
    metrics_endpoint: Optional[str]
    headers: Optional[Dict[str, str]]


def resolve_collector_settings(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> CollectorSettings:
    config = _load_config()
    collector = _get_section(config, "collector")

    env_host = os.environ.get("ABIDEX_COLLECTOR_HOST")
    env_port = _parse_int(os.environ.get("ABIDEX_COLLECTOR_PORT"))

    config_host = _coerce_str(collector.get("host"))
    config_port = _parse_int(collector.get("port"))

    resolved_host = _first_non_empty(host, env_host, config_host, DEFAULT_COLLECTOR_HOST)
    resolved_port = _first_non_none(port, env_port, config_port, DEFAULT_COLLECTOR_PORT)
    return CollectorSettings(host=resolved_host, port=resolved_port)


def resolve_otlp_settings(
    otlp_endpoint: Optional[str] = None,
    otlp_headers: Optional[Dict[str, str]] = None,
    otlp_traces_endpoint: Optional[str] = None,
    otlp_metrics_endpoint: Optional[str] = None,
) -> OtlpSettings:
    config = _load_config()
    otel = _get_section(config, "otel")

    env_endpoint = os.environ.get("ABIDEX_OTLP_ENDPOINT")
    env_traces = os.environ.get("ABIDEX_OTLP_TRACES_ENDPOINT")
    env_metrics = os.environ.get("ABIDEX_OTLP_METRICS_ENDPOINT")
    env_headers = _parse_headers(os.environ.get("ABIDEX_OTLP_HEADERS"))

    config_endpoint = _coerce_str(
        otel.get("endpoint") or otel.get("otlp_endpoint")
    )
    config_traces = _coerce_str(
        otel.get("traces_endpoint") or otel.get("otlp_traces_endpoint")
    )
    config_metrics = _coerce_str(
        otel.get("metrics_endpoint") or otel.get("otlp_metrics_endpoint")
    )
    config_headers = _parse_headers(
        otel.get("headers") or otel.get("otlp_headers")
    )

    resolved_endpoint = _first_non_empty(
        otlp_endpoint, env_endpoint, config_endpoint
    )
    resolved_traces = _first_non_empty(
        otlp_traces_endpoint, env_traces, config_traces
    )
    resolved_metrics = _first_non_empty(
        otlp_metrics_endpoint, env_metrics, config_metrics
    )
    resolved_headers = (
        otlp_headers
        if otlp_headers is not None
        else _first_non_none(env_headers, config_headers)
    )

    traces_endpoint, metrics_endpoint = _normalize_otlp_endpoints(
        resolved_endpoint,
        resolved_traces,
        resolved_metrics,
    )
    return OtlpSettings(
        traces_endpoint=traces_endpoint,
        metrics_endpoint=metrics_endpoint,
        headers=resolved_headers,
    )


def _load_config() -> dict:
    path = _find_config_path()
    if not path or not path.exists():
        return {}
    try:
        raw = path.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _find_config_path() -> Optional[Path]:
    env_path = os.environ.get("ABIDEX_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    for base in (Path.cwd(), get_repo_root()):
        for filename in DEFAULT_CONFIG_FILENAMES:
            candidate = base / filename
            if candidate.exists():
                return candidate
    return None


def _get_section(data: dict, name: str) -> dict:
    section = data.get(name, {})
    return section if isinstance(section, dict) else {}


def _parse_headers(value: Optional[object]) -> Optional[Dict[str, str]]:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): str(val) for key, val in value.items()}
    if isinstance(value, str):
        return _parse_headers_string(value)
    if isinstance(value, (list, tuple, set)):
        merged: Dict[str, str] = {}
        for entry in value:
            if isinstance(entry, str):
                merged.update(_parse_headers_string(entry))
        return merged or None
    return None


def _parse_headers_string(value: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for part in value.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, val = part.split("=", 1)
        key = key.strip()
        val = val.strip()
        if key:
            result[key] = val
    return result


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_str(value: Optional[object]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _first_non_empty(*values: Optional[str]) -> Optional[str]:
    for value in values:
        if value:
            return value
    return None


def _first_non_none(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _normalize_otlp_endpoints(
    endpoint: Optional[str],
    traces_endpoint: Optional[str],
    metrics_endpoint: Optional[str],
) -> Tuple[Optional[str], Optional[str]]:
    if traces_endpoint or metrics_endpoint:
        if not traces_endpoint and endpoint:
            traces_endpoint = _append_otlp_path(endpoint, "/v1/traces")
        if not metrics_endpoint and endpoint:
            metrics_endpoint = _append_otlp_path(endpoint, "/v1/metrics")
        if not endpoint and traces_endpoint and not metrics_endpoint:
            base = _strip_otlp_suffix(traces_endpoint, "/v1/traces")
            if base:
                metrics_endpoint = _append_otlp_path(base, "/v1/metrics")
        if not endpoint and metrics_endpoint and not traces_endpoint:
            base = _strip_otlp_suffix(metrics_endpoint, "/v1/metrics")
            if base:
                traces_endpoint = _append_otlp_path(base, "/v1/traces")
        return traces_endpoint, metrics_endpoint

    if not endpoint:
        return None, None

    endpoint = endpoint.rstrip("/")
    if endpoint.endswith("/v1/traces"):
        base = endpoint[: -len("/v1/traces")]
        return endpoint, _append_otlp_path(base, "/v1/metrics")
    if endpoint.endswith("/v1/metrics"):
        base = endpoint[: -len("/v1/metrics")]
        return _append_otlp_path(base, "/v1/traces"), endpoint
    return _append_otlp_path(endpoint, "/v1/traces"), _append_otlp_path(endpoint, "/v1/metrics")


def _append_otlp_path(endpoint: str, suffix: str) -> str:
    endpoint = endpoint.rstrip("/")
    if not endpoint:
        return suffix
    return f"{endpoint}{suffix}"


def _strip_otlp_suffix(endpoint: str, suffix: str) -> Optional[str]:
    endpoint = endpoint.rstrip("/")
    if endpoint.endswith(suffix):
        return endpoint[: -len(suffix)]
    return None
