from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from ..cli_common import get_repo_root
from .paths import resolve_workflow_notebook_path, resolve_workflow_script_path
from .registry import WorkflowDescription, WorkflowRegistry


@dataclass(frozen=True)
class WorkflowChoice:
    id: str
    display_name: str
    aliases: Sequence[str]
    script_path: Optional[Path] = None
    notebook_path: Optional[Path] = None


@dataclass(frozen=True)
class EvalResolution:
    demo: str
    workflow: Optional[WorkflowDescription]
    script_path: Optional[Path]
    used_script_override: bool


def get_configured_workflows(
    registry: Optional[WorkflowRegistry] = None,
    repo_root: Optional[Path] = None,
    require_script: bool = False,
    require_notebook: bool = False,
) -> List[WorkflowChoice]:
    registry = registry or WorkflowRegistry.load_default()
    repo_root = repo_root or get_repo_root()

    choices = []
    for workflow in registry.list():
        script_path = None
        notebook_path = None

        if require_script:
            script_path = resolve_workflow_script_path(
                workflow.id,
                registry=registry,
                repo_root=repo_root,
            )
            if not script_path:
                continue

        if require_notebook:
            notebook_path = resolve_workflow_notebook_path(
                workflow.id,
                registry=registry,
                repo_root=repo_root,
            )
            if not notebook_path:
                continue

        choices.append(
            WorkflowChoice(
                id=workflow.id,
                display_name=workflow.display_name,
                aliases=workflow.aliases,
                script_path=script_path,
                notebook_path=notebook_path,
            )
        )

    return choices


def format_workflow_choices(choices: Sequence[WorkflowChoice]) -> str:
    lines = []
    for choice in choices:
        alias_text = ""
        if choice.aliases:
            alias_text = f" (aliases: {', '.join(choice.aliases)})"
        lines.append(f"  - {choice.display_name} ({choice.id}){alias_text}")
    return "\n".join(lines)


def resolve_eval_target(
    demo: str,
    script_override: Optional[str],
    registry: Optional[WorkflowRegistry] = None,
    repo_root: Optional[Path] = None,
) -> EvalResolution:
    registry = registry or WorkflowRegistry.load_default()
    repo_root = repo_root or get_repo_root()

    if script_override:
        script_path = resolve_workflow_script_path(
            demo,
            registry=registry,
            script_override=script_override,
            repo_root=repo_root,
        )
        return EvalResolution(
            demo=demo,
            workflow=registry.resolve_name(demo),
            script_path=script_path,
            used_script_override=True,
        )

    workflow = registry.resolve_name(demo)
    resolved_name = workflow.id if workflow else demo
    script_path = resolve_workflow_script_path(
        resolved_name,
        registry=registry,
        repo_root=repo_root,
    )

    return EvalResolution(
        demo=resolved_name,
        workflow=workflow,
        script_path=script_path,
        used_script_override=False,
    )
