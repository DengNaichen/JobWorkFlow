"""
Integration tests for artifact path resolution with real tracker files.

Tests that artifact path resolution works correctly with actual tracker
frontmatter parsing.
"""

import pytest
from pathlib import Path
from utils.tracker_parser import parse_tracker_file, get_frontmatter_field
from utils.artifact_paths import parse_resume_path, resolve_artifact_paths, ArtifactPathError


class TestArtifactPathsWithTrackerParser:
    """Integration tests combining tracker parsing and artifact path resolution."""

    def test_resolve_paths_from_real_tracker(self, tmp_path):
        """Test resolving artifact paths from a real tracker file."""
        # Create a tracker file with resume_path in frontmatter
        tracker_content = """---
job_db_id: 352
company: Amazon
position: Software Engineer
status: Reviewed
resume_path: '[[data/applications/amazon-352/resume/resume.pdf]]'
---

## Job Description
Test content
"""
        tracker_path = tmp_path / "test-tracker.md"
        tracker_path.write_text(tracker_content)

        # Parse tracker and extract resume_path
        parsed = parse_tracker_file(str(tracker_path))
        resume_path_raw = parsed["frontmatter"]["resume_path"]

        # Resolve artifact paths
        pdf_path, tex_path = resolve_artifact_paths(resume_path_raw)

        assert pdf_path == "data/applications/amazon-352/resume/resume.pdf"
        assert tex_path == "data/applications/amazon-352/resume/resume.tex"

    def test_resolve_paths_using_get_frontmatter_field(self, tmp_path):
        """Test resolving paths using the get_frontmatter_field helper."""
        tracker_content = """---
job_db_id: 100
company: Meta
position: ML Engineer
status: Reviewed
resume_path: 'data/applications/meta-100/resume/resume.pdf'
---

## Notes
Plain path format test
"""
        tracker_path = tmp_path / "meta-tracker.md"
        tracker_path.write_text(tracker_content)

        # Get resume_path using helper
        resume_path_raw = get_frontmatter_field(str(tracker_path), "resume_path")

        # Resolve artifact paths
        pdf_path, tex_path = resolve_artifact_paths(resume_path_raw)

        assert pdf_path == "data/applications/meta-100/resume/resume.pdf"
        assert tex_path == "data/applications/meta-100/resume/resume.tex"

    def test_missing_resume_path_in_tracker(self, tmp_path):
        """Test handling tracker without resume_path field."""
        tracker_content = """---
job_db_id: 200
company: Google
position: SWE
status: Reviewed
---

## Job Description
No resume_path field
"""
        tracker_path = tmp_path / "no-resume-path.md"
        tracker_path.write_text(tracker_content)

        # Get resume_path (will be None)
        resume_path_raw = get_frontmatter_field(str(tracker_path), "resume_path")

        # Should raise error when trying to resolve
        with pytest.raises(ArtifactPathError, match="resume_path is required"):
            resolve_artifact_paths(resume_path_raw)

    def test_wiki_link_format_from_tracker(self, tmp_path):
        """Test wiki-link format parsing from tracker."""
        tracker_content = """---
job_db_id: 500
company: Google
position: Staff Engineer
status: Reviewed
resume_path: '[[data/applications/google-500/resume/resume.pdf]]'
---

## Description
Wiki-link format
"""
        tracker_path = tmp_path / "google-tracker.md"
        tracker_path.write_text(tracker_content)

        resume_path_raw = get_frontmatter_field(str(tracker_path), "resume_path")

        # Parse should strip wiki-link brackets
        pdf_path = parse_resume_path(resume_path_raw)
        assert pdf_path == "data/applications/google-500/resume/resume.pdf"
        assert "[[" not in pdf_path
        assert "]]" not in pdf_path

    def test_plain_path_format_from_tracker(self, tmp_path):
        """Test plain path format parsing from tracker."""
        tracker_content = """---
job_db_id: 711
company: General Motors
position: Senior Engineer
status: Reviewed
resume_path: 'data/applications/general_motors-711/resume/resume.pdf'
---

## Description
Plain path format
"""
        tracker_path = tmp_path / "gm-tracker.md"
        tracker_path.write_text(tracker_content)

        resume_path_raw = get_frontmatter_field(str(tracker_path), "resume_path")

        # Parse should return path as-is
        pdf_path = parse_resume_path(resume_path_raw)
        assert pdf_path == "data/applications/general_motors-711/resume/resume.pdf"

    def test_both_formats_resolve_to_same_structure(self, tmp_path):
        """Test that both formats resolve to the same directory structure."""
        # Create two trackers with different path formats
        wiki_tracker = """---
job_db_id: 1
company: CompanyA
status: Reviewed
resume_path: '[[data/applications/company-a-1/resume/resume.pdf]]'
---
Content
"""
        plain_tracker = """---
job_db_id: 2
company: CompanyB
status: Reviewed
resume_path: 'data/applications/company-b-2/resume/resume.pdf'
---
Content
"""

        wiki_path = tmp_path / "wiki.md"
        plain_path = tmp_path / "plain.md"
        wiki_path.write_text(wiki_tracker)
        plain_path.write_text(plain_tracker)

        # Get paths from both trackers
        wiki_resume = get_frontmatter_field(str(wiki_path), "resume_path")
        plain_resume = get_frontmatter_field(str(plain_path), "resume_path")

        # Resolve both
        wiki_pdf, wiki_tex = resolve_artifact_paths(wiki_resume)
        plain_pdf, plain_tex = resolve_artifact_paths(plain_resume)

        # Both should follow the same structure pattern
        assert wiki_pdf.startswith("data/applications/")
        assert plain_pdf.startswith("data/applications/")
        assert wiki_pdf.endswith("/resume/resume.pdf")
        assert plain_pdf.endswith("/resume/resume.pdf")
        assert wiki_tex.endswith("/resume/resume.tex")
        assert plain_tex.endswith("/resume/resume.tex")


class TestRealTrackerFiles:
    """Tests using actual tracker files from the trackers directory."""

    def test_commerceiq_tracker(self):
        """Test artifact path resolution with the CommerceIQ tracker."""
        tracker_path = "trackers/2026-02-05-commerceiq-352.md"

        # Skip if tracker doesn't exist (e.g., in CI)
        if not Path(tracker_path).exists():
            pytest.skip("Tracker file not found")

        # Get resume_path from tracker
        resume_path_raw = get_frontmatter_field(tracker_path, "resume_path")

        # Should be able to resolve paths
        pdf_path, tex_path = resolve_artifact_paths(resume_path_raw)

        assert pdf_path == "data/applications/commerceiq-352/resume/resume.pdf"
        assert tex_path == "data/applications/commerceiq-352/resume/resume.tex"

    def test_all_trackers_have_valid_resume_paths(self):
        """Test that all existing trackers have parsable resume_path fields."""
        trackers_dir = Path("trackers")

        # Skip if trackers directory doesn't exist
        if not trackers_dir.exists():
            pytest.skip("Trackers directory not found")

        # Only include generated tracker notes (exclude templates like "Job Application.md")
        tracker_files = list(trackers_dir.glob("*.md"))
        tracker_files = [path for path in tracker_files if path.name[:4].isdigit()]

        if not tracker_files:
            pytest.skip("No tracker files found")

        for tracker_file in tracker_files:
            # Get resume_path
            resume_path_raw = get_frontmatter_field(str(tracker_file), "resume_path")

            # If resume_path exists, it should be parsable
            if resume_path_raw is not None:
                # Should not raise an error
                pdf_path, tex_path = resolve_artifact_paths(resume_path_raw)

                # Verify paths are non-empty and have correct structure
                assert pdf_path
                assert tex_path
                assert pdf_path.endswith("resume.pdf")
                assert tex_path.endswith("resume.tex")
