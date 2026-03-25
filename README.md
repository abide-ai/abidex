# Abidex

[![PyPI version](https://badge.fury.io/py/abidex.svg)](https://pypi.org/project/abidex/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

AbideX is zero-code monitoring for AI agents. Add one import before CrewAI, LangGraph, Pydantic AI and get spans with role, goal, and timing.

```bash
pip install abidex
# or for OTLP backend: pip install abidex[otlp]
```

```python
import abidex  # first
from crewai import Agent, Task, Crew
# ... run your crew
```

Traces go to **console** by default. For a persistent UI: `abidex backend start` then open **http://localhost:8080** (SigNoz’s default; some older installs use **3301**) and set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`.

---

## CLI

**Traces vs logs.** In OpenTelemetry these are different signals. **Traces** are made of **spans**: nested units of work (e.g. a CrewAI workflow, an agent step) with timing, parent/child links, and attributes such as `gen_ai.agent.role`. Use `abidex trace` / `trace last` and span exports like `spans_*.ndjson`. **Logs** are discrete **log records** (often from Python’s `logging` routed through the OTel logs SDK); they may include trace/span context, and Abidex can attach `gen_ai.*` fields from the active span when a line is emitted. Use `abidex logs` / `logs last` and files such as `logs_*.ndjson`. Both can be sent to the same backend (e.g. SigNoz) but the CLI treats span files and log files separately.

| Command | Description |
|--------|-------------|
| `abidex run SCRIPT.py` | Run a script with span buffer on, then print a trace table (`-n` / `--last` for row count) |
| `abidex backend start` | Clone SigNoz if needed (`~/.abidex/signoz`), `docker compose up`, open UI (8080 or 3301) |
| `abidex backend stop` | Stop SigNoz stack |
| `abidex backend status` | Check if SigNoz UI / OTLP ports are reachable |
| `abidex status` | Config, buffers, patched frameworks (`-v` for extra detail) |
| `abidex trace` · `abidex spans` | List span JSONL files (e.g. `spans.ndjson`, `traces/`, `data/traces/`) |
| `abidex trace last [N]` | Table of last N spans from buffer or latest export (`--file`, `--filter`, `-v`) |
| `abidex trace export -f jsonl -o FILE` | Export spans from buffer to JSONL (`-f pretty` for JSON stdout) |
| `abidex logs` | List log JSONL files (`logs/`, `data/logs/`) |
| `abidex logs last [N]` | Table of last N OTel log records (buffer or latest file; `--file path.ndjson`) |
| `abidex logs export [-o FILE]` | Export buffered logs to JSONL (default `logs/logs.ndjson`) |
| `abidex notebook` | Create `notebooks/abidex_logs.ipynb` from latest logs, optional date filter, launch Jupyter |
| `abidex init` | Print `.env` template and Docker one-liners |
| `abidex summary` | Span stats (count, duration, tokens; `-v` for more) |

```bash
abidex backend start
abidex run main.py
abidex trace last 10
abidex logs last
abidex notebook
```

---

## Docs

- [Frameworks](docs/frameworks.md) — CrewAI, LangGraph, Pydantic AI, LlamaIndex, n8n
- [CrewAI integration](docs/crewai.md) — env vars, import order, troubleshooting
- [Configuration](docs/configuration.md) — env variables
- [Troubleshooting](docs/troubleshooting.md) — common issues

---

**Issues:** [GitHub](https://github.com/abide-ai/abidex/issues) · **License:** Apache 2.0
