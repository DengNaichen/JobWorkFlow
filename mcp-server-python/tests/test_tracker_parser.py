"""
Unit tests for tracker file parser.

Tests frontmatter parsing, body extraction, and error handling.
"""

import pytest

from utils.tracker_parser import (
    parse_tracker_file,
    get_tracker_status,
    get_frontmatter_field,
    parse_tracker_with_error_mapping,
    resolve_resume_pdf_path_from_tracker,
    extract_job_description,
    parse_tracker_for_career_tailor,
    parse_tracker_for_career_tailor_with_error_mapping,
    TrackerParseError,
    _extract_frontmatter_and_body
)
from models.errors import ToolError, ErrorCode


class TestExtractFrontmatterAndBody:
    """Tests for frontmatter and body extraction."""

    def test_extract_valid_frontmatter_and_body(self):
        """Test extraction from valid markdown with frontmatter."""
        content = """---
status: Reviewed
company: Amazon
position: Software Engineer
---

## Job Description

Build scalable systems.

## Notes
"""
        frontmatter, body = _extract_frontmatter_and_body(content)
        
        assert frontmatter["status"] == "Reviewed"
        assert frontmatter["company"] == "Amazon"
        assert frontmatter["position"] == "Software Engineer"
        assert "## Job Description" in body
        assert "Build scalable systems." in body
        assert "## Notes" in body

    def test_extract_with_multiline_values(self):
        """Test extraction with multiline YAML values."""
        content = """---
status: Reviewed
next_action:
- Wait for feedback
- Follow up
salary: 0
---

## Job Description

Content here.
"""
        frontmatter, body = _extract_frontmatter_and_body(content)
        
        assert frontmatter["status"] == "Reviewed"
        assert isinstance(frontmatter["next_action"], list)
        assert len(frontmatter["next_action"]) == 2
        assert frontmatter["next_action"][0] == "Wait for feedback"

    def test_extract_missing_frontmatter_delimiters(self):
        """Test that missing frontmatter delimiters raises error."""
        content = """## Job Description

No frontmatter here.
"""
        with pytest.raises(TrackerParseError) as exc_info:
            _extract_frontmatter_and_body(content)
        
        assert "does not contain valid YAML frontmatter" in str(exc_info.value)

    def test_extract_malformed_yaml(self):
        """Test that malformed YAML raises error."""
        content = """---
status: Reviewed
company: Amazon
  invalid_indent: bad
---

## Job Description
"""
        with pytest.raises(TrackerParseError) as exc_info:
            _extract_frontmatter_and_body(content)
        
        assert "Invalid YAML" in str(exc_info.value)

    def test_extract_non_dict_frontmatter(self):
        """Test that non-dictionary frontmatter raises error."""
        content = """---
- item1
- item2
---

## Job Description
"""
        with pytest.raises(TrackerParseError) as exc_info:
            _extract_frontmatter_and_body(content)
        
        assert "must be a YAML dictionary" in str(exc_info.value)


class TestParseTrackerFile:
    """Tests for complete tracker file parsing."""

    def test_parse_valid_tracker_file(self, tmp_path):
        """Test parsing a valid tracker file."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 352
job_id: li-4331530278
company: Amazon
position: Software Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://example.com/job/123
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/amazon-352/cover/cover-letter.pdf]]'
next_action:
- Wait for feedback
salary: 0
website: ''
---

## Job Description

Build scalable systems.

## Notes
""", encoding='utf-8')
        
        result = parse_tracker_file(str(tracker_path))
        
        assert "frontmatter" in result
        assert "body" in result
        assert "status" in result
        assert result["status"] == "Reviewed"
        assert result["frontmatter"]["company"] == "Amazon"
        assert result["frontmatter"]["position"] == "Software Engineer"
        assert "## Job Description" in result["body"]

    def test_parse_tracker_file_not_found(self, tmp_path):
        """Test that missing tracker file raises FileNotFoundError."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_tracker_file(str(tracker_path))
        
        assert "not found" in str(exc_info.value).lower()

    def test_parse_tracker_path_is_directory(self, tmp_path):
        """Test that directory path raises FileNotFoundError."""
        tracker_dir = tmp_path / "tracker_dir"
        tracker_dir.mkdir()
        
        with pytest.raises(FileNotFoundError) as exc_info:
            parse_tracker_file(str(tracker_dir))
        
        assert "not a file" in str(exc_info.value).lower()

    def test_parse_tracker_missing_status_field(self, tmp_path):
        """Test that missing status field raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 352
company: Amazon
position: Software Engineer
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_file(str(tracker_path))
        
        assert "missing required 'status' field" in str(exc_info.value)

    def test_parse_tracker_malformed_frontmatter(self, tmp_path):
        """Test that malformed frontmatter raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
  bad_indent: invalid
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_file(str(tracker_path))
        
        assert "Failed to parse tracker frontmatter" in str(exc_info.value)

    def test_parse_tracker_no_frontmatter(self, tmp_path):
        """Test that tracker without frontmatter raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""## Job Description

No frontmatter here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_file(str(tracker_path))
        
        assert "Failed to parse tracker frontmatter" in str(exc_info.value)

    def test_parse_tracker_relative_path_resolves_from_repo_root(self, tmp_path, monkeypatch):
        """Relative tracker paths should resolve from JOBWORKFLOW_ROOT/repo root."""
        repo_root = tmp_path
        trackers_dir = repo_root / "trackers"
        trackers_dir.mkdir(parents=True, exist_ok=True)

        tracker_path = trackers_dir / "repo-root-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
---

## Job Description
Content
""", encoding="utf-8")

        work_cwd = tmp_path / "other-cwd"
        work_cwd.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("JOBWORKFLOW_ROOT", str(repo_root))
        monkeypatch.chdir(work_cwd)

        result = parse_tracker_file("trackers/repo-root-tracker.md")
        assert result["status"] == "Reviewed"


class TestGetTrackerStatus:
    """Tests for get_tracker_status convenience function."""

    def test_get_status_from_valid_tracker(self, tmp_path):
        """Test getting status from valid tracker file."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Resume Written
company: Amazon
---

## Job Description
""", encoding='utf-8')
        
        status = get_tracker_status(str(tracker_path))
        assert status == "Resume Written"

    def test_get_status_file_not_found(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError):
            get_tracker_status(str(tracker_path))

    def test_get_status_missing_status_field(self, tmp_path):
        """Test that missing status field raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError):
            get_tracker_status(str(tracker_path))


class TestGetFrontmatterField:
    """Tests for get_frontmatter_field convenience function."""

    def test_get_existing_field(self, tmp_path):
        """Test getting an existing frontmatter field."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
position: Software Engineer
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        company = get_frontmatter_field(str(tracker_path), "company")
        assert company == "Amazon"
        
        position = get_frontmatter_field(str(tracker_path), "position")
        assert position == "Software Engineer"
        
        resume_path = get_frontmatter_field(str(tracker_path), "resume_path")
        assert "resume.pdf" in resume_path

    def test_get_nonexistent_field(self, tmp_path):
        """Test getting a nonexistent field returns None."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
---

## Job Description
""", encoding='utf-8')
        
        result = get_frontmatter_field(str(tracker_path), "nonexistent_field")
        assert result is None

    def test_get_field_file_not_found(self, tmp_path):
        """Test that missing file raises FileNotFoundError."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError):
            get_frontmatter_field(str(tracker_path), "company")


class TestParseTrackerWithErrorMapping:
    """Tests for parse_tracker_with_error_mapping function."""

    def test_parse_valid_tracker_returns_data(self, tmp_path):
        """Test that valid tracker file returns parsed data."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 352
company: Amazon
position: Software Engineer
status: Reviewed
---

## Job Description

Build scalable systems.
""", encoding='utf-8')
        
        result = parse_tracker_with_error_mapping(str(tracker_path))
        
        assert "frontmatter" in result
        assert "body" in result
        assert "status" in result
        assert result["status"] == "Reviewed"
        assert result["frontmatter"]["company"] == "Amazon"

    def test_missing_tracker_raises_file_not_found_error(self, tmp_path):
        """Test that missing tracker file raises ToolError with FILE_NOT_FOUND code."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert "Tracker file not found" in error.message
        assert not error.retryable

    def test_unreadable_tracker_raises_file_not_found_error(self, tmp_path):
        """Test that directory path raises ToolError with FILE_NOT_FOUND code."""
        tracker_dir = tmp_path / "tracker_dir"
        tracker_dir.mkdir()
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_with_error_mapping(str(tracker_dir))
        
        error = exc_info.value
        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert "Tracker file not found" in error.message
        assert not error.retryable

    def test_malformed_frontmatter_raises_validation_error(self, tmp_path):
        """Test that malformed frontmatter raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
  bad_indent: invalid
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Failed to parse tracker frontmatter" in error.message
        assert not error.retryable

    def test_missing_status_field_raises_validation_error(self, tmp_path):
        """Test that missing status field raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 352
company: Amazon
position: Software Engineer
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "missing required 'status' field" in error.message
        assert not error.retryable

    def test_no_frontmatter_raises_validation_error(self, tmp_path):
        """Test that tracker without frontmatter raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""## Job Description

No frontmatter here.
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "Failed to parse tracker frontmatter" in error.message
        assert not error.retryable


class TestResolveResumePdfPathFromTracker:
    """Tests for resolve_resume_pdf_path_from_tracker function."""

    def test_item_override_takes_precedence(self, tmp_path):
        """Test that item_resume_pdf_path override is used when provided."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        # Provide explicit override
        result = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path="data/applications/override/resume/resume.pdf"
        )
        
        # Should use the override, not the tracker value
        assert result == "data/applications/override/resume/resume.pdf"

    def test_resolve_from_tracker_wiki_link(self, tmp_path):
        """Test resolving resume_pdf_path from tracker frontmatter wiki-link."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        # No override - should resolve from tracker
        result = resolve_resume_pdf_path_from_tracker(str(tracker_path))
        
        assert result == "data/applications/amazon-352/resume/resume.pdf"

    def test_resolve_from_tracker_plain_path(self, tmp_path):
        """Test resolving resume_pdf_path from tracker frontmatter plain path."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Meta
resume_path: data/applications/meta-100/resume/resume.pdf
---

## Job Description
""", encoding='utf-8')
        
        # No override - should resolve from tracker
        result = resolve_resume_pdf_path_from_tracker(str(tracker_path))
        
        assert result == "data/applications/meta-100/resume/resume.pdf"

    def test_missing_resume_path_raises_error(self, tmp_path):
        """Test that missing resume_path in tracker raises ValueError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(ValueError) as exc_info:
            resolve_resume_pdf_path_from_tracker(str(tracker_path))
        
        assert "missing 'resume_path' field" in str(exc_info.value)

    def test_empty_resume_path_raises_error(self, tmp_path):
        """Test that empty resume_path in tracker raises error."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
resume_path: ''
---

## Job Description
""", encoding='utf-8')
        
        # Should raise error from parse_resume_path
        with pytest.raises(Exception):  # Could be ValueError or ArtifactPathError
            resolve_resume_pdf_path_from_tracker(str(tracker_path))

    def test_tracker_not_found_raises_file_not_found(self, tmp_path):
        """Test that missing tracker file raises FileNotFoundError."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError):
            resolve_resume_pdf_path_from_tracker(str(tracker_path))

    def test_malformed_tracker_raises_tracker_parse_error(self, tmp_path):
        """Test that malformed tracker raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
  bad_indent: invalid
---

## Job Description
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError):
            resolve_resume_pdf_path_from_tracker(str(tracker_path))

    def test_none_override_resolves_from_tracker(self, tmp_path):
        """Test that explicit None override still resolves from tracker."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
status: Reviewed
company: Amazon
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
---

## Job Description
""", encoding='utf-8')
        
        # Explicit None should resolve from tracker
        result = resolve_resume_pdf_path_from_tracker(
            str(tracker_path),
            item_resume_pdf_path=None
        )
        
        assert result == "data/applications/amazon-352/resume/resume.pdf"



class TestExtractJobDescription:
    """Tests for extract_job_description function."""

    def test_extract_job_description_basic(self):
        """Test extracting job description from basic tracker body."""
        body = """## Job Description

Build scalable systems.
Work with distributed teams.

## Notes
Some notes here.
"""
        result = extract_job_description(body)
        
        assert "Build scalable systems." in result
        assert "Work with distributed teams." in result
        assert "## Notes" not in result
        assert "Some notes here." not in result

    def test_extract_job_description_multiline(self):
        """Test extracting multiline job description."""
        body = """## Job Description

We are looking for a Software Engineer to:
- Design and implement features
- Collaborate with cross-functional teams
- Write clean, maintainable code

Requirements:
- 5+ years of experience
- Strong Python skills

## Application Process
"""
        result = extract_job_description(body)
        
        assert "We are looking for a Software Engineer" in result
        assert "Design and implement features" in result
        assert "5+ years of experience" in result
        assert "Strong Python skills" in result
        assert "## Application Process" not in result

    def test_extract_job_description_case_insensitive(self):
        """Test that job description heading is case-insensitive."""
        body = """## job description

Content here.

## Notes
"""
        result = extract_job_description(body)
        assert "Content here." in result

    def test_extract_job_description_with_extra_spaces(self):
        """Test job description heading with extra spaces."""
        body = """##   Job   Description  

Content here.

## Notes
"""
        result = extract_job_description(body)
        assert "Content here." in result

    def test_extract_job_description_at_end_of_file(self):
        """Test extracting job description when it's the last section."""
        body = """## Notes
Some notes.

## Job Description

This is the job description.
It continues here.
"""
        result = extract_job_description(body)
        
        assert "This is the job description." in result
        assert "It continues here." in result
        assert "Some notes." not in result

    def test_extract_job_description_stops_at_level_1_heading(self):
        """Test that extraction stops at level 1 heading."""
        body = """## Job Description

Content here.

# Major Section

More content.
"""
        result = extract_job_description(body)
        
        assert "Content here." in result
        assert "# Major Section" not in result
        assert "More content." not in result

    def test_extract_job_description_missing_heading_raises_error(self):
        """Test that missing job description heading raises TrackerParseError."""
        body = """## Notes
Some notes here.

## Application Process
More content.
"""
        with pytest.raises(TrackerParseError) as exc_info:
            extract_job_description(body)
        
        assert "missing required '## Job Description' heading" in str(exc_info.value)

    def test_extract_job_description_empty_content(self):
        """Test extracting job description with empty content."""
        body = """## Job Description

## Notes
Some notes.
"""
        result = extract_job_description(body)
        
        # Should return empty string (stripped)
        assert result == ""

    def test_extract_job_description_with_blank_lines(self):
        """Test extracting job description preserves blank lines."""
        body = """## Job Description

First paragraph.

Second paragraph after blank line.

## Notes
"""
        result = extract_job_description(body)
        
        assert "First paragraph." in result
        assert "Second paragraph after blank line." in result
        # Should preserve the blank line between paragraphs
        assert "\n\n" in result


class TestParseTrackerForCareerTailor:
    """Tests for parse_tracker_for_career_tailor function."""

    def test_parse_valid_tracker_with_all_fields(self, tmp_path):
        """Test parsing valid tracker with all required and optional fields."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 3629
company: Amazon
position: Software Engineer
status: Reviewed
resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'
---

## Job Description

Build scalable distributed systems.
Work with cross-functional teams.

## Notes
Some notes here.
""", encoding='utf-8')
        
        result = parse_tracker_for_career_tailor(str(tracker_path))
        
        assert result["company"] == "Amazon"
        assert result["position"] == "Software Engineer"
        assert result["resume_path"] == "[[data/applications/amazon-3629/resume/resume.pdf]]"
        assert result["job_db_id"] == 3629
        assert "Build scalable distributed systems." in result["job_description"]
        assert "Work with cross-functional teams." in result["job_description"]
        assert "## Notes" not in result["job_description"]
        assert "frontmatter" in result
        assert "body" in result

    def test_parse_tracker_without_optional_fields(self, tmp_path):
        """Test parsing tracker without optional job_db_id and resume_path."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Meta
position: Senior Engineer
status: Applied
---

## Job Description

Lead technical initiatives.
""", encoding='utf-8')
        
        result = parse_tracker_for_career_tailor(str(tracker_path))
        
        assert result["company"] == "Meta"
        assert result["position"] == "Senior Engineer"
        assert result["resume_path"] is None
        assert result["job_db_id"] is None
        assert "Lead technical initiatives." in result["job_description"]

    def test_parse_tracker_missing_company_raises_error(self, tmp_path):
        """Test that missing company field raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
position: Software Engineer
status: Applied
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_for_career_tailor(str(tracker_path))
        
        assert "missing required 'company' field" in str(exc_info.value)

    def test_parse_tracker_missing_position_raises_error(self, tmp_path):
        """Test that missing position field raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
status: Applied
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_for_career_tailor(str(tracker_path))
        
        assert "missing required 'position' field" in str(exc_info.value)

    def test_parse_tracker_missing_job_description_raises_error(self, tmp_path):
        """Test that missing job description heading raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
position: Software Engineer
status: Applied
---

## Notes
Some notes here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError) as exc_info:
            parse_tracker_for_career_tailor(str(tracker_path))
        
        assert "missing required '## Job Description' heading" in str(exc_info.value)

    def test_parse_tracker_file_not_found_raises_error(self, tmp_path):
        """Test that missing tracker file raises FileNotFoundError."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(FileNotFoundError):
            parse_tracker_for_career_tailor(str(tracker_path))

    def test_parse_tracker_malformed_frontmatter_raises_error(self, tmp_path):
        """Test that malformed frontmatter raises TrackerParseError."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
position: Engineer
  bad_indent: invalid
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(TrackerParseError):
            parse_tracker_for_career_tailor(str(tracker_path))

    def test_parse_tracker_preserves_all_frontmatter(self, tmp_path):
        """Test that all frontmatter fields are preserved in result."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 100
company: Google
position: Staff Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://example.com/job
salary: 200000
custom_field: custom_value
---

## Job Description

Build infrastructure.
""", encoding='utf-8')
        
        result = parse_tracker_for_career_tailor(str(tracker_path))
        
        assert result["frontmatter"]["application_date"] == "2026-02-05"
        assert result["frontmatter"]["reference_link"] == "https://example.com/job"
        assert result["frontmatter"]["salary"] == 200000
        assert result["frontmatter"]["custom_field"] == "custom_value"


class TestParseTrackerForCareerTailorWithErrorMapping:
    """Tests for parse_tracker_for_career_tailor_with_error_mapping function."""

    def test_parse_valid_tracker_returns_data(self, tmp_path):
        """Test that valid tracker returns parsed data."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
job_db_id: 3629
company: Amazon
position: Software Engineer
status: Reviewed
---

## Job Description

Build scalable systems.
""", encoding='utf-8')
        
        result = parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        assert result["company"] == "Amazon"
        assert result["position"] == "Software Engineer"
        assert result["job_db_id"] == 3629
        assert "Build scalable systems." in result["job_description"]

    def test_missing_tracker_raises_file_not_found_error(self, tmp_path):
        """Test that missing tracker raises ToolError with FILE_NOT_FOUND code."""
        tracker_path = tmp_path / "nonexistent.md"
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert "Tracker file not found" in error.message
        assert not error.retryable

    def test_missing_company_raises_validation_error(self, tmp_path):
        """Test that missing company raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
position: Software Engineer
status: Applied
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "missing required 'company' field" in error.message
        assert not error.retryable

    def test_missing_position_raises_validation_error(self, tmp_path):
        """Test that missing position raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
status: Applied
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "missing required 'position' field" in error.message
        assert not error.retryable

    def test_missing_job_description_raises_validation_error(self, tmp_path):
        """Test that missing job description raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
position: Software Engineer
status: Applied
---

## Notes
Some notes here.
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert "missing required '## Job Description' heading" in error.message
        assert not error.retryable

    def test_malformed_frontmatter_raises_validation_error(self, tmp_path):
        """Test that malformed frontmatter raises ToolError with VALIDATION_ERROR code."""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text("""---
company: Amazon
position: Engineer
  bad_indent: invalid
---

## Job Description

Content here.
""", encoding='utf-8')
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_path))
        
        error = exc_info.value
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert not error.retryable

    def test_unreadable_tracker_raises_file_not_found_error(self, tmp_path):
        """Test that directory path raises ToolError with FILE_NOT_FOUND code."""
        tracker_dir = tmp_path / "tracker_dir"
        tracker_dir.mkdir()
        
        with pytest.raises(ToolError) as exc_info:
            parse_tracker_for_career_tailor_with_error_mapping(str(tracker_dir))
        
        error = exc_info.value
        assert error.code == ErrorCode.FILE_NOT_FOUND
        assert not error.retryable
