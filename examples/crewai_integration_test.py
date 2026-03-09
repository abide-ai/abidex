# 1. Start SigNoz or Uptrace (see README or examples/signoz-quickstart.md, uptrace-quickstart.md)
# 2. Set OTEL_EXPORTER_OTLP_ENDPOINT (e.g. export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317)
# 3. Run this script: python examples/crewai_integration_test.py
# 4. Check SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318 for traces

import os
import abidex

from crewai import Agent, Task, Crew

_llm = None
if os.environ.get("OPENAI_API_KEY"):
    try:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    except ImportError:
        pass

def _agent(**kwargs):
    if _llm is not None:
        kwargs["llm"] = _llm
    return Agent(**kwargs)

researcher = _agent(
    role="Researcher",
    goal="Find accurate, concise facts on the topic.",
    backstory="You are a thorough researcher.",
)
writer = _agent(
    role="Writer",
    goal="Turn research into a short, clear summary.",
    backstory="You are a concise writer.",
)

research_task = Task(
    description="Find one key fact about the given topic.",
    agent=researcher,
)
write_task = Task(
    description="Write one sentence summarizing the research.",
    agent=writer,
    context=[research_task],
)

crew = Crew(agents=[researcher, writer], tasks=[research_task, write_task])

if __name__ == "__main__":
    result = crew.kickoff(inputs={"topic": "OpenTelemetry"})
    print(result)
    print("\nCheck SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318 for traces.")
