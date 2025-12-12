"""
Command-line interface for Abide AgentKit.
"""

import argparse
import subprocess
import sys
from pathlib import Path

from .collector_main import collector_main
from .eval_main import eval_main, run_eval_demo
from .workflows import (
    list_workflows,
    open_workflow_notebook,
    show_workflow_logs,
    show_workflow_map,
)


def run_logs_command(command: str, pattern: str = "*_logs*.jsonl",
    """Discover workflows from log files and return workflow information."""
    import glob
    import json
    from datetime import datetime
    
    workflows = {}
    package_dir = Path(__file__).parent.parent
    
    # Check all log files
    all_log_files = glob.glob("*_logs*.jsonl")
    
    for workflow_id, config in WORKFLOW_REGISTRY.items():
        log_pattern = config["log_pattern"]
        log_files = glob.glob(log_pattern)
        
        if not log_files:
            continue
        
        # Analyze log files to get workflow stats
        total_events = 0
        agents = {}
        agent_last_calls = {}
        last_seen = None
        runs = set()
        
        for file_path in log_files:
            try:
                with open(file_path, 'r') as f:
                    for line in f:
                        if line.strip():
                            try:
                                event = json.loads(line.strip())
                                total_events += 1
                                
                                # Track agents - prioritize tags['agent'] (set by AgentLogger) over agent.name
                                tags = event.get('tags', {})
                                agent_info = event.get('agent', {})
                                
                                # AgentLogger sets agent name in tags, prioritize that
                                agent_name = tags.get('agent')
                                if not agent_name:
                                    # Fall back to agent.name if tags don't have it
                                    agent_name = agent_info.get('name')
                                
                                # Also get role from tags or agent field
                                agent_role = tags.get('role') or agent_info.get('role')
                                
                                if agent_name:
                                    if agent_name not in agents:
                                        agents[agent_name] = {
                                            'events': 0,
                                            'role': agent_role,
                                            'last_call': None,
                                            'last_call_time': None
                                        }
                                    agents[agent_name]['events'] += 1
                                    # Update role if we found one
                                    if agent_role and not agents[agent_name]['role']:
                                        agents[agent_name]['role'] = agent_role
                                    
                                    # Track last call - check multiple sources
                                    call_name = None
                                    metadata = event.get('metadata', {})
                                    action = event.get('action', {})
                                    
                                    # For AgentLogger events, action is in metadata
                                    if tags.get('event_type') == 'action':
                                        # AgentLogger stores action in metadata.action
                                        call_name = metadata.get('action')
                                    elif tags.get('event_type') == 'decision':
                                        call_name = metadata.get('decision')
                                    # For regular events, check action.name
                                    elif action:
                                        call_name = action.get('name')
                                    # Fallback to metadata
                                    if not call_name:
                                        call_name = metadata.get('action') or metadata.get('agent_action')
                                    
                                    if call_name:
                                        telemetry = event.get('telemetry', {})
                                        timestamp = telemetry.get('timestamp_start')
                                        if timestamp:
                                            if (agents[agent_name]['last_call_time'] is None or 
                                                timestamp > agents[agent_name]['last_call_time']):
                                                agents[agent_name]['last_call'] = call_name
                                                agents[agent_name]['last_call_time'] = timestamp
                                    
                                    # Track timestamp
                                    telemetry = event.get('telemetry', {})
                                    timestamp = telemetry.get('timestamp_start')
                                    if timestamp:
                                        if last_seen is None or timestamp > last_seen:
                                            last_seen = timestamp
                                
                                # Track runs
                                run_id = event.get('run_id')
                                if run_id:
                                    runs.add(run_id)
                            except (json.JSONDecodeError, KeyError):
                                pass
            except Exception:
                pass
        
        # Filter out pipeline/system name from agents if specified
        pipeline_name = config.get("pipeline_name")
        if pipeline_name and pipeline_name in agents:
            del agents[pipeline_name]
        
        workflows[workflow_id] = {
            "display_name": config["display_name"],
            "log_pattern": log_pattern,
            "log_files": log_files,
            "notebook": config["notebook"],
            "script": config["script"],
            "total_events": total_events,
            "agents": agents,
            "unique_runs": len(runs),
            "last_seen": last_seen
        }
    
    return workflows


def resolve_workflow_name(name: str) -> Optional[str]:
    """Resolve workflow name or alias to canonical workflow ID."""
    name_lower = name.lower()
    
    # Direct match
    if name_lower in WORKFLOW_REGISTRY:
        return name_lower
    
    # Check aliases
    for workflow_id, config in WORKFLOW_REGISTRY.items():
        if name_lower in [a.lower() for a in config.get("aliases", [])]:
            return workflow_id
    
    return None


def list_workflows():
    """List all discovered workflows."""
    workflows = discover_workflows()
    
    if not workflows:
        print("No workflows found.")
        print("\nTip: Run a workflow first to generate log files.")
        return
    
    print(f"\nFound {len(workflows)} workflow(s):\n")
    
    for workflow_id, info in sorted(workflows.items()):
        print(f" {info['display_name']} ({workflow_id})")
        print(f"   Agents: {len(info['agents'])}")
        print(f"   Total Events: {info['total_events']:,}")
        print(f"   Unique Runs: {info['unique_runs']}")
        if info['last_seen']:
            from datetime import datetime
            last = datetime.fromtimestamp(info['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   Last Seen: {last}")
        print()


def show_workflow_map(workflow_name: str):
    """Show workflow map with agents and their last calls."""
    workflow_id = resolve_workflow_name(workflow_name)
    
    if not workflow_id:
        print(f"Error: Workflow '{workflow_name}' not found.")
        print("\nAvailable workflows:")
        workflows = discover_workflows()
        for wf_id, info in workflows.items():
            print(f"  - {info['display_name']} ({wf_id})")
        return
    
    workflows = discover_workflows()
    
    if workflow_id not in workflows:
        print(f"Error: No data found for workflow '{workflow_name}'.")
        print("Tip: Run the workflow first to generate log files.")
        return
    
    info = workflows[workflow_id]
    
    print(f"\n{info['display_name']} Workflow Map")
    print("=" * 60)
    print(f"Workflow ID: {workflow_id}")
    print(f"Total Events: {info['total_events']:,}")
    print(f"Unique Runs: {info['unique_runs']}")
    print(f"Number of Agents: {len(info['agents'])}")
    print()
    
    if not info['agents']:
        print("No agents found in this workflow.")
        return
    
    print("Agents and Last Calls:")
    print("-" * 60)
    
    for agent_name, agent_data in sorted(info['agents'].items()):
        print(f"\n {agent_name}")
        print(f"   Total Events: {agent_data['events']:,}")
        if agent_data['last_call']:
            from datetime import datetime
            last_call_time = datetime.fromtimestamp(agent_data['last_call_time']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   Last Call: {agent_data['last_call']}")
            print(f"   Last Call Time: {last_call_time}")
        else:
            print(f"   Last Call: N/A")
    
    print()


def show_workflow_logs(workflow_name: str):
    """Show telemetry logs for a specific workflow."""
    workflow_id = resolve_workflow_name(workflow_name)
    
    if not workflow_id:
        print(f"Error: Workflow '{workflow_name}' not found.")
        return
    
    if workflow_id not in WORKFLOW_REGISTRY:
        print(f"Error: Workflow '{workflow_name}' not in registry.")
        return
    
    config = WORKFLOW_REGISTRY[workflow_id]
    log_pattern = config["log_pattern"]
    
    import glob
    log_files = glob.glob(log_pattern)
    
    if not log_files:
        print(f"No log files found for workflow '{workflow_name}'.")
        print(f"Pattern: {log_pattern}")
        return
    
    print(f"\nTelemetry Logs for {config['display_name']}")
    print("=" * 60)
    print(f"Log Pattern: {log_pattern}")
    print(f"Found {len(log_files)} log file(s):\n")
    
    import json
    total_events = 0
    
    for file_path in sorted(log_files):
        file_events = 0
        try:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            json.loads(line.strip())
                            file_events += 1
                            total_events += 1
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass
        
        from pathlib import Path
        file_path_obj = Path(file_path)
        size_mb = file_path_obj.stat().st_size / (1024 * 1024) if file_path_obj.exists() else 0
        print(f"  {file_path}")
        print(f"    Events: {file_events:,} ({size_mb:.2f} MB)")
    
    print(f"\nTotal Events: {total_events:,}")


def open_workflow_notebook(workflow_name: str, port: int = 8888):
    """Open Jupyter notebook for a specific workflow."""
    workflow_id = resolve_workflow_name(workflow_name)
    
    if not workflow_id:
        print(f"Error: Workflow '{workflow_name}' not found.")
        return
    
    if workflow_id not in WORKFLOW_REGISTRY:
        print(f"Error: Workflow '{workflow_name}' not in registry.")
        return
    
    config = WORKFLOW_REGISTRY[workflow_id]
    notebook_file = config["notebook"]
    package_dir = Path(__file__).parent.parent
    notebook_path = package_dir / notebook_file
    
    if not notebook_path.exists():
        print(f"Error: Notebook not found at {notebook_path}")
        print(f"   Make sure you've run the workflow first.")
        sys.exit(1)
    
    print(f"Opening {config['display_name']} Analysis Notebook...")
    print(f"   Notebook: {notebook_path}")
    print(f"   Port: {port}")
    print("\nThe Jupyter notebook will open in your browser.")
    print("   Press Ctrl+C to stop the server.\n")
    
    # Check if jupyter is available
    try:
        import jupyter
    except ImportError:
        print("Error: Jupyter is required. Install with: pip install jupyter")
        sys.exit(1)
    
    # Launch Jupyter notebook
    result = subprocess.run(
        ["jupyter", "notebook", str(notebook_path), "--port", str(port)],
        cwd=str(package_dir)
    )
    
    sys.exit(result.returncode)


def collector_main(args=None):
    """
    Main entry point for the collector CLI.
    
    Args:
        args: Parsed arguments (Namespace object). If None, will parse from sys.argv.
    """
    if not COLLECTOR_AVAILABLE:
        print("Error: Collector is not available. Install with: uv add abidex[collector] (or pip install abidex[collector])")
        sys.exit(1)
    
    # If args not provided, parse them (for standalone usage)
    if args is None:
        parser = argparse.ArgumentParser(
            description="Abide AgentKit Telemetry Collector",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
        
        parser.add_argument(
            "--host",
            default="0.0.0.0",
            help="Host to bind the collector to"
        )
        
        parser.add_argument(
            "--port",
            type=int,
            default=8000,
            help="Port to bind the collector to"
        )
        
        parser.add_argument(
            "--auth-token",
            help="Authentication token for API requests"
        )
        
        parser.add_argument(
            "--cors-origins",
            nargs="*",
            default=["*"],
            help="Allowed CORS origins"
        )
        
        parser.add_argument(
            "--max-batch-size",
            type=int,
            default=1000,
            help="Maximum batch size for event processing"
        )
        
        parser.add_argument(
            "--output-file",
            help="Output file for JSONL sink (optional)"
        )
        
        parser.add_argument(
            "--forward-url",
            help="HTTP URL to forward events to (optional)"
        )
        
        parser.add_argument(
            "--log-level",
            choices=["debug", "info", "warning", "error"],
            default="info",
            help="Log level"
        )
        
        parser.add_argument(
            "--reload",
            action="store_true",
            help="Enable auto-reload for development"
        )
        
        args = parser.parse_args()
    
    if not UVICORN_AVAILABLE:
        print("Error: uvicorn is required to run the collector. Install with: uv add abidex[collector] (or pip install abidex[collector])")
        sys.exit(1)
    
    # Set up telemetry client with optional sinks
    client = TelemetryClient()
    
    if args.output_file:
        client.add_sink(JSONLSink(args.output_file))
        print(f"Added JSONL sink: {args.output_file}")
    
    if args.forward_url:
        client.add_sink(HTTPSink(args.forward_url))
        print(f"Added HTTP sink: {args.forward_url}")
    
    # Create collector app
    app = create_collector_app(
        client=client,
        auth_token=args.auth_token,
        cors_origins=args.cors_origins,
        max_batch_size=args.max_batch_size
    )
    
    print(f"Starting Abide AgentKit Collector on {args.host}:{args.port}")
    if args.auth_token:
        print("Authentication enabled")
    else:
        print("WARNING: No authentication token set - collector is open to all requests")
    
    # Run with uvicorn
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        reload=args.reload
    )


def run_eval_demo(demo: str, transactions: int = 25, output_dir: str = "."):
    """Run an agent demo."""
    # Get the package directory
    package_dir = Path(__file__).parent.parent
    demo_dir = package_dir
    
    if demo in ("simple", "weather"):
        demo_script = demo_dir / "simple_agent_test.py"
        if not demo_script.exists():
            print(f"Error: Demo script not found at {demo_script}")
            sys.exit(1)
        
        print(" Running Weather Agent Logging Demo...")
        print("=" * 50)
        
        # Run the simple agent test
        env = os.environ.copy()
        env['PYTHONPATH'] = str(package_dir) + os.pathsep + env.get('PYTHONPATH', '')
        
        result = subprocess.run(
            [sys.executable, str(demo_script)],
            cwd=str(demo_dir),
            env=env
        )
        
        sys.exit(result.returncode)
    
    elif demo == "fraud":
        demo_script = demo_dir / "fraud_detection_pipeline.py"
        if not demo_script.exists():
            print(f"Error: Demo script not found at {demo_script}")
            sys.exit(1)
        
        print(" Running Fraud Detection Pipeline Demo...")
        print("=" * 50)
        print(f"Processing {transactions} transactions...")
        
        # Run the fraud detection pipeline
        env = os.environ.copy()
        env['PYTHONPATH'] = str(package_dir) + os.pathsep + env.get('PYTHONPATH', '')
        
        # Pass transaction count as environment variable
        env['FRAUD_DEMO_TRANSACTIONS'] = str(transactions)
        
        result = subprocess.run(
            [sys.executable, str(demo_script)],
            cwd=str(demo_dir),
            env=env
        )
        
        sys.exit(result.returncode)


def run_logs_command(command: str, pattern: str = "*_logs*.jsonl", 
>>>>>>> c2a6e2d (resolved #1)
                     notebook: str = "agent", port: int = 8888):
    """Run logs analysis commands."""
    package_dir = Path(__file__).parent.parent

    if command == "list":
        import glob

        log_files = glob.glob(pattern)
        if not log_files:
            print(f" No log files found matching pattern: {pattern}")
            return

        print(f" Found {len(log_files)} log file(s):")
        for file in sorted(log_files):
            file_path = Path(file)
            size = file_path.stat().st_size if file_path.exists() else 0
            size_mb = size / (1024 * 1024)
            print(f"  • {file} ({size_mb:.2f} MB)")

    elif command == "summary":
        import glob
        import json

        log_files = glob.glob(pattern)
        if not log_files:
            print(f" No log files found matching pattern: {pattern}")
            return

        print(f" Summary for {len(log_files)} log file(s):")
        print("=" * 50)

        total_events = 0
        event_types = {}
        agents = {}

        for file_path in log_files:
            with open(file_path, 'r') as f:
                file_events = 0
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line.strip())
                            file_events += 1
                            total_events += 1

                            # Count event types
                            event_type = event.get('event_type', 'unknown')
                            event_types[event_type] = event_types.get(event_type, 0) + 1

                            # Count agents
                            agent_name = event.get('agent', {}).get('name', 'unknown')
                            if agent_name:
                                agents[agent_name] = agents.get(agent_name, 0) + 1
                        except json.JSONDecodeError:
                            pass

            print(f"\n {file_path}:")
            print(f"  • Events: {file_events:,}")

        print(f"\n Overall Summary:")
        print(f"  • Total Events: {total_events:,}")
        print(f"  • Event Types: {len(event_types)}")
        print(f"  • Unique Agents: {len(agents)}")

        if event_types:
            print("\n Event Type Distribution:")
            for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_events) * 100
                print(f"  • {event_type}: {count:,} ({percentage:.1f}%)")

        if agents:
            print("\n Agent Distribution:")
            for agent, count in sorted(agents.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_events) * 100
                print(f"  • {agent}: {count:,} ({percentage:.1f}%)")

    elif command == "agents":
        import glob
        import json

        log_files = glob.glob(pattern)
        if not log_files:
            print(f" No log files found matching pattern: {pattern}")
            return

        print(f" Agents found in {len(log_files)} log file(s):")
        print("=" * 60)

        agents = {}
        agent_details = {}

        for file_path in log_files:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line.strip())
                            agent_info = event.get('agent', {})
                            agent_name = agent_info.get('name')

                            if agent_name:
                                if agent_name not in agents:
                                    agents[agent_name] = 0
                                    agent_details[agent_name] = {
                                        'role': agent_info.get('role'),
                                        'version': agent_info.get('version'),
                                        'events': 0,
                                        'runs': set(),
                                        'first_seen': None,
                                        'last_seen': None
                                    }

                                agents[agent_name] += 1
                                agent_details[agent_name]['events'] += 1

                                # Track runs
                                run_id = event.get('run_id')
                                if run_id:
                                    agent_details[agent_name]['runs'].add(run_id)

                                # Track timestamps
                                telemetry = event.get('telemetry', {})
                                timestamp = telemetry.get('timestamp_start')
                                if timestamp:
                                    if (agent_details[agent_name]['first_seen'] is None or
                                        timestamp < agent_details[agent_name]['first_seen']):
                                        agent_details[agent_name]['first_seen'] = timestamp
                                    if (agent_details[agent_name]['last_seen'] is None or
                                        timestamp > agent_details[agent_name]['last_seen']):
                                        agent_details[agent_name]['last_seen'] = timestamp
                        except (json.JSONDecodeError, KeyError):
                            pass

        if not agents:
            print("No agents found in log files.")
            return

        # Sort by event count
        sorted_agents = sorted(agents.items(), key=lambda x: x[1], reverse=True)

        print(f"\n Found {len(agents)} unique agent(s):\n")

        for agent_name, event_count in sorted_agents:
            details = agent_details[agent_name]
            print(f" {agent_name}")
            if details['role']:
                print(f"   Role: {details['role']}")
            if details['version']:
                print(f"   Version: {details['version']}")
            print(f"   Total Events: {event_count:,}")
            print(f"   Unique Runs: {len(details['runs'])}")

            if details['first_seen'] and details['last_seen']:
                from datetime import datetime
                first = datetime.fromtimestamp(details['first_seen']).strftime('%Y-%m-%d %H:%M:%S')
                last = datetime.fromtimestamp(details['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   First Seen: {first}")
                print(f"   Last Seen: {last}")

            print()

    elif command == "pipelines":
        import glob
        import json

        log_files = glob.glob(pattern)
        if not log_files:
            print(f" No log files found matching pattern: {pattern}")
            return

        print(f" Pipelines found in {len(log_files)} log file(s):")
        print("=" * 60)

        pipelines = {}
        pipeline_details = {}

        for file_path in log_files:
            with open(file_path, 'r') as f:
                for line in f:
                    if line.strip():
                        try:
                            event = json.loads(line.strip())

                            # Look for pipeline identifiers
                            metadata = event.get('metadata', {})
                            tags = event.get('tags', {})

                            # Check various places for pipeline info
                            pipeline_id = (
                                metadata.get('pipeline_id') or
                                metadata.get('pipeline') or
                                tags.get('pipeline') or
                                metadata.get('system')
                            )

                            if pipeline_id:
                                if pipeline_id not in pipelines:
                                    pipelines[pipeline_id] = 0
                                    pipeline_details[pipeline_id] = {
                                        'events': 0,
                                        'runs': set(),
                                        'agents': set(),
                                        'first_seen': None,
                                        'last_seen': None
                                    }

                                pipelines[pipeline_id] += 1
                                pipeline_details[pipeline_id]['events'] += 1

                                # Track runs
                                run_id = event.get('run_id')
                                if run_id:
                                    pipeline_details[pipeline_id]['runs'].add(run_id)

                                # Track agents
                                agent_name = event.get('agent', {}).get('name')
                                if agent_name:
                                    pipeline_details[pipeline_id]['agents'].add(agent_name)

                                # Track timestamps
                                telemetry = event.get('telemetry', {})
                                timestamp = telemetry.get('timestamp_start')
                                if timestamp:
                                    if (pipeline_details[pipeline_id]['first_seen'] is None or
                                        timestamp < pipeline_details[pipeline_id]['first_seen']):
                                        pipeline_details[pipeline_id]['first_seen'] = timestamp
                                    if (pipeline_details[pipeline_id]['last_seen'] is None or
                                        timestamp > pipeline_details[pipeline_id]['last_seen']):
                                        pipeline_details[pipeline_id]['last_seen'] = timestamp
                        except (json.JSONDecodeError, KeyError):
                            pass

        if not pipelines:
            print("No pipelines found in log files.")
            print("\n Tip: Pipelines are identified by 'pipeline_id', 'pipeline', or 'system' in metadata/tags")
            return

        # Sort by event count
        sorted_pipelines = sorted(pipelines.items(), key=lambda x: x[1], reverse=True)

        print(f"\n Found {len(pipelines)} unique pipeline(s):\n")

        for pipeline_id, event_count in sorted_pipelines:
            details = pipeline_details[pipeline_id]
            print(f" {pipeline_id}")
            print(f"   Total Events: {event_count:,}")
            print(f"   Unique Runs: {len(details['runs'])}")
            print(f"   Agents: {', '.join(sorted(details['agents'])) if details['agents'] else 'N/A'}")

            if details['first_seen'] and details['last_seen']:
                from datetime import datetime
                first = datetime.fromtimestamp(details['first_seen']).strftime('%Y-%m-%d %H:%M:%S')
                last = datetime.fromtimestamp(details['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
                print(f"   First Seen: {first}")
                print(f"   Last Seen: {last}")

            print()

    elif command == "analyze":
        # Determine which notebook to open
        if notebook == "fraud":
            notebook_file = package_dir / "fraud_detection_analysis.ipynb"
            notebook_name = "Fraud Detection Analysis"
        else:
            notebook_file = package_dir / "agent_logs_analysis.ipynb"
            notebook_name = "Agent Logs Analysis"

        if not notebook_file.exists():
            print(f" Error: Notebook not found at {notebook_file}")
            print("   Make sure you've run a demo first to generate log files.")
            sys.exit(1)

        print(f" Opening {notebook_name}...")
        print(f"   Notebook: {notebook_file}")
        print(f"   Port: {port}")
        print("\n The Jupyter notebook will open in your browser.")
        print("   Press Ctrl+C to stop the server.\n")

        # Check if jupyter is available
        try:
            import jupyter
        except ImportError:
            print(" Error: Jupyter is required. Install with: pip install jupyter")
            sys.exit(1)

        # Launch Jupyter notebook
        result = subprocess.run(
            ["jupyter", "notebook", str(notebook_file), "--port", str(port)],
            cwd=str(package_dir)
        )

        sys.exit(result.returncode)


def logs_main():
    """Standalone entry point for logs command."""
    parser = argparse.ArgumentParser(
        description="Abide AgentKit Logs - Analyze telemetry data",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("command", choices=["analyze", "list", "summary", "agents", "pipelines"],
                       help="Command to run")
    parser.add_argument("--pattern", default="*_logs*.jsonl",
                       help="Pattern to match log files")
    parser.add_argument("--notebook", choices=["agent", "fraud"], default="agent",
                       help="Which notebook to open")
    parser.add_argument("--port", type=int, default=8888,
                       help="Port for Jupyter notebook")

    args = parser.parse_args()
    run_logs_command(args.command, args.pattern, args.notebook, args.port)


def main():
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(
        description="AbideX - OpenTelemetry-based telemetry and logging SDK for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start the telemetry collector
  abidex collector --port 8000

  # List all available workflows
  abidex workflows

  # Show workflow map with agents and their last calls
  abidex map fraud_detection

  # View logs for a workflow
  abidex logs weather

  # Open Jupyter notebook for a workflow
  abidex notebook fraud_detection

  # Run agent demos
  abidex eval simple
  abidex eval fraud --transactions 50

For more information, visit: https://github.com/abide-ai/agentkit
        """
    )

    subparsers = parser.add_subparsers(dest="main_command", help="Available commands", metavar="COMMAND")

    # Collector command
    collector_parser = subparsers.add_parser(
        "collector",
        help="Start the telemetry collector server",
        description="Start the HTTP collector for receiving telemetry events",
        epilog="""
Examples:
  # Start collector on default port 8000
  abidex collector

  # Start on custom port with authentication
  abidex collector --port 9000 --auth-token my-secret-token

  # Start with JSONL output file
  abidex collector --output-file telemetry.jsonl

  # Start with CORS enabled for specific origins
  abidex collector --cors-origins http://localhost:3000 https://app.example.com
        """
    )
    # Add collector arguments
    collector_parser.add_argument("--host", default="0.0.0.0", help="Host to bind the collector to")
    collector_parser.add_argument("--port", type=int, default=8000, help="Port to bind the collector to")
    collector_parser.add_argument("--auth-token", help="Authentication token for API requests")
    collector_parser.add_argument("--cors-origins", nargs="*", default=["*"], help="Allowed CORS origins")
    collector_parser.add_argument("--max-batch-size", type=int, default=1000, help="Maximum batch size")
    collector_parser.add_argument("--output-file", help="Output file for JSONL sink")
    collector_parser.add_argument("--forward-url", help="HTTP URL to forward events to")
    collector_parser.add_argument("--log-level", choices=["debug", "info", "warning", "error"], default="info")
    collector_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")

    # Eval command
    eval_parser = subparsers.add_parser(
        "eval",
        help="Run agent demos and evaluations",
        description="Run demo scenarios to test agent logging and telemetry",
        epilog="""
Examples:
  # Run weather agent demo
  abidex eval weather

  # Run fraud detection demo with 50 transactions
  abidex eval fraud --transactions 50

  # Run fraud detection and save to custom directory
  abidex eval fraud --transactions 100 --output-dir ./logs
        """
    )
    eval_parser.add_argument("demo", choices=["simple", "weather", "fraud"],
                            help="Which demo to run: 'weather' (or 'simple') for weather agent logging, 'fraud' for fraud detection pipeline")
    eval_parser.add_argument("--transactions", type=int, default=25,
                            help="Number of transactions to process (for fraud demo)")
    eval_parser.add_argument("--output-dir", default=".", help="Directory to save log files")

    # Workflows command
    workflows_parser = subparsers.add_parser(
        "workflows",
        help="List all available workflows",
        description="Discover and list all workflows with their agents and statistics",
        epilog="""
Examples:
  # List all workflows
  abidex workflows

This will show:
  - Workflow names and display names
  - Number of agents in each workflow
  - Total events and unique runs
  - Last seen timestamp
        """
    )

    # Map command
    map_parser = subparsers.add_parser(
        "map",
        help="Show workflow map with agents and last calls",
        description="Display detailed information about a specific workflow including agents and their last calls",
        epilog="""
Examples:
  # Show map for fraud detection workflow
  abidex map fraud_detection

  # Show map for weather workflow (using alias)
  abidex map weather
  abidex map simple_agent  # alias also works

This will show:
  - All agents in the workflow
  - Agent roles (decision-maker, data-processor, notification, etc.)
  - Last call made by each agent
  - Event counts per agent
        """
    )
    map_parser.add_argument("workflow", help="Workflow name (e.g., simple_agent, fraud_detection)")

    # Logs command (workflow-specific)
    logs_parser = subparsers.add_parser(
        "logs",
        help="Show telemetry logs for a workflow",
        description="Display telemetry logs for a specific workflow",
        epilog="""
Examples:
  # Show logs for fraud detection workflow
  abidex logs fraud_detection

  # Show logs for weather workflow
  abidex logs weather

This will show:
  - Log file paths for the workflow
  - File sizes and modification times
  - Total events in each log file
        """
    )
    logs_parser.add_argument("workflow", help="Workflow name (e.g., simple_agent, fraud_detection)")

    # Notebook command
    notebook_parser = subparsers.add_parser(
        "notebook",
        help="Open Jupyter notebook for a workflow",
        description="Launch the analysis notebook for a specific workflow",
        epilog="""
Examples:
  # Open notebook for fraud detection workflow
  abidex notebook fraud_detection

  # Open notebook on custom port
  abidex notebook weather --port 9999

This will:
  - Launch Jupyter notebook server
  - Open the analysis notebook for the workflow
  - Allow you to analyze telemetry data interactively
        """
    )
    notebook_parser.add_argument("workflow", help="Workflow name (e.g., simple_agent, fraud_detection)")
    notebook_parser.add_argument("--port", type=int, default=8888,
                                help="Port for Jupyter notebook server")

    args = parser.parse_args()

    if not args.main_command:
        parser.print_help()
        sys.exit(1)

    # Call the appropriate function with parsed args
    if args.main_command == "collector":
        # Pass the parsed args to collector_main
        collector_main(args)
    elif args.main_command == "eval":
        # Pass the parsed args
        run_eval_demo(args.demo, args.transactions, args.output_dir)
    elif args.main_command == "workflows":
        list_workflows()
    elif args.main_command == "map":
        show_workflow_map(args.workflow)
    elif args.main_command == "logs":
        show_workflow_logs(args.workflow)
    elif args.main_command == "notebook":
        open_workflow_notebook(args.workflow, args.port)


if __name__ == "__main__":
    main()
