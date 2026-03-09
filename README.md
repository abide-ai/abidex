# Abidex

[![PyPI version](https://badge.fury.io/py/abidex.svg)](https://pypi.org/project/abidex/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Zero-code OpenTelemetry tracing for AI agents.** Add one import, get spans for workflows, agents, and tasks—with role, goal, backstory, and timing out of the box.

---

## Installation

```bash
pip install abidex
```

For sending traces to an OTLP backend (SigNoz, Uptrace, Jaeger, etc.):

```bash
pip install abidex[otlp]
```

Optional dev setup (editable install + lint/test):

```bash
pip install -e ".[dev]"
```

Also works with **uv**, **pdm**, **hatch**: `uv add abidex`, `pdm add abidex`, etc.

---

## Quickstart

1. **Install:** `pip install abidex`
2. **Import** abidex before your crew/graph so it can patch frameworks.
3. **Run** your agent script as usual—spans are created automatically.

```python
import abidex  # ← add this first

from crewai import Agent, Task, Crew

researcher = Agent(role="Researcher", goal="Find facts", backstory="You are a researcher.")
task = Task(description="Summarize the topic", agent=researcher)
crew = Crew(agents=[researcher], tasks=[task])

result = crew.kickoff(inputs={"topic": "OpenTelemetry"})
```

No config required. Traces go to the **console** by default; point `OTEL_EXPORTER_OTLP_ENDPOINT` at a backend for a full UI.

---

## Add Abidex to your agent script

Import `abidex` **before** you import or use CrewAI, LangGraph, or Pydantic AI. One line is enough.

### CrewAI

```python
import abidex

from crewai import Agent, Task, Crew

agent = Agent(role="Analyst", goal="Analyze data", backstory="You are an analyst.")
task = Task(description="Summarize the report", agent=agent)
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff(inputs={"topic": "Q4 report"})
```

### LangGraph

```python
import abidex

from langgraph.graph import StateGraph, MessagesState
# ... build your graph ...
compiled = graph.compile()
result = compiled.invoke({"messages": [...]})
```

### Pydantic AI

```python
import abidex

from pydantic_ai import Agent

agent = Agent("my-model", system_prompt="You are a helpful assistant.")
result = agent.run_sync("Explain observability in one sentence.")
```

---

## How to see traces

### Console (default)

If you don’t set `OTEL_EXPORTER_OTLP_ENDPOINT`, spans are printed to **stderr**. Ideal for local debugging.

### SigNoz (persistent UI + dashboards)

1. Start SigNoz (see [examples/signoz-quickstart.md](examples/signoz-quickstart.md) or [SigNoz Docker docs](https://signoz.io/docs/install/docker/)):

   ```bash
   git clone https://github.com/signoz/signoz.git && cd signoz
   docker compose -f deploy/docker-compose/standalone/docker-compose.yaml up -d
   ```

2. Set env and run your script:

   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   pip install abidex[otlp]
   python your_agent_script.py
   ```

3. Open **http://localhost:3301** → Traces. Filter by `gen_ai.agent.role`, `gen_ai.workflow.name`, etc.

### Uptrace (lightweight, dev-friendly)

1. Start Uptrace:

   ```bash
   docker run -d -p 14317:4317 -p 14318:4318 --name uptrace \
     -e UPTRACE_DSN=postgres://uptrace:uptrace@host.docker.internal:5432/uptrace \
     uptrace/uptrace:latest
   ```

2. Set env and run:

   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317
   pip install abidex[otlp]
   python your_agent_script.py
   ```

3. Open **http://localhost:14318** → sign up (first user) → Traces.

See [examples/uptrace-quickstart.md](examples/uptrace-quickstart.md) for more detail.

---

## Testing checklist

After running a traced workflow, verify:

| Check | What to look for |
|-------|------------------|
| **Role / goal / backstory** | Spans include `gen_ai.agent.role`, `gen_ai.agent.goal`, `gen_ai.agent.backstory` (CrewAI) or equivalent. |
| **Hierarchy** | Workflow span is parent of agent/task spans. |
| **Disable in tests** | Set `ABIDEX_AUTO=false` (or don’t import abidex) in tests to avoid patching and use your own tracer/mocks. |

Example for tests:

```bash
ABIDEX_AUTO=false pytest tests/
```

---

## CLI

The `abidex` command gives you a rich CLI (tables, colors, spinners). Enable the in-memory buffer so the CLI can see spans from the same process:

```bash
export ABIDEX_BUFFER_ENABLED=true
python your_agent_script.py
abidex trace last 10
```

| Command | Description |
|--------|-------------|
| `abidex status` | Config, OTEL endpoint, patched frameworks, buffer size. When endpoint is unset, shows a hint: *To see persistent traces, start SigNoz/Uptrace and set OTEL_EXPORTER_OTLP_ENDPOINT.* Use `-v` for last-run hint. |
| `abidex trace last [N]` | Table of last N spans: name, duration, status (✓ OK / ✗ ERROR), role/goal, start time. Help text: *After running your agent, use this to view recent spans.* |
| `abidex trace last --filter "role=Researcher"` | Filter by attribute (e.g. `role=Researcher` or plain substring). |
| `abidex trace export --format jsonl -o file.ndjson [--last N]` | Export spans to JSONL. |
| `abidex trace export --format pretty [--last N]` | Colored JSON in the terminal (default last 10). |
| `abidex init` | Print `.env` template and Docker one-liners for SigNoz and Uptrace. |
| `abidex summary` | Stats: count by span name, avg duration, total tokens (if present), error count. |

**Examples:**

```bash
abidex status
abidex status -v
abidex trace last 10
abidex trace last 5 --filter "role=Researcher"
abidex trace last --file spans.ndjson
abidex trace export --format jsonl -o traces.ndjson --last 100
abidex trace export --format pretty --last 5
abidex init
abidex summary
```

For cross-process use: export from your app with `abidex.trace_buffer.export_to_jsonl("spans.ndjson", 100)`, then run `abidex trace last --file spans.ndjson`.

---

## Supported frameworks

| Framework | Entry points | Extracted fields |
|-----------|--------------|------------------|
| **CrewAI** | `Crew.kickoff` / `akickoff`; Agent `execute_task` / `do_task` | Workflow name, team agents; agent role, goal, backstory, task description |
| **LangGraph** | `CompiledStateGraph.invoke` / `.stream` | `gen_ai.framework`, optional `langgraph_node` from config |
| **Pydantic AI** | `Agent.run` / `run_sync` | Agent name, instructions (truncated) |
| **AutoGen** | (stub) | Planned |
| **LlamaIndex Workflows** | (stub) | Planned |

---

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `ABIDEX_AUTO` | `true` | Auto-init and patch on import. Set to `false` to disable (e.g. in tests). |
| `ABIDEX_VERBOSE` | `false` | When `true`, print patching messages on init (e.g. "Patched CrewAI successfully"). |
| `ABIDEX_BUFFER_ENABLED` | `false` | When `true`, keep last 1000 spans in memory for `abidex trace last` / `abidex trace export`. |
| `OTEL_SERVICE_NAME` | — | Service name in traces (e.g. `my-agent-app`). |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | OTLP gRPC endpoint (e.g. `http://localhost:4317`). Requires `pip install abidex[otlp]`. |

---

## Troubleshooting

| Issue | What to try |
|-------|-------------|
| **No spans** | Import `abidex` **before** CrewAI/LangGraph/Pydantic AI. Check that your framework version is supported. |
| **Spans only in console** | Set `OTEL_EXPORTER_OTLP_ENDPOINT` and install `abidex[otlp]`. Ensure the backend (SigNoz/Uptrace/Jaeger) is running and reachable. |
| **CLI says "No spans in buffer"** | Set `ABIDEX_BUFFER_ENABLED=true` and run your agent in the same process, or export to JSONL and use `abidex trace last --file file.ndjson`. |
| **Wrong or missing attributes** | Run with `ABIDEX_VERBOSE=true` to confirm which framework was patched. Check that you’re using the expected entry points (e.g. `crew.kickoff`, not a custom wrapper). |

---

## Contributing & feedback

- **Bugs & features:** [GitHub Issues](https://github.com/abide-ai/abidex/issues).
- **Contributions:** PRs welcome. Run `pytest` and `ruff check` (or use `pip install -e ".[dev]"`).

We’re focused on Phase 1: execution observability (workflow/agent/task spans and GenAI attributes). More frameworks and deeper instrumentation are on the roadmap.

---

## License

MIT
