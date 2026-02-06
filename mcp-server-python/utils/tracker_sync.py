"""
Tracker file synchronization utilities for update_tracker_status tool.

This module provides functions to safely update tracker frontmatter status
while preserving all other frontmatter fields and body content.
"""

from pathlib import Path
from typing import Dict, Any
import os
import tempfile
import yaml

from utils.path_resolution import resolve_repo_relative_path


def update_tracker_status(tracker_path: str, new_status: str) -> None:
    """
    Update tracker frontmatter status field atomically.
    
    This function:
    1. Reads the tracker file and parses frontmatter + body
    2. Updates only the 'status' field in frontmatter
    3. Preserves all other frontmatter fields exactly
    4. Preserves body content byte-for-byte
    5. Writes atomically using temp file + fsync + os.replace
    
    Args:
        tracker_path: Path to the tracker markdown file
        new_status: New status value to set
        
    Raises:
        FileNotFoundError: If tracker file does not exist
        IOError: If file operations fail
        
    Requirements:
        - 7.1: Update only the status field in frontmatter
        - 7.2: Tracker write is atomic (temporary file + rename)
        - 7.3: Preserve original body content exactly
        - 7.4: Preserve original frontmatter keys/values except status
        - 7.5: When write fails, original tracker file remains intact
        
    Examples:
        >>> # Update status from "Reviewed" to "Resume Written"
        >>> update_tracker_status("trackers/2026-02-05-amazon-3629.md", "Resume Written")
        
        >>> # Verify status was updated
        >>> from utils.tracker_parser import get_tracker_status
        >>> get_tracker_status("trackers/2026-02-05-amazon-3629.md")
        'Resume Written'
    """
    path = resolve_repo_relative_path(tracker_path)
    
    # Verify file exists
    if not path.exists():
        raise FileNotFoundError(f"Tracker file not found: {tracker_path}")
    
    # Read and parse current tracker content
    content = path.read_text(encoding='utf-8')
    frontmatter, body = _extract_frontmatter_and_body(content)
    
    # Update only the status field (Requirement 7.1, 7.4)
    frontmatter["status"] = new_status
    
    # Render updated tracker content
    updated_content = _render_tracker_content(frontmatter, body)
    
    # Write atomically (Requirement 7.2, 7.5)
    _atomic_write(path, updated_content)


def _extract_frontmatter_and_body(content: str) -> tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter and body content from markdown.
    
    Expects frontmatter to be delimited by '---' at the start and end.
    
    Args:
        content: Full markdown file content
        
    Returns:
        Tuple of (frontmatter_dict, body_string)
        
    Raises:
        ValueError: If frontmatter is missing or malformed
    """
    import re
    
    # Match frontmatter pattern: --- at start, YAML content, --- delimiter
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    
    if not match:
        raise ValueError("Tracker file does not contain valid YAML frontmatter delimited by '---'")
    
    yaml_content = match.group(1)
    body = match.group(2)
    
    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in frontmatter: {str(e)}") from e
    
    # Ensure frontmatter is a dictionary
    if not isinstance(frontmatter, dict):
        raise ValueError("Frontmatter must be a YAML dictionary")
    
    return frontmatter, body


def _render_tracker_content(frontmatter: Dict[str, Any], body: str) -> str:
    """
    Render complete tracker markdown content with frontmatter and body.
    
    Args:
        frontmatter: Dictionary of frontmatter fields
        body: Markdown body content
        
    Returns:
        Complete markdown content as string
        
    Requirements:
        - 7.3: Preserve original body content exactly
        - 7.4: Preserve original frontmatter keys/values except status
    """
    # Render YAML frontmatter with consistent formatting
    yaml_content = yaml.dump(
        frontmatter,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False
    )
    
    # Assemble complete markdown document
    # Note: Body is preserved exactly as-is (Requirement 7.3)
    markdown_parts = [
        "---",
        yaml_content.rstrip(),
        "---",
        "",
        body
    ]
    
    return "\n".join(markdown_parts)


def _atomic_write(path: Path, content: str) -> None:
    """
    Write content to file atomically using temp file + fsync + os.replace.
    
    This ensures that:
    1. The original file is never corrupted if write fails
    2. The write is durable (fsync ensures data is on disk)
    3. The replacement is atomic (os.replace is atomic on all platforms)
    
    Args:
        path: Target file path
        content: Content to write
        
    Raises:
        IOError: If write operations fail
        
    Requirements:
        - 7.2: Tracker write is atomic (temporary file + rename)
        - 7.5: When write fails, original tracker file remains intact
    """
    temp_fd = None
    temp_path = None
    
    try:
        # Use unique temp file in same directory to avoid predictable-name symlink attacks.
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp"
        )

        # Write to temp file and fsync for durability.
        content_bytes = content.encode("utf-8")
        os.write(temp_fd, content_bytes)
        os.fsync(temp_fd)
        os.close(temp_fd)
        temp_fd = None
        
        # Atomic replace (Requirement 7.2)
        # os.replace is atomic on all platforms and overwrites destination
        os.replace(temp_path, path)
        
    except Exception:
        # Clean up temp file on failure (Requirement 7.5)
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_path is not None and os.path.exists(temp_path):
            try:
                os.unlink(temp_path)
            except Exception:
                pass  # Best effort cleanup
        raise
