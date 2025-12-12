# AbideX

OpenTelemetry-native observability SDK for AI agents, providing comprehensive telemetry for agent workflows, model calls, and tool executions.

## Installation

```bash
# Recommended: using uv (faster)
uv add abidex

# Or using pip
pip install abidex
```

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
