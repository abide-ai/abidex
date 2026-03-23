import os
import abidex
from crewai import Agent, Task, Crew
_llm = None
if os.environ.get('GROQ_API_KEY'):
    try:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(model='llama-3.1-8b-instant', temperature=0)
    except ImportError:
        pass
if _llm is None and os.environ.get('OPENAI_API_KEY'):
    try:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(model='gpt-4o-mini', temperature=0)
    except ImportError:
        pass

def _agent(**kwargs):
    if _llm is not None:
        kwargs['llm'] = _llm
    return Agent(**kwargs)
researcher = _agent(role='Researcher', goal='Find accurate, concise facts on the topic', backstory='You are a thorough researcher.')
writer = _agent(role='Writer', goal='Write clear, short summaries', backstory='You are a concise writer.')
task = Task(description='Summarize the given topic in 2–3 sentences.', agent=researcher)
crew = Crew(agents=[researcher, writer], tasks=[task])
if __name__ == '__main__':
    result = crew.kickoff(inputs={'topic': 'OpenTelemetry'})
    print(result)