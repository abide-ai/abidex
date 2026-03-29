import abidex
from pydantic_ai import Agent
agent = Agent('openai:gpt-4o-mini', system_prompt='You are a helpful assistant. Reply in one short sentence.')
if __name__ == '__main__':
    result = agent.run_sync('What is OpenTelemetry in one sentence?')
    print(result.data)
    print('\nCheck SigNoz at http://localhost:8080 or Uptrace at http://localhost:14318 for traces.')