#!/usr/bin/env python3
"""
Weather demo to demonstrate agent log collection using the AbideX SDK.
"""

import json
import os
import sys
import time
from datetime import datetime

# Add the package to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from abidex import AgentRun, TelemetryClient
from abidex.sinks import JSONLSink


def run_weather_logging_demo():
    """Run the weather agent logging flow and return the log file path."""

    print(" Weather Agent Log Collection Test")
    print("=" * 50)

    client = TelemetryClient(
        agent_id="WeatherAgent",
        metadata={
            "environment": "local_test",
            "user": "test_user",
        },
    )

    log_file = f"weather_agent_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    client.add_sink(JSONLSink(log_file))

    print(f" Logs will be saved to: {log_file}")
    print()

    print("1. Basic Client Logging")
    client.log("Agent starting up", level="info", data={"version": "1.0"})
    client.log("Configuration loaded", level="info", data={"config": "test.yaml"})

    time.sleep(0.1)

    print("2. Agent Run with Context")
    with AgentRun("weather_task", client=client) as run:
        run.add_data("task_type", "weather_lookup")
        run.add_data("location", "San Francisco")

        client.log(
            "Processing weather request",
            level="info",
            data={"step": "data_collection"},
            run_id=run.run_id,
            span_id=run.span_id,
        )

        with client.infer("gpt-4", "openai") as model_call:
            time.sleep(0.1)
            model_call.input_token_count = 45
            model_call.output_token_count = 23

        client.log(
            "Weather data processed",
            level="info",
            data={"result": "success", "temperature": "22C"},
            run_id=run.run_id,
            span_id=run.span_id,
        )

        run.add_data("result", "completed")

    time.sleep(0.1)

    print("3. Error Logging")
    try:
        raise ValueError("Simulated API timeout")
    except Exception as e:
        client.error(e, context={"retry_count": 1, "fallback": True})

    print("4. Metrics")
    client.metric("response_time", 250.5, unit="ms")
    client.metric("tokens_used", 68, unit="tokens")

    client.flush()
    client.close()

    print("\n Weather agent logging test complete!")
    print(f" Check the log file: {log_file}")

    return log_file


def analyze_logs(log_file):
    """Analyze the generated logs."""

    print("\n" + "=" * 50)
    print(" LOG ANALYSIS")
    print("=" * 50)

    if not os.path.exists(log_file):
        print(f" Log file not found: {log_file}")
        return

    logs = []
    with open(log_file, "r") as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line.strip()))

    print(f" Total events collected: {len(logs)}")
    print()

    event_types = {}
    for log in logs:
        event_type = log.get("event_type", "unknown")
        event_types[event_type] = event_types.get(event_type, 0) + 1

    print(" Event Types:")
    for event_type, count in event_types.items():
        print(f"  - {event_type}: {count} events")

    print("\n Sample Events:")
    print("-" * 30)

    for i, log in enumerate(logs[:8]):  # Show first 8 events
        print(f"\n[{i + 1}] {log.get('event_type', 'unknown').upper()}")

        telemetry = log.get("telemetry", {})
        if telemetry.get("timestamp_start_iso"):
            print(f"    Time: {telemetry['timestamp_start_iso']}")

        agent = log.get("agent", {})
        if agent and agent.get("name"):
            print(f"    Agent: {agent['name']}")

        action = log.get("action", {})
        if action and action.get("name"):
            print(f"    Action: {action['name']}")
            if action.get("input"):
                print(f"    Input: {str(action['input'])[:50]}...")

        model_call = log.get("model_call", {})
        if model_call and model_call.get("model"):
            print(
                f"    Model: {model_call['model']} ({model_call.get('backend', 'N/A')})"
            )
            if model_call.get("input_token_count"):
                print(
                    f"    Tokens: {model_call['input_token_count']} in, "
                    f"{model_call.get('output_token_count', 0)} out"
                )

        if telemetry.get("latency_ms"):
            print(f"    Latency: {telemetry['latency_ms']:.1f}ms")

        metadata = log.get("metadata", {})
        if metadata:
            print(f"    Metadata: {json.dumps(metadata)}")

    print(f"\n Full logs in: {log_file}")
    print(" View with: cat " + log_file + " | jq .")


def main():
    print(" Testing Weather Agent Log Collection")
    print("This demonstrates what logs are collected from an AI agent.\n")

    log_file = run_weather_logging_demo()

    analyze_logs(log_file)

    print("\n WHAT WE LEARNED:")
    print("- Agent events include: runs, model calls, logs, errors, metrics")
    print("- Each event has structured data with agent, action, model_call sections")
    print("- Context is preserved (run_id, span_id, trace_id)")
    print("- Performance metrics are automatically tracked")
    print("- All data is JSON structured for easy analysis")
    print("- Events can be sent to multiple sinks (files, HTTP, Prometheus)")

    os._exit(0)


if __name__ == "__main__":
    main()
