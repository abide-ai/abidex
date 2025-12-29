"""
Eval CLI entry point for Abide AgentKit demos.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


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

    else:
        print(f"Error: Unknown demo '{demo}'")
        sys.exit(1)


def eval_main():
    """Standalone entry point for eval command."""
    parser = argparse.ArgumentParser(
        description="Abide AgentKit Evaluation - Run agent demos and tests",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument("demo", choices=["simple", "fraud"],
                       help="Which demo to run")
    parser.add_argument("--transactions", type=int, default=25,
                       help="Number of transactions (for fraud demo)")
    parser.add_argument("--output-dir", default=".", help="Output directory")

    args = parser.parse_args()
    run_eval_demo(args.demo, args.transactions, args.output_dir)
