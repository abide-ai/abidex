# AbideX CLI Architecture Diagram

## Overview

This document describes the architecture of the AbideX CLI, showing how commands are structured, routed, and how they interact with each other.

---

## High-Level Architecture

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000'}}}%%
graph TB
    Start([User runs: abidex]) --> Main[main function]
    Main --> Parse[argparse.parse_args]
    Parse --> Route{main_command?}
    
    Route -->|collector| Collector[collector_main]
    Route -->|eval| Eval[run_eval_demo]
    Route -->|workflows| Workflows[list_workflows]
    Route -->|map| Map[show_workflow_map]
    Route -->|logs| Logs[show_workflow_logs]
    Route -->|notebook| Notebook[open_workflow_notebook]
    Route -->|None| Help[print_help & exit]
    
    Collector --> HTTP[HTTP Collector Server]
    Eval --> Script[Run Demo Script]
    Script --> LogFiles[Generate .jsonl Files]
    
    Workflows --> Discover[discover_workflows]
    Map --> Discover
    Logs --> Discover
    Notebook --> Discover
    
    Discover --> Registry[WORKFLOW_REGISTRY]
    Discover --> Glob[glob.glob patterns]
    Discover --> ReadLogs[Read JSONL Files]
    
    ReadLogs --> Analyze[Analyze Events]
    Analyze --> Output[Display Results]
    
    style Start fill:#4a90e2,stroke:#000000,stroke-width:2px,color:#ffffff
    style Main fill:#f5a623,stroke:#000000,stroke-width:2px,color:#000000
    style Discover fill:#7ed321,stroke:#000000,stroke-width:2px,color:#000000
    style LogFiles fill:#bd10e0,stroke:#000000,stroke-width:2px,color:#ffffff
    style Output fill:#50e3c2,stroke:#000000,stroke-width:2px,color:#000000
```

---

## Command Flow Diagram

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000', 'fontSize':'16px', 'fontFamily':'Arial, sans-serif'}}}%%
graph TB
    subgraph Entry[" "]
        A["CLI Entry: abidex"] --> B["main()"]
    end
    
    subgraph Routing[" "]
        B --> C{"Parse Args"}
        C -->|collector| D1["collector"]
        C -->|eval| D2["eval"]
        C -->|workflows| D3["workflows"]
        C -->|map| D4["map"]
        C -->|logs| D5["logs"]
        C -->|notebook| D6["notebook"]
    end
    
    subgraph Collector[" "]
        D1 --> E1["collector_main"]
        E1 --> E2["create_collector_app"]
        E2 --> E3["uvicorn.run"]
        E3 --> E4["HTTP Server"]
    end
    
    subgraph Eval[" "]
        D2 --> F1["run_eval_demo"]
        F1 --> F2{"Demo Type?"}
        F2 -->|simple| F3["simple_agent_test.py"]
        F2 -->|fraud| F4["fraud_detection_pipeline.py"]
        F3 --> F5["Generate Logs"]
        F4 --> F5
    end
    
    subgraph Discovery[" "]
        D3 --> G1["list_workflows"]
        D4 --> G2["show_workflow_map"]
        D5 --> G3["show_workflow_logs"]
        D6 --> G4["open_workflow_notebook"]
        
        G1 --> H1["discover_workflows"]
        G2 --> H1
        G3 --> H1
        G4 --> H1
        
        H1 --> H2["WORKFLOW_REGISTRY"]
        H1 --> H3["glob.glob"]
        H3 --> H4["Read JSONL"]
        H4 --> H5["Parse Events"]
        H5 --> H6["Extract Metadata"]
    end
    
    style A fill:#4a90e2,stroke:#000000,stroke-width:4px,color:#ffffff
    style B fill:#f5a623,stroke:#000000,stroke-width:4px,color:#000000
    style C fill:#ffffff,stroke:#000000,stroke-width:4px,color:#000000
    style D1 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style D2 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style D3 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style D4 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style D5 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style D6 fill:#e8f5e9,stroke:#000000,stroke-width:3px,color:#000000
    style E1 fill:#b3e5fc,stroke:#000000,stroke-width:3px,color:#000000
    style E2 fill:#b3e5fc,stroke:#000000,stroke-width:3px,color:#000000
    style E3 fill:#b3e5fc,stroke:#000000,stroke-width:3px,color:#000000
    style E4 fill:#50e3c2,stroke:#000000,stroke-width:3px,color:#000000
    style F1 fill:#ffe0b2,stroke:#000000,stroke-width:3px,color:#000000
    style F2 fill:#ffffff,stroke:#000000,stroke-width:3px,color:#000000
    style F3 fill:#ffe0b2,stroke:#000000,stroke-width:3px,color:#000000
    style F4 fill:#ffe0b2,stroke:#000000,stroke-width:3px,color:#000000
    style F5 fill:#bd10e0,stroke:#000000,stroke-width:4px,color:#ffffff
    style G1 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style G2 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style G3 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style G4 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style H1 fill:#7ed321,stroke:#000000,stroke-width:4px,color:#000000
    style H2 fill:#ffcdd2,stroke:#000000,stroke-width:3px,color:#000000
    style H3 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style H4 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style H5 fill:#c8e6c9,stroke:#000000,stroke-width:3px,color:#000000
    style H6 fill:#50e3c2,stroke:#000000,stroke-width:3px,color:#000000
```

---

## Detailed Command Flow

### 1. Collector Command Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000', 'actorBkgColor':'#ffffff', 'actorBorderColor':'#000000', 'actorTextColor':'#000000', 'signalColor':'#000000', 'signalTextColor':'#000000', 'labelBoxBkgColor':'#ffffff', 'labelBoxBorderColor':'#000000', 'labelTextColor':'#000000', 'loopTextColor':'#000000', 'noteBkgColor':'#fff9c4', 'noteBorderColor':'#000000', 'noteTextColor':'#000000', 'activationBorderColor':'#000000', 'activationBkgColor':'#e1f5ff'}}}%%
sequenceDiagram
    participant User
    participant CLI
    participant Collector
    participant FastAPI
    participant Uvicorn
    
    User->>CLI: abidex collector --port 8000
    CLI->>CLI: Parse arguments
    CLI->>Collector: collector_main(args)
    Collector->>Collector: Check COLLECTOR_AVAILABLE
    Collector->>Collector: Create TelemetryClient
    Collector->>Collector: Add JSONLSink (if --output-file)
    Collector->>Collector: Add HTTPSink (if --forward-url)
    Collector->>FastAPI: create_collector_app()
    FastAPI->>FastAPI: Setup routes (/events, /health)
    Collector->>Uvicorn: uvicorn.run(app, port=8000)
    Uvicorn->>User: Server running on port 8000
```

### 2. Eval Command Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000', 'actorBkgColor':'#ffffff', 'actorBorderColor':'#000000', 'actorTextColor':'#000000', 'signalColor':'#000000', 'signalTextColor':'#000000', 'labelBoxBkgColor':'#ffffff', 'labelBoxBorderColor':'#000000', 'labelTextColor':'#000000', 'loopTextColor':'#000000', 'noteBkgColor':'#fff9c4', 'noteBorderColor':'#000000', 'noteTextColor':'#000000', 'activationBorderColor':'#000000', 'activationBkgColor':'#e1f5ff'}}}%%
sequenceDiagram
    participant User
    participant CLI
    participant Eval
    participant Script
    participant TelemetryClient
    participant JSONLSink
    
    User->>CLI: abidex eval fraud --transactions 50
    CLI->>CLI: Parse arguments
    CLI->>Eval: run_eval_demo("fraud", 50, ".")
    Eval->>Eval: Determine script path
    Eval->>Eval: Set FRAUD_DEMO_TRANSACTIONS=50
    Eval->>Script: subprocess.run(fraud_detection_pipeline.py)
    Script->>TelemetryClient: Create client
    Script->>JSONLSink: Create sink with log file
    Script->>TelemetryClient: Run pipeline
    TelemetryClient->>JSONLSink: Write events
    JSONLSink->>JSONLSink: Save to fraud_detection_logs_*.jsonl
    Script->>Eval: Exit with return code
    Eval->>User: Demo complete
```

### 3. Workflow Discovery Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000', 'actorBkgColor':'#ffffff', 'actorBorderColor':'#000000', 'actorTextColor':'#000000', 'signalColor':'#000000', 'signalTextColor':'#000000', 'labelBoxBkgColor':'#ffffff', 'labelBoxBorderColor':'#000000', 'labelTextColor':'#000000', 'loopTextColor':'#000000', 'noteBkgColor':'#fff9c4', 'noteBorderColor':'#000000', 'noteTextColor':'#000000', 'activationBorderColor':'#000000', 'activationBkgColor':'#e1f5ff'}}}%%
sequenceDiagram
    participant User
    participant CLI
    participant Command
    participant Discover
    participant Registry
    participant FileSystem
    participant Parser
    
    User->>CLI: abidex workflows
    CLI->>Command: list_workflows()
    Command->>Discover: discover_workflows()
    Discover->>Registry: Iterate WORKFLOW_REGISTRY
    Registry->>Discover: Get log_pattern for each workflow
    Discover->>FileSystem: glob.glob(log_pattern)
    FileSystem->>Discover: Return matching log files
    Discover->>FileSystem: Open each log file
    FileSystem->>Parser: Read JSONL lines
    Parser->>Discover: Parse JSON events
    Discover->>Discover: Extract agents, events, runs
    Discover->>Command: Return workflow dict
    Command->>User: Display workflow list
```

### 4. Map/Logs/Notebook Command Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000', 'actorBkgColor':'#ffffff', 'actorBorderColor':'#000000', 'actorTextColor':'#000000', 'signalColor':'#000000', 'signalTextColor':'#000000', 'labelBoxBkgColor':'#ffffff', 'labelBoxBorderColor':'#000000', 'labelTextColor':'#000000', 'loopTextColor':'#000000', 'noteBkgColor':'#fff9c4', 'noteBorderColor':'#000000', 'noteTextColor':'#000000', 'activationBorderColor':'#000000', 'activationBkgColor':'#e1f5ff'}}}%%
sequenceDiagram
    participant User
    participant CLI
    participant Command
    participant Resolve
    participant Discover
    participant Registry
    
    User->>CLI: abidex map fraud_detection
    CLI->>Command: show_workflow_map("fraud_detection")
    Command->>Resolve: resolve_workflow_name("fraud_detection")
    Resolve->>Registry: Check WORKFLOW_REGISTRY
    Registry->>Resolve: Return "fraud_detection" (canonical ID)
    Resolve->>Command: Return workflow_id
    Command->>Discover: discover_workflows()
    Discover->>Command: Return workflows dict
    Command->>Command: Check if workflow_id exists
    Command->>Command: Extract agents, last calls, stats
    Command->>User: Display workflow map
```

---

## Data Flow Diagram

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000'}}}%%
graph TD
    subgraph "Data Sources"
        A1[WORKFLOW_REGISTRY<br/>Hardcoded Config]
        A2[Log Files<br/>*.jsonl]
        A3[Notebooks<br/>*.ipynb]
        A4[Scripts<br/>*.py]
    end
    
    subgraph "Discovery Layer"
        B1[discover_workflows]
        B2[resolve_workflow_name]
        B3[glob.glob]
    end
    
    subgraph "Processing Layer"
        C1[Parse JSONL Events]
        C2[Extract Agents]
        C3[Extract Metadata]
        C4[Calculate Stats]
    end
    
    subgraph "Command Layer"
        D1[list_workflows]
        D2[show_workflow_map]
        D3[show_workflow_logs]
        D4[open_workflow_notebook]
    end
    
    subgraph "Output"
        E1[Console Output]
        E2[Jupyter Notebook]
        E3[Log Files]
    end
    
    A1 --> B1
    A2 --> B3
    A3 --> D4
    A4 --> D4
    
    B3 --> B1
    B1 --> C1
    B2 --> D2
    B2 --> D3
    B2 --> D4
    
    C1 --> C2
    C1 --> C3
    C2 --> C4
    C3 --> C4
    
    C4 --> D1
    C4 --> D2
    C4 --> D3
    
    D1 --> E1
    D2 --> E1
    D3 --> E1
    D4 --> E2
    
    style A1 fill:#ffcdd2,stroke:#000000,stroke-width:2px,color:#000000
    style A2 fill:#c8e6c9,stroke:#000000,stroke-width:2px,color:#000000
    style B1 fill:#ffe0b2,stroke:#000000,stroke-width:2px,color:#000000
    style C1 fill:#b3e5fc,stroke:#000000,stroke-width:2px,color:#000000
    style E1 fill:#e1bee7,stroke:#000000,stroke-width:2px,color:#000000
    style E2 fill:#e1bee7,stroke:#000000,stroke-width:2px,color:#000000
```

---

## Command Dependencies

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000'}}}%%
graph TB
    subgraph "Independent Commands"
        C1[collector<br/>Standalone]
        C2[eval<br/>Generates Data]
    end
    
    subgraph "Discovery-Dependent Commands"
        C3[workflows<br/>Needs: Log Files]
        C4[map<br/>Needs: Log Files + Registry]
        C5[logs<br/>Needs: Log Files + Registry]
        C6[notebook<br/>Needs: Log Files + Registry + Notebook]
    end
    
    C2 -->|Generates| LogFiles[Log Files<br/>*.jsonl]
    LogFiles --> C3
    LogFiles --> C4
    LogFiles --> C5
    LogFiles --> C6
    
    Registry[WORKFLOW_REGISTRY] --> C4
    Registry --> C5
    Registry --> C6
    
    Notebooks[Notebook Files<br/>*.ipynb] --> C6
    
    style C1 fill:#c8e6c9,stroke:#000000,stroke-width:2px,color:#000000
    style C2 fill:#c8e6c9,stroke:#000000,stroke-width:2px,color:#000000
    style C3 fill:#fff9c4,stroke:#000000,stroke-width:2px,color:#000000
    style C4 fill:#fff9c4,stroke:#000000,stroke-width:2px,color:#000000
    style C5 fill:#fff9c4,stroke:#000000,stroke-width:2px,color:#000000
    style C6 fill:#fff9c4,stroke:#000000,stroke-width:2px,color:#000000
    style LogFiles fill:#e1bee7,stroke:#000000,stroke-width:2px,color:#000000
    style Registry fill:#ffcdd2,stroke:#000000,stroke-width:2px,color:#000000
    style Notebooks fill:#b3e5fc,stroke:#000000,stroke-width:2px,color:#000000
```

---

## Function Call Hierarchy

```
main()
├── argparse.ArgumentParser()
│   ├── add_subparsers() → Creates command structure
│   ├── collector_parser → Collector arguments
│   ├── eval_parser → Eval arguments
│   ├── workflows_parser → No arguments
│   ├── map_parser → Workflow name argument
│   ├── logs_parser → Workflow name argument
│   └── notebook_parser → Workflow name + port
│
├── parser.parse_args()
│
└── Route by main_command:
    │
    ├── "collector" → collector_main(args)
    │   ├── Check COLLECTOR_AVAILABLE
    │   ├── Create TelemetryClient
    │   ├── Add sinks (JSONLSink, HTTPSink)
    │   ├── create_collector_app()
    │   └── uvicorn.run()
    │
    ├── "eval" → run_eval_demo(demo, transactions, output_dir)
    │   ├── Determine script path
    │   ├── Set environment variables
    │   └── subprocess.run(script)
    │
    ├── "workflows" → list_workflows()
    │   └── discover_workflows()
    │       ├── Iterate WORKFLOW_REGISTRY
    │       ├── glob.glob(log_pattern)
    │       ├── Read JSONL files
    │       ├── Parse events
    │       └── Extract metadata
    │
    ├── "map" → show_workflow_map(workflow)
    │   ├── resolve_workflow_name(workflow)
    │   └── discover_workflows()
    │
    ├── "logs" → show_workflow_logs(workflow)
    │   ├── resolve_workflow_name(workflow)
    │   ├── Get config from WORKFLOW_REGISTRY
    │   └── glob.glob(log_pattern)
    │
    └── "notebook" → open_workflow_notebook(workflow, port)
        ├── resolve_workflow_name(workflow)
        ├── Get config from WORKFLOW_REGISTRY
        ├── Check notebook exists
        └── subprocess.run(jupyter notebook)
```

---

## Key Components

### 1. **Entry Point** (`main()`)
- Creates argument parser with subcommands
- Routes to appropriate handler based on `main_command`
- Handles help and error cases

### 2. **Workflow Registry** (`WORKFLOW_REGISTRY`)
- Hardcoded dictionary mapping workflow IDs to configurations
- Contains: display_name, log_pattern, notebook, script, aliases
- Used by all workflow-related commands

### 3. **Discovery System** (`discover_workflows()`)
- Core function used by multiple commands
- Reads WORKFLOW_REGISTRY
- Scans filesystem for log files matching patterns
- Parses JSONL files to extract metadata
- Returns enriched workflow information

### 4. **Workflow Resolution** (`resolve_workflow_name()`)
- Converts user input (name or alias) to canonical workflow ID
- Checks direct matches and aliases
- Used by map, logs, and notebook commands

### 5. **Command Handlers**
- **collector_main()**: Sets up HTTP collector server
- **run_eval_demo()**: Executes demo scripts
- **list_workflows()**: Lists discovered workflows
- **show_workflow_map()**: Shows workflow agent map
- **show_workflow_logs()**: Shows log file information
- **open_workflow_notebook()**: Launches Jupyter notebook

---

## Typical User Workflows

### Workflow 1: Running a Demo and Analyzing

```
1. User: abidex eval fraud --transactions 50
   → Generates: fraud_detection_logs_*.jsonl

2. User: abidex workflows
   → Discovers and lists workflows including "fraud_detection"

3. User: abidex map fraud_detection
   → Shows agents and their last calls

4. User: abidex notebook fraud_detection
   → Opens Jupyter notebook for analysis
```

### Workflow 2: Starting Collector

```
1. User: abidex collector --port 8000 --output-file telemetry.jsonl
   → Starts HTTP server on port 8000
   → Saves events to telemetry.jsonl
   → Runs until interrupted
```

### Workflow 3: Exploring Existing Logs

```
1. User: abidex workflows
   → Lists all discovered workflows

2. User: abidex logs weather
   → Shows log files for weather workflow

3. User: abidex map weather
   → Shows detailed workflow map
```

---

## Dependencies Between Commands

| Command | Requires | Generates | Used By |
|---------|----------|-----------|---------|
| `eval` | Demo scripts | Log files | `workflows`, `map`, `logs`, `notebook` |
| `workflows` | Log files, Registry | Workflow list | User (discovery) |
| `map` | Log files, Registry | Workflow map | User (analysis) |
| `logs` | Log files, Registry | Log info | User (inspection) |
| `notebook` | Log files, Registry, Notebooks | Jupyter server | User (analysis) |
| `collector` | FastAPI, uvicorn | HTTP server | External agents |

---

## File System Interactions

```
Project Root/
├── abidex/
│   ├── cli.py (main entry point)
│   ├── client.py
│   └── ...
├── simple_agent_test.py (demo script)
├── fraud_detection_pipeline.py (demo script)
├── simple_agent_logs_*.jsonl (generated logs)
├── fraud_detection_logs_*.jsonl (generated logs)
├── agent_logs_analysis.ipynb (notebook)
└── fraud_detection_analysis.ipynb (notebook)
```

---

## Error Handling Flow

```mermaid
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#ffffff', 'primaryTextColor':'#000000', 'primaryBorderColor':'#000000', 'lineColor':'#000000', 'secondaryColor':'#f0f0f0', 'tertiaryColor':'#ffffff', 'background':'#ffffff', 'mainBkgColor':'#ffffff', 'secondBkgColor':'#f5f5f5', 'textColor':'#000000'}}}%%
graph TD
    A[Command Execution] --> B{Error?}
    B -->|No| C[Success]
    B -->|Yes| D{Error Type?}
    
    D -->|Workflow Not Found| E[Print: Workflow not found<br/>Show available workflows]
    D -->|No Log Files| F[Print: Run workflow first<br/>Tip: Use 'abidex eval']
    D -->|Notebook Not Found| G[Print: Notebook not found<br/>Exit with error]
    D -->|Collector Unavailable| H[Print: Install collector<br/>Exit with error]
    D -->|Script Not Found| I[Print: Script not found<br/>Exit with error]
    
    E --> J[Exit]
    F --> J
    G --> J
    H --> J
    I --> J
    
    style A fill:#4a90e2,stroke:#000000,stroke-width:2px,color:#ffffff
    style C fill:#7ed321,stroke:#000000,stroke-width:2px,color:#000000
    style E fill:#f5a623,stroke:#000000,stroke-width:2px,color:#000000
    style F fill:#f5a623,stroke:#000000,stroke-width:2px,color:#000000
    style G fill:#d0021b,stroke:#000000,stroke-width:2px,color:#ffffff
    style H fill:#d0021b,stroke:#000000,stroke-width:2px,color:#ffffff
    style I fill:#d0021b,stroke:#000000,stroke-width:2px,color:#ffffff
    style J fill:#9013fe,stroke:#000000,stroke-width:2px,color:#ffffff
```

---

## Configuration Points

### Hardcoded (Current)
- `WORKFLOW_REGISTRY`: Workflow definitions
- Log file patterns: `"*_logs*.jsonl"`
- Default ports: `8000` (collector), `8888` (notebook)
- Script paths: `simple_agent_test.py`, `fraud_detection_pipeline.py`
- Notebook paths: `agent_logs_analysis.ipynb`, `fraud_detection_analysis.ipynb`

### Configurable (Future)
- Workflow registry via config file
- Log file patterns via environment/config
- Ports via environment variables
- Script/notebook discovery via patterns

---

## Performance Considerations

1. **Discovery Caching**: `discover_workflows()` reads all log files each time
   - **Impact**: Slow for large log files
   - **Solution**: Implement caching or sampling

2. **File I/O**: Multiple commands read the same log files
   - **Impact**: Redundant file reads
   - **Solution**: Cache parsed results

3. **Pattern Matching**: `glob.glob()` called multiple times
   - **Impact**: Filesystem queries
   - **Solution**: Cache glob results

---

## Extension Points

### Adding New Commands

1. Add subparser in `main()`
2. Add routing in `main()` command handler
3. Implement command function
4. Update help text

### Adding New Workflows

1. Add entry to `WORKFLOW_REGISTRY` (current)
2. Or implement auto-discovery (future)

### Customizing Discovery

1. Modify `discover_workflows()` logic
2. Add new metadata extraction
3. Support custom patterns

