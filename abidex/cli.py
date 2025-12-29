"""
Command-line interface for Abide AgentKit.
"""

import argparse
import sys
import os
import subprocess
from typing import Optional
from pathlib import Path

# Import functions from dedicated modules
from .collector_main import collector_main
from .eval_main import eval_main
from .cli_common import get_repo_root
from .workflows.registry import WorkflowRegistry
from .workflows.discovery import discover_workflows, resolve_workflow_name




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
        # Try direct match (for auto-discovered workflows)
        workflows = discover_workflows()
        if workflow_name.lower() in workflows:
            workflow_id = workflow_name.lower()
        else:
            print(f"Error: Workflow '{workflow_name}' not found.")
            print("\nAvailable workflows:")
            for wf_id, info in workflows.items():
                print(f"  - {info['display_name']} ({wf_id})")
            return
    
    # Get workflow info from discovered workflows
    workflows = discover_workflows()
    
    if workflow_id not in workflows:
        print(f"Error: Workflow '{workflow_name}' not found.")
        print("\nAvailable workflows:")
        for wf_id, info in workflows.items():
            print(f"  - {info['display_name']} ({wf_id})")
        return
    
    workflow_info = workflows[workflow_id]
    log_files = workflow_info.get("log_files", [])
    log_pattern = workflow_info.get("log_pattern", "")
    display_name = workflow_info.get("display_name", workflow_id)
    
    if not log_files:
        print(f"No log files found for workflow '{workflow_name}'.")
        if log_pattern:
            print(f"Pattern: {log_pattern}")
        return
    
    print(f"\nTelemetry Logs for {display_name}")
    print("=" * 60)
    if log_pattern:
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
        # Try direct match (for auto-discovered workflows)
        workflows = discover_workflows()
        if workflow_name.lower() in workflows:
            workflow_id = workflow_name.lower()
        else:
            print(f"Error: Workflow '{workflow_name}' not found.")
            print("\nAvailable workflows:")
            for wf_id, info in workflows.items():
                print(f"  - {info['display_name']} ({wf_id})")
            return
    
    # Get workflow info from discovered workflows
    workflows = discover_workflows()
    
    if workflow_id not in workflows:
        print(f"Error: Workflow '{workflow_name}' not found.")
        print("\nAvailable workflows:")
        for wf_id, info in workflows.items():
            print(f"  - {info['display_name']} ({wf_id})")
        return
    
    workflow_info = workflows[workflow_id]
    notebook_file = workflow_info.get("notebook")
    display_name = workflow_info.get("display_name", workflow_id)
    
    if not notebook_file:
        print(f"Error: No notebook found for workflow '{workflow_name}'.")
        print("   Auto-discovered workflows may not have associated notebooks.")
        print("   You can create one or add it to workflows.json.")
        return
    
    package_dir = get_repo_root()
    
    # Check notebooks subdirectory first, then root
    notebook_path = package_dir / "notebooks" / notebook_file
    if not notebook_path.exists():
        notebook_path = package_dir / notebook_file
    
    if not notebook_path.exists():
        print(f"Error: Notebook not found at {notebook_path}")
        print(f"   Expected notebook: {notebook_file}")
        print(f"   Make sure the notebook exists in the project directory.")
        sys.exit(1)
    
    print(f"Opening {display_name} Analysis Notebook...")
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




def run_logs_command(command: str, pattern: str = "*_logs*.jsonl", 
                     notebook: str = "agent", port: int = 8888):
    """Run logs analysis commands."""
    package_dir = get_repo_root()
    
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
            print(f"\n Event Type Distribution:")
            for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
                percentage = (count / total_events) * 100
                print(f"  • {event_type}: {count:,} ({percentage:.1f}%)")
        
        if agents:
            print(f"\n Agent Distribution:")
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
                                    if agent_details[agent_name]['first_seen'] is None or timestamp < agent_details[agent_name]['first_seen']:
                                        agent_details[agent_name]['first_seen'] = timestamp
                                    if agent_details[agent_name]['last_seen'] is None or timestamp > agent_details[agent_name]['last_seen']:
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
                                    if pipeline_details[pipeline_id]['first_seen'] is None or timestamp < pipeline_details[pipeline_id]['first_seen']:
                                        pipeline_details[pipeline_id]['first_seen'] = timestamp
                                    if pipeline_details[pipeline_id]['last_seen'] is None or timestamp > pipeline_details[pipeline_id]['last_seen']:
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
            print(f"   Make sure you've run a demo first to generate log files.")
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
        # Pass the parsed args to eval_main
        eval_main(args)
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
