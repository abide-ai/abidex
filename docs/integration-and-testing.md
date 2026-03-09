# Integrating & Testing Abidex in Your Agentic Workflows

This playbook walks you through adding Abidex to your agent code and verifying traces. For installation and overview, see the [README](../README.md).

---

## 1. Quick integration

Add a single import **before** your framework imports. No config required for console output.

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

# ... build your graph (nodes, edges, etc.) ...
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

**Rule of thumb:** `import abidex` must be the first of these imports so patching runs before the framework is used.

---

## 2. Recommended persistent backends

To see traces in a UI (search, filter, dashboards), run a backend and point Abidex at it.

### SigNoz

1. Start SigNoz:

   ```bash
   git clone https://github.com/signoz/signoz.git && cd signoz
   docker compose -f deploy/docker-compose/standalone/docker-compose.yaml up -d
   ```

2. Set env and install OTLP extra:

   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
   pip install abidex[otlp]
   ```

3. Run your agent script. Open **http://localhost:3301** → Traces.

See [examples/signoz-quickstart.md](../examples/signoz-quickstart.md) for more detail.

### Uptrace

1. Start Uptrace:

   ```bash
   docker run -d -p 14317:4317 -p 14318:4318 --name uptrace \
     -e UPTRACE_DSN=postgres://uptrace:uptrace@host.docker.internal:5432/uptrace \
     uptrace/uptrace:latest
   ```

2. Set env and install OTLP extra:

   ```bash
   export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317
   pip install abidex[otlp]
   ```

3. Run your agent script. Open **http://localhost:14318** → sign up (first user) → Traces.

See [examples/uptrace-quickstart.md](../examples/uptrace-quickstart.md) for more detail.

---

## 3. What to test for

Use this checklist after running a traced workflow (console or UI).

| Check | How to verify |
|-------|----------------|
| **Spans present** | At least one span per workflow run; for CrewAI, expect Workflow + Agent (and/or task) spans. |
| **Attributes correct** | CrewAI: `gen_ai.agent.role`, `gen_ai.agent.goal`, `gen_ai.agent.backstory`, `gen_ai.workflow.name`. LangGraph: `gen_ai.framework`. Pydantic AI: `gen_ai.agent.name`, `gen_ai.instructions`. |
| **Hierarchy** | Workflow/root span is parent of agent or task spans (inspect parent/child in trace view). |
| **Disable in tests** | In unit/integration tests, set `ABIDEX_AUTO=false` (or avoid importing abidex) so your test tracer or mocks are used. |
| **Overhead** | Trace creation is lightweight; if you see latency, ensure you’re not exporting to a slow or unreachable backend (use console for quick local runs). |

**Quick test with CLI (same process):**

```bash
export ABIDEX_BUFFER_ENABLED=true
python your_agent_script.py
abidex trace last 10
abidex summary
```

---

## 4. Common failure modes & fixes

| Problem | Cause | Fix |
|--------|--------|-----|
| **Spans missing** | Abidex not patching; import order wrong. | Import `abidex` **before** CrewAI, LangGraph, or Pydantic AI. |
| **Spans only in console** | No OTLP endpoint or backend not running. | Set `OTEL_EXPORTER_OTLP_ENDPOINT`, install `abidex[otlp]`, and start SigNoz/Uptrace/Jaeger. |
| **Long backstory/goal truncated** | By design for display and payload size. | Expected; full value may be in span attributes in the backend; CLI truncates for table readability. |
| **Wrong or no framework detected** | Unsupported version or custom entry points. | Run with `ABIDEX_VERBOSE=true` to see which framework was patched. Use standard entry points (e.g. `crew.kickoff`, `compiled.invoke`). |
| **CLI: "No spans in buffer"** | Buffer disabled or CLI run in another process. | Set `ABIDEX_BUFFER_ENABLED=true` and run the script and CLI in the same process, or export to JSONL and use `abidex trace last --file file.ndjson`. |
| **Tests failing or double traces** | Abidex auto-init conflicts with test tracer. | Use `ABIDEX_AUTO=false` when running tests (e.g. in `conftest.py` or env). |

---

## 5. Example script

Minimal CrewAI crew with Abidex. **Run this after starting SigNoz or Uptrace** (see Section 2) and setting `OTEL_EXPORTER_OTLP_ENDPOINT`.

```python
# 1. Start SigNoz or Uptrace (see Section 2 or README).
# 2. Set: export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  (SigNoz) or :14317 (Uptrace)
# 3. Install: pip install abidex[otlp]
# 4. Run: python this_script.py → traces appear in the UI (SigNoz http://localhost:3301, Uptrace http://localhost:14318)

import os
import abidex

from crewai import Agent, Task, Crew

if os.environ.get("OPENAI_API_KEY"):
    from langchain_openai import ChatOpenAI
    _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
else:
    _llm = None

researcher = Agent(
    role="Researcher",
    goal="Find one short fact about the topic.",
    backstory="You are a concise researcher.",
    **({"llm": _llm} if _llm else {}),
)
task = Task(
    description="State one fact about the given topic in one sentence.",
    agent=researcher,
)
crew = Crew(agents=[researcher], tasks=[task])

if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "OpenTelemetry"})
    print(result)
    print("\nCheck SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318")
```

A copy of this example lives in [examples/test-with-signoz.py](../examples/test-with-signoz.py).

---

For more options (CLI, env vars, troubleshooting), see the [README](../README.md).
