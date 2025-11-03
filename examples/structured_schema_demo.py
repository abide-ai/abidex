"""
Demonstration of the new structured telemetry schema.

This example shows how events now follow a structured format with
nested objects for agent, action, model_call, telemetry, and metadata.
"""

import json
import time
import sys
import os

# Add parent directory to path for importing abide_agentkit
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abide_agentkit import TelemetryClient, AgentRun, ModelCall, ToolCall
from abide_agentkit.sinks import JSONLSink


def main():
    print("🔥 Structured Schema Demo - Abide AgentKit")
    
    # Set up client with metadata
    client = TelemetryClient(
        agent_id="ResearchAgent",
        metadata={
            "env": "prod",
            "session_user": "hashed_user_123",
            "pipeline": "research_agent"
        }
    )
    
    # Add sink to capture structured events
    client.add_sink(JSONLSink("structured_events.jsonl"))
    
    print("\n1. Creating structured events...")
    
    # Example 1: Tool call event matching the schema
    with ToolCall("web_search", client=client, run_id="conv-1234") as tool:
        # Set agent info
        tool.client.emit(tool.client.new_event(
            agent_name="ResearchAgent",
            agent_role="retriever", 
            agent_version="1.2",
            conversation_id="conv-1234"
        ))
        
        # Set tool input
        tool.set_input(query="latest papers on sparse transformers")
        
        # Simulate tool execution
        time.sleep(0.52)  # 520ms latency
        
        # Set tool output
        result = [{"title": "Sparse Transformer Paper", "year": 2023}]
        tool.set_output(result)
    
    print("✅ Tool call event created")
    
    # Example 2: Model call event with full schema
    with ModelCall("claude-3-sonnet", "anthropic_claude", run_id="conv-1234") as model:
        # Create a more detailed event manually to show full schema
        event = client.new_event(
            agent_name="ResearchAgent",
            agent_role="retriever",
            agent_version="1.2",
            conversation_id="conv-1234"
        )
        
        # Set the trace ID to match your example
        event.trace_id = "b80d9f"  # Shortened for demo
        
        # Set action info
        event.set_action_info(
            action_type="tool_call",
            name="web_search", 
            input_data="latest papers on sparse transformers",
            output_data='[{"title":"Sparse Transformer Paper","year":2023}]'
        )
        
        # Set model call info
        event.set_model_call_info(
            backend="anthropic_claude",
            model="claude-3-sonnet",
            prompt="User asked: summarize this article...",
            completion="This article discusses...",
            input_tokens=246,
            output_tokens=128
        )
        
        # Set custom metadata
        event.metadata.update({
            "env": "prod",
            "session_user": "hashed_user_id", 
            "pipeline": "research_agent"
        })
        
        # Simulate processing time and finish
        time.sleep(0.52)
        event.finish()
        
        # Calculate throughput (tokens per second)
        if event.telemetry.latency_ms and event.model_call.output_token_count:
            event.telemetry.throughput_tokens_per_sec = (
                event.model_call.output_token_count / (event.telemetry.latency_ms / 1000.0)
            )
        
        client.emit(event)
    
    print("✅ Model call event with full structured schema created")
    
    # Example 3: Agent run with nested events
    with AgentRun("research_task", client=client) as run:
        run.add_data("task_complexity", "high")
        
        # Create event with agent info
        agent_event = client.new_event(
            agent_name="ResearchAgent",
            agent_role="retriever",
            agent_version="1.2",
            conversation_id=run.run_id
        )
        
        agent_event.metadata.update({
            "env": "prod",
            "session_user": "hashed_user_id",
            "pipeline": "research_agent"
        })
        
        # Nested model call
        with client.infer("gpt-4", "openai") as infer_event:
            time.sleep(0.1)
            
            # Set structured model call info
            infer_event.set_model_call_info(
                backend="openai",
                model="gpt-4",
                prompt="Analyze research papers...",
                completion="Based on the analysis...",
                input_tokens=150,
                output_tokens=75
            )
            
            # Set agent info
            infer_event.set_agent_info("ResearchAgent", "retriever", "1.2")
            infer_event.conversation_id = run.run_id
        
        run.add_data("result", "analysis_complete")
    
    print("✅ Agent run with nested structured events created")
    
    # Flush and close
    client.flush()
    client.close()
    
    print("\n2. Reading back structured events...")
    
    # Read and display the structured events
    try:
        with open("structured_events.jsonl", "r") as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    event_data = json.loads(line.strip())
                    print(f"\n--- Event {i} ---")
                    print(json.dumps(event_data, indent=2))
                    
                    # Highlight the structured sections
                    if "agent" in event_data and event_data["agent"]:
                        print(f"Agent: {event_data['agent']}")
                    if "action" in event_data and event_data["action"]:
                        print(f"Action: {event_data['action']}")
                    if "model_call" in event_data and event_data["model_call"]:
                        print(f"Model Call: {event_data['model_call']}")
                    if "telemetry" in event_data and event_data["telemetry"]:
                        print(f"Telemetry: {event_data['telemetry']}")
                    
                    if i >= 3:  # Limit output for demo
                        break
    except FileNotFoundError:
        print("No events file found")
    
    print("\n🎉 Structured schema demonstration complete!")
    print("\nKey benefits of the structured schema:")
    print("- Clear separation of concerns (agent, action, model_call, telemetry)")
    print("- Consistent field names across all events")
    print("- Rich performance metrics (latency, throughput, tokens)")
    print("- Easy to query and analyze")
    print("- Compatible with time-series databases and analytics tools")


def create_example_schema_event():
    """Create an event that exactly matches your example schema."""
    client = TelemetryClient()
    
    event = client.new_event(
        agent_name="ResearchAgent",
        agent_role="retriever",
        agent_version="1.2",
        conversation_id="conv-1234"
    )
    
    # Set the exact values from your schema example
    event.trace_id = "b80d...9f"
    event.conversation_id = "conv-1234"
    
    # Agent info
    event.set_agent_info("ResearchAgent", "retriever", "1.2")
    
    # Action info
    event.set_action_info(
        action_type="tool_call",
        name="web_search",
        input_data="latest papers on sparse transformers",
        output_data='[{"title":"Sparse Transformer Paper","year":2023}]'
    )
    event.action.success = True
    event.action.latency_ms = 520
    
    # Model call info
    event.set_model_call_info(
        backend="anthropic_claude",
        model="claude-3-sonnet",
        prompt="User asked: summarize this article...",
        completion="This article discusses...",
        input_tokens=246,
        output_tokens=128
    )
    
    # Telemetry info
    event.telemetry.timestamp_start = 1730660000.123
    event.telemetry.timestamp_end = 1730660000.643
    event.telemetry.latency_ms = 520
    event.telemetry.total_tokens = 374
    event.telemetry.throughput_tokens_per_sec = 720.0
    
    # Metadata
    event.metadata.update({
        "env": "prod",
        "session_user": "hashed_user_id",
        "pipeline": "research_agent"
    })
    
    return event


if __name__ == "__main__":
    main()
    
    print("\n" + "="*50)
    print("EXAMPLE MATCHING YOUR SCHEMA:")
    print("="*50)
    
    # Create and display the exact example
    example_event = create_example_schema_event()
    example_dict = example_event.to_dict()
    print(json.dumps(example_dict, indent=2))
