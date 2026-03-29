# Logs

Abidex captures OpenTelemetry logs and enriches them with agentic context from the active span.

## How it works

1. **Python logging → OTel**  
   A `LoggingHandler` bridges `logging.info()`, `logging.warning()`, etc. into the OTel logs pipeline.

2. **`gen_ai.*` enrichment**  
   Logs emitted inside a workflow or agent span get attributes from that span, e.g.:
   - `gen_ai.workflow.name`
   - `gen_ai.agent.role`
   - `gen_ai.agent.goal`
   - `gen_ai.agent.backstory`
   - `gen_ai.task.description`

3. **Export to `logs/`**  
   Call `log_buffer.export_to_jsonl("logs/logs.ndjson", 100)` in your script to persist logs.

## Usage

```python
import logging
import abidex
from abidex import log_buffer
from crew_agent import run

result = run(inputs={"topic": "Q4"})
log_buffer.export_to_jsonl("logs/logs.ndjson", 100)
```

```bash
abidex logs last 10
abidex logs export -o logs/logs.ndjson
```

## Config

| Variable | Default | Description |
|----------|---------|-------------|
| `ABIDEX_LOGS_ENABLED` | `true` | Enable log capture and enrichment. |
| `ABIDEX_LOGS_BUFFER_ENABLED` | `true` | Buffer logs for `abidex logs last` / `logs export`. |

Logs are exported to OTLP if `OTEL_EXPORTER_OTLP_ENDPOINT` is set (same as traces).
