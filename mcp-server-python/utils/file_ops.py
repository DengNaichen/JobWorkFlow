"""
Atomic file operations for tracker initialization.

This module provides atomic write operations using temporary files
and atomic rename to ensure tracker files are never partially written.
"""

import os
import tempfile
from pathlib import Path
from typing import Union


def atomic_write(file_path: Union[str, Path], content: str) -> None:
    """
    Write content to file atomically using temporary file + rename.

    This function ensures that the target file is never in a partially
    written state. It writes to a temporary file in the same directory,
    syncs to disk, then atomically renames to the target path.

    File handles are always closed, even on failure.

    Args:
        file_path: Target file path (string or Path object)
        content: Content to write to the file

    Raises:
        OSError: If directory creation, file write, or rename fails
        IOError: If file operations fail

    Requirements:
        - 5.1: Write atomically (temporary file + rename)
        - 5.5: Close all file handles even on failure

    Examples:
        >>> atomic_write("trackers/test.md", "# Test Content")
        >>> Path("trackers/test.md").read_text()
        '# Test Content'
    """
    file_path = Path(file_path)

    # Ensure parent directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Create temporary file in same directory as target
    # This ensures atomic rename works (same filesystem)
    temp_fd = None
    temp_path = None

    try:
        # Create temporary file in target directory
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp"
        )

        # Write content to temporary file
        # Use os.write for the file descriptor
        content_bytes = content.encode('utf-8')
        os.write(temp_fd, content_bytes)

        # Sync to disk to ensure durability
        os.fsync(temp_fd)

        # Close the file descriptor before rename
        os.close(temp_fd)
        temp_fd = None

        # Atomic rename: replaces target file if it exists
        # os.replace is atomic on both Unix and Windows
        os.replace(temp_path, file_path)

    except Exception:
        # Clean up temporary file on any failure
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass  # Ignore errors during cleanup

        if temp_path is not None and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except OSError:
                pass  # Ignore errors during cleanup

        # Re-raise the original exception
        raise


def ensure_directory(dir_path: Union[str, Path]) -> None:
    """
    Ensure directory exists, creating it if necessary.

    Args:
        dir_path: Directory path to ensure exists

    Raises:
        OSError: If directory creation fails

    Examples:
        >>> ensure_directory("data/applications/test/resume")
        >>> Path("data/applications/test/resume").is_dir()
        True
    """
    Path(dir_path).mkdir(parents=True, exist_ok=True)


def ensure_workspace_directories(application_slug: str, base_dir: str = "data/applications") -> None:
    """
    Create workspace directories for a job application.

    This function creates the required directory structure for storing
    resume and cover letter files for a specific job application.
    It does NOT create any content files (resume.pdf, cover-letter.pdf).

    Directory structure created:
        data/applications/<application_slug>/resume/
        data/applications/<application_slug>/cover/

    Args:
        application_slug: Unique slug for the application workspace
        base_dir: Base directory for applications (default: "data/applications")

    Raises:
        OSError: If directory creation fails

    Requirements:
        - 3.4: Create workspace directories when missing
        - 3.5: Do NOT generate resume or cover letter content files

    Examples:
        >>> ensure_workspace_directories("amazon-3629")
        >>> Path("data/applications/amazon-3629/resume").is_dir()
        True
        >>> Path("data/applications/amazon-3629/cover").is_dir()
        True
    """
    workspace_root = Path(base_dir) / application_slug
    resume_dir = workspace_root / "resume"
    cover_dir = workspace_root / "cover"

    # Create both directories (parents=True creates intermediate dirs)
    resume_dir.mkdir(parents=True, exist_ok=True)
    cover_dir.mkdir(parents=True, exist_ok=True)


def resolve_write_action(file_exists: bool, force: bool) -> str:
    """
    Resolve the write action based on file existence and force flag.

    This function implements the idempotent action resolution logic
    for tracker file initialization:
    - Missing file -> "created"
    - Existing file + force=false -> "skipped_exists"
    - Existing file + force=true -> "overwritten"

    Args:
        file_exists: Whether the target file already exists
        force: Whether to overwrite existing files

    Returns:
        Action string: "created", "skipped_exists", or "overwritten"

    Requirements:
        - 4.1: Existing file + force=false -> skipped_exists
        - 4.2: Existing file + force=true -> overwritten
        - 4.4: Include skipped items in results with explicit action reason
        - 5.4: Return per-item actions

    Examples:
        >>> resolve_write_action(file_exists=False, force=False)
        'created'
        >>> resolve_write_action(file_exists=True, force=False)
        'skipped_exists'
        >>> resolve_write_action(file_exists=True, force=True)
        'overwritten'
    """
    if not file_exists:
        return "created"
    elif force:
        return "overwritten"
    else:
        return "skipped_exists"
