import os
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from ..cli_common import get_repo_root
from .registry import WorkflowRegistry, WorkflowDescription


def get_workflow_log_dir(project_name: str, output_dir: str = ".") -> Path:
    """
    Get the log directory for a workflow project.
    
    Logs are saved to: {output_dir}/logs/{project_name}/
    
    Args:
        project_name: Name of the project/workflow (e.g., "fraud_detection", "simple_weather")
        output_dir: Base output directory (default: current directory)
    
    Returns:
        Path to the log directory
    """
    log_dir = Path(output_dir) / "logs" / project_name
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_workflow_dir(project_name: str, base_dir: str = ".") -> Path:
    """
    Get the workflow directory for a workflow project.
    
    Workflow files (scripts, notebooks, configs) are saved to: {base_dir}/workflows/{project_name}/
    
    Args:
        project_name: Name of the project/workflow
        base_dir: Base directory (default: current directory)
    
    Returns:
        Path to the workflow directory
    """
    workflow_dir = Path(base_dir) / "workflows" / project_name
    workflow_dir.mkdir(parents=True, exist_ok=True)
    return workflow_dir


def resolve_workflow_log_path(
    project_name: str,
    log_filename: str,
    output_dir: Optional[str] = None
) -> Path:
    """
    Resolve the full path for a workflow log file.
    
    Args:
        project_name: Name of the project/workflow
        log_filename: Name of the log file (e.g., "fraud_detection_logs_20240101.jsonl")
        output_dir: Optional output directory (defaults to current directory or from env)
    
    Returns:
        Full path to the log file
    """
    if output_dir is None:
        output_dir = os.environ.get("ABIDEX_OUTPUT_DIR", ".")
    
    log_dir = get_workflow_log_dir(project_name, output_dir)
    return log_dir / log_filename


SCRIPT_PATTERNS = (
    "{name}.py",
    "{name}_pipeline.py",
    "{name}_test.py",
    "{name}_agent.py",
)

NOTEBOOK_PATTERNS = (
    "{name}_analysis.ipynb",
    "{name}_logs_analysis.ipynb",
    "{name}.ipynb",
)


def resolve_workflow_script_path(
    workflow_name: str,
    registry: Optional[WorkflowRegistry] = None,
    script_override: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve a workflow script path from overrides, registry, or discovery."""
    repo_root = repo_root or get_repo_root()
    registry = registry or WorkflowRegistry.load_default()

    search_dirs = _default_search_dirs(repo_root)

    if script_override:
        resolved = _resolve_path(script_override, search_dirs)
        return resolved

    workflow = registry.resolve_name(workflow_name)
    if workflow:
        resolved = _resolve_workflow_script(workflow, search_dirs)
        if resolved:
            return resolved
        workflow_name = workflow.id

    return _discover_script(workflow_name, search_dirs)


def resolve_workflow_notebook_path(
    workflow_name: Optional[str],
    registry: Optional[WorkflowRegistry] = None,
    notebook_override: Optional[str] = None,
    repo_root: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve a workflow notebook path from overrides, registry, or discovery."""
    repo_root = repo_root or get_repo_root()
    registry = registry or WorkflowRegistry.load_default()

    search_dirs = _default_search_dirs(repo_root, include_notebooks=True)

    if notebook_override:
        resolved = _resolve_path(notebook_override, search_dirs)
        return resolved

    if workflow_name:
        workflow = registry.resolve_name(workflow_name)
        if workflow:
            resolved = _resolve_workflow_notebook(workflow, search_dirs)
            if resolved:
                return resolved
            workflow_name = workflow.id

        return _discover_notebook(workflow_name, search_dirs)

    return _discover_any_notebook(search_dirs)


def resolve_notebook_path(
    notebook_input: Optional[str],
    registry: Optional[WorkflowRegistry] = None,
    repo_root: Optional[Path] = None,
) -> Optional[Path]:
    """Resolve a notebook from a path, workflow name, or registry fallback."""
    repo_root = repo_root or get_repo_root()
    registry = registry or WorkflowRegistry.load_default()

    search_dirs = _default_search_dirs(repo_root, include_notebooks=True)

    if notebook_input:
        resolved = _resolve_path(notebook_input, search_dirs)
        if resolved:
            return resolved
        if _looks_like_path(notebook_input):
            return None
        return resolve_workflow_notebook_path(
            notebook_input,
            registry=registry,
            repo_root=repo_root,
        )

    for workflow in registry.list():
        resolved = _resolve_workflow_notebook(workflow, search_dirs)
        if resolved:
            return resolved

    return _discover_any_notebook(search_dirs)


def _resolve_workflow_script(
    workflow: WorkflowDescription,
    search_dirs: Sequence[Path],
) -> Optional[Path]:
    """Resolve a script path using workflow metadata and search dirs."""
    if not workflow.script:
        return None
    resolved = _resolve_path(workflow.script, search_dirs)
    return resolved


def _resolve_workflow_notebook(
    workflow: WorkflowDescription,
    search_dirs: Sequence[Path],
) -> Optional[Path]:
    """Resolve a notebook path using workflow metadata and search dirs."""
    if not workflow.notebook:
        return None
    resolved = _resolve_path(workflow.notebook, search_dirs)
    return resolved


def _resolve_path(path_value: str, search_dirs: Sequence[Path]) -> Optional[Path]:
    """Resolve absolute paths directly or search for relative paths."""
    if not path_value:
        return None

    path = Path(os.path.expanduser(path_value))
    if path.is_absolute():
        return path if path.exists() else None

    for base in search_dirs:
        candidate = base / path
        if candidate.exists():
            return candidate
    return None


def _default_search_dirs(repo_root: Path, include_notebooks: bool = False) -> List[Path]:
    """Return the ordered list of directories to search."""
    dirs = [repo_root, repo_root / "examples"]
    
    # Add workflows/*/ subdirectories for workflow-specific files
    workflows_base = repo_root / "workflows"
    if workflows_base.exists():
        for workflow_dir in workflows_base.iterdir():
            if workflow_dir.is_dir():
                dirs.append(workflow_dir)
    
    if include_notebooks:
        dirs.extend(
            [
                repo_root / "notebooks",
                repo_root / "examples" / "notebooks",
            ]
        )
        # Also check workflows/*/ for notebooks
        if workflows_base.exists():
            for workflow_dir in workflows_base.iterdir():
                if workflow_dir.is_dir():
                    dirs.append(workflow_dir)
    
    return dirs


def _discover_script(workflow_name: str, search_dirs: Sequence[Path]) -> Optional[Path]:
    """Find a script by matching known patterns."""
    for name in _candidate_names(workflow_name):
        for pattern in SCRIPT_PATTERNS:
            matches = _glob_in_dirs(search_dirs, pattern.format(name=name))
            if matches:
                return matches[0]
    return None


def _discover_notebook(workflow_name: str, search_dirs: Sequence[Path]) -> Optional[Path]:
    """Find a notebook by matching known patterns."""
    for name in _candidate_names(workflow_name):
        for pattern in NOTEBOOK_PATTERNS:
            matches = _glob_in_dirs(search_dirs, pattern.format(name=name))
            if matches:
                return matches[0]
    return None


def _discover_any_notebook(search_dirs: Sequence[Path]) -> Optional[Path]:
    """Return the first notebook found in the search dirs."""
    matches = _glob_in_dirs(search_dirs, "*.ipynb")
    if matches:
        return matches[0]
    return None


def _candidate_names(workflow_name: str) -> List[str]:
    """Generate workflow name variants for pattern matching."""
    if not workflow_name:
        return []
    raw = workflow_name.strip()
    normalized = raw.lower().replace("-", "_").replace(" ", "_")
    names = [normalized]
    if raw != normalized:
        names.append(raw)
    return names


def _glob_in_dirs(search_dirs: Sequence[Path], pattern: str) -> List[Path]:
    """Glob a pattern across multiple directories."""
    matches: List[Path] = []
    for base in search_dirs:
        if not base.exists():
            continue
        for path in sorted(base.glob(pattern)):
            matches.append(path)
    return matches


def _looks_like_path(value: str) -> bool:
    """Heuristic check for path-like notebook input."""
    if not value:
        return False
    path = Path(value)
    return path.suffix.lower() == ".ipynb" or "/" in value or "\\" in value
