"""
Tests for ai_context_renderer module.

This module tests the AI context rendering functionality for career_tailor,
including atomic writes and content generation.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from utils.ai_context_renderer import render_ai_context, regenerate_ai_context


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory for testing."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def temp_full_resume(temp_workspace):
    """Create a temporary full resume file for testing."""
    full_resume_path = Path(temp_workspace) / "full_resume.md"
    full_resume_content = """# John Doe
- Location: ON, Canada
- Email: john@example.com
- Phone: +1 555-555-5555

## Summary
Experienced software engineer with expertise in Python and distributed systems.

## Technical Skills
- Languages: Python, Go, TypeScript
- Backend: FastAPI, Django, Flask
- Databases: PostgreSQL, Redis

## Work Experience
### Tech Corp — Senior Software Engineer — Jan 2020 to Present
- Built scalable microservices handling 1M+ requests/day
- Optimized database queries reducing latency by 50%
- Mentored junior engineers on best practices
"""
    full_resume_path.write_text(full_resume_content, encoding="utf-8")
    return str(full_resume_path)


class TestRenderAiContext:
    """Tests for render_ai_context function."""

    def test_render_ai_context_basic(self, temp_full_resume):
        """Test basic ai_context rendering without writing to file."""
        content = render_ai_context(
            company="Amazon",
            position="Software Engineer",
            job_description="Build scalable distributed systems using Python and Go.",
            full_resume_path=temp_full_resume,
            output_path=None,
        )

        # Verify structure
        assert "# AI Context" in content
        assert "## Full Resume Source (raw)" in content
        assert "## Job Description" in content
        assert "## Notes" in content
        assert "## Instructions" in content

        # Verify content
        assert "John Doe" in content
        assert "Build scalable distributed systems" in content
        assert "Company: Amazon" in content
        assert "Position: Software Engineer" in content
        assert "career_tailor MCP Tool" in content

    def test_render_ai_context_with_write(self, temp_full_resume, temp_workspace):
        """Test ai_context rendering with atomic write to file."""
        output_path = Path(temp_workspace) / "ai_context.md"

        content = render_ai_context(
            company="Meta",
            position="Research Scientist",
            job_description="Develop AI systems for large-scale applications.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        # Verify file was created
        assert output_path.exists()

        # Verify file content matches returned content
        file_content = output_path.read_text(encoding="utf-8")
        assert file_content == content

        # Verify content structure
        assert "Meta" in file_content
        assert "Research Scientist" in file_content
        assert "Develop AI systems" in file_content

    def test_render_ai_context_missing_full_resume(self, temp_workspace):
        """Test error handling when full resume file is missing."""
        with pytest.raises(FileNotFoundError, match="Full resume file not found"):
            render_ai_context(
                company="Amazon",
                position="Software Engineer",
                job_description="Build systems.",
                full_resume_path="nonexistent/full_resume.md",
                output_path=None,
            )

    def test_render_ai_context_creates_parent_dirs(self, temp_full_resume, temp_workspace):
        """Test that atomic_write creates parent directories if needed."""
        output_path = Path(temp_workspace) / "applications" / "amazon" / "resume" / "ai_context.md"

        # Parent directories don't exist yet
        assert not output_path.parent.exists()

        render_ai_context(
            company="Amazon",
            position="Software Engineer",
            job_description="Build systems.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        # Verify file and parent directories were created
        assert output_path.exists()
        assert output_path.parent.exists()

    def test_render_ai_context_overwrites_existing(self, temp_full_resume, temp_workspace):
        """Test that rendering overwrites existing ai_context.md atomically."""
        output_path = Path(temp_workspace) / "ai_context.md"

        # Create initial file
        output_path.write_text("Old content", encoding="utf-8")
        assert output_path.read_text() == "Old content"

        # Render new content
        render_ai_context(
            company="Amazon",
            position="Software Engineer",
            job_description="New job description.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        # Verify file was overwritten
        new_content = output_path.read_text(encoding="utf-8")
        assert "Old content" not in new_content
        assert "New job description" in new_content

    def test_render_ai_context_multiline_job_description(self, temp_full_resume, temp_workspace):
        """Test rendering with multiline job description."""
        job_description = """Build scalable distributed systems.
Work with cross-functional teams.
Mentor junior engineers.

Requirements:
- 5+ years Python experience
- Strong system design skills"""

        content = render_ai_context(
            company="Amazon",
            position="Senior Software Engineer",
            job_description=job_description,
            full_resume_path=temp_full_resume,
            output_path=None,
        )

        # Verify multiline content is preserved
        assert "Build scalable distributed systems." in content
        assert "Work with cross-functional teams." in content
        assert "5+ years Python experience" in content

    def test_render_ai_context_special_characters(self, temp_full_resume, temp_workspace):
        """Test rendering with special characters in company/position."""
        content = render_ai_context(
            company="O'Reilly & Associates",
            position="Software Engineer (ML/AI)",
            job_description="Build AI systems.",
            full_resume_path=temp_full_resume,
            output_path=None,
        )

        # Verify special characters are preserved
        assert "O'Reilly & Associates" in content
        assert "Software Engineer (ML/AI)" in content


class TestRegenerateAiContext:
    """Tests for regenerate_ai_context function."""

    def test_regenerate_ai_context_basic(self, temp_full_resume, temp_workspace):
        """Test basic ai_context regeneration from tracker data."""
        # Create workspace structure
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        resume_dir = workspace_dir / "resume"
        resume_dir.mkdir(parents=True)

        tracker_data = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "Build scalable systems using Python and Go.",
        }

        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify path is correct
        expected_path = str(workspace_dir / "resume" / "ai_context.md")
        assert ai_context_path == expected_path

        # Verify file was created
        assert Path(ai_context_path).exists()

        # Verify content
        content = Path(ai_context_path).read_text(encoding="utf-8")
        assert "Amazon" in content
        assert "Software Engineer" in content
        assert "Build scalable systems" in content
        assert "John Doe" in content  # From full resume

    def test_regenerate_ai_context_missing_tracker_fields(self, temp_full_resume, temp_workspace):
        """Test error handling when tracker data is missing required fields."""
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        workspace_dir.mkdir(parents=True)

        # Missing 'position' field
        tracker_data = {"company": "Amazon", "job_description": "Build systems."}

        with pytest.raises(KeyError):
            regenerate_ai_context(
                tracker_data=tracker_data,
                workspace_dir=str(workspace_dir),
                full_resume_path=temp_full_resume,
            )

    def test_regenerate_ai_context_creates_resume_dir(self, temp_full_resume, temp_workspace):
        """Test that regenerate creates resume directory if it doesn't exist."""
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        # Don't create resume directory

        tracker_data = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "Build systems.",
        }

        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify file and directories were created
        assert Path(ai_context_path).exists()
        assert Path(ai_context_path).parent.exists()

    def test_regenerate_ai_context_overwrites_existing(self, temp_full_resume, temp_workspace):
        """Test that regenerate overwrites existing ai_context.md."""
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        resume_dir = workspace_dir / "resume"
        resume_dir.mkdir(parents=True)

        # Create existing ai_context.md
        ai_context_path = resume_dir / "ai_context.md"
        ai_context_path.write_text("Old content", encoding="utf-8")

        tracker_data = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "New job description.",
        }

        result_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify file was overwritten
        content = Path(result_path).read_text(encoding="utf-8")
        assert "Old content" not in content
        assert "New job description" in content

    def test_regenerate_ai_context_custom_full_resume_path(self, temp_workspace):
        """Test regenerate with custom full resume path."""
        # Create custom full resume
        custom_resume_path = Path(temp_workspace) / "custom_resume.md"
        custom_resume_path.write_text("# Custom Resume\nCustom content here.", encoding="utf-8")

        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        resume_dir = workspace_dir / "resume"
        resume_dir.mkdir(parents=True)

        tracker_data = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "Build systems.",
        }

        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=str(custom_resume_path),
        )

        # Verify custom resume content is included
        content = Path(ai_context_path).read_text(encoding="utf-8")
        assert "Custom Resume" in content
        assert "Custom content here" in content


class TestAtomicWrites:
    """Tests for atomic write behavior."""

    def test_atomic_write_no_partial_content(self, temp_full_resume, temp_workspace):
        """Test that atomic write never leaves partial content on failure."""
        output_path = Path(temp_workspace) / "ai_context.md"

        # This should succeed
        render_ai_context(
            company="Amazon",
            position="Software Engineer",
            job_description="Build systems.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        # Verify file exists and has complete content
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert content.startswith("# AI Context")
        assert content.endswith("\n")
        assert "## Full Resume Source (raw)" in content
        assert "## Job Description" in content
        assert "## Instructions" in content


class TestRequirementsCoverage:
    """Tests that verify specific requirements are met."""

    def test_requirement_4_5_regenerate_every_run(self, temp_full_resume, temp_workspace):
        """
        Requirement 4.5: Regenerate resume/ai_context.md on each successful item run.

        Verify that calling regenerate_ai_context multiple times updates the file.
        """
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-3629"
        resume_dir = workspace_dir / "resume"
        resume_dir.mkdir(parents=True)

        # First run
        tracker_data_1 = {
            "company": "Amazon",
            "position": "Software Engineer",
            "job_description": "First job description.",
        }

        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data_1,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        content_1 = Path(ai_context_path).read_text(encoding="utf-8")
        assert "First job description" in content_1

        # Second run with different data
        tracker_data_2 = {
            "company": "Meta",
            "position": "Research Scientist",
            "job_description": "Second job description.",
        }

        regenerate_ai_context(
            tracker_data=tracker_data_2,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify file was regenerated with new content
        content_2 = Path(ai_context_path).read_text(encoding="utf-8")
        assert "First job description" not in content_2
        assert "Second job description" in content_2
        assert "Meta" in content_2
        assert "Research Scientist" in content_2

    def test_requirement_4_6_atomic_writes(self, temp_full_resume, temp_workspace):
        """
        Requirement 4.6: Generated files SHALL be written atomically.

        Verify that files are written using atomic operations (temp file + rename).
        This is tested indirectly by verifying the file is never in a partial state.
        """
        output_path = Path(temp_workspace) / "ai_context.md"

        # Write initial content
        render_ai_context(
            company="Amazon",
            position="Software Engineer",
            job_description="Initial content.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        output_path.read_text(encoding="utf-8")

        # Overwrite with new content
        render_ai_context(
            company="Meta",
            position="Research Scientist",
            job_description="New content.",
            full_resume_path=temp_full_resume,
            output_path=str(output_path),
        )

        new_content = output_path.read_text(encoding="utf-8")

        # Verify file was completely replaced (not partially updated)
        assert "Initial content" not in new_content
        assert "New content" in new_content
        assert new_content.startswith("# AI Context")
        assert new_content.endswith("\n")
