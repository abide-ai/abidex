import glob
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Union

from .cli_common import get_repo_root


DEFAULT_LOG_PATTERNS = [
    "*_logs_*.jsonl",
    "*_telemetry_*.jsonl",
    "agent_logs_*.jsonl",
]

DEFAULT_CONFIG_FILENAMES = ("abidex.json", ".abidex.json")

PatternInput = Optional[Union[str, Sequence[str]]]


@dataclass(frozen=True)
class LogPatternConfig:
    patterns: List[str]
    auto_detect: bool
    source: Optional[Path] = None


def normalize_log_patterns(value: PatternInput) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = re.split(r"[;,]", value)
        return [part.strip() for part in parts if part.strip()]
    if isinstance(value, (list, tuple, set)):
        patterns = []
        for entry in value:
            if isinstance(entry, str) and entry.strip():
                patterns.extend(normalize_log_patterns(entry))
        return patterns
    return []


def find_log_config_path() -> Optional[Path]:
    env_path = os.environ.get("ABIDEX_CONFIG")
    if env_path:
        return Path(env_path).expanduser()

    for base in (Path.cwd(), get_repo_root()):
        for filename in DEFAULT_CONFIG_FILENAMES:
            candidate = base / filename
            if candidate.exists():
                return candidate
    return None


def load_log_pattern_config() -> LogPatternConfig:
    path = find_log_config_path()
    if not path or not path.exists():
        return LogPatternConfig(patterns=[], auto_detect=True, source=path)

    try:
        raw = path.read_text()
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return LogPatternConfig(patterns=[], auto_detect=True, source=path)

    patterns: List[str] = []
    auto_detect = True

    if isinstance(data, dict):
        logs = data.get("logs", {})
        if isinstance(logs, dict):
            patterns = normalize_log_patterns(
                logs.get("patterns")
                or logs.get("log_patterns")
                or logs.get("log_pattern")
            )
            auto_detect = bool(logs.get("auto_detect", True))
        else:
            patterns = normalize_log_patterns(
                data.get("log_patterns") or data.get("log_pattern")
            )
            auto_detect = bool(data.get("auto_detect", True))
    elif isinstance(data, list):
        patterns = normalize_log_patterns(data)

    return LogPatternConfig(patterns=patterns, auto_detect=auto_detect, source=path)


def detect_log_patterns(search_dir: Optional[Path] = None) -> List[str]:
    search_dir = search_dir or Path.cwd()
    patterns = set()

    for path in sorted(search_dir.glob("*.jsonl")):
        name = path.name
        match = re.match(r"^(.+?)_(logs|telemetry)_.+\.jsonl$", name)
        if match:
            patterns.add(f"{match.group(1)}_{match.group(2)}_*.jsonl")
            continue
        match = re.match(r"^(.+?)_logs.+\.jsonl$", name)
        if match:
            patterns.add(f"{match.group(1)}_logs*.jsonl")
            continue
        patterns.add(name)

    return sorted(patterns)


def resolve_log_patterns(
    explicit: PatternInput = None,
    search_dir: Optional[Path] = None,
) -> List[str]:
    patterns = normalize_log_patterns(explicit)
    if patterns:
        return patterns

    config = load_log_pattern_config()
    if config.patterns:
        return config.patterns

    if config.auto_detect:
        detected = detect_log_patterns(search_dir)
        if detected:
            return detected

    return list(DEFAULT_LOG_PATTERNS)


def format_log_patterns(patterns: Sequence[str]) -> str:
    clean = normalize_log_patterns(patterns)
    if not clean:
        return ""
    if len(clean) == 1:
        return clean[0]
    return ", ".join(clean)


def find_log_files(
    patterns: Iterable[str],
    search_dir: Optional[Path] = None,
) -> List[str]:
    search_dir = search_dir or Path.cwd()
    seen = set()
    matches: List[str] = []

    for pattern in normalize_log_patterns(patterns):
        for path in _iter_pattern_matches(pattern, search_dir):
            path_str = str(path)
            if path_str in seen:
                continue
            seen.add(path_str)
            matches.append(path_str)

    return matches


def _iter_pattern_matches(pattern: str, search_dir: Path) -> Iterable[Path]:
    pattern = pattern.strip()
    if not pattern:
        return

    if pattern.startswith("re:"):
        regex = re.compile(pattern[3:])
        for path in search_dir.glob("*.jsonl"):
            if regex.search(path.name):
                yield path
        return

    if os.path.isabs(pattern):
        for match in glob.glob(pattern):
            yield Path(match)
        return

    for match in glob.glob(str(search_dir / pattern)):
        yield Path(match)
