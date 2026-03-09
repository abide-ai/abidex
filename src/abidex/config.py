"""
Abidex config: ABIDEX_* and OTEL_* env vars.

Recommended backends (OTEL_EXPORTER_OTLP_ENDPOINT):
- Console (default): no extra setup; spans go to terminal. Do not set the endpoint.
- SigNoz local: export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
  (after running SigNoz docker-compose; see README / examples/signoz-quickstart.md).
- Jaeger: same endpoint http://localhost:4317 after running Jaeger all-in-one Docker.
- Any OTEL-compatible: Honeycomb, Grafana Cloud, Uptrace, etc. Set endpoint to the collector URL.
"""
import os
from typing import Optional


def _env_auto() -> bool:
    raw = os.environ.get("ABIDEX_AUTO", "true").strip().lower()
    return raw in ("true", "1", "yes")


def _env_bool(key: str, default: bool = True) -> bool:
    raw = os.environ.get(key, "").strip().lower()
    if not raw:
        return default
    return raw in ("true", "1", "yes")


ABIDEX_AUTO: bool = _env_auto()
# When True, print patching success/failure messages on init (e.g. "Patched CrewAI kickoff successfully").
ABIDEX_VERBOSE: bool = _env_bool("ABIDEX_VERBOSE", False)
# When True, spans are appended to an in-memory buffer for CLI (trace last, export jsonl). Default false to keep minimal.
ABIDEX_BUFFER_ENABLED: bool = _env_bool("ABIDEX_BUFFER_ENABLED", False)


def get_service_name() -> Optional[str]:
    return os.environ.get("OTEL_SERVICE_NAME")
