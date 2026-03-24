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

Traces go to **console** by default. For a persistent UI: `abidex backend start` then set `OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317`.

---

## CLI

| Command | Description |
|--------|-------------|
| `abidex run main.py` | Run script, then show trace table |
| `abidex backend start` | Start SigNoz (clones to `~/.abidex/signoz`), open UI |
| `abidex backend stop` | Stop SigNoz |
| `abidex backend status` | Check if backend is reachable |
| `abidex status` | Config, buffer, patched frameworks |
| `abidex trace last [N]` | Table of last N spans (buffer or `spans.ndjson`) |
| `abidex trace last --file file.ndjson` | Read from JSONL file |
| `abidex trace export -f jsonl -o file.ndjson` | Export spans |
| `abidex init` | Print `.env` template, Docker one-liners |
| `abidex summary` | Span stats (count, duration, tokens) |

```bash
abidex backend start
abidex run main.py
abidex trace last 10
```

---

## Docs

- [Frameworks](docs/frameworks.md) — CrewAI, LangGraph, Pydantic AI, LlamaIndex, n8n
- [CrewAI integration](docs/crewai.md) — env vars, import order, troubleshooting
- [Configuration](docs/configuration.md) — env variables
- [Troubleshooting](docs/troubleshooting.md) — common issues

---

**Issues:** [GitHub](https://github.com/abide-ai/abidex/issues) · **License:** Apache 2.0
