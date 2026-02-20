# Abide AgentKit CLI Usage

The Abide AgentKit now includes powerful CLI commands for running demos and analyzing telemetry data.

## Installation

After installing the package, the CLI commands are available:

```bash
# Install the package (if not already installed)
pip install -e .
```

## Available Commands

### `abidex eval` - Run Agent Demos

Run demo scenarios to test agent logging and telemetry:

```bash
# Run weather agent logging demo
abidex eval weather

# Run fraud detection pipeline demo
abidex eval fraud

# Run fraud detection with custom transaction count
abidex eval fraud --transactions 50

# Run a custom demo script without registry config
abidex eval custom_demo --script-path ./examples/custom_demo.py
```

**Options:**
- `WORKFLOW` - Workflow ID or alias from your workflow config
- `--transactions N` - Number of transactions to process (default: 25, fraud demo only)
- `--output-dir DIR` - Directory to save log files (default: current directory)
- `--script-path PATH` - Explicit demo script path (overrides workflow config)

### Workflow Configuration

Workflow-aware commands (like `eval`, `notebook`, and `logs analyze`) are driven by
configured workflows. Define them in one of the following locations:

- `workflows.json` or `.abidex_workflows.json` in the repo root or current directory
- `ABIDEX_WORKFLOW_CONFIG` for a specific config file path
- `ABIDEX_WORKFLOW_DIR` for a directory of workflow config JSON files

Each workflow entry should include `id`, `display_name`, `script`, `notebook`, and
`log_patterns` (or `log_pattern`), plus optional `aliases`.

### `abidex logs` - Analyze Telemetry Logs

Analyze and visualize telemetry data from agent runs:

```bash
# List all log files
abidex logs list

# List fraud detection logs
abidex logs list --pattern "fraud_detection_logs*.jsonl"

# Get quick summary of logs
abidex logs summary

# Get summary of specific pattern
abidex logs summary --pattern "weather_agent_logs*.jsonl"

# List all agents found in logs
abidex logs agents

# List all agents from fraud detection logs
abidex logs agents --pattern "fraud_detection_logs*.jsonl"

# List all pipelines found in logs
abidex logs pipelines

# List pipelines from specific pattern
abidex logs pipelines --pattern "*agent_logs*.jsonl"

# Open Jupyter notebook for analysis
abidex logs analyze

# Open fraud detection analysis notebook
abidex logs analyze --notebook fraud

# Open notebook on custom port
abidex logs analyze --port 9999
```

**Subcommands:**
- `list` - List all log files matching pattern with file sizes
- `summary` - Quick statistics about events, agents, and event types
- `agents` - List all unique agents with details (role, version, runs, timestamps)
- `pipelines` - List all unique pipelines with details (agents, runs, timestamps)
- `analyze` - Opens Jupyter notebook for interactive analysis

**Options:**
- `--pattern PATTERN` - Glob pattern to match log files (default: `*agent_logs*.jsonl`)
- `--notebook WORKFLOW_OR_PATH` - Workflow name or notebook path (defaults to first available)
- `--port PORT` - Port for Jupyter notebook server (default: 8888)

### `abidex collector` - Start Telemetry Collector

Start the HTTP collector server for receiving telemetry events:

```bash
abidex collector --port 8000
```

## Examples

### Complete Workflow

```bash
# 1. Run the fraud detection demo
abidex eval fraud --transactions 30

# 2. Check what logs were generated
abidex logs list

# 3. Get a quick summary
abidex logs summary --pattern "fraud_detection_logs*.jsonl"

# 4. Open the analysis notebook
abidex logs analyze --notebook fraud
```

### Quick Test

```bash
# Run weather demo
abidex eval weather

# View the logs
abidex logs list
abidex logs summary
```

## What Gets Generated

### Weather Demo (`eval weather`)
- Generates: `weather_agent_logs_YYYYMMDD_HHMMSS.jsonl`
- Shows: Weather agent logging, model calls, metrics, errors

### Fraud Detection Demo (`eval fraud`)
- Generates: `fraud_detection_logs_YYYYMMDD_HHMMSS.jsonl`
- Shows: Complete 3-agent pipeline with:
  - Agent thinking, actions, decisions, observations
  - Risk analysis and fraud detection
  - Multi-channel alerting
  - Comprehensive telemetry

## Analysis Notebooks

The `logs analyze` command opens Jupyter notebooks that provide:

- **Workflow-specific analysis** (`--notebook <workflow>`):
  - Uses the notebook path defined in your workflow config
  - Falls back to the first available notebook if `--notebook` is omitted
  - You can also pass a direct notebook file path

## Requirements

- **For demos**: No additional requirements (uses core SDK)
- **For analysis**: `jupyter` and `pandas` (install with `pip install jupyter pandas matplotlib seaborn`)
- **For collector**: `fastapi` and `uvicorn` (install with `pip install abidex[collector]`)

## Troubleshooting

**Command not found:**
```bash
# Make sure package is installed
pip install -e .

# Or use Python module syntax
python -m abidex.cli eval weather
```

**Notebook not found:**
- Make sure you've run a demo first to generate log files
- The notebooks are in the package directory

**Import errors:**
- Install optional dependencies: `pip install jupyter pandas matplotlib seaborn`
- For collector: `pip install abidex[collector]`
