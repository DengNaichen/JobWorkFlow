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
            dir=file_path.parent, prefix=f".{file_path.name}.", suffix=".tmp"
        )

        # Write content to temporary file
        # Use os.write for the file descriptor
        content_bytes = content.encode("utf-8")
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


def ensure_workspace_directories(
    application_slug: str, base_dir: str = "data/applications"
) -> None:
    """
    Create workspace directories for a job application.

    This function creates the required directory structure for storing
    resume, cover letter, and CV files for a specific job application.
    It does NOT create any content files (resume.pdf, cover-letter.pdf, cv.pdf).

    Directory structure created:
        data/applications/<application_slug>/resume/
        data/applications/<application_slug>/cover/
        data/applications/<application_slug>/cv/

    Args:
        application_slug: Unique slug for the application workspace
        base_dir: Base directory for applications (default: "data/applications")

    Raises:
        OSError: If directory creation fails

    Requirements:
        - 4.2: Create workspace directories (resume/, cover/, cv/) when missing
        - 3.5: Do NOT generate resume or cover letter content files

    Examples:
        >>> ensure_workspace_directories("amazon-3629")
        >>> Path("data/applications/amazon-3629/resume").is_dir()
        True
        >>> Path("data/applications/amazon-3629/cover").is_dir()
        True
        >>> Path("data/applications/amazon-3629/cv").is_dir()
        True
    """
    workspace_root = Path(base_dir) / application_slug
    resume_dir = workspace_root / "resume"
    cover_dir = workspace_root / "cover"
    cv_dir = workspace_root / "cv"

    # Create all three directories (parents=True creates intermediate dirs)
    resume_dir.mkdir(parents=True, exist_ok=True)
    cover_dir.mkdir(parents=True, exist_ok=True)
    cv_dir.mkdir(parents=True, exist_ok=True)


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


def materialize_resume_tex(
    template_path: str = "data/templates/resume_skeleton_example.tex",
    target_path: Union[str, Path] = None,
    force: bool = False,
) -> str:
    """
    Materialize resume.tex from template with force behavior.

    This function implements the resume.tex initialization logic:
    - Missing file -> create from template (action: "created")
    - Existing file + force=false -> preserve existing (action: "preserved")
    - Existing file + force=true -> overwrite from template (action: "overwritten")

    Args:
        template_path: Path to resume template file
        target_path: Target path for resume.tex file
        force: Whether to overwrite existing resume.tex

    Returns:
        Action string: "created", "preserved", or "overwritten"

    Raises:
        FileNotFoundError: If template file does not exist
        OSError: If file operations fail

    Requirements:
        - 4.3: Initialize resume/resume.tex from template when missing
        - 4.4: When force=true, overwrite existing resume.tex from template
        - 4.6: Generated files SHALL be written atomically

    Examples:
        >>> # Create new resume.tex
        >>> action = materialize_resume_tex(
        ...     template_path="data/templates/resume_skeleton_example.tex",
        ...     target_path="data/applications/amazon-3629/resume/resume.tex",
        ...     force=False
        ... )
        >>> action
        'created'

        >>> # Preserve existing resume.tex
        >>> action = materialize_resume_tex(
        ...     target_path="data/applications/amazon-3629/resume/resume.tex",
        ...     force=False
        ... )
        >>> action
        'preserved'

        >>> # Overwrite existing resume.tex
        >>> action = materialize_resume_tex(
        ...     target_path="data/applications/amazon-3629/resume/resume.tex",
        ...     force=True
        ... )
        >>> action
        'overwritten'
    """
    template_path = Path(template_path)
    target_path = Path(target_path)

    # Verify template exists
    if not template_path.exists():
        raise FileNotFoundError(f"Template file not found: {template_path}")

    # Check if target already exists
    target_exists = target_path.exists()

    # Determine action based on existence and force flag
    if target_exists and not force:
        # Preserve existing file
        return "preserved"

    # Read template content
    template_content = template_path.read_text(encoding="utf-8")

    # Write to target using atomic write
    atomic_write(target_path, template_content)

    # Return appropriate action
    if target_exists:
        return "overwritten"
    else:
        return "created"
