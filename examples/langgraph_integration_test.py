import abidex
from typing import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    topic: str
    research: str
    summary: str

def researcher(state: State) -> dict:
    topic = state.get('topic', 'unknown')
    return {'research': f'Researched: key facts about {topic}.'}

def summarizer(state: State) -> dict:
    research = state.get('research', '')
    return {'summary': f'Summary: {research[:80]}...'}
builder = StateGraph(State)
builder.add_node('researcher', researcher)
builder.add_node('summarizer', summarizer)
builder.add_edge(START, 'researcher')
builder.add_edge('researcher', 'summarizer')
builder.add_edge('summarizer', END)
graph = builder.compile()
if __name__ == '__main__':
    result = graph.invoke({'topic': 'OpenTelemetry', 'research': '', 'summary': ''})
    print('Result:', result)
    print('\nCheck SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318 for traces.')