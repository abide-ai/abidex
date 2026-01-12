import subprocess
import sys
from datetime import datetime
from pathlib import Path

from ..cli_common import get_repo_root
from ..log_patterns import find_log_files, format_log_patterns
from .discovery import discover_workflows
from .registry import WorkflowRegistry
from .paths import resolve_workflow_notebook_path


def list_workflows(registry: WorkflowRegistry = None):
    """List all discovered workflows."""
    if registry is None:
        registry = WorkflowRegistry.load_default()

    workflows = discover_workflows(registry)

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
            last = datetime.fromtimestamp(info['last_seen']).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   Last Seen: {last}")
        print()


def show_workflow_map(workflow_name: str, registry: WorkflowRegistry = None):
    """Show workflow map with agents and their last calls."""
    if registry is None:
        registry = WorkflowRegistry.load_default()

    workflow = registry.resolve_name(workflow_name)

    if not workflow:
        print(f"Error: Workflow '{workflow_name}' not found.")
        print("\nAvailable workflows:")
        for info in registry.list():
            print(f"  - {info.display_name} ({info.id})")
        return

    workflows = discover_workflows(registry)

    if workflow.id not in workflows:
        print(f"Error: No data found for workflow '{workflow_name}'.")
        print("Tip: Run the workflow first to generate log files.")
        return

    info = workflows[workflow.id]

    print(f"\n{info['display_name']} Workflow Map")
    print("=" * 60)
    print(f"Workflow ID: {workflow.id}")
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
            last_call_time = datetime.fromtimestamp(
                agent_data['last_call_time']
            ).strftime('%Y-%m-%d %H:%M:%S')
            print(f"   Last Call: {agent_data['last_call']}")
            print(f"   Last Call Time: {last_call_time}")
        else:
            print("   Last Call: N/A")

    print()


def show_workflow_logs(workflow_name: str, registry: WorkflowRegistry = None):
    """Show telemetry logs for a specific workflow."""
    if registry is None:
        registry = WorkflowRegistry.load_default()

    workflow = registry.resolve_name(workflow_name)

    if not workflow:
        print(f"Error: Workflow '{workflow_name}' not found.")
        return

    log_patterns = workflow.log_patterns
    log_files = find_log_files(log_patterns)

    if not log_files:
        print(f"No log files found for workflow '{workflow_name}'.")
        formatted = format_log_patterns(log_patterns)
        if formatted:
            print(f"Patterns: {formatted}")
        return

    print(f"\nTelemetry Logs for {workflow.display_name}")
    print("=" * 60)
    formatted = format_log_patterns(log_patterns)
    if formatted:
        print(f"Log Patterns: {formatted}")
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

        file_path_obj = Path(file_path)
        size_mb = file_path_obj.stat().st_size / (1024 * 1024) if file_path_obj.exists() else 0
        print(f"  {file_path}")
        print(f"    Events: {file_events:,} ({size_mb:.2f} MB)")

    print(f"\nTotal Events: {total_events:,}")


def open_workflow_notebook(workflow_name: str, port: int = 8888,
                           registry: WorkflowRegistry = None):
    """Open Jupyter notebook for a specific workflow."""
    if registry is None:
        registry = WorkflowRegistry.load_default()

    package_dir = get_repo_root()
    notebook_path = resolve_workflow_notebook_path(
        workflow_name,
        registry=registry,
        repo_root=package_dir,
    )

    if not notebook_path or not notebook_path.exists():
        print(f"Error: Notebook not found for '{workflow_name}'.")
        print("   Make sure you've run the workflow or configured a notebook path.")
        sys.exit(1)

    print(f"Opening {workflow.display_name} Analysis Notebook...")
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
