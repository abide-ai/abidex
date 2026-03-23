# CrewAI Integration Guide

This guide covers AbideX setup for [CrewAI](https://docs.crewai.com/) with recommended environment configuration and import order.

---

## Quick start

```python
import abidex  # must be first

from crewai import Agent, Task, Crew

agent = Agent(role="Analyst", goal="Analyze data", backstory="You are an analyst.")
task = Task(description="Summarize the report", agent=agent)
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff(inputs={"topic": "Q4 report"})
```

---

## Import order

**Import `abidex` before CrewAI** so patching runs before the framework is loaded:

```python
import abidex  # ← first

from crewai import Agent, Task, Crew
# or: from crew_agent import run  (abidex must still be imported in main before crew_agent)
```

If your crew lives in another module, ensure the entry-point script imports abidex before importing that module:

```python
# main.py
import abidex
from crew_agent import run  # crew_agent imports crewai
```

---

## Recommended environment variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `ABIDEX_BUFFER_ENABLED` | `true` | Enable in-memory span buffer for `abidex trace last` and JSONL export. |
| `CREWAI_TRACING_ENABLED` | `false` | Disable CrewAI’s own tracing so it doesn’t conflict with AbideX. |
| `CREWAI_DISABLE_TELEMETRY` | `true` | Prevent CrewAI from setting its own tracer provider, which would override AbideX’s. |

Optional:

| Variable | Purpose |
|----------|---------|
| `ABIDEX_VERBOSE` | `true` — print patch success messages (e.g. "Patched CrewAI successfully") on startup. |
| `CREWAI_STORAGE_DIR` | Set to a writable path if CrewAI’s SQLite storage fails (e.g. `unable to open database file`); often needed in restricted environments. |

### Example `.env` or script setup

```bash
export ABIDEX_BUFFER_ENABLED=true
export CREWAI_TRACING_ENABLED=false
export CREWAI_DISABLE_TELEMETRY=true
python your_crew_script.py
```

Or in Python before any imports:

```python
import os
os.environ.setdefault("ABIDEX_BUFFER_ENABLED", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

import abidex
from crewai import Agent, Task, Crew
# ...
```

---

## Exporting spans (standard behavior)

Call `trace_buffer.export_to_jsonl()` after your crew finishes. By default this writes spans to a JSONL file **and prints a pretty table** to stdout:

```python
import abidex
from abidex import trace_buffer
from crew_agent import run

result = run(inputs={"topic": "OpenTelemetry"})
trace_buffer.export_to_jsonl("spans.ndjson", 100)  # shows table automatically
```

Set `show_table=False` for headless/CI runs:

```python
trace_buffer.export_to_jsonl("spans.ndjson", 100, show_table=False)
```

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| **"No spans in buffer"** | Set `ABIDEX_BUFFER_ENABLED=true` and run the script; or export to JSONL and use `abidex trace last --file file.ndjson`. |
| **"Overriding of current TracerProvider is not allowed"** | Set `CREWAI_DISABLE_TELEMETRY=true` before importing. CrewAI will skip setting its tracer. |
| **`unable to open database file`** | Set `CREWAI_STORAGE_DIR` to a writable path (e.g. `./.crewai_storage`). |
| **No spans created** | Ensure `import abidex` runs before any CrewAI import. Run with `ABIDEX_VERBOSE=true` to confirm "Patched CrewAI successfully". |

---

For general integration, backends, and CLI usage, see [integration-and-testing.md](integration-and-testing.md) and the [README](../README.md).
