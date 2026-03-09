# 1. Start SigNoz or Uptrace (see README or examples/signoz-quickstart.md, uptrace-quickstart.md)
# 2. Set OTEL_EXPORTER_OTLP_ENDPOINT (e.g. export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317)
# 3. Run this script: python examples/pydantic_ai_integration_test.py
#    (Requires a model: set OPENAI_API_KEY for openai:gpt-4o-mini or use another model.)
# 4. Check SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318 for traces

import abidex
from pydantic_ai import Agent

agent = Agent(
    "openai:gpt-4o-mini",
    system_prompt="You are a helpful assistant. Reply in one short sentence.",
)

if __name__ == "__main__":
    result = agent.run_sync("What is OpenTelemetry in one sentence?")
    print(result.data)
    print("\nCheck SigNoz at http://localhost:3301 or Uptrace at http://localhost:14318 for traces.")
