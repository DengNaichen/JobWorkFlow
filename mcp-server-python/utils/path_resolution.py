"""
Path resolution helpers for repository-root anchored behavior.

These helpers ensure relative paths are interpreted from JobWorkFlow
repository root (or JOBWORKFLOW_ROOT override), not process cwd.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Union

from config import config

DEFAULT_DB_RELATIVE_PATH = Path("data/capture/jobs.db")


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
        return resolve_repo_relative_path(config.trackers_dir)
    return resolve_repo_relative_path(trackers_dir)


def resolve_db_path(db_path: str | None = None) -> Path:
    """
    Resolve database path with consistent precedence across DB tools.

    Resolution order:
    1. Explicit `db_path` argument
    2. `JOBWORKFLOW_DB`
    3. `JOBWORKFLOW_ROOT/data/capture/jobs.db`
    4. `<repo_root>/data/capture/jobs.db`
    """
    if db_path is not None:
        return resolve_repo_relative_path(db_path)

    db_env = os.getenv("JOBWORKFLOW_DB")
    if db_env:
        return resolve_repo_relative_path(db_env)

    root_env = os.getenv("JOBWORKFLOW_ROOT")
    if root_env:
        return Path(root_env).expanduser().resolve() / DEFAULT_DB_RELATIVE_PATH

    return resolve_repo_relative_path(DEFAULT_DB_RELATIVE_PATH)
