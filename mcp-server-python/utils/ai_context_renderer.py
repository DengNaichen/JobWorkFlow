"""
AI context renderer for career_tailor tool.

This module provides functions to generate ai_context.md files that contain
the full resume source and job description for AI-assisted resume tailoring.
"""

from pathlib import Path
from typing import Optional

from utils.file_ops import atomic_write


def render_ai_context(
    company: str,
    position: str,
    job_description: str,
    full_resume_path: str = "data/templates/full_resume_example.md",
    output_path: Optional[str] = None,
) -> str:
    """
    Render ai_context.md file with full resume and job description.

    This function generates an ai_context.md file that contains:
    1. Full resume source content (raw markdown)
    2. Job description from the tracker
    3. Instructions for AI-assisted tailoring

    The file is written atomically to ensure it's never in a partially written state.

    Args:
        company: Company name from tracker frontmatter
        position: Position title from tracker frontmatter
        job_description: Job description content extracted from tracker
        full_resume_path: Path to full resume markdown file (default: data/templates/full_resume_example.md)
        output_path: Target path for ai_context.md (if None, returns content without writing)

    Returns:
        Rendered ai_context.md content as string

    Raises:
        FileNotFoundError: If full_resume_path does not exist
        OSError: If file write fails

    Requirements:
        - 4.5: Regenerate resume/ai_context.md on each successful item run
        - 4.6: Generated files SHALL be written atomically

    Examples:
        >>> # Generate and write ai_context.md
        >>> content = render_ai_context(
        ...     company="Amazon",
        ...     position="Software Engineer",
        ...     job_description="Build scalable systems...",
        ...     full_resume_path="data/templates/full_resume_example.md",
        ...     output_path="data/applications/amazon-3629/resume/ai_context.md"
        ... )
        >>> "## Full Resume Source (raw)" in content
        True
        >>> "## Job Description" in content
        True

        >>> # Generate content without writing
        >>> content = render_ai_context(
        ...     company="Meta",
        ...     position="Research Scientist",
        ...     job_description="Develop AI systems...",
        ...     full_resume_path="data/templates/full_resume_example.md"
        ... )
        >>> "Meta" in content
        True
    """
    # Read full resume content
    full_resume_path_obj = Path(full_resume_path)
    if not full_resume_path_obj.exists():
        raise FileNotFoundError(f"Full resume file not found: {full_resume_path}")

    full_resume_content = full_resume_path_obj.read_text(encoding="utf-8")

    # Build ai_context.md content
    content_parts = [
        "# AI Context",
        "",
        "## Full Resume Source (raw)",
        full_resume_content.strip(),
        "",
        "## Job Description",
        job_description.strip(),
        "",
        "## Notes",
        f"- Company: {company}",
        f"- Position: {position}",
        "- Created via career_tailor MCP Tool",
        "",
        "## Instructions",
        "- Tailor the resume content to match the job description.",
        "- Keep content truthful and consistent with the source resume.",
        "- Update resume.tex in this folder accordingly.",
        "",
    ]

    content = "\n".join(content_parts)

    # Write atomically if output_path is provided (Requirement 4.6)
    if output_path is not None:
        atomic_write(output_path, content)

    return content


def regenerate_ai_context(
    tracker_data: dict,
    workspace_dir: str,
    full_resume_path: str = "data/templates/full_resume_example.md",
) -> str:
    """
    Regenerate ai_context.md for a workspace from tracker data.

    This is a convenience function that combines tracker data extraction
    and ai_context rendering into a single call. It's designed to be used
    by the career_tailor tool during batch processing.

    Args:
        tracker_data: Parsed tracker data from parse_tracker_for_career_tailor
        workspace_dir: Application workspace directory (e.g., data/applications/amazon-3629)
        full_resume_path: Path to full resume markdown file

    Returns:
        Path to the generated ai_context.md file

    Raises:
        FileNotFoundError: If full_resume_path does not exist
        OSError: If file write fails
        KeyError: If tracker_data is missing required fields

    Requirements:
        - 4.5: Regenerate resume/ai_context.md on each successful item run
        - 4.6: Generated files SHALL be written atomically

    Examples:
        >>> tracker_data = {
        ...     "company": "Amazon",
        ...     "position": "Software Engineer",
        ...     "job_description": "Build scalable systems..."
        ... }
        >>> ai_context_path = regenerate_ai_context(
        ...     tracker_data=tracker_data,
        ...     workspace_dir="data/applications/amazon-3629",
        ...     full_resume_path="data/templates/full_resume_example.md"
        ... )
        >>> ai_context_path
        'data/applications/amazon-3629/resume/ai_context.md'
    """
    # Extract required fields from tracker data
    company = tracker_data["company"]
    position = tracker_data["position"]
    job_description = tracker_data["job_description"]

    # Construct output path
    workspace_path = Path(workspace_dir)
    ai_context_path = workspace_path / "resume" / "ai_context.md"

    # Render and write ai_context.md
    render_ai_context(
        company=company,
        position=position,
        job_description=job_description,
        full_resume_path=full_resume_path,
        output_path=str(ai_context_path),
    )

    return str(ai_context_path)
