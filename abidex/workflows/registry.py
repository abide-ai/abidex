import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional

from ..cli_common import get_repo_root
from ..log_patterns import normalize_log_patterns


@dataclass(frozen=True)
class WorkflowDescription:
    id: str
    display_name: str
    log_patterns: List[str]
    notebook: str
    script: str
    aliases: List[str] = field(default_factory=list)
    pipeline_name: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "WorkflowDescription":
        if not isinstance(data, dict):
            raise ValueError("Workflow data must be a dict")

        def required_field(key: str) -> str:
            value = data.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"Missing or invalid field: {key}")
            return value.strip()

        workflow_id = required_field("id")
        display_name = required_field("display_name")
        raw_patterns = data.get("log_patterns", data.get("log_pattern"))
        log_patterns = normalize_log_patterns(raw_patterns)
        if not log_patterns:
            raise ValueError("Missing or invalid field: log_pattern")
        notebook = required_field("notebook")
        script = required_field("script")

        aliases = data.get("aliases") or []
        if isinstance(aliases, str):
            aliases = [aliases]
        if not isinstance(aliases, list):
            raise ValueError("Aliases must be a list or string")
        clean_aliases = [
            alias.strip() for alias in aliases
            if isinstance(alias, str) and alias.strip()
        ]

        pipeline_name = data.get("pipeline_name")
        if pipeline_name is not None and not isinstance(pipeline_name, str):
            pipeline_name = None

        return cls(
            id=workflow_id,
            display_name=display_name,
            log_patterns=log_patterns,
            notebook=notebook,
            script=script,
            aliases=clean_aliases,
            pipeline_name=pipeline_name
        )

    @property
    def log_pattern(self) -> str:
        return self.log_patterns[0] if self.log_patterns else ""


class WorkflowRegistry:
    def __init__(self, workflows: Iterable[WorkflowDescription] = ()):
        self._workflows = {}
        self._aliases = {}
        self._source_paths = []
        for workflow in workflows:
            self.add(workflow)

    @property
    def source_paths(self) -> List[Path]:
        return list(self._source_paths)

    def add(self, workflow: WorkflowDescription, override: bool = True) -> None:
        key = workflow.id.lower().strip()
        if not key:
            return
        if key in self._workflows and not override:
            return
        self._workflows[key] = workflow
        self._rebuild_aliases()

    def list(self) -> List[WorkflowDescription]:
        return [self._workflows[key] for key in sorted(self._workflows)]

    def get(self, workflow_id: str) -> Optional[WorkflowDescription]:
        if not workflow_id:
            return None
        return self._workflows.get(workflow_id.lower())

    def resolve_name(self, name: str) -> Optional[WorkflowDescription]:
        if not name:
            return None
        key = name.lower()
        workflow = self._workflows.get(key)
        if workflow:
            return workflow
        alias_target = self._aliases.get(key)
        if alias_target:
            return self._workflows.get(alias_target)
        return None

    def _rebuild_aliases(self) -> None:
        aliases = {}
        for workflow in self._workflows.values():
            for alias in workflow.aliases:
                alias_key = alias.lower().strip()
                if alias_key:
                    aliases[alias_key] = workflow.id.lower()
        self._aliases = aliases

    @classmethod
    def load_default(cls) -> "WorkflowRegistry":
        return cls.load(cls._default_paths())

    @classmethod
    def load(cls, paths: Iterable[Path]) -> "WorkflowRegistry":
        registry = cls()
        for path in cls._unique_paths(paths):
            if path.is_dir():
                registry._load_from_dir(path)
            else:
                registry._load_from_file(path)
        return registry

    @classmethod
    def _default_paths(cls) -> List[Path]:
        paths = []
        env_paths = os.environ.get("ABIDEX_WORKFLOW_CONFIG")
        if env_paths:
            for entry in env_paths.split(os.pathsep):
                entry = entry.strip()
                if entry:
                    paths.append(Path(entry))

        env_dir = os.environ.get("ABIDEX_WORKFLOW_DIR")
        if env_dir:
            paths.append(Path(env_dir))

        repo_root = get_repo_root()
        for base in (Path.cwd(), repo_root):
            paths.append(base / "workflows.json")
            paths.append(base / ".abidex_workflows.json")
            paths.append(base / "workflows")

        return paths

    @staticmethod
    def _unique_paths(paths: Iterable[Path]) -> List[Path]:
        unique = []
        seen = set()
        for path in paths:
            if not isinstance(path, Path):
                path = Path(path)
            try:
                resolved = path.expanduser().resolve()
            except FileNotFoundError:
                resolved = path.expanduser()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique.append(path)
        return unique

    def _load_from_dir(self, directory: Path) -> None:
        if not directory.exists():
            return
        for path in sorted(directory.glob("*.json")):
            self._load_from_file(path)

    def _load_from_file(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            raw = path.read_text()
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError):
            return

        workflows = []
        if isinstance(data, dict):
            workflows = data.get("workflows", [])
        elif isinstance(data, list):
            workflows = data

        if not isinstance(workflows, list):
            return

        for entry in workflows:
            try:
                workflow = WorkflowDescription.from_dict(entry)
            except ValueError:
                continue
            self.add(workflow, override=True)
        self._source_paths.append(path)
