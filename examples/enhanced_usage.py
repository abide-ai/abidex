"""
Enhanced usage examples for Abide AgentKit with new features.

This example demonstrates:
- Enhanced Event schema with latency and token tracking
- Sampling support
- Telemetry logging integration
- Automatic instrumentation
- Context managers and decorators
"""

import time
from abide_agentkit import (
    TelemetryClient, AgentRun, get_logger, get_agent_logger,
    setup_telemetry_logging, instrumentation
)
from abide_agentkit.sinks import JSONLSink, PrometheusSink


def main():
    print("🚀 Enhanced Abide AgentKit Usage Examples")
    
    # 1. Set up enhanced telemetry client with sampling
    print("\n1. Setting up enhanced telemetry client...")
    client = TelemetryClient(
        agent_id="enhanced_demo_agent",
        sample_rate=0.8,  # Sample 80% of events
        metadata={"version": "2.0", "environment": "demo"},
        default_tags={"demo": "enhanced_features"}
    )
    
    # Add sinks
    client.add_sink(JSONLSink("enhanced_telemetry.jsonl"))
    
    # Add Prometheus sink if available
    try:
        client.add_sink(PrometheusSink(metric_prefix="demo_agent"))
        print("✅ Prometheus metrics enabled")
    except ImportError:
        print("⚠️ Prometheus not available, skipping metrics")
    
    # 2. Demonstrate new Event schema with performance tracking
    print("\n2. Creating events with enhanced schema...")
    
    # Using the new infer() context manager
    with client.infer("gpt-4", "openai", batch_size=3) as event:
        # Simulate model call
        time.sleep(0.1)
        
        # Set token counts
        event.input_token_count = 150
        event.output_token_count = 75
        event.total_tokens = 225
        event.prompt_char_length = 600
        event.response_char_length = 300
    
    print("✅ Model call tracked with performance metrics")
    
    # 3. Demonstrate decorator-based instrumentation
    print("\n3. Using decorator-based instrumentation...")
    
    @client.record(model="custom-model", backend="demo")
    def simulate_ai_task(prompt, max_tokens=100):
        """Simulate an AI task that we want to track."""
        time.sleep(0.05)  # Simulate processing
        return f"Response to: {prompt[:50]}..."
    
    result = simulate_ai_task("What is the meaning of life?", max_tokens=150)
    print(f"✅ Decorated function result: {result}")
    
    # 4. Telemetry logging integration
    print("\n4. Demonstrating telemetry logging...")
    
    # Get a telemetry logger
    logger = get_logger("demo_logger", client=client)
    logger.info("This is a log message that goes to telemetry", 
                data={"user_id": "123", "action": "demo"})
    
    # Get an agent-specific logger
    agent_logger = get_agent_logger("demo_agent", client=client)
    agent_logger.thinking("I need to process this request...")
    agent_logger.action("processing_request", details={"complexity": "medium"})
    agent_logger.decision("use_gpt4", reasoning="Complex query requires advanced model")
    
    print("✅ Telemetry logging demonstrated")
    
    # 5. Agent run with enhanced tracking
    print("\n5. Enhanced agent run tracking...")
    
    with AgentRun("enhanced_demo_run", client=client) as run:
        run.add_data("task", "demonstrate enhanced features")
        run.add_data("complexity", "high")
        
        # Simulate some work with logging
        with run.client.infer("claude-3", "anthropic") as model_call:
            time.sleep(0.1)
            model_call.input_token_count = 200
            model_call.output_token_count = 100
            model_call.total_tokens = 300
        
        # Log within the run context
        run_logger = logger.with_context(run_id=run.run_id, span_id=run.span_id)
        run_logger.info("Processing within agent run")
        
        run.add_data("result", "success")
    
    print("✅ Enhanced agent run completed")
    
    # 6. Automatic instrumentation examples
    print("\n6. Automatic instrumentation examples...")
    
    # Mock OpenAI-like client
    class MockOpenAIClient:
        class Chat:
            class Completions:
                def create(self, model="gpt-4", messages=None, **kwargs):
                    time.sleep(0.1)
                    return type('Response', (), {
                        'choices': [type('Choice', (), {
                            'message': type('Message', (), {
                                'content': f"Mock response to {len(messages or [])} messages"
                            })()
                        })()],
                        'usage': type('Usage', (), {
                            'prompt_tokens': 50,
                            'completion_tokens': 25,
                            'total_tokens': 75
                        })()
                    })()
            
            def __init__(self):
                self.completions = self.Completions()
        
        def __init__(self):
            self.chat = self.Chat()
    
    # Instrument the mock client
    mock_client = MockOpenAIClient()
    instrumented_client = instrumentation.instrument_openai_client(
        mock_client, 
        telemetry_client=client
    )
    
    # Use the instrumented client - calls are automatically tracked
    response = instrumented_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello, world!"}]
    )
    
    print(f"✅ Instrumented OpenAI call: {response.choices[0].message.content}")
    
    # 7. Custom function instrumentation
    print("\n7. Custom function instrumentation...")
    
    def extract_token_count(result, *args, **kwargs):
        # Custom token extractor
        return {"output_tokens": len(str(result).split())}
    
    @instrumentation.create_instrumented_function(
        lambda prompt: f"AI response to: {prompt}",
        telemetry_client=client,
        model="custom-ai",
        backend="demo",
        extract_tokens=extract_token_count
    )
    def custom_ai_function(prompt):
        time.sleep(0.05)
        return f"Intelligent response to: {prompt}"
    
    ai_result = custom_ai_function("What's the weather like?")
    print(f"✅ Custom instrumented function: {ai_result}")
    
    # 8. Batch event creation
    print("\n8. Batch event creation...")
    
    # Create multiple events quickly
    events = []
    for i in range(5):
        event = client.new_event(
            model=f"model-{i}",
            backend="batch_demo",
            tags={"batch_id": "demo_batch", "index": str(i)}
        )
        event.input_token_count = 10 + i
        event.output_token_count = 5 + i
        event.finish()
        events.append(event)
    
    # Emit all events
    for event in events:
        client.emit(event)
    
    print(f"✅ Created and emitted {len(events)} batch events")
    
    # 9. Integration with standard Python logging
    print("\n9. Standard Python logging integration...")
    
    import logging
    
    # Set up telemetry logging for all Python loggers
    setup_telemetry_logging(client=client, level=logging.INFO)
    
    # Now standard Python logging also goes to telemetry
    py_logger = logging.getLogger("demo.standard")
    py_logger.info("This standard log message also goes to telemetry!")
    py_logger.error("This error is tracked in telemetry too!")
    
    print("✅ Standard Python logging integrated")
    
    # 10. Performance and sampling demonstration
    print("\n10. Performance and sampling demonstration...")
    
    # Create a high-volume client with lower sampling
    high_volume_client = TelemetryClient(
        agent_id="high_volume_agent",
        sample_rate=0.1,  # Only sample 10% to reduce overhead
        sinks=[JSONLSink("high_volume.jsonl")]
    )
    
    # Generate many events - only ~10% will be actually recorded
    start_time = time.time()
    for i in range(100):
        with high_volume_client.infer(f"model-{i%5}", "high_volume") as event:
            event.input_token_count = i
            event.output_token_count = i // 2
    
    duration = time.time() - start_time
    print(f"✅ Generated 100 events in {duration:.3f}s (with 10% sampling)")
    
    # Cleanup
    client.flush()
    client.close()
    high_volume_client.flush()
    high_volume_client.close()
    
    print("\n🎉 Enhanced features demonstration complete!")
    print("Check 'enhanced_telemetry.jsonl' for detailed event logs")


if __name__ == "__main__":
    main()
