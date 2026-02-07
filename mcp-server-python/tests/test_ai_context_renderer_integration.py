"""
Integration tests for ai_context_renderer with tracker_parser.

This module tests the integration between tracker parsing and ai_context
rendering to ensure the complete workflow works end-to-end.
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from utils.tracker_parser import parse_tracker_for_career_tailor
from utils.ai_context_renderer import regenerate_ai_context
from utils.file_ops import ensure_workspace_directories


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
    full_resume_content = """# Jane Smith
- Location: Toronto, ON, Canada
- Email: jane.smith@example.com
- Phone: +1 416-555-1234
- LinkedIn: https://www.linkedin.com/in/janesmith
- GitHub: https://github.com/janesmith

## Summary
Full-stack software engineer with 8+ years of experience building scalable web applications
and distributed systems. Expert in Python, TypeScript, and cloud infrastructure.

## Technical Skills
- Languages: Python, TypeScript, Go, SQL
- Backend: FastAPI, Django, Flask, Node.js
- Frontend: React, Vue.js, TypeScript
- Databases: PostgreSQL, MongoDB, Redis
- Cloud: AWS (EC2, S3, Lambda), GCP, Docker, Kubernetes
- Tools: Git, CI/CD, Terraform

## Work Experience
### Tech Innovations Inc. — Senior Software Engineer — Jan 2020 to Present — Toronto, ON
- Architected and deployed microservices platform serving 5M+ users with 99.9% uptime
- Led migration from monolith to microservices, reducing deployment time by 80%
- Implemented GraphQL API layer improving frontend performance by 40%
- Mentored team of 5 junior engineers on best practices and code review

### StartupCo — Software Engineer — Jun 2017 to Dec 2019 — Toronto, ON
- Built real-time analytics dashboard processing 100K+ events per second
- Optimized database queries reducing API response time from 2s to 200ms
- Implemented automated testing pipeline achieving 90% code coverage
- Collaborated with product team to define technical requirements

### WebDev Agency — Junior Developer — Jan 2016 to May 2017 — Toronto, ON
- Developed responsive web applications using React and Node.js
- Integrated third-party APIs for payment processing and authentication
- Participated in agile development process with 2-week sprints

## Education
- University of Toronto — B.Sc. Computer Science — Sep 2012 to Apr 2016 — Toronto, ON
  - GPA: 3.8/4.0
  - Dean's List: 2014, 2015, 2016
"""
    full_resume_path.write_text(full_resume_content, encoding="utf-8")
    return str(full_resume_path)


@pytest.fixture
def temp_tracker(temp_workspace):
    """Create a temporary tracker file for testing."""
    tracker_path = Path(temp_workspace) / "trackers" / "2026-02-07-amazon-4000.md"
    tracker_path.parent.mkdir(parents=True, exist_ok=True)

    tracker_content = """---
status: Shortlisted
company: Amazon
position: Senior Software Engineer
job_db_id: 4000
resume_path: "[[data/applications/amazon-4000/resume/resume.pdf]]"
date_applied: 2026-02-07
---

## Job Description

Amazon is seeking a Senior Software Engineer to join our AWS team. You will design and build
highly scalable distributed systems that power AWS services used by millions of customers.

**Responsibilities:**
- Design and implement distributed systems at massive scale
- Write clean, maintainable code in Python, Java, or Go
- Collaborate with cross-functional teams to deliver features
- Mentor junior engineers and conduct code reviews
- Participate in on-call rotation for production systems

**Requirements:**
- 5+ years of software development experience
- Strong proficiency in at least one programming language (Python, Java, Go)
- Experience with distributed systems and microservices architecture
- Knowledge of AWS services (EC2, S3, Lambda, DynamoDB)
- Excellent problem-solving and communication skills

**Preferred Qualifications:**
- Experience with containerization (Docker, Kubernetes)
- Knowledge of CI/CD pipelines and infrastructure as code
- Contributions to open-source projects
- M.Sc. or Ph.D. in Computer Science

## Notes

- Salary range: $150K - $200K CAD
- Remote-friendly with occasional office visits
- Strong benefits package
"""
    tracker_path.write_text(tracker_content, encoding="utf-8")
    return str(tracker_path)


class TestAiContextRendererIntegration:
    """Integration tests for ai_context_renderer with tracker_parser."""

    def test_end_to_end_tracker_to_ai_context(self, temp_tracker, temp_full_resume, temp_workspace):
        """
        Test complete workflow: parse tracker -> regenerate ai_context.

        This test verifies that:
        1. Tracker is parsed correctly
        2. Workspace directories are created
        3. ai_context.md is generated with correct content
        4. All required sections are present
        """
        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(temp_tracker)

        # Verify tracker data
        assert tracker_data["company"] == "Amazon"
        assert tracker_data["position"] == "Senior Software Engineer"
        assert tracker_data["job_db_id"] == 4000
        assert "distributed systems" in tracker_data["job_description"]

        # Create workspace
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-4000"
        ensure_workspace_directories(
            "amazon-4000", base_dir=str(Path(temp_workspace) / "applications")
        )

        # Regenerate ai_context
        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify ai_context.md was created
        assert Path(ai_context_path).exists()

        # Read and verify content
        content = Path(ai_context_path).read_text(encoding="utf-8")

        # Verify structure
        assert "# AI Context" in content
        assert "## Full Resume Source (raw)" in content
        assert "## Job Description" in content
        assert "## Notes" in content
        assert "## Instructions" in content

        # Verify full resume content is included
        assert "Jane Smith" in content
        assert "Tech Innovations Inc." in content
        assert "University of Toronto" in content

        # Verify job description is included
        assert "Amazon is seeking a Senior Software Engineer" in content
        assert "distributed systems" in content
        assert "5+ years of software development experience" in content

        # Verify metadata
        assert "Company: Amazon" in content
        assert "Position: Senior Software Engineer" in content
        assert "career_tailor MCP Tool" in content

    def test_regenerate_overwrites_existing_ai_context(
        self, temp_tracker, temp_full_resume, temp_workspace
    ):
        """
        Test that regenerating ai_context overwrites existing file.

        This verifies Requirement 4.5: Regenerate on each successful item run.
        """
        # Parse tracker
        tracker_data = parse_tracker_for_career_tailor(temp_tracker)

        # Create workspace
        workspace_dir = Path(temp_workspace) / "applications" / "amazon-4000"
        ensure_workspace_directories(
            "amazon-4000", base_dir=str(Path(temp_workspace) / "applications")
        )

        # Create existing ai_context.md with old content
        ai_context_path = workspace_dir / "resume" / "ai_context.md"
        ai_context_path.write_text("OLD CONTENT - SHOULD BE REPLACED", encoding="utf-8")

        # Regenerate ai_context
        result_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify file was overwritten
        content = Path(result_path).read_text(encoding="utf-8")
        assert "OLD CONTENT" not in content
        assert "Jane Smith" in content
        assert "Amazon" in content

    def test_multiple_trackers_different_workspaces(self, temp_full_resume, temp_workspace):
        """
        Test generating ai_context for multiple trackers in different workspaces.

        This simulates batch processing of multiple job applications.
        """
        # Create two tracker files
        tracker1_path = Path(temp_workspace) / "trackers" / "amazon.md"
        tracker1_path.parent.mkdir(parents=True, exist_ok=True)
        tracker1_content = """---
status: Shortlisted
company: Amazon
position: Senior Software Engineer
job_db_id: 4000
---

## Job Description
Build distributed systems at Amazon scale.
"""
        tracker1_path.write_text(tracker1_content, encoding="utf-8")

        tracker2_path = Path(temp_workspace) / "trackers" / "meta.md"
        tracker2_content = """---
status: Shortlisted
company: Meta
position: Research Scientist
job_db_id: 4001
---

## Job Description
Develop AI systems for social media applications.
"""
        tracker2_path.write_text(tracker2_content, encoding="utf-8")

        # Process first tracker
        tracker1_data = parse_tracker_for_career_tailor(str(tracker1_path))
        workspace1_dir = Path(temp_workspace) / "applications" / "amazon-4000"
        ensure_workspace_directories(
            "amazon-4000", base_dir=str(Path(temp_workspace) / "applications")
        )

        ai_context1_path = regenerate_ai_context(
            tracker_data=tracker1_data,
            workspace_dir=str(workspace1_dir),
            full_resume_path=temp_full_resume,
        )

        # Process second tracker
        tracker2_data = parse_tracker_for_career_tailor(str(tracker2_path))
        workspace2_dir = Path(temp_workspace) / "applications" / "meta-4001"
        ensure_workspace_directories(
            "meta-4001", base_dir=str(Path(temp_workspace) / "applications")
        )

        ai_context2_path = regenerate_ai_context(
            tracker_data=tracker2_data,
            workspace_dir=str(workspace2_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify both files exist
        assert Path(ai_context1_path).exists()
        assert Path(ai_context2_path).exists()

        # Verify content is different
        content1 = Path(ai_context1_path).read_text(encoding="utf-8")
        content2 = Path(ai_context2_path).read_text(encoding="utf-8")

        assert "Amazon" in content1
        assert "distributed systems" in content1
        assert "Meta" not in content1

        assert "Meta" in content2
        assert "AI systems" in content2
        assert "Amazon" not in content2

    def test_ai_context_with_complex_job_description(self, temp_full_resume, temp_workspace):
        """
        Test ai_context generation with complex job description containing special formatting.
        """
        # Create tracker with complex job description
        tracker_path = Path(temp_workspace) / "trackers" / "complex.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)

        tracker_content = """---
status: Shortlisted
company: Tech Corp
position: Staff Engineer
job_db_id: 5000
---

## Job Description

**About the Role:**

We're looking for a Staff Engineer to lead our platform team.

**Key Responsibilities:**
- Design & implement scalable systems
- Mentor 5-10 engineers
- Drive technical roadmap

**Requirements:**
1. 8+ years experience
2. Strong Python/Go skills
3. Distributed systems expertise

**Nice to Have:**
- Open source contributions
- Conference speaking
- Technical blog

**Compensation:**
- Base: $180K-$220K
- Equity: 0.1%-0.3%
- Benefits: Full package

## Notes
Great opportunity!
"""
        tracker_path.write_text(tracker_content, encoding="utf-8")

        # Parse and generate ai_context
        tracker_data = parse_tracker_for_career_tailor(str(tracker_path))
        workspace_dir = Path(temp_workspace) / "applications" / "techcorp-5000"
        ensure_workspace_directories(
            "techcorp-5000", base_dir=str(Path(temp_workspace) / "applications")
        )

        ai_context_path = regenerate_ai_context(
            tracker_data=tracker_data,
            workspace_dir=str(workspace_dir),
            full_resume_path=temp_full_resume,
        )

        # Verify complex formatting is preserved
        content = Path(ai_context_path).read_text(encoding="utf-8")
        assert "**About the Role:**" in content
        assert "**Key Responsibilities:**" in content
        assert "1. 8+ years experience" in content
        assert "Base: $180K-$220K" in content
        assert "Tech Corp" in content
        assert "Staff Engineer" in content


class TestErrorHandling:
    """Test error handling in integration scenarios."""

    def test_missing_job_description_section(self, temp_full_resume, temp_workspace):
        """Test error when tracker is missing ## Job Description section."""
        # Create tracker without job description
        tracker_path = Path(temp_workspace) / "trackers" / "no-jd.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)

        tracker_content = """---
status: Shortlisted
company: Amazon
position: Software Engineer
---

## Notes
Some notes here but no job description.
"""
        tracker_path.write_text(tracker_content, encoding="utf-8")

        # Should raise TrackerParseError
        from utils.tracker_parser import TrackerParseError

        with pytest.raises(TrackerParseError, match="Job Description"):
            parse_tracker_for_career_tailor(str(tracker_path))

    def test_missing_required_frontmatter_fields(self, temp_full_resume, temp_workspace):
        """Test error when tracker is missing required frontmatter fields."""
        # Create tracker without company field
        tracker_path = Path(temp_workspace) / "trackers" / "no-company.md"
        tracker_path.parent.mkdir(parents=True, exist_ok=True)

        tracker_content = """---
status: Shortlisted
position: Software Engineer
---

## Job Description
Build systems.
"""
        tracker_path.write_text(tracker_content, encoding="utf-8")

        # Should raise TrackerParseError
        from utils.tracker_parser import TrackerParseError

        with pytest.raises(TrackerParseError, match="company"):
            parse_tracker_for_career_tailor(str(tracker_path))
