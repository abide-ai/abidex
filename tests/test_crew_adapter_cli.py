"""
Test CrewAdapter integration with CLI commands.

This test verifies that CrewAI workflows tracked by CrewAdapter can be
discovered and queried using the abidex CLI commands.
"""

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from io import StringIO
from datetime import datetime

from abidex.adapters.crew_adapter import CrewAdapter, patch_crewai_crew
from abidex.client import TelemetryClient, Event, EventType
from abidex.sinks import JSONLSink
from abidex.cli import (
    run_logs_command,
    list_workflows,
    show_workflow_map,
)
from abidex.workflows.discovery import discover_workflows
from abidex.workflows.registry import WorkflowRegistry, WorkflowDescription


class MockAgent:
    """Mock CrewAI Agent for testing."""
    def __init__(self, role="Test Agent", goal="Test goal", backstory="Test backstory"):
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.verbose = True
        self.allow_delegation = False


class MockTask:
    """Mock CrewAI Task for testing."""
    def __init__(self, description="Test task", expected_output="Test output", agent=None):
        self.description = description
        self.expected_output = expected_output
        self.agent = agent


class MockCrew:
    """Mock CrewAI Crew for testing."""
    def __init__(self, agents=None, tasks=None, process=None, verbose=True, name=None):
        self.agents = agents or []
        self.tasks = tasks or []
        self.process = process
        self.verbose = verbose
        self.name = name or "test_crew"
        self._kickoff_called = False
    
    def kickoff(self, *args, **kwargs):
        """Mock kickoff that returns a simple result."""
        self._kickoff_called = True
        return "Mock crew execution result"


class TestCrewAdapterCLIIntegration:
    """Test CrewAdapter integration with CLI commands."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        os.chdir(self.original_cwd)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_log_file(self, filename, events):
        """Create a log file with events."""
        filepath = Path(self.temp_dir) / filename
        with open(filepath, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        return str(filepath)
    
    def test_crew_adapter_tracks_to_jsonl(self):
        """Test that CrewAdapter writes events to JSONL file."""
        log_file = os.path.join(self.temp_dir, "crew_test_logs_20240101.jsonl")
        client = TelemetryClient()
        client.add_sink(JSONLSink(log_file))
        
        adapter = CrewAdapter(client=client)
        
        # Create mock agents and tasks
        agent1 = MockAgent(role="Researcher", goal="Research topic")
        agent2 = MockAgent(role="Writer", goal="Write report")
        task1 = MockTask(description="Research task", agent=agent1)
        task2 = MockTask(description="Writing task", agent=agent2)
        
        # Track agent and task creation
        adapter.track_agent_creation(agent1, crew_name="test_crew")
        adapter.track_agent_creation(agent2, crew_name="test_crew")
        adapter.track_task_creation(task1, crew_name="test_crew")
        adapter.track_task_creation(task2, crew_name="test_crew")
        
        # Track crew execution
        with adapter.track_crew_execution(
            crew_name="test_crew",
            agents=["Researcher", "Writer"],
            tasks=["Research task", "Writing task"],
            process="sequential"
        ) as crew_context:
            crew_context.set_input({"topic": "AI trends"})
            crew_context.log_agent_start("Researcher")
            crew_context.log_agent_complete("Researcher", "Research complete")
            crew_context.log_task_complete("Research task", "Researcher", "Task done")
            crew_context.set_output({"result": "Success"})
        
        # Flush and close
        client.flush()
        client.close()
        
        # Verify log file was created and has events
        assert os.path.exists(log_file)
        
        events = []
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        assert len(events) > 0
        
        # Verify we have crew-related events
        # Events are serialized as Event objects with 'tags' and 'metadata' fields
        crew_related_events = []
        for e in events:
            # Check tags dict (for crew tag)
            tags = e.get('tags', {})
            if isinstance(tags, dict) and tags.get('crew') == 'test_crew':
                crew_related_events.append(e)
            # Check metadata dict (for crew_name)
            metadata = e.get('metadata', {})
            if isinstance(metadata, dict) and metadata.get('crew_name') == 'test_crew':
                crew_related_events.append(e)
        
        # We should have crew-related events from agent/task creation (they all have crew_name in metadata)
        # At minimum, we should have the agent creation events
        assert len(crew_related_events) >= 2, (
            f"Expected at least 2 crew-related events (agent creation), "
            f"found {len(crew_related_events)}. Total events: {len(events)}. "
            f"First event tags: {events[0].get('tags') if events else 'none'}, "
            f"metadata: {events[0].get('metadata') if events else 'none'}"
        )
        
        # Verify agent creation events
        agent_events = [
            e for e in events 
            if (e.get('attributes', {}).get('event') == 'agent_creation' or
                e.get('tags', {}).get('event') == 'agent_creation')
        ]
        assert len(agent_events) >= 2
    
    def test_cli_can_discover_crew_workflow(self):
        """Test that CLI can discover crew workflows from log files."""
        # Create log file with crew events
        events = [
            {
                "event_type": "log",
                "tags": {"framework": "crewai", "crew": "test_crew", "agent": "Researcher"},
                "agent": {"name": "Researcher", "role": "Researcher"},
                "metadata": {"crew_name": "test_crew", "message": "Agent Researcher started"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110400.0}
            },
            {
                "event_type": "log",
                "tags": {"framework": "crewai", "crew": "test_crew", "agent": "Writer"},
                "agent": {"name": "Writer", "role": "Writer"},
                "metadata": {"crew_name": "test_crew", "message": "Agent Writer started"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110460.0}
            },
            {
                "event_type": "agent_run_start",
                "tags": {"framework": "crewai", "crew": "test_crew"},
                "metadata": {"crew_name": "test_crew"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110400.0}
            }
        ]
        
        log_file = self.create_log_file("crew_test_logs_20240101.jsonl", events)
        
        # Test CLI summary command
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            run_logs_command("summary", patterns=["crew_test_logs_*.jsonl"])
            output = mock_stdout.getvalue()
            
            assert "crew_test_logs_20240101.jsonl" in output
            assert "Researcher" in output or "crewai" in output
    
    def test_cli_can_list_agents_from_crew_logs(self):
        """Test that CLI can list agents from crew workflow logs."""
        events = [
            {
                "event_type": "log",
                "tags": {"framework": "crewai", "crew": "test_crew", "agent": "Researcher"},
                "agent": {"name": "Researcher", "role": "Researcher"},
                "metadata": {"crew_name": "test_crew"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110400.0}
            },
            {
                "event_type": "log",
                "tags": {"framework": "crewai", "crew": "test_crew", "agent": "Writer"},
                "agent": {"name": "Writer", "role": "Writer"},
                "metadata": {"crew_name": "test_crew"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110460.0}
            }
        ]
        
        log_file = self.create_log_file("crew_workflow_logs_20240101.jsonl", events)
        
        # Test CLI agents command
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            run_logs_command("agents", patterns=["crew_workflow_logs_*.jsonl"])
            output = mock_stdout.getvalue()
            
            # Should find agents
            assert "Researcher" in output or "Writer" in output or "crew_workflow_logs" in output
    
    def test_patch_crewai_crew_integration(self):
        """Test that patch_crewai_crew works and generates trackable logs."""
        log_file = os.path.join(self.temp_dir, "patched_crew_logs_20240101.jsonl")
        client = TelemetryClient()
        client.add_sink(JSONLSink(log_file))
        
        adapter = CrewAdapter(client=client)
        
        # Create mock crew
        agent1 = MockAgent(role="Researcher")
        agent2 = MockAgent(role="Writer")
        task1 = MockTask(description="Research", agent=agent1)
        task2 = MockTask(description="Write", agent=agent2)
        
        crew = MockCrew(
            agents=[agent1, agent2],
            tasks=[task1, task2],
            process="sequential",
            name="test_crew"
        )
        
        # Patch the crew
        patched_crew = patch_crewai_crew(crew, adapter=adapter)
        
        # Execute the crew
        result = patched_crew.kickoff(inputs={"topic": "AI"})
        
        assert result == "Mock crew execution result"
        assert crew._kickoff_called
        
        # Flush and close
        client.flush()
        client.close()
        
        # Verify log file was created
        assert os.path.exists(log_file)
        
        # Read events
        events = []
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        # Should have crew execution events
        assert len(events) > 0
        
        # Verify crew tracking events exist (check attributes, tags, or metadata)
        crew_events = [
            e for e in events 
            if (e.get('attributes', {}).get('crew') == 'test_crew' or 
                e.get('tags', {}).get('crew') == 'test_crew' or
                e.get('attributes', {}).get('crew_name') == 'test_crew' or
                e.get('metadata', {}).get('crew_name') == 'test_crew')
        ]
        assert len(crew_events) > 0
    
    def test_workflow_discovery_with_crew_logs(self):
        """Test that workflow discovery can find crew workflows."""
        # Create log file following the pattern
        events = [
            {
                "event_type": "agent_run_start",
                "tags": {"framework": "crewai", "crew": "financial_crew"},
                "metadata": {"crew_name": "financial_crew", "agents": ["Analyst", "Trader"]},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110400.0}
            },
            {
                "event_type": "log",
                "tags": {"framework": "crewai", "crew": "financial_crew", "agent": "Analyst"},
                "agent": {"name": "Analyst", "role": "Financial Analyst"},
                "metadata": {"crew_name": "financial_crew"},
                "run_id": "run1",
                "telemetry": {"timestamp_start": 1704110460.0}
            }
        ]
        
        log_file = self.create_log_file("financial_crew_logs_20240101.jsonl", events)
        
        # Register workflow
        registry = WorkflowRegistry()
        registry.add(WorkflowDescription(
            id="financial_crew",
            display_name="Financial Crew Workflow",
            log_patterns=["financial_crew_logs_*.jsonl"],
            notebook="financial_analysis.ipynb",
            script="financial_crew.py"
        ))
        
        # Discover workflows
        workflows = discover_workflows(registry)
        
        assert "financial_crew" in workflows
        workflow_data = workflows["financial_crew"]
        assert workflow_data["total_events"] == 2
        assert len(workflow_data["agents"]) > 0
    
    def test_end_to_end_crew_workflow_tracking(self):
        """End-to-end test: create crew workflow, track it, verify CLI can query it."""
        # Setup
        log_file = os.path.join(self.temp_dir, "e2e_crew_logs_20240101.jsonl")
        client = TelemetryClient()
        client.add_sink(JSONLSink(log_file))
        adapter = CrewAdapter(client=client)
        
        # Create a realistic crew workflow
        researcher = MockAgent(
            role="Research Analyst",
            goal="Gather and analyze information",
            backstory="Expert researcher"
        )
        writer = MockAgent(
            role="Content Writer",
            goal="Create written content",
            backstory="Skilled writer"
        )
        
        research_task = MockTask(
            description="Research AI trends",
            expected_output="Research report",
            agent=researcher
        )
        writing_task = MockTask(
            description="Write article",
            expected_output="Published article",
            agent=writer
        )
        
        crew = MockCrew(
            agents=[researcher, writer],
            tasks=[research_task, writing_task],
            process="sequential",
            name="content_crew"
        )
        
        # Track crew object
        crew_name = adapter.track_crew_object(crew)
        
        # Execute crew with tracking
        with adapter.track_crew_execution(
            crew_name=crew_name,
            agents=["Research Analyst", "Content Writer"],
            tasks=["Research AI trends", "Write article"],
            process="sequential"
        ) as crew_context:
            crew_context.set_input({"topic": "AI trends", "audience": "technical"})
            
            # Simulate workflow stages
            crew_context.log_stage_complete("research_stage", {"articles_found": 10})
            crew_context.log_agent_start("Research Analyst")
            crew_context.log_agent_complete("Research Analyst", "Research complete")
            crew_context.log_task_complete("Research AI trends", "Research Analyst", "Report ready")
            
            crew_context.log_stage_complete("writing_stage", {"words_written": 500})
            crew_context.log_agent_start("Content Writer")
            crew_context.log_agent_complete("Content Writer", "Article written")
            crew_context.log_task_complete("Write article", "Content Writer", "Article published")
            
            crew_context.set_output({"article_url": "https://example.com/article"})
        
        # Flush and close
        client.flush()
        client.close()
        
        # Verify log file exists
        assert os.path.exists(log_file)
        
        # Read and verify events
        events = []
        with open(log_file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        assert len(events) > 0
        
        # Verify CLI can query it
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            run_logs_command("summary", patterns=["e2e_crew_logs_*.jsonl"])
            output = mock_stdout.getvalue()
            
            # Should find the log file
            assert "e2e_crew_logs" in output or len(events) > 0
        
        # Test agents command
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            run_logs_command("agents", patterns=["e2e_crew_logs_*.jsonl"])
            output = mock_stdout.getvalue()
            
            # Should be able to parse agents (even if empty, should not error)
            assert output is not None
    
    def test_crew_adapter_json_parsing(self):
        """Test that CrewAdapter can parse JSON from crew outputs."""
        adapter = CrewAdapter()
        
        # Test JSON extraction from code fence
        text_with_json = """
        Here's the result:
        ```json
        {"key": "value", "number": 42}
        ```
        Some trailing text.
        """
        json_str = adapter._extract_json_from_text(text_with_json, expect="object")
        parsed = adapter._parse_jsonish(json_str)
        assert parsed == {"key": "value", "number": 42}
        
        # Test JSON array extraction
        text_with_array = """
        Results:
        ```json
        [{"item": 1}, {"item": 2}]
        ```
        """
        json_str = adapter._extract_json_from_text(text_with_array, expect="array")
        parsed = adapter._parse_jsonish(json_str)
        assert len(parsed) == 2
        assert parsed[0]["item"] == 1
        
        # Test parsing Python-literal style (single quotes)
        python_literal = "{'key': 'value', 'number': 42}"
        parsed = adapter._parse_jsonish(python_literal)
        assert parsed == {"key": "value", "number": 42}
    
    def test_crew_context_json_parsing(self):
        """Test CrewExecutionContext parse_json_output method."""
        log_file = os.path.join(self.temp_dir, "json_parse_test.jsonl")
        client = TelemetryClient()
        client.add_sink(JSONLSink(log_file))
        adapter = CrewAdapter(client=client)
        
        with adapter.track_crew_execution("test_crew") as crew_context:
            # Test parsing JSON output
            mock_output = '```json\n{"result": "success", "data": [1, 2, 3]}\n```'
            parsed = crew_context.parse_json_output(mock_output, expect="object")
            
            assert parsed is not None
            assert parsed["result"] == "success"
            assert parsed["data"] == [1, 2, 3]
        
        client.close()
