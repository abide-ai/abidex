"""
Eval CLI entry point for Abide AgentKit demos.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .cli_common import get_repo_root
from .workflows.cli_helpers import (
    format_workflow_choices,
    get_configured_workflows,
    resolve_eval_target,
)
from .workflows.paths import resolve_workflow_script_path
from .workflows.registry import WorkflowRegistry


def run_eval_demo(
    demo: str,
    transactions: int = 25,
    output_dir: str = ".",
    script_path: Optional[str] = None,
):
    """Run an agent demo."""
    repo_root = get_repo_root()
    registry = WorkflowRegistry.load_default()
    demo_script = resolve_workflow_script_path(
        demo,
        registry=registry,
        script_override=script_path,
        repo_root=repo_root,
    )

    if not demo_script or not demo_script.exists():
        if script_path:
            print(f"Error: Demo script not found at {script_path}")
        else:
            print(f"Error: Demo script not found for '{demo}'")
        sys.exit(1)

    workflow = registry.resolve_name(demo)
    display_name = workflow.display_name if workflow else demo

    if demo in ("fraud", "fraud_detection"):
        print(" Running Fraud Detection Pipeline Demo...")
        print("=" * 50)
        print(f"Processing {transactions} transactions...")
    else:
        print(f" Running {display_name} Demo...")
        print("=" * 50)

    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root) + os.pathsep + env.get("PYTHONPATH", "")

    if demo in ("fraud", "fraud_detection"):
        env["FRAUD_DEMO_TRANSACTIONS"] = str(transactions)

    result = subprocess.run(
        [sys.executable, str(demo_script)],
        cwd=str(demo_script.parent),
        env=env
    )

    sys.exit(result.returncode)


def eval_main(args=None):
    """
    Main entry point for the eval CLI.
    
    Args:
        args: Parsed arguments (Namespace object). If None, will parse from sys.argv.
    """
    # If args not provided, parse them (for standalone usage)
    if args is None:
        parser = argparse.ArgumentParser(
            description="Abide AgentKit Evaluation - Run agent demos and tests",
            formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )

        parser.add_argument(
            "demo",
            help="Workflow ID or alias (from workflows.json or ABIDEX_WORKFLOW_DIR)"
        )
        parser.add_argument("--transactions", type=int, default=25,
                           help="Number of transactions (for fraud demo)")
        parser.add_argument("--output-dir", default=".", help="Output directory")
        parser.add_argument(
            "--script-path",
            help="Optional path to the demo script (overrides workflow config)"
        )

        args = parser.parse_args()

    registry = WorkflowRegistry.load_default()
    repo_root = get_repo_root()
    resolution = resolve_eval_target(
        args.demo,
        args.script_path,
        registry=registry,
        repo_root=repo_root,
    )

    if resolution.used_script_override:
        if not resolution.script_path:
            print(f"Error: Demo script not found at {args.script_path}")
            sys.exit(1)
    else:
        if not resolution.script_path:
            if resolution.workflow is None:
                print(f"Error: Workflow '{args.demo}' not found.")
            else:
                print(f"Error: Demo script not found for '{args.demo}'.")
            _print_eval_workflow_help(registry, repo_root)
            sys.exit(1)
        args.demo = resolution.demo
    
    run_eval_demo(args.demo, args.transactions, args.output_dir, args.script_path)


def _print_eval_workflow_help(registry: WorkflowRegistry, repo_root: Path) -> None:
    choices = get_configured_workflows(
        registry=registry,
        repo_root=repo_root,
        require_script=True,
    )
    if choices:
        print("\nAvailable workflows:")
        print(format_workflow_choices(choices))
    else:
        print("\nNo configured workflows with scripts were found.")
    print("\nTip: configure workflows in workflows.json or set "
          "ABIDEX_WORKFLOW_CONFIG/ABIDEX_WORKFLOW_DIR.")
