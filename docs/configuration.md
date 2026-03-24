# Configuration

Environment variables.

| Variable | Default | Description |
|----------|---------|-------------|
| `ABIDEX_AUTO` | `true` | Auto-init and patch on import. Set `false` in tests. |
| `ABIDEX_VERBOSE` | `false` | Print patching messages (e.g. "Patched CrewAI successfully"). |
| `ABIDEX_BUFFER_ENABLED` | `false` | Keep last 1000 spans for `abidex trace last` / `trace export`. |
| `OTEL_SERVICE_NAME` | — | Service name in traces (e.g. `my-agent-app`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP endpoint. gRPC: `http://localhost:4317`. HTTP: `http://localhost:4318`. Requires `pip install abidex[otlp]`. |
| `ABIDEX_LOGS_ENABLED` | `true` | Capture OTel logs (Python `logging` → OTel) with `gen_ai.*` enrichment from the active span. |
| `ABIDEX_LOGS_BUFFER_ENABLED` | `true` | Buffer logs for `abidex logs last` and `logs export`. |
