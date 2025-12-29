# Auto-Discovery Workflow Feature

## Overview

The enhanced `discover_workflows()` function now automatically detects workflows from log files without requiring pre-registration in `WORKFLOW_REGISTRY`. This allows users to add new workflow scripts and have them recognized automatically.

## Architecture

### Three-Phase Discovery Process

```
Phase 1: Registry-Based Discovery (Existing)
├── Process workflows from WORKFLOW_REGISTRY
├── Use known log patterns
└── Apply registry configuration

Phase 2: Pattern-Based File Scanning
├── Scan for log files using patterns:
│   ├── {workflow}_logs_*.jsonl
│   ├── {workflow}_telemetry_*.jsonl
│   └── agent_logs_*.jsonl
└── Extract workflow names from filenames

Phase 3: Content Analysis & Enrichment
├── Read sample events (first 100 lines)
├── Extract metadata:
│   ├── workflow_name (from metadata/tags)
│   ├── display_name (from metadata or inferred)
│   └── agents (from events)
├── Find matching scripts and notebooks
└── Analyze all events for statistics
```

## Filename Patterns

The system recognizes these patterns:

| Pattern | Example | Workflow Name |
|---------|---------|---------------|
| `{workflow}_logs_*.jsonl` | `customer_service_logs_20240101.jsonl` | `customer_service` |
| `{workflow}_telemetry_*.jsonl` | `fraud_detection_telemetry_20240101.jsonl` | `fraud_detection` |
| `agent_logs_*.jsonl` | `agent_logs_20240101.jsonl` | `agent` |

## Metadata Extraction

### Workflow Name Sources (Priority Order)

1. `metadata.workflow_name`
2. `metadata.workflow`
3. `metadata.pipeline`
4. `tags.workflow`
5. `tags.pipeline`
6. Filename pattern (fallback)

### Display Name Sources

1. `metadata.workflow_display_name`
2. `metadata.display_name`
3. Inferred from workflow name (e.g., `fraud_detection` → `Fraud Detection`)
4. Inferred from agent names

### Agent Extraction

- From `tags.agent` (prioritized)
- From `agent.name`
- From `agent.role` (for role information)

## Resource Discovery

### Script Discovery

Automatically searches for matching Python scripts:

- `{workflow_name}.py`
- `{workflow_name}_pipeline.py`
- `{workflow_name}_test.py`
- `{workflow_name}_agent.py`

**Search locations**: Project root directory

### Notebook Discovery

Automatically searches for matching Jupyter notebooks:

- `{workflow_name}_analysis.ipynb`
- `{workflow_name}.ipynb`

**Search locations**: 
- `notebooks/` subdirectory (first)
- Project root directory (fallback)

## Implementation Details

### Helper Functions

#### `_extract_workflow_name_from_filename(filename: str) -> Optional[str]`
Extracts workflow name from filename using regex patterns.

#### `_analyze_log_file_content(file_path: str, max_sample_lines: int = 100) -> dict`
Analyzes first 100 lines of log file to extract:
- Workflow name from metadata/tags
- Display name
- Agent names

#### `_find_matching_script(workflow_name: str, search_dir: Path) -> Optional[str]`
Searches for matching Python script files.

#### `_find_matching_notebook(workflow_name: str, search_dir: Path) -> Optional[str]`
Searches for matching Jupyter notebook files.

#### `_infer_display_name(workflow_name: str, agents: list) -> str`
Infers human-readable display name from workflow name and agents.

#### `_analyze_workflow_logs(log_files: list) -> dict`
Analyzes all log files to extract statistics:
- Total events
- Agents and their details
- Unique runs
- Last seen timestamp

## Updated Functions

### `discover_workflows()`
**Enhanced to**:
- Process registry workflows (Phase 1)
- Auto-discover new workflows (Phase 2)
- Enrich with metadata (Phase 3)
- Return combined results

**Returns**: Dict with `source` field indicating:
- `"registry"` - From WORKFLOW_REGISTRY
- `"auto_discovered"` - Auto-discovered from files

### `resolve_workflow_name(name: str)`
**Enhanced to**:
- Check registry first (existing behavior)
- Check auto-discovered workflows
- Support fuzzy matching (handles `-` vs `_`)

### `show_workflow_logs(workflow_name: str)`
**Enhanced to**:
- Work with both registry and auto-discovered workflows
- Use `discover_workflows()` instead of direct registry access

### `open_workflow_notebook(workflow_name: str, port: int)`
**Enhanced to**:
- Work with auto-discovered workflows
- Search for notebooks in `notebooks/` subdirectory
- Handle missing notebooks gracefully

## Usage Examples

### Example 1: Auto-Discover New Workflow

```bash
# User creates a new workflow script
# customer_service.py generates: customer_service_logs_20240101.jsonl

# No need to modify WORKFLOW_REGISTRY!
$ abidex workflows
# Output includes:
#   Customer Service (customer_service)
#     Agents: 3
#     Total Events: 1,234
#     Source: auto_discovered

$ abidex map customer_service
# Shows workflow map with agents

$ abidex logs customer_service
# Shows log files
```

### Example 2: Workflow with Metadata

If log files contain metadata:

```json
{
  "metadata": {
    "workflow_name": "customer_onboarding",
    "workflow_display_name": "Customer Onboarding Pipeline"
  },
  "tags": {
    "agent": "OnboardingAgent"
  }
}
```

The system will:
- Use `customer_onboarding` as workflow ID
- Use `Customer Onboarding Pipeline` as display name
- Extract `OnboardingAgent` as an agent

### Example 3: Workflow Name Inference

If no metadata is present, the system infers from filename:

```
customer_support_logs_20240101.jsonl
→ workflow_id: customer_support
→ display_name: Customer Support
```

## Benefits

1. **Zero Configuration**: New workflows automatically discovered
2. **Backward Compatible**: Existing registry workflows still work
3. **Metadata-Aware**: Extracts information from log file content
4. **Resource Discovery**: Automatically finds scripts and notebooks
5. **Flexible**: Works with or without metadata

## Limitations

1. **Performance**: Scans filesystem and reads log files (can be slow for many files)
2. **Pattern Dependency**: Relies on filename patterns
3. **No Aliases**: Auto-discovered workflows don't have aliases (can be added manually to registry)
4. **Script/Notebook Matching**: Uses simple name matching (may not find all resources)

## Future Improvements

1. **Caching**: Cache discovered workflows to avoid re-scanning
2. **Indexing**: Create index file for faster lookups
3. **Configurable Patterns**: Allow users to define custom filename patterns
4. **Better Resource Matching**: Use content analysis to match scripts/notebooks
5. **Alias Support**: Auto-generate aliases from workflow names

## Migration Guide

### For Existing Users

No changes required! Existing registry workflows continue to work.

### For New Workflows

1. **Option A**: Just create log files with correct naming pattern
   - System will auto-discover them
   - No code changes needed

2. **Option B**: Add to WORKFLOW_REGISTRY (for aliases, custom config)
   - Provides more control
   - Supports aliases and custom patterns

### Best Practices

1. **Use Consistent Naming**: Follow `{workflow}_logs_*.jsonl` pattern
2. **Include Metadata**: Add workflow metadata to events for better discovery
3. **Name Resources Consistently**: Scripts and notebooks should match workflow name
4. **Registry for Complex Cases**: Use registry for workflows needing special configuration

## Testing

To test auto-discovery:

```bash
# Create a test log file
echo '{"event_type":"log","metadata":{"workflow_name":"test_workflow"},"agent":{"name":"TestAgent"}}' > test_workflow_logs_20240101.jsonl

# Run discovery
$ abidex workflows
# Should show test_workflow

# View details
$ abidex map test_workflow
$ abidex logs test_workflow
```

