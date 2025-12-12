"""
Test script to demonstrate agent log collection locally.
Shows exactly what logs are collected and how they appear.
"""

import sys
import os
import time
import json
import logging
from datetime import datetime

# Add the package to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from abidex import (
    TelemetryClient, 
    AgentRun, 
    get_logger, 
    get_agent_logger,
    setup_telemetry_logging
)
from abidex.sinks import JSONLSink


def simulate_agent_workflow():
    """Simulate a complete agent workflow with various types of logs."""
    
    print(" Starting Agent Log Collection Test")
    print("=" * 50)
    
    # 1. Set up telemetry client
    client = TelemetryClient(
        agent_id="TestAgent_v1.0",
        metadata={
            "environment": "local_test",
            "user": "test_user",
            "session_id": "test_session_123"
        }
    )
    
    # Add JSON sink to capture all logs
    log_file = f"agent_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    client.add_sink(JSONLSink(log_file))
    
    print(f" Logs will be saved to: {log_file}")
    print()
    
    # 2. Get different types of loggers
    general_logger = get_logger("agent.general", client=client)
    agent_logger = get_agent_logger("TestAgent", client=client)
    
    # 3. Set up standard Python logging integration
    setup_telemetry_logging(client=client, level=logging.INFO)
    py_logger = logging.getLogger("agent.python")
    
    print(" Simulating agent workflow...")
    print()
    
    # 4. Agent startup logs
    print("1. Agent Startup Phase")
    agent_logger.info("Agent starting up", {"version": "1.0", "mode": "test"})
    general_logger.info("Configuration loaded", {"config_file": "test.yaml"})
    py_logger.info("Standard Python log: Agent initialized")
    
    time.sleep(0.1)
    
    # 5. Agent thinking/reasoning phase
    print("2. Agent Reasoning Phase")
    agent_logger.thinking("I need to analyze the user's request about weather data")
    agent_logger.thinking("Let me break this down: location, timeframe, data type needed")
    
    time.sleep(0.1)
    
    # 6. Agent decision making
    print("3. Agent Decision Phase")
    agent_logger.decision(
        "use_weather_api", 
        reasoning="Weather API provides most accurate current data",
        options={"alternatives": ["web_scraping", "cached_data"], "confidence": 0.85}
    )
    
    time.sleep(0.1)
    
    # 7. Agent actions with context
    print("4. Agent Action Phase")
    with AgentRun("weather_lookup_task", client=client) as run:
        run.add_data("task_type", "weather_query")
        run.add_data("location", "San Francisco")
        
        # Log within the run context
        run_logger = agent_logger.with_context(run_id=run.run_id, span_id=run.span_id)
        
        run_logger.action("fetching_weather_data", {
            "api": "openweather",
            "endpoint": "/current",
            "params": {"q": "San Francisco", "units": "metric"}
        })
        
        # Simulate API call with model inference
        with client.infer("gpt-4", "openai") as model_call:
            time.sleep(0.2)  # Simulate API delay
            
            model_call.input_token_count = 45
            model_call.output_token_count = 23
            model_call.total_tokens = 68
            
            run_logger.info("Model processed weather data interpretation")
        
        run_logger.action("formatting_response", {
            "format": "natural_language",
            "temperature": "22°C",
            "conditions": "partly_cloudy"
        })
        
        run.add_data("result", "success")
        run.add_data("temperature", "22°C")
    
    time.sleep(0.1)
    
    # 8. Error handling demonstration
    print("5. Error Handling Phase")
    try:
        # Simulate an error
        raise ValueError("Simulated API timeout")
    except Exception as e:
        agent_logger.error("API call failed", error=e, data={
            "retry_count": 1,
            "fallback_available": True
        })
        general_logger.warning("Falling back to cached data")
    
    time.sleep(0.1)
    
    # 9. Agent completion
    print("6. Agent Completion Phase")
    agent_logger.info("Task completed successfully", {
        "execution_time_ms": 500,
        "tokens_used": 68,
        "api_calls": 2
    })
    
    # Various log levels
    agent_logger.debug("Debug info: internal state clean")
    agent_logger.warning("Warning: API rate limit approaching")
    py_logger.error("Standard Python error log for testing")
    
    # 10. Cleanup and flush
    client.flush()
    client.close()
    
    print()
    print(" Agent workflow simulation complete!")
    print(f" Check the log file: {log_file}")
    
    return log_file


def analyze_collected_logs(log_file):
    """Analyze and display the collected logs."""
    
    print("\n" + "=" * 50)
    print(" COLLECTED LOGS ANALYSIS")
    print("=" * 50)
    
    if not os.path.exists(log_file):
        print(f" Log file not found: {log_file}")
        return
    
    logs = []
    with open(log_file, 'r') as f:
        for line in f:
            if line.strip():
                logs.append(json.loads(line.strip()))
    
    print(f" Total logs collected: {len(logs)}")
    print()
    
    # Group logs by type
    log_types = {}
    for log in logs:
        event_type = log.get('event_type', 'unknown')
        log_types[event_type] = log_types.get(event_type, 0) + 1
    
    print(" Log Types:")
    for log_type, count in log_types.items():
        print(f"  • {log_type}: {count} events")
    
    print("\n Sample Log Entries:")
    print("-" * 30)
    
    # Show different types of logs
    for i, log in enumerate(logs[:10]):  # Show first 10 logs
        print(f"\n[{i+1}] {log.get('event_type', 'unknown').upper()}")
        print(f"    Timestamp: {log.get('telemetry', {}).get('timestamp_start_iso', 'N/A')}")
        
        if 'agent' in log and log['agent']:
            print(f"    Agent: {log['agent'].get('name', 'N/A')}")
        
        if 'action' in log and log['action']:
            action = log['action']
            print(f"    Action: {action.get('name', action.get('type', 'N/A'))}")
            if action.get('input'):
                print(f"    Input: {str(action['input'])[:50]}...")
        
        if 'model_call' in log and log['model_call']:
            model = log['model_call']
            print(f"    Model: {model.get('model', 'N/A')} ({model.get('backend', 'N/A')})")
            if model.get('input_token_count'):
                print(f"    Tokens: {model['input_token_count']} in, {model.get('output_token_count', 0)} out")
        
        if log.get('level'):
            print(f"    Level: {log['level']}")
        
        if log.get('metadata'):
            print(f"    Metadata: {json.dumps(log['metadata'], indent=6)}")
    
    print(f"\n Full logs available in: {log_file}")
    print(" You can examine all logs with: cat " + log_file + " | jq .")


def main():
    """Main test function."""
    print(" Agent Log Collection Test")
    print("This will simulate an AI agent workflow and show what logs are collected.\n")
    
    # Run the simulation
    log_file = simulate_agent_workflow()
    
    # Analyze the results
    analyze_collected_logs(log_file)
    
    print("\n KEY INSIGHTS:")
    print("• Agent logs include: startup, thinking, decisions, actions, errors")
    print("• Each log has structured data: agent info, timestamps, metadata")
    print("• Model calls are tracked with token counts and performance metrics")
    print("• Context is preserved across related operations (run_id, span_id)")
    print("• Standard Python logging is also captured")
    print("• All logs are JSON formatted for easy parsing and analysis")


if __name__ == "__main__":
    main()
