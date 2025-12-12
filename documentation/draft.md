# AbideX Architecture & Technical Documentation

## Table of Contents
1. [CLI Workflow & Command Execution](#cli-workflow--command-execution)
2. [CLI Usage Guide](#cli-usage-guide)
3. [Querying Agents and Pipelines](#querying-agents-and-pipelines)
4. [High-Level Architecture](#high-level-architecture)
5. [Component Flow](#component-flow)
6. [Data Flow](#data-flow)
7. [Design Decisions](#design-decisions)
8. [Data Structures & Key Variables](#data-structures--key-variables)
9. [Data Capture Points](#data-capture-points)
10. [File-by-File Breakdown](#file-by-file-breakdown)
11. [Code Flow & Patterns](#code-flow--patterns)
12. [OpenTelemetry Integration](#opentelemetry-integration)
13. [Integration Points](#integration-points)
14. [Performance & Security](#performance--security)
15. [Component-to-File Mapping](#component-to-file-mapping)

---

## CLI Workflow & Command Execution

### Overview

The AbideX CLI provides commands for running evaluations, discovering workflows, collecting telemetry, and analyzing results. Understanding the execution order is crucial for proper workflow.

### Available Commands

#### 1. `abidex workflows` - Discover Workflows
**Purpose**: Lists all discovered workflows in your codebase.

**When to run**: First step - run this to see what workflows are available.

**What it does**:
- Scans your codebase for workflow definitions
- Registers workflows in the `WORKFLOW_REGISTRY`
- Displays available workflows with their metadata

**Example**:
```bash
abidex workflows
# Output:
# Available workflows:
#   - simple_agent_test
#   - fraud_detection_pipeline
```

**Execution Flow**:
```
abidex workflows
    │
    ├─→ Scan codebase for workflow files
    ├─→ Parse workflow definitions
    ├─→ Register in WORKFLOW_REGISTRY
    └─→ Display list of workflows
```

#### 2. `abidex workflows map` - Visualize Workflow Structure
**Purpose**: Shows a visual map/diagram of workflow structure.

**When to run**: After discovering workflows, to understand their structure.

**What it does**:
- Generates a visual representation of workflow components
- Shows relationships between agents, tasks, and tools
- Helps understand workflow architecture

**Example**:
```bash
abidex workflows map simple_agent_test
```

**Execution Flow**:
```
abidex workflows map <workflow_name>
    │
    ├─→ Load workflow from registry
    ├─→ Parse workflow structure
    ├─→ Generate visualization
    └─→ Display workflow map
```

#### 3. `abidex evals` (or `abidex eval`) - Run Evaluations
**Purpose**: Executes evaluation scripts/workflows with telemetry collection.

**When to run**: After discovering workflows, to actually run them and collect telemetry.

**What it does**:
- Runs the specified workflow/evaluation script
- Automatically collects telemetry during execution
- Writes telemetry data to JSONL files or sends to collector
- Creates spans, metrics, and logs for analysis

**Example**:
```bash
abidex evals simple_agent_test
# or
abidex eval fraud_detection_pipeline
```

**Execution Flow**:
```
abidex evals <workflow_name>
    │
    ├─→ Load workflow from registry
    ├─→ Initialize TelemetryClient
    │   ├─→ Set up OpenTelemetry providers
    │   ├─→ Configure sinks (JSONL, HTTP, etc.)
    │   └─→ Create tracer and meter
    │
    ├─→ Execute workflow script
    │   ├─→ AgentRun context manager starts
    │   ├─→ Model calls tracked
    │   ├─→ Tool calls tracked
    │   ├─→ Logs captured
    │   └─→ AgentRun context manager ends
    │
    ├─→ Flush telemetry data
    ├─→ Close sinks
    └─→ Display execution summary
```

**What happens during execution**:
1. **Initialization**: TelemetryClient sets up OpenTelemetry providers
2. **Workflow Start**: Creates `AgentRun` span, emits `AGENT_RUN_START` event
3. **Execution**: Tracks all model calls, tool calls, and logs
4. **Workflow End**: Creates `AGENT_RUN_END` event, calculates metrics
5. **Export**: Data written to JSONL files or sent to HTTP collector

#### 4. `abidex collector` - Start HTTP Collector Server
**Purpose**: Starts a FastAPI server to receive telemetry events from remote agents.

**When to run**: 
- **Before** running evals if you want centralized telemetry collection
- In a separate terminal/process for production deployments

**What it does**:
- Starts FastAPI HTTP server (default port 8000)
- Receives telemetry events via REST API
- Supports batch event submission
- Can forward events to other backends

**Example**:
```bash
# Terminal 1: Start collector
abidex collector --port 8000

# Terminal 2: Run evals (they'll send to collector)
abidex evals simple_agent_test --collector-url http://localhost:8000
```

**Execution Flow**:
```
abidex collector
    │
    ├─→ Create FastAPI app
    ├─→ Initialize HTTPCollector
    ├─→ Set up routes:
    │   ├─→ POST /events (single event)
    │   └─→ POST /events/batch (batch events)
    ├─→ Start uvicorn server
    └─→ Listen for incoming events
```

#### 5. `abidex workflows logs` - View Telemetry Logs
**Purpose**: Displays telemetry logs from JSONL files.

**When to run**: After running evals, to view collected telemetry.

**What it does**:
- Reads JSONL files from default location
- Filters and displays events
- Can filter by workflow, run_id, event_type, etc.

**Example**:
```bash
abidex workflows logs simple_agent_test
abidex workflows logs --run-id run-123
```

**Execution Flow**:
```
abidex workflows logs [options]
    │
    ├─→ Find JSONL files
    ├─→ Parse events
    ├─→ Apply filters
    └─→ Display formatted output
```

#### 6. `abidex notebook` - Open Analysis Notebook
**Purpose**: Launches Jupyter notebook for analyzing telemetry data.

**When to run**: After collecting telemetry, to analyze results.

**What it does**:
- Opens pre-configured analysis notebook
- Loads telemetry data from JSONL files
- Provides visualization and analysis tools

**Example**:
```bash
abidex notebook simple_agent_test
# Opens: agent_logs_analysis.ipynb or fraud_detection_analysis.ipynb
```

**Execution Flow**:
```
abidex notebook <workflow_name>
    │
    ├─→ Find corresponding notebook
    ├─→ Load telemetry data
    ├─→ Start Jupyter server
    └─→ Open notebook in browser
```

### Typical Workflow Sequences

#### Sequence 1: Local Development & Analysis

```bash
# Step 1: Discover available workflows
abidex workflows

# Step 2: Understand workflow structure (optional)
abidex workflows map simple_agent_test

# Step 3: Run evaluation (telemetry written to local JSONL files)
abidex evals simple_agent_test

# Step 4: View logs
abidex workflows logs simple_agent_test

# Step 5: Analyze in notebook
abidex notebook simple_agent_test
```

**Data Flow**:
```
abidex evals
    │
    └─→ TelemetryClient
        │
        ├─→ JSONLSink → agent_logs.jsonl (local file)
        └─→ OpenTelemetry → ConsoleSpanExporter (console output)
```

#### Sequence 2: Centralized Collection (Production)

```bash
# Terminal 1: Start collector server
abidex collector --port 8000 --auth-token my-secret-token

# Terminal 2: Run evaluations (send to collector)
abidex evals simple_agent_test \
    --collector-url http://localhost:8000 \
    --collector-token my-secret-token

# Terminal 3: View collected logs
abidex workflows logs --collector-url http://localhost:8000
```

**Data Flow**:
```
abidex evals
    │
    └─→ TelemetryClient
        │
        ├─→ HTTPSink → POST /events/batch → Collector Server
        │   └─→ Collector → Forward to backends (Jaeger, Datadog, etc.)
        └─→ JSONLSink → agent_logs.jsonl (backup/local)
```

#### Sequence 3: OTLP Export (Production Monitoring)

```bash
# Run with OTLP endpoint (e.g., Jaeger, Datadog)
abidex evals simple_agent_test \
    --otlp-endpoint http://jaeger:4317 \
    --otlp-headers "api-key=your-key"
```

**Data Flow**:
```
abidex evals
    │
    └─→ TelemetryClient
        │
        └─→ OTLPSpanExporter → Jaeger/Datadog/Backend
            └─→ BatchSpanProcessor (background thread)
```

### Command Dependencies & Order

```
┌─────────────────────────────────────────────────────────┐
│ 1. abidex workflows                                     │
│    (Discovers workflows - no dependencies)              │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. abidex workflows map [optional]                     │
│    (Visualizes workflow - depends on #1)                │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3a. abidex collector [if using centralized collection]  │
│     (Start server - run in separate terminal)          │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3b. abidex evals <workflow>                            │
│     (Runs workflow - depends on #1, optionally #3a)   │
│     - Creates telemetry data                            │
│     - Writes to JSONL files                            │
│     - Optionally sends to collector                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 4. abidex workflows logs [optional]                    │
│    (Views logs - depends on #3b)                        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 5. abidex notebook [optional]                         │
│    (Analyzes data - depends on #3b)                    │
└─────────────────────────────────────────────────────────┘
```

### Key Points

1. **`abidex workflows` is typically first** - You need to discover workflows before running them
2. **`abidex evals` is the main execution command** - This is where telemetry collection happens
3. **`abidex collector` is optional** - Only needed for centralized collection
4. **Order matters**: Workflows → Evals → Logs/Notebook
5. **Collector can run independently** - Start it before or after workflows discovery, but before evals if you want centralized collection

### Configuration Options

**For `abidex evals`**:
- `--output-dir`: Where to write JSONL files
- `--collector-url`: HTTP collector endpoint
- `--otlp-endpoint`: OTLP backend endpoint
- `--sample-rate`: Sampling rate (0.0-1.0)
- `--no-console`: Disable console output

**For `abidex collector`**:
- `--port`: Server port (default: 8000)
- `--auth-token`: Authentication token
- `--cors`: Enable CORS
- `--host`: Bind address

---

## CLI Usage Guide

### Installation

After installing the package, the CLI commands are available:

```bash
# Install the package (if not already installed)
pip install -e .
```

### Available Commands

#### `abidex eval` - Run Agent Demos

Run demo scenarios to test agent logging and telemetry:

```bash
# Run simple agent logging demo
abidex eval simple

# Run fraud detection pipeline demo
abidex eval fraud

# Run fraud detection with custom transaction count
abidex eval fraud --transactions 50
```

**Options:**
- `simple` - Basic agent logging demonstration
- `fraud` - Complete fraud detection pipeline with 3 agents
- `--transactions N` - Number of transactions to process (default: 25, fraud demo only)
- `--output-dir DIR` - Directory to save log files (default: current directory)

#### `abidex logs` - Analyze Telemetry Logs

Analyze and visualize telemetry data from agent runs:

```bash
# List all log files
abidex logs list

# List fraud detection logs
abidex logs list --pattern "fraud_detection_logs*.jsonl"

# Get quick summary of logs
abidex logs summary

# Get summary of specific pattern
abidex logs summary --pattern "simple_agent_logs*.jsonl"

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
- `--notebook {agent,fraud}` - Which notebook to open (default: `agent`)
- `--port PORT` - Port for Jupyter notebook server (default: 8888)

#### `abidex collector` - Start Telemetry Collector

Start the HTTP collector server for receiving telemetry events:

```bash
abidex collector --port 8000
```

### Complete Workflow Examples

#### Example 1: Complete Analysis Workflow

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

#### Example 2: Quick Test

```bash
# Run simple demo
abidex eval simple

# View the logs
abidex logs list
abidex logs summary
```

### What Gets Generated

#### Simple Demo (`eval simple`)
- Generates: `simple_agent_logs_YYYYMMDD_HHMMSS.jsonl`
- Shows: Basic agent logging, model calls, metrics, errors

#### Fraud Detection Demo (`eval fraud`)
- Generates: `fraud_detection_logs_YYYYMMDD_HHMMSS.jsonl`
- Shows: Complete 3-agent pipeline with:
  - Agent thinking, actions, decisions, observations
  - Risk analysis and fraud detection
  - Multi-channel alerting
  - Comprehensive telemetry

### Analysis Notebooks

The `logs analyze` command opens Jupyter notebooks that provide:

- **Agent Logs Analysis** (`--notebook agent`):
  - General agent telemetry analysis
  - Event type distributions
  - Performance metrics
  - Time series analysis

- **Fraud Detection Analysis** (`--notebook fraud`):
  - Specialized fraud detection metrics
  - Agent behavior analysis (thinking, actions, decisions)
  - Risk assessment patterns
  - Decision reasoning quality
  - OpenTelemetry-style comprehensive metrics

### Requirements

- **For demos**: No additional requirements (uses core SDK)
- **For analysis**: `jupyter` and `pandas` (install with `pip install jupyter pandas matplotlib seaborn`)
- **For collector**: `fastapi` and `uvicorn` (install with `uv add abidex[collector]` or `pip install abidex[collector]`)

### Troubleshooting

**Command not found:**
```bash
# Make sure package is installed
pip install -e .

# Or use Python module syntax
python -m abidex.cli eval simple
```

**Notebook not found:**
- Make sure you've run a demo first to generate log files
- The notebooks are in the package directory

**Import errors:**
- Install optional dependencies: `pip install jupyter pandas matplotlib seaborn`
- For collector: `uv add abidex[collector]` (or `pip install abidex[collector]`)

---

## Querying Agents and Pipelines

### Overview

This section provides a quick reference for discovering and querying agents and pipelines in your telemetry data using both CLI commands and Jupyter notebook queries.

### CLI Commands for Discovery

#### List All Agents

```bash
# List all agents from all log files
abidex logs agents

# List agents from specific log pattern
abidex logs agents --pattern "fraud_detection_logs*.jsonl"

# List agents from simple agent logs
abidex logs agents --pattern "simple_agent_logs*.jsonl"
```

**Output includes:**
- Agent name
- Role (if available)
- Version (if available)
- Total events
- Unique runs
- First seen / Last seen timestamps

#### List All Pipelines

```bash
# List all pipelines from all log files
abidex logs pipelines

# List pipelines from specific pattern
abidex logs pipelines --pattern "fraud_detection_logs*.jsonl"
```

**Output includes:**
- Pipeline ID
- Total events
- Unique runs
- Associated agents
- First seen / Last seen timestamps

### Jupyter Notebook Queries

The fraud detection analysis notebook includes a dedicated section for agent and pipeline discovery. You can also use these pandas queries:

#### Get All Unique Agents

```python
# Simple list of agent names
unique_agents = df['agent_name'].dropna().unique()
print(unique_agents)

# Detailed agent summary
agent_summary = df[df['agent_name'].notna()].groupby('agent_name').agg({
    'event_id': 'count',
    'agent_role': 'first',
    'agent_version': 'first',
    'run_id': 'nunique',
    'timestamp': ['min', 'max']
})
print(agent_summary)
```

#### Get All Pipelines

```python
# Extract pipelines from metadata
pipelines = []
for idx, row in df[df['metadata_json'].notna()].iterrows():
    try:
        metadata = json.loads(row['metadata_json'])
        pipeline_id = metadata.get('pipeline_id') or metadata.get('pipeline') or metadata.get('system')
        if pipeline_id:
            pipelines.append(pipeline_id)
    except:
        pass

unique_pipelines = list(set(pipelines))
print(unique_pipelines)
```

#### Query Events by Agent

```python
# Get all events for a specific agent
risk_agent_events = df[df['agent_name'] == 'Risk Analysis Agent']

# Get agent performance metrics
agent_perf = df[df['agent_name'] == 'Data Collection Agent'].groupby('event_type').agg({
    'latency_ms': 'mean',
    'success': 'mean'
})
```

#### Query Events by Pipeline

```python
# Get all events for a specific pipeline
fraud_pipeline_events = df[
    (df['metadata_json'].str.contains('fraud_detection', na=False)) |
    (df['tags_json'].str.contains('fraud_detection', na=False))
]

# Get pipeline summary
pipeline_summary = fraud_pipeline_events.groupby('agent_name').agg({
    'event_id': 'count',
    'latency_ms': 'mean',
    'success': 'mean'
})
```

#### Agent-Pipeline Relationships

```python
# Find which agents work in which pipelines
agent_pipeline = df.groupby(['agent_name', 'metadata_json']).size()

# Or extract from metadata
agent_pipeline_map = {}
for idx, row in df[df['metadata_json'].notna()].iterrows():
    try:
        metadata = json.loads(row['metadata_json'])
        pipeline_id = metadata.get('pipeline_id') or metadata.get('pipeline')
        agent_name = row['agent_name']
        
        if pipeline_id and agent_name:
            if pipeline_id not in agent_pipeline_map:
                agent_pipeline_map[pipeline_id] = set()
            agent_pipeline_map[pipeline_id].add(agent_name)
    except:
        pass

for pipeline, agents in agent_pipeline_map.items():
    print(f"{pipeline}: {', '.join(agents)}")
```

### Quick Query Examples

#### Find Most Active Agent

```python
most_active = df['agent_name'].value_counts().head(1)
print(f"Most active agent: {most_active.index[0]} with {most_active.values[0]} events")
```

#### Find Agents in a Specific Pipeline

```python
pipeline_agents = df[
    df['metadata_json'].str.contains('fraud_detection', na=False)
]['agent_name'].unique()
print(f"Agents in fraud detection pipeline: {pipeline_agents}")
```

#### Get Agent Statistics

```python
agent_stats = df.groupby('agent_name').agg({
    'event_id': 'count',
    'latency_ms': ['mean', 'std', 'min', 'max'],
    'success': 'mean',
    'total_tokens': 'sum'
})
print(agent_stats)
```

#### Get Pipeline Statistics

```python
# Filter by pipeline
pipeline_events = df[df['tags_json'].str.contains('fraud_detection', na=False)]

pipeline_stats = pipeline_events.groupby('agent_name').agg({
    'event_id': 'count',
    'latency_ms': 'mean',
    'success': 'mean'
})
print(pipeline_stats)
```

### Using the CLI vs Notebook

**Use CLI when:**
- Quick discovery of what agents/pipelines exist
- Command-line automation
- Quick checks before detailed analysis

**Use Notebook when:**
- Need detailed analysis and visualizations
- Want to explore relationships
- Need custom queries and filtering
- Creating reports and dashboards

### Query Tips

1. **Pipeline Identification**: Pipelines are identified by:
   - `metadata.pipeline_id`
   - `metadata.pipeline`
   - `metadata.system`
   - `tags.pipeline`
   - `tags.system`

2. **Agent Information**: Agent details are in:
   - `agent.name` - Agent name
   - `agent.role` - Agent role (e.g., "decision-maker", "data-processor")
   - `agent.version` - Agent version

3. **Filtering**: Use pandas boolean indexing for complex queries:
   ```python
   # Multiple conditions
   filtered = df[
       (df['agent_name'] == 'Risk Analysis Agent') &
       (df['latency_ms'] > 100) &
       (df['success'] == True)
   ]
   ```

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Your AI Agent Code                         │
│  (Python scripts, Jupyter notebooks, production services)    │
│  Files: simple_agent_test.py, fraud_detection_pipeline.py    │
└──────────────────────┬────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    AbideX SDK                                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  TelemetryClient (Core Engine)                       │  │
│  │  File: abidex/client.py                              │  │
│  │  - Event construction                                 │  │
│  │  - OpenTelemetry setup                                │  │
│  │  - Span/metric creation                               │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────┴─────────────────────────────────────┐  │
│  │  Context Managers (Spans)                               │  │
│  │  File: abidex/spans.py                                  │  │
│  │  - AgentRun, ModelCall, ToolCall                        │  │
│  │  - SpanContext base class                               │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────┴─────────────────────────────────────┐  │
│  │  Loggers (Structured Logging)                           │  │
│  │  File: abidex/logger.py                                │  │
│  │  - TelemetryLogger, AgentLogger                         │  │
│  │  - TelemetryLogHandler                                  │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────┴─────────────────────────────────────┐  │
│  │  Instrumentation (Auto-tracking)                        │  │
│  │  File: abidex/instrumentation.py                        │  │
│  │  - Auto-instrument AI libraries                        │  │
│  └──────────────────┬─────────────────────────────────────┘  │
│                     │                                        │
│  ┌──────────────────┴─────────────────────────────────────┐  │
│  │  Adapters (Framework Integrations)                      │  │
│  │  Files: abidex/adapters/                               │  │
│  │  - claude_adapter.py (Anthropic Claude)                 │  │
│  │  - crew_adapter.py (CrewAI)                             │  │
│  │  - n8n_adapter.py (n8n workflows)                       │  │
│  └──────────────────┬─────────────────────────────────────┘  │
└─────────────────────┼────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              OpenTelemetry Integration Layer                │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  TracerProvider & MeterProvider Setup                 │  │
│  │  File: abidex/client.py (lines 325-383)               │  │
│  │  - Resource creation                                  │  │
│  │  - Span processors (Simple/Batch)                     │  │
│  │  - Metric readers (PeriodicExporting)                 │  │
│  │  - Global provider registration                       │  │
│  └──────────────────┬─────────────────────────────────────┘  │
└─────────────────────┼────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│                    Export Layer (Sinks)                     │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  JSONL File Sink                                     │  │
│  │  File: abidex/sinks/jsonl_sink.py                    │  │
│  │  - File writing with rotation                        │  │
│  │  - Reentrant locks                                   │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  HTTP Sink                                           │  │
│  │  File: abidex/sinks/http_sink.py                     │  │
│  │  - Batching with background threads                  │  │
│  │  - Retry logic                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Prometheus Sink                                      │  │
│  │  File: abidex/sinks/prometheus_sink.py                │  │
│  │  - Prometheus metrics export                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  OTLP Export (via OpenTelemetry)                     │  │
│  │  File: abidex/client.py (OTLPSpanExporter)           │  │
│  │  - Direct OpenTelemetry export                       │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────┬────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              HTTP Collector (Optional)                      │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastAPI-based Collector                             │  │
│  │  File: abidex/collectors/http_collector.py            │  │
│  │  - REST API for receiving events                     │  │
│  │  - Batch processing                                   │  │
│  │  - CORS support                                       │  │
│  └──────────────────┬─────────────────────────────────────┘  │
└─────────────────────┼────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│              Monitoring & Analysis Backends                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │  Jaeger  │  │  Zipkin  │  │ Datadog  │  │ Grafana  │  │
│  │  (UI)    │  │  (UI)    │  │  (APM)   │  │(Dashboards)│ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Local Analysis                                       │  │
│  │  Files: *.jsonl files, *.ipynb notebooks             │  │
│  │  - agent_logs_analysis.ipynb                         │  │
│  │  - fraud_detection_analysis.ipynb                    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Supporting Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Utilities                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Redaction                                           │  │
│  │  File: abidex/utils/redaction.py                     │  │
│  │  - Sensitive data redaction                          │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Token Counter                                       │  │
│  │  File: abidex/utils/token_counter.py                 │  │
│  │  - Token estimation                                  │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  ID Utils                                            │  │
│  │  File: abidex/utils/id_utils.py                       │  │
│  │  - ID generation                                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    CLI Interface                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Command-Line Interface                               │  │
│  │  File: abidex/cli.py                                  │  │
│  │  - Demo execution (eval)                               │  │
│  │  - Collector server (collector)                        │  │
│  │  - Workflow discovery (workflows, map, logs)          │  │
│  │  - Notebook launcher (notebook)                        │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Flow

### 1. Agent Code → AbideX SDK
```python
# Your code uses high-level abstractions
with AgentRun("task", client=client):
    with client.infer("gpt-4", "openai"):
        # Your LLM call
```

### 2. AbideX SDK → OpenTelemetry
```python
# AbideX converts to OpenTelemetry spans/metrics
tracer = trace.get_tracer("abidex")
with tracer.start_as_current_span("agent.run") as span:
    span.set_attribute("agent.name", "MyAgent")
    # ...
```

### 3. OpenTelemetry → Exporters
```python
# OpenTelemetry exporters send to backends
span_exporter = OTLPSpanExporter(endpoint="...")
processor = BatchSpanProcessor(span_exporter)
```

### 4. Exporters → Backends
- OTLP → Jaeger, Zipkin, Datadog, etc.
- JSONL → Local files for analysis
- HTTP → Custom endpoints
- Prometheus → Metrics collection

---

## Data Flow

```
Agent Execution
    │
    ├─→ AgentRun (span)
    │   File: abidex/spans.py (AgentRun class)
    │       │
    │       ├─→ ModelCall (child span)
    │       │   File: abidex/client.py (infer() method)
    │       │       ├─→ Input tokens (set by user)
    │       │       ├─→ Output tokens (set by user)
    │       │       └─→ Latency (calculated automatically)
    │       │
    │       ├─→ ToolCall (child span)
    │       │   File: abidex/spans.py (ToolCall class)
    │       │       └─→ Execution time (calculated automatically)
    │       │
    │       └─→ Logs (events)
    │           File: abidex/logger.py (AgentLogger class)
    │               ├─→ Thinking (logger.thinking())
    │               ├─→ Actions (logger.action())
    │               └─→ Decisions (logger.decision())
    │
    └─→ Metrics
        File: abidex/client.py (metric() method)
            ├─→ Model calls counter (automatic)
            ├─→ Error counter (automatic)
            └─→ Latency histogram (automatic)
```

### Event Processing Flow

```
1. Event Creation
   File: abidex/client.py (Event dataclass)
   │
   ├─→ Event.to_dict()
   │   File: abidex/client.py (Event.to_dict() method)
   │   └─→ Convert to dictionary
   │
   ├─→ Sampling Check
   │   File: abidex/client.py (TelemetryClient.emit())
   │   └─→ Set event.sampled based on sample_rate
   │
   ├─→ Redaction (if enabled)
   │   File: abidex/utils/redaction.py (redact_sensitive_data())
   │   └─→ Redact sensitive data patterns
   │
   └─→ Send to Sinks
       File: abidex/client.py (TelemetryClient.emit())
       │
       ├─→ JSONLSink.send()
       │   File: abidex/sinks/jsonl_sink.py
       │   └─→ Write to file (with lock)
       │
       ├─→ HTTPSink.send()
       │   File: abidex/sinks/http_sink.py
       │   └─→ Queue for batching (background thread)
       │
       └─→ OpenTelemetry Export
           File: abidex/client.py (via span processors)
           └─→ Via OTLPSpanExporter or ConsoleSpanExporter
```

---

## Design Decisions

### 1. OpenTelemetry-Native Architecture

**Decision**: Build directly on OpenTelemetry APIs, not a wrapper.

**Rationale**:
- Industry standard (CNCF project)
- No vendor lock-in
- Works with existing monitoring infrastructure
- Future-proof

**Implementation**:
- `TelemetryClient` directly uses `TracerProvider` and `MeterProvider`
- All spans are OpenTelemetry spans
- All metrics are OpenTelemetry metrics
- Events are converted to OpenTelemetry attributes

**Trade-offs**:
- ✅ Standard format, wide compatibility
- ✅ No abstraction layer overhead
- ⚠️ Requires OpenTelemetry knowledge for advanced use

### 2. Dual Span Processor Strategy

**Decision**: Use `SimpleSpanProcessor` for console, `BatchSpanProcessor` for OTLP.

**Rationale**:
- `BatchSpanProcessor` uses background threads that prevent clean exit
- Console mode is for demos/development (clean exit important)
- OTLP mode is for production (performance important)

**Implementation** (`client.py:327-340`):
```python
if otlp_endpoint:
    # Production: Use BatchSpanProcessor for performance
    self.span_processor = BatchSpanProcessor(span_exporter)
else:
    # Development: Use SimpleSpanProcessor (no background threads)
    self.span_processor = SimpleSpanProcessor(span_exporter)
```

**Trade-offs**:
- ✅ Clean exit in console mode
- ✅ Better performance in production
- ⚠️ Two code paths to maintain

### 3. No Metrics Export for Console Mode

**Decision**: Don't use `PeriodicExportingMetricReader` in console mode.

**Rationale**:
- `PeriodicExportingMetricReader` has background threads
- Prevents clean process exit
- Metrics can still be recorded, just not exported

**Implementation** (`client.py:354-370`):
```python
if otlp_endpoint:
    # Production: Export metrics
    metric_reader = PeriodicExportingMetricReader(metric_exporter)
    metric_readers.append(metric_reader)
    self.metric_reader = metric_reader
else:
    # Development: Don't export (no background threads)
    self.metric_reader = None
```

**Trade-offs**:
- ✅ Clean exit in console mode
- ⚠️ Metrics not visible in console mode
- ✅ Metrics still recorded for OTLP mode

### 4. Reentrant Locks in Sinks

**Decision**: Use `RLock` instead of `Lock` in JSONL sink.

**Rationale**:
- `close()` method calls `flush()` while holding the lock
- Regular `Lock` would deadlock
- `RLock` allows same thread to acquire lock multiple times

**Implementation** (`jsonl_sink.py:35`):
```python
self._lock = RLock()  # Use reentrant lock to avoid deadlock in close()
```

**Trade-offs**:
- ✅ Prevents deadlocks
- ⚠️ Slightly more overhead
- ✅ Safer for cleanup operations

### 5. Structured Event Schema

**Decision**: Use nested dataclasses for event structure.

**Rationale**:
- Type safety
- Clear structure
- Easy to serialize/deserialize
- Self-documenting

**Implementation** (`client.py:44-110`):
```python
@dataclass
class Event:
    agent: AgentInfo
    action: ActionInfo
    model_call: ModelCallInfo
    telemetry: TelemetryInfo
    metadata: Dict[str, Any]
    # ...
```

**Trade-offs**:
- ✅ Type safety and validation
- ✅ Clear structure
- ⚠️ More verbose than dict

### 6. Context Manager Pattern

**Decision**: Use context managers for tracking spans.

**Rationale**:
- Automatic start/end tracking
- Exception handling built-in
- Clean API
- Pythonic

**Implementation** (`spans.py`):
```python
with AgentRun("task", client=client) as run:
    # Automatic start/end tracking
    pass
```

**Trade-offs**:
- ✅ Clean API
- ✅ Automatic cleanup
- ✅ Exception handling
- ⚠️ Requires context manager usage

---

## Data Structures & Key Variables

### Core Data Structures

#### 1. `Event` (`client.py:85-110`)

**Purpose**: Main event structure containing all telemetry data.

**Key Fields**:
```python
@dataclass
class Event:
    # Identifiers
    trace_id: str                    # Distributed trace ID
    conversation_id: Optional[str]   # Conversation/session ID
    event_id: str                    # Unique event ID
    event_type: EventType            # Type of event
    
    # Structured data sections
    agent: AgentInfo                 # Agent information
    action: ActionInfo               # Action/tool information
    model_call: ModelCallInfo        # Model call information
    telemetry: TelemetryInfo         # Timing/performance data
    metadata: Dict[str, Any]         # Custom metadata
    
    # Context
    run_id: Optional[str]            # Agent run ID
    span_id: Optional[str]           # Span ID
    parent_id: Optional[str]         # Parent span ID
    
    # Status
    success: bool = True
    error: Optional[str] = None
    level: str = "info"
    
    # Sampling
    sampled: bool = True
```

**Key Variables**:
- `trace_id`: Links related events across services
- `run_id`: Groups events within an agent run
- `span_id`: Identifies specific span
- `event_type`: Determines event category (AGENT_RUN_START, MODEL_CALL_END, etc.)

#### 2. `AgentInfo` (`client.py:44-49`)

**Purpose**: Agent identification and metadata.

```python
@dataclass
class AgentInfo:
    name: Optional[str] = None      # Agent name
    role: Optional[str] = None      # Agent role (decision-maker, etc.)
    version: Optional[str] = None   # Agent version
```

**Captured At**: 
- Agent initialization
- Agent run start
- Logger creation

#### 3. `ActionInfo` (`client.py:52-60`)

**Purpose**: Action/tool execution information.

```python
@dataclass
class ActionInfo:
    type: Optional[str] = None       # 'tool_call', 'api_call', etc.
    name: Optional[str] = None       # Action name
    input: Optional[str] = None      # Action input (truncated to 200 chars)
    output: Optional[str] = None      # Action output (truncated to 500 chars)
    success: bool = True
    latency_ms: Optional[float] = None
```

**Captured At**:
- Tool call start/end
- Action execution
- API calls

#### 4. `ModelCallInfo` (`client.py:63-71`)

**Purpose**: LLM model call information.

```python
@dataclass
class ModelCallInfo:
    backend: Optional[str] = None              # 'openai', 'anthropic', etc.
    model: Optional[str] = None                # 'gpt-4', 'claude-3', etc.
    prompt_preview: Optional[str] = None        # Truncated to 500 chars
    completion_preview: Optional[str] = None    # Truncated to 500 chars
    input_token_count: Optional[int] = None
    output_token_count: Optional[int] = None
```

**Captured At**:
- Model call start (model, backend)
- Model call end (tokens, completion)

#### 5. `TelemetryInfo` (`client.py:74-81`)

**Purpose**: Performance and timing data.

```python
@dataclass
class TelemetryInfo:
    timestamp_start: float                      # Unix timestamp
    timestamp_end: Optional[float] = None
    latency_ms: Optional[float] = None          # Calculated from timestamps
    total_tokens: Optional[int] = None          # Sum of input + output tokens
    throughput_tokens_per_sec: Optional[float] = None  # Calculated metric
```

**Calculated Fields**:
- `latency_ms`: `(timestamp_end - timestamp_start) * 1000`
- `total_tokens`: `input_token_count + output_token_count`
- `throughput_tokens_per_sec`: `output_token_count / (latency_ms / 1000)`

### TelemetryClient Key Variables

#### Instance Variables (`client.py:305-311`)

```python
class TelemetryClient:
    # Identity
    agent_id: str                    # Unique agent ID (UUID if not provided)
    
    # Configuration
    sinks: List[TelemetrySink]       # Export destinations
    default_tags: Dict[str, str]      # Default tags for all events
    sample_rate: float                # Sampling rate (0.0-1.0)
    metadata: Dict[str, Any]         # Custom metadata
    
    # OpenTelemetry
    tracer_provider: TracerProvider  # OpenTelemetry tracer provider
    meter_provider: MeterProvider     # OpenTelemetry meter provider
    span_processor: SpanProcessor    # Span processor (Simple or Batch)
    metric_reader: Optional[MetricReader]  # Metric reader (None for console)
    
    # Tracers and Meters
    tracer: Tracer                   # OpenTelemetry tracer
    meter: Meter                      # OpenTelemetry meter
    
    # Metrics
    model_calls_counter: Counter      # Counter for model calls
    model_latency_histogram: Histogram # Histogram for model latency
    errors_counter: Counter           # Counter for errors
```

### SpanContext Key Variables (`spans.py:20-41`)

```python
class SpanContext:
    span_id: str                      # Unique span ID (UUID)
    span_type: str                    # 'agent_run', 'model_call', 'tool_call'
    name: str                         # Span name
    client: TelemetryClient           # Telemetry client
    run_id: Optional[str]             # Parent run ID
    parent_id: Optional[str]          # Parent span ID
    tags: Dict[str, str]              # Span tags
    data: Dict[str, Any]              # Span data
    start_time: Optional[float]       # Start timestamp
    end_time: Optional[float]        # End timestamp
    error: Optional[Exception]        # Error if any
    otel_span: Optional[Span]         # OpenTelemetry span object
```

---

## Data Capture Points

### 1. Agent Run Tracking

**Location**: `spans.py:AgentRun`

**Captured Data**:
- Start timestamp (`start_time`)
- End timestamp (`end_time`)
- Run ID (generated UUID)
- Agent name and role
- Run metadata (user_id, task_type, etc.)

**Code Flow**:
```python
with AgentRun("task_name", client=client) as run:
    # 1. AgentRun.__enter__() called
    #    - Generates run_id
    #    - Creates OpenTelemetry span
    #    - Sets start_time
    #    - Emits AGENT_RUN_START event
    
    # 2. User code executes
    
    # 3. AgentRun.__exit__() called
    #    - Sets end_time
    #    - Calculates latency_ms
    #    - Emits AGENT_RUN_END event
    #    - Ends OpenTelemetry span
```

**Key Variables Captured**:
- `run.run_id`: Unique run identifier
- `run.span_id`: Span identifier
- `run.start_time`: Start timestamp
- `run.end_time`: End timestamp

### 2. Model Call Tracking

**Location**: `client.py:TelemetryClient.infer()` (lines 789-820)

**Captured Data**:
- Model name and backend
- Input/output token counts
- Latency
- Prompt/completion previews (truncated)

**Code Flow**:
```python
with client.infer("gpt-4", "openai") as span:
    # 1. infer() creates OpenTelemetry span
    #    - Sets attributes: model, backend, batch_size
    #    - Records start_time
    
    # 2. User makes API call
    response = openai_client.chat.completions.create(...)
    
    # 3. User sets token counts
    span.set_attribute("input_token_count", 150)
    span.set_attribute("output_token_count", 75)
    
    # 4. __exit__() called
    #    - Calculates latency_ms
    #    - Records to histogram
    #    - Increments counter
    #    - Ends span
```

**Key Variables Captured**:
- `model`: Model name (e.g., "gpt-4")
- `backend`: Backend name (e.g., "openai")
- `input_token_count`: Input tokens
- `output_token_count`: Output tokens
- `latency_ms`: Call duration

### 3. Tool Call Tracking

**Location**: `spans.py:ToolCall`

**Captured Data**:
- Tool name and type
- Input/output (truncated)
- Execution time
- Success/failure

**Code Flow**:
```python
with ToolCall("web_search", client=client) as tool:
    # 1. ToolCall.__enter__() called
    #    - Creates span
    #    - Sets start_time
    
    # 2. Tool executes
    result = web_search(query)
    
    # 3. Set input/output
    tool.set_input(query)
    tool.set_output(result)
    
    # 4. __exit__() called
    #    - Calculates latency
    #    - Ends span
```

### 4. Logging Integration

**Location**: `logger.py:TelemetryLogger` and `AgentLogger`

**Captured Data**:
- Log level (debug, info, warn, error)
- Message
- Context data
- Agent information (for AgentLogger)

**Code Flow**:
```python
logger = get_agent_logger("MyAgent", client=client)

logger.thinking("I need to analyze...")
# Creates Event with:
# - event_type: LOG
# - level: debug
# - tags: {event_type: "thinking", agent: "MyAgent"}
# - metadata: {thought: "...", context: {...}}

logger.action("web_search", details={...})
# Creates Event with:
# - event_type: LOG
# - level: info
# - tags: {event_type: "action", agent: "MyAgent"}
# - metadata: {action: "web_search", details: {...}}
```

**Key Variables Captured**:
- `level`: Log level
- `message`: Log message
- `data`: Additional context
- `tags`: Structured tags
- `agent.name`: Agent name (for AgentLogger)

### 5. Error Tracking

**Location**: `client.py:TelemetryClient.error()` (lines 378-395)

**Captured Data**:
- Exception type and message
- Stack trace
- Context information
- Error attributes

**Code Flow**:
```python
try:
    # Some code
except Exception as e:
    client.error(e, context={"retry_count": 1})
    # Creates:
    # - Error span with ERROR status
    # - Records exception
    # - Increments error counter
    # - Emits error event
```

**Key Variables Captured**:
- `error_type`: Exception class name
- `error_message`: Exception message
- `context`: Additional context
- `span.status`: Set to ERROR

### 6. Metrics Collection

**Location**: `client.py:TelemetryClient.metric()` (lines 368-376)

**Captured Data**:
- Metric name
- Metric value
- Unit
- Attributes/tags

**Code Flow**:
```python
client.metric("response_time", 250.5, unit="ms")
# Records to OpenTelemetry histogram with:
# - name: "response_time"
# - value: 250.5
# - attributes: {unit: "ms"}
```

**Key Variables Captured**:
- `name`: Metric name
- `value`: Metric value
- `unit`: Unit of measurement
- `attributes`: Additional attributes

---

## File-by-File Breakdown

### Core Files

#### `abidex/client.py` (930 lines)

**Purpose**: Core telemetry client and event structures.

**Key Classes**:
- `EventType`: Enum of event types
- `AgentInfo`, `ActionInfo`, `ModelCallInfo`, `TelemetryInfo`: Data structures
- `Event`: Main event dataclass
- `TelemetryClient`: Core client class

**Key Functions**:
- `TelemetryClient.__init__()`: Initialize OpenTelemetry providers
- `TelemetryClient.emit()`: Emit event to sinks
- `TelemetryClient.span()`: Create OpenTelemetry span
- `TelemetryClient.infer()`: Track model calls
- `TelemetryClient.metric()`: Record metrics
- `TelemetryClient.error()`: Record errors
- `TelemetryClient.close()`: Shutdown and cleanup

**Key Variables**:
- `self.tracer_provider`: OpenTelemetry tracer provider
- `self.meter_provider`: OpenTelemetry meter provider
- `self.span_processor`: Span processor (Simple or Batch)
- `self.metric_reader`: Metric reader (None for console)
- `self.sinks`: List of export sinks
- `self.sample_rate`: Sampling rate

**Design Patterns**:
- Factory pattern for event creation
- Strategy pattern for span processors
- Observer pattern for sinks

#### `abidex/spans.py` (394 lines)

**Purpose**: Context managers for tracking spans.

**Key Classes**:
- `SpanContext`: Base span context
- `AgentRun`: Agent run tracking
- `ModelCall`: Model call tracking
- `ToolCall`: Tool call tracking

**Key Functions**:
- `SpanContext.start()`: Start OpenTelemetry span
- `SpanContext.end()`: End span and calculate metrics
- `AgentRun.__enter__()`: Start agent run
- `AgentRun.__exit__()`: End agent run
- `ModelCall.__enter__()`: Start model call
- `ModelCall.__exit__()`: End model call

**Key Variables**:
- `self.span_id`: Unique span ID
- `self.run_id`: Parent run ID
- `self.otel_span`: OpenTelemetry span object
- `self.start_time`, `self.end_time`: Timing

**Design Patterns**:
- Context manager pattern
- Template method pattern (SpanContext base class)

#### `abidex/logger.py` (465 lines)

**Purpose**: Logging integration with telemetry.

**Key Classes**:
- `TelemetryLogHandler`: Python logging handler
- `TelemetryLogger`: Standard logger
- `AgentLogger`: Agent-specific logger

**Key Functions**:
- `TelemetryLogger._create_event()`: Create event from log
- `AgentLogger.thinking()`: Log agent thinking
- `AgentLogger.action()`: Log agent action
- `AgentLogger.decision()`: Log agent decision
- `get_logger()`: Factory for TelemetryLogger
- `get_agent_logger()`: Factory for AgentLogger

**Key Variables**:
- `self.client`: Telemetry client
- `self.run_id`, `self.span_id`: Context IDs
- `self.agent_name`, `self.agent_role`: Agent info (AgentLogger)

**Design Patterns**:
- Adapter pattern (Python logging → Telemetry)
- Factory pattern for logger creation

### Sink Files

#### `abidex/sinks/jsonl_sink.py` (161 lines)

**Purpose**: Export events to JSONL files.

**Key Classes**:
- `JSONLSink`: JSONL file sink
- `RotatingJSONLSink`: Rotating file sink

**Key Functions**:
- `JSONLSink.send()`: Write event to file
- `JSONLSink.flush()`: Flush file buffer
- `JSONLSink.close()`: Close file
- `JSONLSink._rotate_file()`: Rotate log file

**Key Variables**:
- `self._file`: File handle
- `self._lock`: Reentrant lock (RLock)
- `self.file_path`: File path
- `self.max_file_size`: Max size before rotation
- `self.backup_count`: Number of backup files

**Design Patterns**:
- Strategy pattern for file rotation

#### `abidex/sinks/http_sink.py` (275 lines)

**Purpose**: Export events to HTTP endpoints.

**Key Classes**:
- `HTTPSink`: HTTP sink with batching
- `StreamingHTTPSink`: Immediate HTTP sink

**Key Functions**:
- `HTTPSink.send()`: Queue event for batching
- `HTTPSink._batch_worker()`: Background thread for batching
- `HTTPSink._send_batch()`: Send batched events
- `HTTPSink.flush()`: Flush pending events
- `HTTPSink.close()`: Stop worker thread

**Key Variables**:
- `self._queue`: Event queue
- `self._batch`: Current batch
- `self._thread`: Background worker thread
- `self._running`: Thread control flag
- `self.batch_size`: Batch size
- `self.batch_timeout`: Batch timeout

**Design Patterns**:
- Producer-consumer pattern
- Thread pool pattern

### Collector Files

#### `abidex/collectors/http_collector.py` (403 lines)

**Purpose**: HTTP server for receiving telemetry.

**Key Classes**:
- `HTTPCollector`: FastAPI-based collector
- `EventData`, `BatchEventRequest`: Pydantic models

**Key Functions**:
- `create_collector_app()`: Create FastAPI app
- `HTTPCollector.receive_event()`: Receive single event
- `HTTPCollector.receive_batch()`: Receive batch events

**Key Variables**:
- `self.client`: Telemetry client
- `self.stats`: Statistics dictionary
- `self.max_batch_size`: Max batch size
- `self.auth_token`: Authentication token

**Design Patterns**:
- REST API pattern
- Middleware pattern (CORS, auth)

### Adapter Files

#### `abidex/adapters/claude_adapter.py`

**Purpose**: Track Anthropic Claude API calls.

**Key Functions**:
- `ClaudeAdapter.track_completion()`: Track Claude completion
- `patch_anthropic_client()`: Auto-patch client

#### `abidex/adapters/crew_adapter.py`

**Purpose**: Track CrewAI workflows.

**Key Functions**:
- `CrewAdapter.track_crew_execution()`: Track crew run
- `CrewAdapter.track_agent_task()`: Track agent task

### Utility Files

#### `abidex/utils/redaction.py`

**Purpose**: Redact sensitive data.

**Key Functions**:
- `redact_sensitive_data()`: Redact data in event
- `add_redaction_rule()`: Add custom redaction rule

**Key Variables**:
- `REDACTION_RULES`: Dictionary of redaction patterns

#### `abidex/utils/token_counter.py`

**Purpose**: Estimate token counts.

**Key Functions**:
- `estimate_tokens()`: Estimate token count
- `count_tokens()`: Count tokens in text

### CLI File

#### `abidex/cli.py` (1050 lines)

**Purpose**: Command-line interface.

**Key Functions**:
- `main()`: CLI entry point
- `run_eval_demo()`: Run demo scripts
- `collector_main()`: Start HTTP collector
- `list_workflows()`: List discovered workflows
- `show_workflow_map()`: Show workflow visualization
- `open_workflow_notebook()`: Open analysis notebook

**Key Variables**:
- `WORKFLOW_REGISTRY`: Registry of known workflows

---

## Code Flow & Patterns

### Event Lifecycle

```
1. User Code
   │
   ├─→ AgentRun.__enter__()
   │   │
   │   ├─→ Generate run_id
   │   ├─→ Create OpenTelemetry span
   │   ├─→ Set start_time
   │   └─→ Emit AGENT_RUN_START event
   │
   ├─→ ModelCall.__enter__()
   │   │
   │   ├─→ Create child span
   │   ├─→ Set model/backend attributes
   │   └─→ Set start_time
   │
   ├─→ User makes API call
   │   │
   │   └─→ Set token counts
   │
   ├─→ ModelCall.__exit__()
   │   │
   │   ├─→ Calculate latency
   │   ├─→ Record to histogram
   │   ├─→ Increment counter
   │   └─→ End span
   │
   └─→ AgentRun.__exit__()
       │
       ├─→ Calculate total latency
       ├─→ Emit AGENT_RUN_END event
       └─→ End span
```

### Span Creation Flow

```
1. client.span() or context manager
   │
   ├─→ Get current tracer
   │   └─→ trace.get_tracer("abidex")
   │
   ├─→ Start span
   │   └─→ tracer.start_as_current_span(name, attributes)
   │
   ├─→ Set attributes
   │   └─→ span.set_attribute(key, value)
   │
   └─→ End span
       └─→ span.end()
```

---

## OpenTelemetry Integration

### TracerProvider Setup

**Location**: `client.py:325-342`

```python
# Create resource with service info
resource = Resource.create({
    "service.name": service_name,
    "service.version": service_version,
    "agent.id": self.agent_id,
    **self.metadata
})

# Create tracer provider
self.tracer_provider = TracerProvider(resource=resource)

# Add span processor
self.tracer_provider.add_span_processor(self.span_processor)

# Set as global
trace.set_tracer_provider(self.tracer_provider)
```

### MeterProvider Setup

**Location**: `client.py:372-383`

```python
# Create meter provider
self.meter_provider = MeterProvider(
    resource=resource,
    metric_readers=metric_readers  # Empty for console mode
)

# Set as global
metrics.set_meter_provider(self.meter_provider)

# Get meter
self.meter = metrics.get_meter("abidex", version=service_version)
```

### Span Attributes

**Common Attributes Set**:
- `span.type`: Span type (agent_run, model_call, tool_call)
- `span.name`: Span name
- `run_id`: Run identifier
- `parent_id`: Parent span ID
- `model`: Model name (for model calls)
- `backend`: Backend name (for model calls)
- `latency_ms`: Duration in milliseconds

### Metrics Created

**Counters**:
- `abidex.model.calls`: Total model calls
- `abidex.errors`: Total errors

**Histograms**:
- `abidex.model.latency`: Model call latency
- Custom metrics via `client.metric()`

---

## Integration Points

### 1. Direct OpenTelemetry
```python
from abidex import trace, metrics
tracer = trace.get_tracer("my_agent")
# Use OpenTelemetry directly
```

### 2. High-Level Abstractions
```python
from abidex import TelemetryClient, AgentRun
client = TelemetryClient()
with AgentRun("task", client=client):
    # Automatic telemetry
```

### 3. Framework Adapters
```python
from abidex.adapters import ClaudeAdapter
adapter = ClaudeAdapter()
with adapter.track_completion("claude-3", messages):
    # Tracked automatically
```

### 4. Logging Integration
```python
from abidex import get_agent_logger
logger = get_agent_logger("MyAgent")
logger.thinking("...")
logger.action("...")
```

### Event Schema

```json
{
  "event_type": "agent.run",
  "agent": {
    "name": "MyAgent",
    "role": "decision-maker",
    "id": "agent-123"
  },
  "action": {
    "name": "process_query",
    "input": {...},
    "output": {...}
  },
  "model_call": {
    "model": "gpt-4",
    "backend": "openai",
    "input_token_count": 150,
    "output_token_count": 75,
    "total_tokens": 225
  },
  "telemetry": {
    "timestamp_start_iso": "2024-01-01T12:00:00Z",
    "timestamp_end_iso": "2024-01-01T12:00:01Z",
    "latency_ms": 1250.5
  },
  "metadata": {
    "version": "1.0",
    "environment": "production"
  },
  "run_id": "run-123",
  "span_id": "span-456",
  "trace_id": "trace-789"
}
```

---

## Performance & Security

### Performance Considerations

1. **Sampling**: Configurable sampling rates for high-volume scenarios
2. **Batching**: BatchSpanProcessor batches spans for efficiency
3. **Async**: Can be used with async/await (OpenTelemetry supports it)
4. **Background Threads**: Only used for OTLP export, not console

### Security Considerations

1. **Redaction**: Automatic redaction of sensitive data (SSNs, credit cards)
2. **Custom Rules**: Add custom redaction patterns
3. **Auth**: HTTP sinks support authentication tokens
4. **SSL**: Configurable SSL verification

---

## Component-to-File Mapping

Quick reference for finding where each component is implemented:

| Component | File(s) | Key Classes/Functions |
|-----------|---------|----------------------|
| **Core Client** | `abidex/client.py` | `TelemetryClient`, `Event`, `EventType` |
| **Context Managers** | `abidex/spans.py` | `AgentRun`, `ModelCall`, `ToolCall`, `SpanContext` |
| **Loggers** | `abidex/logger.py` | `TelemetryLogger`, `AgentLogger`, `TelemetryLogHandler` |
| **Instrumentation** | `abidex/instrumentation.py` | Auto-instrumentation functions |
| **Claude Adapter** | `abidex/adapters/claude_adapter.py` | `ClaudeAdapter` |
| **CrewAI Adapter** | `abidex/adapters/crew_adapter.py` | `CrewAdapter` |
| **n8n Adapter** | `abidex/adapters/n8n_adapter.py` | `N8NAdapter` |
| **JSONL Sink** | `abidex/sinks/jsonl_sink.py` | `JSONLSink`, `RotatingJSONLSink` |
| **HTTP Sink** | `abidex/sinks/http_sink.py` | `HTTPSink`, `StreamingHTTPSink` |
| **Prometheus Sink** | `abidex/sinks/prometheus_sink.py` | `PrometheusSink`, `PrometheusHTTPSink` |
| **HTTP Collector** | `abidex/collectors/http_collector.py` | `HTTPCollector`, `create_collector_app()` |
| **Redaction** | `abidex/utils/redaction.py` | `redact_sensitive_data()`, `add_redaction_rule()` |
| **Token Counter** | `abidex/utils/token_counter.py` | `estimate_tokens()`, `count_tokens()` |
| **ID Utils** | `abidex/utils/id_utils.py` | ID generation functions |
| **CLI** | `abidex/cli.py` | `main()`, `run_eval_demo()`, `collector_main()` |
| **Public API** | `abidex/__init__.py` | Exports and re-exports |
| **Demo Scripts** | `simple_agent_test.py`, `fraud_detection_pipeline.py` | Demo implementations |
| **Analysis Notebooks** | `agent_logs_analysis.ipynb`, `fraud_detection_analysis.ipynb` | Analysis examples |

---

## Key Takeaways

1. **OpenTelemetry-Native**: Not a wrapper, direct use of OpenTelemetry APIs
2. **Dual Strategy**: SimpleSpanProcessor for dev, BatchSpanProcessor for prod
3. **Structured Events**: Type-safe dataclasses with nested structures
4. **Context Managers**: Automatic tracking with clean API
5. **Multiple Export Paths**: JSONL, HTTP, OTLP, Prometheus
6. **Thread Safety**: Reentrant locks prevent deadlocks
7. **Clean Exit**: Console mode avoids background threads
8. **Sampling Support**: Configurable sampling for high-volume scenarios
9. **Redaction**: Automatic sensitive data redaction
10. **Extensible**: Easy to add new sinks, adapters, collectors
