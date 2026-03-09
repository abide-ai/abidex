from unittest.mock import Mock

import pytest

from abidex.patches.crewai import _wrap_kickoff


def test_crewai_kickoff_creates_workflow_span(memory_exporter_cleared):
    memory_exporter = memory_exporter_cleared
    noop = lambda *a, **k: None
    kickoff = _wrap_kickoff(noop)
    mock_crew = Mock()
    mock_crew.name = "TestCrew"
    mock_crew.agents = [Mock(role="Researcher")]
    kickoff(mock_crew, inputs={"topic": "test"})
    spans = memory_exporter.get_finished_spans()
    assert len(spans) >= 1, "expected at least one span"
    span = spans[0]
    assert "Workflow" in span.name
    assert span.attributes.get("gen_ai.framework") == "crewai"
    assert span.attributes.get("gen_ai.workflow.name") == "TestCrew"
    assert span.attributes.get("gen_ai.team.agents") == "Researcher"


def test_crewai_kickoff_unnamed_crew(memory_exporter_cleared):
    memory_exporter = memory_exporter_cleared
    noop = lambda *a, **k: None
    kickoff = _wrap_kickoff(noop)
    mock_crew = Mock()
    mock_crew.name = None
    mock_crew.agents = []
    kickoff(mock_crew, inputs={})
    spans = memory_exporter.get_finished_spans()
    assert len(spans) >= 1
    span = spans[0]
    assert "UnnamedCrew" in span.name
    assert span.attributes.get("gen_ai.workflow.name") == "UnnamedCrew"
    assert span.attributes.get("gen_ai.framework") == "crewai"
