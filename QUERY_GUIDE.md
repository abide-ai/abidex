#  Agent and Pipeline Query Guide

Quick reference for discovering and querying agents and pipelines in your telemetry data.

## CLI Commands

### List All Agents

```bash
# List all agents from all log files
abidex-logs agents

# List agents from specific log pattern
abidex-logs agents --pattern "fraud_detection_logs*.jsonl"

# List agents from weather agent logs
abidex-logs agents --pattern "simple_agent_logs*.jsonl"
```

**Output includes:**
- Agent name
- Role (if available)
- Version (if available)
- Total events
- Unique runs
- First seen / Last seen timestamps

### List All Pipelines

```bash
# List all pipelines from all log files
abidex-logs pipelines

# List pipelines from specific pattern
abidex-logs pipelines --pattern "fraud_detection_logs*.jsonl"
```

**Output includes:**
- Pipeline ID
- Total events
- Unique runs
- Associated agents
- First seen / Last seen timestamps

## Jupyter Notebook Queries

### In the Analysis Notebook

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

## Quick Examples

### Find Most Active Agent

```python
most_active = df['agent_name'].value_counts().head(1)
print(f"Most active agent: {most_active.index[0]} with {most_active.values[0]} events")
```

### Find Agents in a Specific Pipeline

```python
pipeline_agents = df[
    df['metadata_json'].str.contains('fraud_detection', na=False)
]['agent_name'].unique()
print(f"Agents in fraud detection pipeline: {pipeline_agents}")
```

### Get Agent Statistics

```python
agent_stats = df.groupby('agent_name').agg({
    'event_id': 'count',
    'latency_ms': ['mean', 'std', 'min', 'max'],
    'success': 'mean',
    'total_tokens': 'sum'
})
print(agent_stats)
```

### Get Pipeline Statistics

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

## Using the CLI vs Notebook

**Use CLI when:**
- Quick discovery of what agents/pipelines exist
- Command-line automation
- Quick checks before detailed analysis

**Use Notebook when:**
- Need detailed analysis and visualizations
- Want to explore relationships
- Need custom queries and filtering
- Creating reports and dashboards

## Tips

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
