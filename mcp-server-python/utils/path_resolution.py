"""
Path resolution helpers for repository-root anchored behavior.

These helpers ensure relative paths are interpreted from JobWorkFlow
repository root (or JOBWORKFLOW_ROOT override), not process cwd.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union


def get_repo_root() -> Path:
    """
    Resolve JobWorkFlow repository root.

    Resolution order:
    1. JOBWORKFLOW_ROOT environment variable
    2. Parent of mcp-server-python directory
    """
    root_env = os.getenv("JOBWORKFLOW_ROOT")
    if root_env:
        return Path(root_env).expanduser().resolve()

    # path_resolution.py is under mcp-server-python/utils/
    return Path(__file__).resolve().parents[2]


def resolve_repo_relative_path(path: Union[str, Path]) -> Path:
    """
    Resolve absolute path directly; resolve relative path from repo root.
    """
    path_obj = Path(path)
    if path_obj.is_absolute():
        return path_obj
    return get_repo_root() / path_obj


def resolve_trackers_dir(trackers_dir: str | None) -> Path:
    """
    Resolve trackers directory with repo-root anchored default.

    Default directory is <repo_root>/trackers.
    """
    if trackers_dir is None:
        return get_repo_root() / "trackers"
    return resolve_repo_relative_path(trackers_dir)
