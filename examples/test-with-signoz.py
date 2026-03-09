# 1. Start SigNoz first (see README or examples/signoz-quickstart.md)
# 2. Set: export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
# 3. Install: pip install abidex[otlp]
# 4. Run this script → traces appear in SigNoz UI

import os
import abidex

from crewai import Agent, Task, Crew

if os.environ.get("OPENAI_API_KEY"):
    from langchain_openai import ChatOpenAI
    _llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
else:
    _llm = None  # Set OPENAI_API_KEY or use Ollama; CrewAI may use its default

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
    print("\nCheck SigNoz at http://localhost:3301")
