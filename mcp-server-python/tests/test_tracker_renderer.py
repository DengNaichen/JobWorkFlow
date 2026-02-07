"""
Unit tests for tracker markdown renderer.

Tests stable frontmatter rendering, section structure, and content handling.
"""

from utils.tracker_renderer import render_tracker_markdown, _extract_date, _render_job_description


class TestExtractDate:
    """Tests for date extraction from timestamps."""

    def test_extract_date_with_t_separator(self):
        """Test date extraction from ISO format with T separator."""
        assert _extract_date("2026-02-04T15:30:00") == "2026-02-04"
        assert _extract_date("2025-12-31T23:59:59") == "2025-12-31"

    def test_extract_date_with_space_separator(self):
        """Test date extraction from format with space separator."""
        assert _extract_date("2026-02-04 15:30:00") == "2026-02-04"
        assert _extract_date("2025-12-31 23:59:59") == "2025-12-31"


class TestRenderJobDescription:
    """Tests for job description rendering with fallback."""

    def test_render_with_valid_description(self):
        """Test rendering with valid description text."""
        description = "Build scalable systems and work with great team."
        result = _render_job_description(description)
        assert result == description

    def test_render_with_none_description(self):
        """Test rendering with None description uses fallback."""
        result = _render_job_description(None)
        assert result == "No description available."

    def test_render_with_empty_description(self):
        """Test rendering with empty string uses fallback."""
        result = _render_job_description("")
        assert result == "No description available."


class TestRenderTrackerMarkdown:
    """Tests for complete tracker markdown rendering."""

    def test_render_includes_required_frontmatter_fields(self):
        """Test that rendered tracker includes all required frontmatter fields."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        # Check required frontmatter fields are present
        assert "job_db_id: 3629" in content
        assert "job_id: '4368663835'" in content or 'job_id: "4368663835"' in content
        assert "company: Amazon" in content
        assert "position: Software Engineer" in content
        assert "status: Reviewed" in content
        assert (
            "application_date: '2026-02-04'" in content or "application_date: 2026-02-04" in content
        )
        assert "reference_link: https://example.com/job/123" in content
        assert "resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'" in content
        assert (
            "cover_letter_path: '[[data/applications/amazon-3629/cover/cover-letter.pdf]]'"
            in content
        )

    def test_render_sets_initial_status_to_reviewed(self):
        """Test that initial tracker status is set to 'Reviewed'."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        assert "status: Reviewed" in content

    def test_render_includes_exact_section_headings(self):
        """Test that tracker includes exact '## Job Description' and '## Notes' headings."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        assert "## Job Description" in content
        assert "## Notes" in content

    def test_render_includes_description_text(self):
        """Test that tracker includes job description text."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems and work with great team.",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        assert "Build scalable systems and work with great team." in content

    def test_render_uses_fallback_for_missing_description(self):
        """Test that tracker uses fallback text when description is missing."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": None,
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        assert "No description available." in content

    def test_render_has_yaml_frontmatter_delimiters(self):
        """Test that tracker has proper YAML frontmatter delimiters."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        # Should start with --- and have closing ---
        lines = content.split("\n")
        assert lines[0] == "---"
        assert "---" in lines[1:]  # Closing delimiter exists

    def test_render_includes_compatibility_fields(self):
        """Test that tracker includes compatibility fields for current ecosystem."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content = render_tracker_markdown(job, plan)

        # Check compatibility fields
        assert "next_action:" in content
        assert "Wait for feedback" in content
        assert "salary: 0" in content
        assert "website:" in content

    def test_render_determinism(self):
        """Test that same inputs produce same output."""
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }
        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        content1 = render_tracker_markdown(job, plan)
        content2 = render_tracker_markdown(job, plan)

        assert content1 == content2
