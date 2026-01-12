from abidex.workflows.paths import (
    resolve_notebook_path,
    resolve_workflow_notebook_path,
    resolve_workflow_script_path,
)
from abidex.workflows.registry import WorkflowDescription, WorkflowRegistry


def _make_registry(script: str, notebook: str) -> WorkflowRegistry:
    workflow = WorkflowDescription(
        id="demo",
        display_name="Demo Workflow",
        log_patterns=["demo_logs_*.jsonl"],
        notebook=notebook,
        script=script,
        aliases=["demo"],
    )
    return WorkflowRegistry([workflow])


def test_resolve_workflow_script_path_uses_examples_dir(tmp_path):
    examples_dir = tmp_path / "examples"
    examples_dir.mkdir()
    script_path = examples_dir / "demo_script.py"
    script_path.write_text("print('ok')\n")

    registry = _make_registry(script="demo_script.py", notebook="demo_analysis.ipynb")

    resolved = resolve_workflow_script_path(
        "demo",
        registry=registry,
        repo_root=tmp_path,
    )

    assert resolved == script_path


def test_resolve_workflow_notebook_path_falls_back_to_patterns(tmp_path):
    notebooks_dir = tmp_path / "examples" / "notebooks"
    notebooks_dir.mkdir(parents=True)
    notebook_path = notebooks_dir / "demo_analysis.ipynb"
    notebook_path.write_text("{}")

    registry = _make_registry(script="demo_script.py", notebook="missing.ipynb")

    resolved = resolve_workflow_notebook_path(
        "demo",
        registry=registry,
        repo_root=tmp_path,
    )

    assert resolved == notebook_path


def test_resolve_notebook_path_defaults_to_registry(tmp_path):
    notebooks_dir = tmp_path / "examples" / "notebooks"
    notebooks_dir.mkdir(parents=True)
    notebook_path = notebooks_dir / "demo_analysis.ipynb"
    notebook_path.write_text("{}")

    registry = _make_registry(script="demo_script.py", notebook="demo_analysis.ipynb")

    resolved = resolve_notebook_path(
        None,
        registry=registry,
        repo_root=tmp_path,
    )

    assert resolved == notebook_path
