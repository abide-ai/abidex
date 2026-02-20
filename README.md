# AbideX

OpenTelemetry-native observability SDK for AI agents, providing comprehensive telemetry for agent workflows, model calls, and tool executions.

## Installation

```bash
<<<<<<< HEAD
# Recommended: using uv (fast, creates environment automatically)
uv install abidex

# Using pip
=======
# Recommended: using uv (faster)
uv add abidex

# Or using pip
>>>>>>> d1ff0baefb0f84aa5d7a7d3d665698bc0d47872e
pip install abidex
```

### With Optional Dependencies

```bash
# Prometheus metrics
uv install "abidex[prometheus]"
# or
pip install "abidex[prometheus]"

# Claude integration
uv install "abidex[claude]"
# or
pip install "abidex[claude]"

# CrewAI integration
uv install "abidex[crew]"
# or
pip install "abidex[crew]"

# All optional features
uv install "abidex[all]"
# or
pip install "abidex[all]"
```

**Note**: The HTTP collector dependencies (FastAPI, uvicorn) are now included by default, so the collector command works out of the box.

## CLI

Use the CLI to run demos, explore workflows, and analyze logs:

```bash
# Run demos
abidex eval simple
abidex eval weather
abidex eval fraud --transactions 50

# Discover workflows and inspect logs
abidex workflows
abidex map fraud_detection
abidex logs fraud_detection
abidex notebook fraud_detection

# Analyze logs across files
abidex-logs list
abidex-logs summary --pattern "fraud_detection_logs*.jsonl"
abidex-logs analyze --notebook fraud

# Start collector
abidex collector --port 8000
```

See `CLI_USAGE.md` for workflow configuration and full CLI examples.

## Quick Start

```python
from abidex import TelemetryClient, AgentRun
from abidex.sinks import JSONLSink

client = TelemetryClient()
client.add_sink(JSONLSink("telemetry.jsonl"))

with AgentRun("my_task", client=client) as run:
    # Your agent code here
    pass
```

## Documentation

- **[Technical Documentation](documentation/draft.md)**: Complete guide including:
  - CLI workflow & command execution
  - CLI usage guide
  - Querying agents and pipelines
  - Architecture & design decisions
  - Integration examples
- **[Examples](examples/)**: Usage examples

### Usage Examples

```python
# Decorator-based instrumentation
@client.record(model="gpt-4", backend="openai")
def generate_text(prompt):
    return openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )

# Automatic framework instrumentation
from abidex import instrumentation

# Auto-instrument OpenAI client
openai_client = instrumentation.instrument_openai_client(openai_client)
# Now all calls are automatically tracked!

# Agent-specific logging
agent_logger = get_agent_logger("my_agent")
agent_logger.thinking("I need to analyze this request...")
agent_logger.action("web_search", details={"query": "AI trends"})
agent_logger.decision("use_gpt4", reasoning="Complex query needs advanced model")
```

### Framework Integrations

#### Claude Integration

```python
from abidex.adapters import ClaudeAdapter
import anthropic

# Set up adapter
adapter = ClaudeAdapter()
client = anthropic.Anthropic(api_key="your-key")

# Track Claude API calls
with adapter.track_completion("claude-3-opus-20240229", messages) as call:
    response = client.messages.create(
        model="claude-3-opus-20240229",
        messages=messages,
        max_tokens=1000
    )
    call.set_response(response)

# Or use automatic patching
from abidex.adapters import patch_anthropic_client
client = patch_anthropic_client(client)
# Now all calls are automatically tracked
```

#### CrewAI Integration

```python
from abidex.adapters import CrewAdapter

adapter = CrewAdapter()

# Track crew execution
with adapter.track_crew_execution("research_crew", agents=["researcher", "writer"]) as crew:
    crew.set_input({"topic": "AI trends"})
    # ... execute crew ...
    crew.set_output(result)

# Track individual agent tasks
with adapter.track_agent_task("researcher", "Research AI trends") as task:
    task.set_result("Found 10 relevant articles")
```

#### n8n Integration

```python
from abidex.adapters import N8NAdapter

adapter = N8NAdapter()

# Track workflow execution
with adapter.track_workflow_execution("customer_onboarding", webhook_data) as workflow:
    workflow.set_input(webhook_data)
    # ... execute workflow ...
    workflow.set_output(result)

# Track individual nodes
with adapter.track_node_execution("http_request", "HTTP Request") as node:
    node.set_input({"url": "https://api.example.com"})
    response = make_http_request()
    node.set_output(response)
```

### Sinks and Data Export

#### JSONL File Sink

```python
from abidex.sinks import JSONLSink

# Basic file sink
sink = JSONLSink("telemetry.jsonl")

# With rotation
sink = JSONLSink(
    "telemetry.jsonl",
    max_file_size=10*1024*1024,  # 10MB
    backup_count=5
)
```

#### HTTP Sink

```python
from abidex.sinks import HTTPSink

# Send to HTTP endpoint
sink = HTTPSink(
    "https://your-collector.com/events",
    auth_token="your-token",
    batch_size=50
)

# Webhook sink
from abidex.sinks import WebhookSink
sink = WebhookSink(
    "https://your-webhook.com",
    secret="webhook-secret"
)
```

#### Prometheus Metrics

```python
from abidex.sinks import PrometheusSink

# Export metrics
sink = PrometheusSink(metric_prefix="my_agent")

# With HTTP server
from abidex.sinks import PrometheusHTTPSink
sink = PrometheusHTTPSink(port=8000)
```

### HTTP Collector

Run a centralized collector to receive telemetry from multiple agents:

```python
from abidex.collectors import create_collector_app
import uvicorn

# Create collector app
app = create_collector_app(
    auth_token="your-secret-token",
    enable_cors=True
)

# Run with uvicorn
uvicorn.run(app, host="127.0.0.1", port=8000)
```

Or use the CLI:

```bash
abidex collector --port 8000 --auth-token your-secret-token
```

Configuration defaults can be set with environment variables or `abidex.json`:

- `ABIDEX_COLLECTOR_HOST`, `ABIDEX_COLLECTOR_PORT`
- `ABIDEX_OTLP_ENDPOINT`, `ABIDEX_OTLP_TRACES_ENDPOINT`, `ABIDEX_OTLP_METRICS_ENDPOINT`
- `ABIDEX_OTLP_HEADERS` (comma-separated `key=value` pairs)

Example `abidex.json`:

```json
{
  "collector": {
    "host": "127.0.0.1",
    "port": 8000
  },
  "otel": {
    "endpoint": "http://localhost:4318",
    "headers": {
      "api-key": "your-key"
    }
  }
}
```

### Data Privacy and Redaction

```python
from abidex.utils.redaction import RedactionManager, add_redaction_rule
import re

# Add custom redaction rules
add_redaction_rule(
    "custom_id",
    re.compile(r'ID-\d{6}'),
    "[CUSTOMER_ID]"
)

# Use with sinks
sink = JSONLSink("telemetry.jsonl", redact_sensitive=True)
```

## Configuration

### Environment Variables

- `ABIDE_AGENT_ID`: Default agent ID
- `ABIDE_LOG_LEVEL`: Default log level (debug, info, warn, error)
- `ABIDE_REDACT_SENSITIVE`: Enable/disable sensitive data redaction (true/false)

### Global Client Setup

```python
from abidex import set_client, TelemetryClient
from abidex.sinks import HTTPSink

# Configure global client
client = TelemetryClient(
    agent_id="my-agent",
    default_tags={"environment": "production"}
)
client.add_sink(HTTPSink("https://your-collector.com/events"))
set_client(client)

# Now all spans will use this client by default
```

## API Reference

### Core Classes

- **`TelemetryClient`**: Main client for emitting events
- **`Event`**: Core event structure
- **`AgentRun`**: Context manager for tracking agent executions
- **`ModelCall`**: Context manager for tracking model API calls
- **`ToolCall`**: Context manager for tracking tool executions

### Sinks

- **`JSONLSink`**: Write events to JSONL files
- **`HTTPSink`**: Send events to HTTP endpoints
- **`PrometheusSink`**: Export metrics to Prometheus
- **`WebhookSink`**: Send events to webhook endpoints

### Adapters

- **`ClaudeAdapter`**: Integration with Anthropic Claude
- **`CrewAdapter`**: Integration with CrewAI
- **`N8NAdapter`**: Integration with n8n workflows

### Utilities

- **`TokenCounter`**: Estimate token usage
- **`RedactionManager`**: Handle sensitive data redaction
- **`IDGenerator`**: Generate unique identifiers

## Examples

See the `/examples` directory for complete usage examples:

- `basic_usage.py`: Simple telemetry tracking
- `claude_integration.py`: Claude API integration
- `crew_integration.py`: CrewAI workflow tracking
- `http_collector.py`: Running a telemetry collector
- `custom_sinks.py`: Creating custom sinks

- **[Technical Documentation](documentation/draft.md)**: Complete guide including:
  - CLI workflow & command execution
  - CLI usage guide
  - Querying agents and pipelines
  - Architecture & design decisions
  - Integration examples
- **[Examples](examples/)**: Usage examples

## Contributing

```bash
git clone https://github.com/abide-ai/abidex.git
cd abidex

# Install in development mode
pip install -e .[dev]
# Or using uv (faster)
uv pip install -e .[dev]

# For testing unpublished packages in other projects:
# uv pip install /path/to/abidex
# or
# uv add /path/to/abidex

pytest
```

## License

MIT License

## Support

- Issues: https://github.com/abide-ai/abidex/issues
- Discord: https://discord.gg/ZHuWhGqCm4
