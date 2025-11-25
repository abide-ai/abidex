# AbideX

AbideX is an SDK for AI agents, providing industry-standard observability and monitoring capabilities for agent workflows, model calls, and tool executions.

## Features

- **OpenTelemetry Native**: Built entirely on OpenTelemetry - all functions use OpenTelemetry APIs
- **Comprehensive Telemetry**: Track agent runs, model calls, and tool executions with detailed context
- **HTTP Collector**: FastAPI-based collector for centralized telemetry gathering
- **Enhanced Event Schema**: Built-in latency tracking, token counting, and performance metrics
- **Sampling Support**: Configurable sampling rates for high-volume scenarios
- **Data Privacy**: Automatic redaction of sensitive information
- **Easy Integration**: Simple context managers and decorators for minimal code changes
- **Multiple Sinks**: Export data to JSONL files, HTTP endpoints, OTLP (OpenTelemetry Protocol), or Prometheus metrics
- **Framework Adapters**: Built-in support for popular AI frameworks (Claude, CrewAI, n8n)
- **Automatic Instrumentation**: Decorator and monkey-patching support for popular AI libraries

## Technology Stack

### Core Technologies

- **Python 3.8+**: Modern Python with type hints and async support
- **OpenTelemetry**: Industry-standard observability framework
 
### Core Dependencies

- **FastAPI**: Modern, fast web framework for the HTTP collector
- **Uvicorn**: ASGI server for running the collector
- **Pydantic**: Data validation and settings management
- **Requests**: HTTP client for external API calls

### Optional Dependencies

- **Prometheus Client**: For Prometheus metrics export
- **Anthropic SDK**: For Claude AI integration
- **CrewAI**: For CrewAI framework integration

### Development Tools

- **pytest**: Testing framework
- **black**: Code formatter
- **isort**: Import sorter
- **flake8**: Linter
- **mypy**: Type checker
- **pre-commit**: Git hooks for code quality

### Compatible Backends

AbideX works with any OpenTelemetry-compatible backend:

- **Jaeger**: Distributed tracing backend
- **Zipkin**: Distributed tracing system
- **Prometheus**: Metrics and monitoring
- **Grafana**: Visualization and dashboards
- **Datadog**: APM and monitoring
- **New Relic**: Application performance monitoring
- **Honeycomb**: Observability platform
- **Lightstep**: Observability platform
- **Any OTLP-compatible backend**: Via OTLP exporter

### Package Management

- **pip**: Standard Python package installer
- **uv**: Fast Python package installer (recommended)

## Installation

### Basic Installation

```bash
# Recommended: using uv (fast, creates environment automatically)
uv install abidex

# Using pip
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

## Quick Start

### Using OpenTelemetry Directly

```python
from abidex import (
    trace, metrics, Span, Status, StatusCode,
    TracerProvider, MeterProvider,
    OTLPSpanExporter, OTLPMetricExporter
)
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

# Set up OpenTelemetry
tracer_provider = TracerProvider()
tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://localhost:4318/v1/traces"))
)
trace.set_tracer_provider(tracer_provider)

meter_provider = MeterProvider(
    metric_readers=[
        PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint="http://localhost:4318/v1/metrics")
        )
    ]
)
metrics.set_meter_provider(meter_provider)

# Use OpenTelemetry directly
tracer = trace.get_tracer("my_agent")
with tracer.start_as_current_span("agent_task") as span:
    span.set_attribute("agent.name", "MyAgent")
    span.set_attribute("task.type", "processing")
    # ... your agent logic ...

# Record metrics
meter = metrics.get_meter("my_agent")
counter = meter.create_counter("tasks.completed")
counter.add(1, attributes={"agent": "MyAgent"})
```

### Using AbideX Client (OpenTelemetry Backend)

```python
from abidex import TelemetryClient, AgentRun, get_logger
from abidex.sinks import JSONLSink

# Set up enhanced telemetry client with sampling
client = TelemetryClient(
    sample_rate=0.8,  # Sample 80% of events
    metadata={"version": "1.0", "environment": "production"}
)
client.add_sink(JSONLSink("telemetry.jsonl"))

# Get a telemetry-integrated logger
logger = get_logger("my_agent", client=client)

# Track an agent run with automatic performance metrics
with AgentRun("process_user_query", client=client) as run:
    run.add_data("user_id", "123")
    
    # Use context manager for automatic latency/token tracking
    with client.infer("gpt-4", "openai") as event:
        # Make your API call here
        response = openai_client.chat.completions.create(...)
        
        # Set token counts (extracted automatically with instrumentation)
        event.input_token_count = 150
        event.output_token_count = 75
        event.total_tokens = 225
    
    # Log with telemetry integration
    logger.info("Query processed successfully", 
                data={"processing_time": 1.2, "tokens_used": 225})
```

### Enhanced Features

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
uvicorn.run(app, host="0.0.0.0", port=8000)
```

Or use the CLI:

```bash
abide-collector --port 8000 --auth-token your-secret-token
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Run the test suite: `pytest`
5. Submit a pull request

## Development Setup

```bash
git clone https://github.com/abide-ai/agentkit
cd agentkit
pip install -e .[dev]
pre-commit install
```

## License

MIT License - see LICENSE file for details.

## Support

- Documentation: https://docs.abide.ai/agentkit
- Issues: https://github.com/abide-ai/agentkit/issues
- Discord: https://discord.gg/abide-ai
