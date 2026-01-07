from pathlib import Path


def get_repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
