import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

from abidex.workflows.registry import WorkflowRegistry, WorkflowDescription
from abidex.workflows.discovery import discover_workflows
from abidex.cli import (
    discover_workflows as cli_discover_workflows,
    resolve_workflow_name,
    list_workflows,
    show_workflow_map,
    show_workflow_logs,
    open_workflow_notebook
)


class TestWorkflowRegistry:
    """Test WorkflowRegistry functionality."""

    def test_workflow_description_from_dict(self):
        """Test creating WorkflowDescription from dictionary."""
        data = {
            "id": "test_workflow",
            "display_name": "Test Workflow",
            "log_pattern": "test_logs_*.jsonl",
            "notebook": "test_analysis.ipynb",
            "script": "test_script.py",
            "aliases": ["test", "tw"],
            "pipeline_name": "TestPipeline"
        }

        workflow = WorkflowDescription.from_dict(data)

        assert workflow.id == "test_workflow"
        assert workflow.display_name == "Test Workflow"
        assert workflow.log_pattern == "test_logs_*.jsonl"
        assert workflow.notebook == "test_analysis.ipynb"
        assert workflow.script == "test_script.py"
        assert workflow.aliases == ["test", "tw"]
        assert workflow.pipeline_name == "TestPipeline"

    def test_workflow_description_from_dict_minimal(self):
        """Test creating WorkflowDescription with minimal required fields."""
        data = {
            "id": "minimal",
            "display_name": "Minimal Workflow",
            "log_pattern": "*.jsonl",
            "notebook": "analysis.ipynb",
            "script": "script.py"
        }

        workflow = WorkflowDescription.from_dict(data)

        assert workflow.id == "minimal"
        assert workflow.aliases == []
        assert workflow.pipeline_name is None

    def test_workflow_description_from_dict_invalid(self):
        """Test WorkflowDescription validation."""
        # Missing required field
        with pytest.raises(ValueError, match="Missing or invalid field"):
            WorkflowDescription.from_dict({
                "display_name": "Test",
                "log_pattern": "*.jsonl",
                "notebook": "analysis.ipynb",
                "script": "script.py"
            })

        # Invalid aliases type
        with pytest.raises(ValueError, match="Aliases must be a list"):
            WorkflowDescription.from_dict({
                "id": "test",
                "display_name": "Test",
                "log_pattern": "*.jsonl",
                "notebook": "analysis.ipynb",
                "script": "script.py",
                "aliases": 123
            })

    def test_registry_add_and_get(self):
        """Test adding and retrieving workflows from registry."""
        registry = WorkflowRegistry()

        workflow = WorkflowDescription(
            id="test",
            display_name="Test Workflow",
            log_pattern="*.jsonl",
            notebook="test.ipynb",
            script="test.py"
        )

        registry.add(workflow)
        assert registry.get("test") == workflow
        assert registry.get("nonexistent") is None

    def test_registry_resolve_name(self):
        """Test name resolution with aliases."""
        registry = WorkflowRegistry()

        workflow = WorkflowDescription(
            id="weather",
            display_name="Weather Agent",
            log_pattern="weather_*.jsonl",
            notebook="weather.ipynb",
            script="weather.py",
            aliases=["simple", "weather_agent"]
        )

        registry.add(workflow)

        # Test exact match
        assert registry.resolve_name("weather") == workflow

        # Test alias match
        assert registry.resolve_name("simple") == workflow
        assert registry.resolve_name("weather_agent") == workflow

        # Test no match
        assert registry.resolve_name("nonexistent") is None

    def test_registry_load_from_file(self):
        """Test loading workflows from JSON file."""
        data = {
            "workflows": [
                {
                    "id": "test1",
                    "display_name": "Test Workflow 1",
                    "log_pattern": "test1_*.jsonl",
                    "notebook": "test1.ipynb",
                    "script": "test1.py"
                },
                {
                    "id": "test2",
                    "display_name": "Test Workflow 2",
                    "log_pattern": "test2_*.jsonl",
                    "notebook": "test2.ipynb",
                    "script": "test2.py",
                    "aliases": ["t2"]
                }
            ]
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            registry = WorkflowRegistry.load([Path(temp_path)])

            assert len(registry.list()) == 2
            assert registry.get("test1").display_name == "Test Workflow 1"
            assert registry.get("test2").aliases == ["t2"]
        finally:
            os.unlink(temp_path)

    def test_registry_load_from_directory(self):
        """Test loading workflows from directory with multiple JSON files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create first workflow file
            data1 = {
                "workflows": [{
                    "id": "wf1",
                    "display_name": "Workflow 1",
                    "log_pattern": "wf1_*.jsonl",
                    "notebook": "wf1.ipynb",
                    "script": "wf1.py"
                }]
            }

            with open(os.path.join(temp_dir, "file1.json"), 'w') as f:
                json.dump(data1, f)

            # Create second workflow file
            data2 = {
                "workflows": [{
                    "id": "wf2",
                    "display_name": "Workflow 2",
                    "log_pattern": "wf2_*.jsonl",
                    "notebook": "wf2.ipynb",
                    "script": "wf2.py"
                }]
            }

            with open(os.path.join(temp_dir, "file2.json"), 'w') as f:
                json.dump(data2, f)

            registry = WorkflowRegistry.load([Path(temp_dir)])

            assert len(registry.list()) == 2
            assert registry.get("wf1") is not None
            assert registry.get("wf2") is not None


class TestWorkflowDiscovery:
    """Test workflow discovery functionality."""

    def create_mock_log_file(self, temp_dir, filename, events):
        """Create a mock log file with JSONL events."""
        filepath = os.path.join(temp_dir, filename)
        with open(filepath, 'w') as f:
            for event in events:
                f.write(json.dumps(event) + '\n')
        return filepath

    def test_discover_workflows_no_logs(self):
        """Test discovery when no log files exist."""
        registry = WorkflowRegistry()
        registry.add(WorkflowDescription(
            id="test",
            display_name="Test Workflow",
            log_pattern="nonexistent_*.jsonl",
            notebook="test.ipynb",
            script="test.py"
        ))

        result = discover_workflows(registry)
        assert "test" not in result

    def test_discover_workflows_with_logs(self):
        """Test discovery with mock log files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create mock log file
            events = [
                {
                    "tags": {"agent": "agent1", "role": "decision-maker", "event_type": "action"},
                    "metadata": {"action": "analyze_data"},
                    "telemetry": {"timestamp_start": "2024-01-01T10:00:00Z"},
                    "run_id": "run1"
                },
                {
                    "tags": {"agent": "agent2", "role": "data-processor"},
                    "metadata": {"action": "process_data"},
                    "telemetry": {"timestamp_start": "2024-01-01T10:01:00Z"},
                    "run_id": "run1"
                },
                {
                    "tags": {"agent": "agent1", "event_type": "decision"},
                    "metadata": {"decision": "make_choice"},
                    "telemetry": {"timestamp_start": "2024-01-01T10:02:00Z"},
                    "run_id": "run2"
                }
            ]

            self.create_mock_log_file(temp_dir, "test_logs_20240101.jsonl", events)

            # Change to temp directory for glob to work
            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                registry = WorkflowRegistry()
                registry.add(WorkflowDescription(
                    id="test",
                    display_name="Test Workflow",
                    log_pattern="test_logs_*.jsonl",
                    notebook="test.ipynb",
                    script="test.py"
                ))

                result = discover_workflows(registry)

                assert "test" in result
                workflow_data = result["test"]
                assert workflow_data["total_events"] == 3
                assert len(workflow_data["agents"]) == 2
                assert "agent1" in workflow_data["agents"]
                assert "agent2" in workflow_data["agents"]
                assert workflow_data["agents"]["agent1"]["events"] == 2
                assert workflow_data["agents"]["agent1"]["role"] == "decision-maker"
                assert workflow_data["agents"]["agent1"]["last_call"] == "make_choice"
                assert workflow_data["unique_runs"] == 2
                assert workflow_data["last_seen"] == "2024-01-01T10:02:00Z"

            finally:
                os.chdir(original_cwd)

    def test_discover_workflows_pipeline_filtering(self):
        """Test that pipeline names are filtered from agents."""
        with tempfile.TemporaryDirectory() as temp_dir:
            events = [
                {
                    "tags": {"agent": "agent1"},
                    "telemetry": {"timestamp_start": "2024-01-01T10:00:00Z"}
                },
                {
                    "tags": {"agent": "PipelineSystem"},
                    "telemetry": {"timestamp_start": "2024-01-01T10:01:00Z"}
                }
            ]

            self.create_mock_log_file(temp_dir, "pipeline_logs.jsonl", events)

            original_cwd = os.getcwd()
            os.chdir(temp_dir)

            try:
                registry = WorkflowRegistry()
                registry.add(WorkflowDescription(
                    id="pipeline_test",
                    display_name="Pipeline Test",
                    log_pattern="pipeline_logs.jsonl",
                    notebook="test.ipynb",
                    script="test.py",
                    pipeline_name="PipelineSystem"
                ))

                result = discover_workflows(registry)

                assert "pipeline_test" in result
                agents = result["pipeline_test"]["agents"]
                assert "agent1" in agents
                assert "PipelineSystem" not in agents

            finally:
                os.chdir(original_cwd)


class TestCLICommands:
    """Test CLI commands for workflow discovery."""

    @patch('sys.stdout', new_callable=StringIO)
    def test_list_workflows(self, mock_stdout):
        """Test the workflows list command."""
        with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
            registry = WorkflowRegistry()
            registry.add(WorkflowDescription(
                id="test_workflow",
                display_name="Test Workflow",
                log_pattern="test_*.jsonl",
                notebook="test.ipynb",
                script="test.py"
            ))
            mock_load.return_value = registry

            with patch('abidex.cli.discover_workflows') as mock_discover:
                mock_discover.return_value = {
                    "test_workflow": {
                        "display_name": "Test Workflow",
                        "total_events": 10,
                        "agents": {"agent1": {"events": 5}, "agent2": {"events": 5}},
                        "unique_runs": 2,
                        "last_seen": "2024-01-01T10:00:00Z"
                    }
                }

                list_workflows()

                output = mock_stdout.getvalue()
                assert "Test Workflow" in output
                assert "2 agents" in output
                assert "10 events" in output
                assert "2 runs" in output

    @patch('sys.stdout', new_callable=StringIO)
    def test_show_workflow_map(self, mock_stdout):
        """Test the workflow map command."""
        with patch('abidex.cli.resolve_workflow_name') as mock_resolve:
            mock_resolve.return_value = "test_workflow"

            with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
                registry = WorkflowRegistry()
                registry.add(WorkflowDescription(
                    id="test_workflow",
                    display_name="Test Workflow",
                    log_pattern="test_*.jsonl",
                    notebook="test.ipynb",
                    script="test.py"
                ))
                mock_load.return_value = registry

                with patch('abidex.cli.discover_workflows') as mock_discover:
                    mock_discover.return_value = {
                        "test_workflow": {
                            "display_name": "Test Workflow",
                            "agents": {
                                "agent1": {
                                    "role": "decision-maker",
                                    "events": 10,
                                    "last_call": "analyze_data"
                                },
                                "agent2": {
                                    "role": "data-processor",
                                    "events": 8,
                                    "last_call": "process_data"
                                }
                            }
                        }
                    }

                    show_workflow_map("test_workflow")

                    output = mock_stdout.getvalue()
                    assert "Test Workflow" in output
                    assert "agent1" in output
                    assert "decision-maker" in output
                    assert "analyze_data" in output
                    assert "agent2" in output
                    assert "data-processor" in output
                    assert "process_data" in output

    @patch('sys.stdout', new_callable=StringIO)
    def test_show_workflow_logs(self, mock_stdout):
        """Test the workflow logs command."""
        with patch('abidex.cli.resolve_workflow_name') as mock_resolve:
            mock_resolve.return_value = "test_workflow"

            with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
                registry = WorkflowRegistry()
                registry.add(WorkflowDescription(
                    id="test_workflow",
                    display_name="Test Workflow",
                    log_pattern="test_*.jsonl",
                    notebook="test.ipynb",
                    script="test.py"
                ))
                mock_load.return_value = registry

                with patch('abidex.cli.discover_workflows') as mock_discover:
                    mock_discover.return_value = {
                        "test_workflow": {
                            "display_name": "Test Workflow",
                            "log_files": ["/path/to/test_logs_1.jsonl", "/path/to/test_logs_2.jsonl"]
                        }
                    }

                    show_workflow_logs("test_workflow")

                    output = mock_stdout.getvalue()
                    assert "Test Workflow" in output
                    assert "test_logs_1.jsonl" in output
                    assert "test_logs_2.jsonl" in output

    @patch('subprocess.run')
    def test_open_workflow_notebook(self, mock_subprocess):
        """Test the workflow notebook command."""
        with patch('abidex.cli.resolve_workflow_name') as mock_resolve:
            mock_resolve.return_value = "test_workflow"

            with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
                registry = WorkflowRegistry()
                registry.add(WorkflowDescription(
                    id="test_workflow",
                    display_name="Test Workflow",
                    log_pattern="test_*.jsonl",
                    notebook="test_analysis.ipynb",
                    script="test.py"
                ))
                mock_load.return_value = registry

                open_workflow_notebook("test_workflow", port=9999)

                # Check that jupyter notebook was called with correct arguments
                mock_subprocess.assert_called_once()
                args = mock_subprocess.call_args[0][0]
                assert "jupyter" in args
                assert "notebook" in args
                assert "test_analysis.ipynb" in args
                assert "--port=9999" in args

    def test_resolve_workflow_name(self):
        """Test workflow name resolution."""
        with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
            registry = WorkflowRegistry()
            registry.add(WorkflowDescription(
                id="weather",
                display_name="Weather Agent",
                log_pattern="weather_*.jsonl",
                notebook="weather.ipynb",
                script="weather.py",
                aliases=["simple", "weather_agent"]
            ))
            mock_load.return_value = registry

            assert resolve_workflow_name("weather") == "weather"
            assert resolve_workflow_name("simple") == "weather"
            assert resolve_workflow_name("weather_agent") == "weather"
            assert resolve_workflow_name("nonexistent") is None

    @patch('sys.stdout', new_callable=StringIO)
    def test_list_workflows_no_workflows(self, mock_stdout):
        """Test listing workflows when none are discovered."""
        with patch('abidex.cli.WorkflowRegistry.load_default') as mock_load:
            registry = WorkflowRegistry()
            mock_load.return_value = registry

            with patch('abidex.cli.discover_workflows') as mock_discover:
                mock_discover.return_value = {}

                list_workflows()

                output = mock_stdout.getvalue()
                assert "No workflows discovered" in output

    @patch('sys.stdout', new_callable=StringIO)
    def test_show_workflow_map_not_found(self, mock_stdout):
        """Test showing map for non-existent workflow."""
        with patch('abidex.cli.resolve_workflow_name') as mock_resolve:
            mock_resolve.return_value = None

            show_workflow_map("nonexistent")

            output = mock_stdout.getvalue()
            assert "Error: Workflow 'nonexistent' not found" in output