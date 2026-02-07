"""
Tracker file parser for update_tracker_status tool.

This module provides functions to parse tracker markdown files,
extract frontmatter and body content, and validate required fields.
"""

from typing import Dict, Any, Tuple, Optional
import re
import yaml

from models.errors import (
    create_file_not_found_error,
    create_validation_error
)
from utils.path_resolution import resolve_repo_relative_path


class TrackerParseError(Exception):
    """Exception raised when tracker parsing fails."""
    pass


def parse_tracker_file(tracker_path: str) -> Dict[str, Any]:
    """
    Parse tracker markdown file and extract frontmatter and body.
    
    This function reads a tracker file, parses the YAML frontmatter,
    validates that the required 'status' field is present, and extracts
    the body content.
    
    Args:
        tracker_path: Path to the tracker markdown file
        
    Returns:
        Dictionary containing:
        - frontmatter: Dict with all frontmatter fields
        - body: String containing the markdown body content
        - status: String with the current status value (convenience field)
        
    Raises:
        FileNotFoundError: If tracker file does not exist or is not readable
        TrackerParseError: If frontmatter is malformed or missing required 'status' field
        
    Requirements:
        - 2.1: Verify tracker_path exists and is readable
        - 2.2: Return FILE_NOT_FOUND when tracker file is missing
        - 2.3: Require YAML frontmatter with status field
        - 2.4: Return VALIDATION_ERROR when frontmatter is malformed or missing status
        
    Examples:
        >>> # Valid tracker file
        >>> result = parse_tracker_file("trackers/2026-02-05-amazon-3629.md")
        >>> result["status"]
        'Reviewed'
        >>> "frontmatter" in result
        True
        >>> "body" in result
        True
    """
    # Verify file exists and is readable (Requirement 2.1)
    path = resolve_repo_relative_path(tracker_path)
    if not path.exists():
        raise FileNotFoundError(f"Tracker file not found: {tracker_path}")
    
    if not path.is_file():
        raise FileNotFoundError(f"Tracker path is not a file: {tracker_path}")
    
    try:
        content = path.read_text(encoding='utf-8')
    except (IOError, OSError) as e:
        raise FileNotFoundError(f"Tracker file not readable: {tracker_path}") from e
    
    # Parse frontmatter and body
    try:
        frontmatter, body = _extract_frontmatter_and_body(content)
    except Exception as e:
        raise TrackerParseError(f"Failed to parse tracker frontmatter: {str(e)}") from e
    
    # Validate that status field is present (Requirement 2.3, 2.4)
    if "status" not in frontmatter:
        raise TrackerParseError("Tracker frontmatter is missing required 'status' field")
    
    # Return parsed data with convenience status field
    return {
        "frontmatter": frontmatter,
        "body": body,
        "status": frontmatter["status"]
    }


def _extract_frontmatter_and_body(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter and body content from markdown.
    
    Expects frontmatter to be delimited by '---' at the start and end.
    
    Args:
        content: Full markdown file content
        
    Returns:
        Tuple of (frontmatter_dict, body_string)
        
    Raises:
        TrackerParseError: If frontmatter is missing or malformed
        
    Examples:
        >>> content = '''---
        ... status: Reviewed
        ... company: Amazon
        ... ---
        ... 
        ... ## Job Description
        ... Content here
        ... '''
        >>> fm, body = _extract_frontmatter_and_body(content)
        >>> fm["status"]
        'Reviewed'
        >>> "## Job Description" in body
        True
    """
    # Match frontmatter pattern: --- at start, YAML content, --- delimiter
    # Pattern explanation:
    # ^---\s*\n  : Start with ---, optional whitespace, newline
    # (.*?)      : Capture YAML content (non-greedy)
    # \n---\s*\n : End with newline, ---, optional whitespace, newline
    # (.*)$      : Capture remaining content as body
    pattern = r'^---\s*\n(.*?)\n---\s*\n(.*)$'
    match = re.match(pattern, content, re.DOTALL)
    
    if not match:
        raise TrackerParseError("Tracker file does not contain valid YAML frontmatter delimited by '---'")
    
    yaml_content = match.group(1)
    body = match.group(2)
    
    # Parse YAML frontmatter
    try:
        frontmatter = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise TrackerParseError(f"Invalid YAML in frontmatter: {str(e)}") from e
    
    # Ensure frontmatter is a dictionary
    if not isinstance(frontmatter, dict):
        raise TrackerParseError("Frontmatter must be a YAML dictionary")
    
    return frontmatter, body


def get_tracker_status(tracker_path: str) -> str:
    """
    Get the current status from a tracker file.
    
    Convenience function that parses the tracker and returns only the status.
    
    Args:
        tracker_path: Path to the tracker markdown file
        
    Returns:
        Current status value as string
        
    Raises:
        FileNotFoundError: If tracker file does not exist or is not readable
        TrackerParseError: If frontmatter is malformed or missing status field
        
    Examples:
        >>> status = get_tracker_status("trackers/2026-02-05-amazon-3629.md")
        >>> status
        'Reviewed'
    """
    parsed = parse_tracker_file(tracker_path)
    return parsed["status"]


def get_frontmatter_field(tracker_path: str, field_name: str) -> Any:
    """
    Get a specific frontmatter field value from a tracker file.
    
    Args:
        tracker_path: Path to the tracker markdown file
        field_name: Name of the frontmatter field to retrieve
        
    Returns:
        Value of the requested field, or None if field does not exist
        
    Raises:
        FileNotFoundError: If tracker file does not exist or is not readable
        TrackerParseError: If frontmatter is malformed or missing status field
        
    Examples:
        >>> company = get_frontmatter_field("trackers/2026-02-05-amazon-3629.md", "company")
        >>> company
        'Amazon'
        >>> resume_path = get_frontmatter_field("trackers/2026-02-05-amazon-3629.md", "resume_path")
        >>> "resume.pdf" in resume_path
        True
    """
    parsed = parse_tracker_file(tracker_path)
    return parsed["frontmatter"].get(field_name)


def parse_tracker_with_error_mapping(tracker_path: str) -> Dict[str, Any]:
    """
    Parse tracker file and map exceptions to ToolError for MCP tool responses.
    
    This function wraps parse_tracker_file and converts exceptions to ToolError
    instances with appropriate error codes for MCP tool responses:
    - Missing/unreadable tracker -> FILE_NOT_FOUND
    - Malformed frontmatter -> VALIDATION_ERROR
    
    Args:
        tracker_path: Path to the tracker markdown file
        
    Returns:
        Dictionary containing:
        - frontmatter: Dict with all frontmatter fields
        - body: String containing the markdown body content
        - status: String with the current status value (convenience field)
        
    Raises:
        ToolError: With FILE_NOT_FOUND code if tracker file is missing/unreadable,
                   or VALIDATION_ERROR code if frontmatter is malformed or missing status
        
    Requirements:
        - 2.1: Verify tracker_path exists and is readable
        - 2.2: Return FILE_NOT_FOUND when tracker file is missing
        - 2.3: Require YAML frontmatter with status field
        - 2.4: Return VALIDATION_ERROR when frontmatter is malformed or missing status
        - 10.1: Request-level input validation failures return VALIDATION_ERROR
        - 10.2: Missing tracker file returns FILE_NOT_FOUND
        
    Examples:
        >>> # Valid tracker file
        >>> result = parse_tracker_with_error_mapping("trackers/2026-02-05-amazon-3629.md")
        >>> result["status"]
        'Reviewed'
        
        >>> # Missing tracker file
        >>> try:
        ...     parse_tracker_with_error_mapping("trackers/nonexistent.md")
        ... except ToolError as e:
        ...     print(e.code)
        FILE_NOT_FOUND
        
        >>> # Malformed frontmatter
        >>> try:
        ...     parse_tracker_with_error_mapping("trackers/malformed.md")
        ... except ToolError as e:
        ...     print(e.code)
        VALIDATION_ERROR
    """
    try:
        return parse_tracker_file(tracker_path)
    except FileNotFoundError as e:
        # Missing or unreadable tracker -> FILE_NOT_FOUND (Requirement 2.2, 10.2)
        raise create_file_not_found_error(tracker_path, "Tracker file") from e
    except TrackerParseError as e:
        # Malformed frontmatter or missing status -> VALIDATION_ERROR (Requirement 2.4, 10.1)
        raise create_validation_error(str(e)) from e


def resolve_resume_pdf_path_from_tracker(
    tracker_path: str,
    item_resume_pdf_path: Optional[str] = None
) -> str:
    """
    Resolve resume_pdf_path from tracker frontmatter when not provided by item.
    
    This function supports the finalize_resume_batch tool by resolving the
    resume_pdf_path from the tracker's frontmatter resume_path field when
    the item doesn't provide an explicit override.
    
    Resolution logic:
    1. If item_resume_pdf_path is provided, return it as-is (item override)
    2. Otherwise, parse tracker and extract resume_path from frontmatter
    3. Parse the resume_path wiki-link to get the actual PDF path
    
    Args:
        tracker_path: Path to the tracker markdown file
        item_resume_pdf_path: Optional resume_pdf_path override from finalize item
        
    Returns:
        Resolved resume_pdf_path string
        
    Raises:
        FileNotFoundError: If tracker file does not exist or is not readable
        TrackerParseError: If frontmatter is malformed or missing required fields
        ValueError: If resume_path is missing from tracker frontmatter or unparsable
        
    Requirements:
        - 3.6: Resolve resume_pdf_path from tracker frontmatter when item override is not provided
        - 10.2: Include resume_pdf_path in results
        
    Examples:
        >>> # Item provides override - use it directly
        >>> resolve_resume_pdf_path_from_tracker(
        ...     "trackers/2026-02-05-amazon.md",
        ...     item_resume_pdf_path="data/applications/amazon/resume/resume.pdf"
        ... )
        'data/applications/amazon/resume/resume.pdf'
        
        >>> # No item override - resolve from tracker frontmatter
        >>> resolve_resume_pdf_path_from_tracker("trackers/2026-02-05-amazon.md")
        'data/applications/amazon-352/resume/resume.pdf'
        
        >>> # Missing resume_path in tracker
        >>> resolve_resume_pdf_path_from_tracker("trackers/missing-resume-path.md")
        Traceback (most recent call last):
        ...
        ValueError: Tracker frontmatter is missing 'resume_path' field
    """
    # Import here to avoid circular dependency
    from utils.artifact_paths import parse_resume_path
    
    # If item provides explicit override, use it
    if item_resume_pdf_path is not None:
        return item_resume_pdf_path
    
    # Parse tracker to get frontmatter
    parsed = parse_tracker_file(tracker_path)
    frontmatter = parsed["frontmatter"]
    
    # Get resume_path from frontmatter
    resume_path_raw = frontmatter.get("resume_path")
    if resume_path_raw is None:
        raise ValueError("Tracker frontmatter is missing 'resume_path' field")
    
    # Parse the resume_path (handles wiki-link format)
    resume_pdf_path = parse_resume_path(resume_path_raw)
    
    if resume_pdf_path is None:
        raise ValueError("Failed to parse resume_path from tracker frontmatter")
    
    return resume_pdf_path


def extract_job_description(body: str) -> str:
    """
    Extract job description content from tracker body.
    
    Searches for the '## Job Description' heading and extracts all content
    until the next heading of the same or higher level (## or #).
    
    Args:
        body: Markdown body content from tracker file
        
    Returns:
        Job description content (without the heading itself)
        
    Raises:
        TrackerParseError: If '## Job Description' heading is not found
        
    Requirements:
        - 3.4: Require ## Job Description heading
        - 3.6: Extract job description content for ai_context.md
        
    Examples:
        >>> body = '''## Job Description
        ... 
        ... Build scalable systems.
        ... Work with distributed teams.
        ... 
        ... ## Notes
        ... Some notes here.
        ... '''
        >>> extract_job_description(body)
        'Build scalable systems.\\nWork with distributed teams.'
        
        >>> # Missing job description heading
        >>> body = '''## Notes
        ... Some notes here.
        ... '''
        >>> extract_job_description(body)
        Traceback (most recent call last):
        ...
        TrackerParseError: Tracker is missing required '## Job Description' heading
    """
    # Search for ## Job Description heading (case-insensitive)
    jd_pattern = r'^##\s+Job\s+Description\s*$'
    lines = body.split('\n')
    
    jd_start_idx = None
    for i, line in enumerate(lines):
        if re.match(jd_pattern, line.strip(), re.IGNORECASE):
            jd_start_idx = i
            break
    
    if jd_start_idx is None:
        raise TrackerParseError("Tracker is missing required '## Job Description' heading")
    
    # Extract content until next heading of same or higher level (## or #)
    jd_content_lines = []
    for i in range(jd_start_idx + 1, len(lines)):
        line = lines[i]
        # Check if this is a heading of level 1 or 2
        if re.match(r'^#{1,2}\s+', line):
            break
        jd_content_lines.append(line)
    
    # Join lines and strip leading/trailing whitespace
    jd_content = '\n'.join(jd_content_lines).strip()
    
    return jd_content


def parse_tracker_for_career_tailor(tracker_path: str) -> Dict[str, Any]:
    """
    Parse tracker file for career_tailor tool with required field validation.
    
    This function parses a tracker file and extracts all fields needed for
    the career_tailor workflow:
    - Frontmatter fields: company, position, resume_path, optional job_db_id
    - Job description content from '## Job Description' section
    
    Args:
        tracker_path: Path to the tracker markdown file
        
    Returns:
        Dictionary containing:
        - company: Company name from frontmatter
        - position: Position title from frontmatter
        - resume_path: Resume path from frontmatter (may be None)
        - job_db_id: Job database ID from frontmatter (may be None)
        - job_description: Extracted job description content
        - frontmatter: Complete frontmatter dict (for additional fields)
        - body: Complete body content (for reference)
        
    Raises:
        FileNotFoundError: If tracker file does not exist or is not readable
        TrackerParseError: If frontmatter is malformed, missing required fields,
                          or '## Job Description' heading is missing
        
    Requirements:
        - 3.1: Load tracker markdown from tracker_path
        - 3.3: Extract frontmatter fields needed for workspace resolution
        - 3.4: Require ## Job Description heading
        - 3.6: Extract job description content for ai_context.md
        
    Examples:
        >>> result = parse_tracker_for_career_tailor("trackers/2026-02-05-amazon.md")
        >>> result["company"]
        'Amazon'
        >>> result["position"]
        'Software Engineer'
        >>> "Build scalable systems" in result["job_description"]
        True
        >>> result["job_db_id"]
        3629
    """
    # Parse tracker file (Requirement 3.1)
    parsed = parse_tracker_file(tracker_path)
    frontmatter = parsed["frontmatter"]
    body = parsed["body"]
    
    # Extract required frontmatter fields (Requirement 3.3)
    company = frontmatter.get("company")
    position = frontmatter.get("position")
    resume_path = frontmatter.get("resume_path")
    job_db_id = frontmatter.get("job_db_id")
    
    # Validate required fields
    if company is None:
        raise TrackerParseError("Tracker frontmatter is missing required 'company' field")
    if position is None:
        raise TrackerParseError("Tracker frontmatter is missing required 'position' field")
    
    # Extract job description (Requirements 3.4, 3.6)
    job_description = extract_job_description(body)
    
    return {
        "company": company,
        "position": position,
        "resume_path": resume_path,
        "job_db_id": job_db_id,
        "job_description": job_description,
        "frontmatter": frontmatter,
        "body": body,
    }


def parse_tracker_for_career_tailor_with_error_mapping(tracker_path: str) -> Dict[str, Any]:
    """
    Parse tracker file for career_tailor with ToolError mapping.
    
    This function wraps parse_tracker_for_career_tailor and converts exceptions
    to ToolError instances with appropriate error codes for MCP tool responses:
    - Missing/unreadable tracker -> FILE_NOT_FOUND
    - Malformed frontmatter or missing required fields -> VALIDATION_ERROR
    - Missing '## Job Description' heading -> VALIDATION_ERROR
    
    Args:
        tracker_path: Path to the tracker markdown file
        
    Returns:
        Dictionary containing parsed tracker data (see parse_tracker_for_career_tailor)
        
    Raises:
        ToolError: With FILE_NOT_FOUND code if tracker file is missing/unreadable,
                   or VALIDATION_ERROR code if validation fails
        
    Requirements:
        - 3.2: Return FILE_NOT_FOUND when tracker file is missing
        - 3.5: Return VALIDATION_ERROR when ## Job Description is missing
        
    Examples:
        >>> result = parse_tracker_for_career_tailor_with_error_mapping("trackers/valid.md")
        >>> result["company"]
        'Amazon'
        
        >>> # Missing tracker file
        >>> try:
        ...     parse_tracker_for_career_tailor_with_error_mapping("trackers/missing.md")
        ... except ToolError as e:
        ...     print(e.code)
        FILE_NOT_FOUND
        
        >>> # Missing job description
        >>> try:
        ...     parse_tracker_for_career_tailor_with_error_mapping("trackers/no-jd.md")
        ... except ToolError as e:
        ...     print(e.code)
        VALIDATION_ERROR
    """
    try:
        return parse_tracker_for_career_tailor(tracker_path)
    except FileNotFoundError as e:
        # Missing or unreadable tracker -> FILE_NOT_FOUND (Requirement 3.2)
        raise create_file_not_found_error(tracker_path, "Tracker file") from e
    except TrackerParseError as e:
        # Malformed frontmatter, missing fields, or missing JD -> VALIDATION_ERROR (Requirement 3.5)
        raise create_validation_error(str(e)) from e
