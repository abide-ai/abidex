from abidex.workflows.cli_helpers import (
    get_configured_workflows,
    resolve_eval_target,
)
from abidex.workflows.registry import WorkflowDescription, WorkflowRegistry


def _make_registry() -> WorkflowRegistry:
    workflow = WorkflowDescription(
        id="weather",
        display_name="Weather Demo",
        log_patterns=["weather_logs_*.jsonl"],
        notebook="weather_analysis.ipynb",
        script="weather.py",
        aliases=["simple"],
    )
    return WorkflowRegistry([workflow])


def test_resolve_eval_target_alias_uses_canonical_id(tmp_path):
    script_path = tmp_path / "examples" / "weather.py"
    script_path.parent.mkdir(parents=True)
    script_path.write_text("print('ok')\n")

    registry = _make_registry()

    resolution = resolve_eval_target(
        "simple",
        None,
        registry=registry,
        repo_root=tmp_path,
    )

    assert resolution.demo == "weather"
    assert resolution.script_path == script_path
    assert resolution.used_script_override is False


def test_resolve_eval_target_script_override(tmp_path):
    script_path = tmp_path / "custom_demo.py"
    script_path.write_text("print('ok')\n")

    registry = WorkflowRegistry()

    resolution = resolve_eval_target(
        "custom",
        str(script_path),
        registry=registry,
        repo_root=tmp_path,
    )

    assert resolution.script_path == script_path
    assert resolution.used_script_override is True


def test_get_configured_workflows_filters_missing_scripts(tmp_path):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    good_script = examples_dir / "good.py"
    good_script.write_text("print('ok')\n")

    good_workflow = WorkflowDescription(
        id="good",
        display_name="Good Demo",
        log_patterns=["good_logs_*.jsonl"],
        notebook="good_analysis.ipynb",
        script="good.py",
    )
    missing_workflow = WorkflowDescription(
        id="missing",
        display_name="Missing Demo",
        log_patterns=["missing_logs_*.jsonl"],
        notebook="missing_analysis.ipynb",
        script="missing.py",
    )

    registry = WorkflowRegistry([good_workflow, missing_workflow])

    choices = get_configured_workflows(
        registry=registry,
        repo_root=tmp_path,
        require_script=True,
    )

    assert [choice.id for choice in choices] == ["good"]
