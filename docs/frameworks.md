# Supported Frameworks

Import `abidex` **before** your framework so patching runs first.

## CrewAI

```python
import abidex

from crewai import Agent, Task, Crew

agent = Agent(role="Analyst", goal="Analyze data", backstory="You are an analyst.")
task = Task(description="Summarize the report", agent=agent)
crew = Crew(agents=[agent], tasks=[task])
result = crew.kickoff(inputs={"topic": "Q4 report"})
```

See [crewai.md](crewai.md) for env vars, import order, and troubleshooting.

---

## LangGraph

```python
import abidex

from langgraph.graph import StateGraph, MessagesState

# ... build your graph ...
compiled = graph.compile()
result = compiled.invoke({"messages": [...]})
```

---

## Pydantic AI

```python
import abidex

from pydantic_ai import Agent

agent = Agent("my-model", system_prompt="You are a helpful assistant.")
result = agent.run_sync("Explain observability in one sentence.")
```

---

## LlamaIndex Workflows

```python
import abidex

from llama_index.core.workflow import Workflow

# ... build workflow ...
result = workflow.run(...)
```

---

## n8n

```python
import abidex

from n8n_sdk_python import N8nClient

client = N8nClient(...)
result = client.execute_workflow(...)
```

---

## Reference

| Framework | Entry points | Extracted fields |
|-----------|--------------|------------------|
| **CrewAI** | `Crew.kickoff` / `akickoff`; Agent `execute_task` / `do_task` | Workflow name, team agents; agent role, goal, backstory, task description |
| **LangGraph** | `CompiledStateGraph.invoke` / `.stream` | `gen_ai.framework`, optional `langgraph_node` |
| **Pydantic AI** | `Agent.run` / `run_sync` | Agent name, instructions |
| **LlamaIndex** | `Workflow.run` | Workflow name, `gen_ai.framework` |
| **n8n** | `N8nClient.execute_workflow` / `run_workflow` / `run` | Workflow ID/name, `gen_ai.framework` |
