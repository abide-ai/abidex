# Integrating & Testing Abidex

---

## Quick integration

See [frameworks.md](frameworks.md) for framework-specific examples. Import `abidex` before your framework.

---

## Backends

### SigNoz (recommended)

```bash
pip install abidex[otlp]
abidex backend start
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
abidex run main.py
```

UI at **http://localhost:3301**.

### Uptrace

```bash
docker run -d -p 14317:4317 -p 14318:4318 --name uptrace \
  -e UPTRACE_DSN=sqlite3:///tmp/uptrace.sqlite?mode=memory uptrace/uptrace:latest
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:14317
```

UI at **http://localhost:14318**.

---

## What to test for

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

## Failure modes

See [troubleshooting.md](troubleshooting.md).
