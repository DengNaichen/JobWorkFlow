"""
Integration tests for atomic file operations with tracker rendering.

Tests verify that atomic_write works correctly with tracker_renderer
to create complete tracker files.
"""

from utils.file_ops import atomic_write, ensure_directory, ensure_workspace_directories
from utils.tracker_renderer import render_tracker_markdown


class TestAtomicWriteIntegration:
    """Integration tests for atomic_write with tracker rendering."""

    def test_atomic_write_with_tracker_content(self, tmp_path):
        """Test atomic_write with real tracker markdown content."""
        # Setup test data
        job = {
            "id": 3629,
            "job_id": "4368663835",
            "title": "Software Engineer",
            "company": "Amazon",
            "description": "Build scalable systems...",
            "url": "https://example.com/job/123",
            "captured_at": "2026-02-04T15:30:00",
        }

        plan = {
            "resume_path": "[[data/applications/amazon-3629/resume/resume.pdf]]",
            "cover_letter_path": "[[data/applications/amazon-3629/cover/cover-letter.pdf]]",
            "application_slug": "amazon-3629",
        }

        # Render tracker content
        content = render_tracker_markdown(job, plan)

        # Write atomically
        tracker_path = tmp_path / "trackers" / "2026-02-04-amazon-3629.md"
        atomic_write(tracker_path, content)

        # Verify file exists and content is correct
        assert tracker_path.exists()
        written_content = tracker_path.read_text()
        assert written_content == content
        assert "## Job Description" in written_content
        assert "status: Reviewed" in written_content
        assert "job_db_id: 3629" in written_content

    def test_workspace_directory_creation(self, tmp_path):
        """Test ensure_directory for workspace structure."""
        application_slug = "amazon-3629"

        # Create workspace directories
        resume_dir = tmp_path / "data" / "applications" / application_slug / "resume"
        cover_dir = tmp_path / "data" / "applications" / application_slug / "cover"

        ensure_directory(resume_dir)
        ensure_directory(cover_dir)

        # Verify directories exist
        assert resume_dir.exists()
        assert resume_dir.is_dir()
        assert cover_dir.exists()
        assert cover_dir.is_dir()

    def test_complete_tracker_initialization_workflow(self, tmp_path):
        """Test complete workflow: create workspace dirs + write tracker."""
        # Setup
        job = {
            "id": 3711,
            "job_id": "4368670000",
            "title": "Senior Engineer",
            "company": "General Motors",
            "description": None,  # Test fallback
            "url": "https://example.com/job/456",
            "captured_at": "2026-02-05 10:00:00",
        }

        application_slug = "general_motors-3711"
        plan = {
            "resume_path": f"[[data/applications/{application_slug}/resume/resume.pdf]]",
            "cover_letter_path": f"[[data/applications/{application_slug}/cover/cover-letter.pdf]]",
            "application_slug": application_slug,
        }

        # Create workspace directories using the new helper
        base_dir = tmp_path / "data" / "applications"
        ensure_workspace_directories(application_slug, str(base_dir))

        # Render and write tracker
        content = render_tracker_markdown(job, plan)
        tracker_path = tmp_path / "trackers" / "2026-02-05-general_motors-3711.md"
        atomic_write(tracker_path, content)

        # Verify complete setup
        workspace_root = base_dir / application_slug
        assert (workspace_root / "resume").is_dir()
        assert (workspace_root / "cover").is_dir()
        assert (workspace_root / "cv").is_dir()
        assert tracker_path.exists()

        written_content = tracker_path.read_text()
        assert "No description available." in written_content
        assert "job_db_id: 3711" in written_content
        assert "company: General Motors" in written_content

    def test_idempotent_action_resolution_workflow(self, tmp_path):
        """Test complete idempotent action resolution workflow."""
        from utils.file_ops import resolve_write_action

        # Setup test data
        job = {
            "id": 4000,
            "job_id": "4368680000",
            "title": "Backend Engineer",
            "company": "Google",
            "description": "Build distributed systems...",
            "url": "https://example.com/job/789",
            "captured_at": "2026-02-06T12:00:00",
        }

        application_slug = "google-4000"
        plan = {
            "resume_path": f"[[data/applications/{application_slug}/resume/resume.pdf]]",
            "cover_letter_path": f"[[data/applications/{application_slug}/cover/cover-letter.pdf]]",
            "application_slug": application_slug,
        }

        tracker_path = tmp_path / "trackers" / "2026-02-06-google-4000.md"

        # First run: file doesn't exist, force=False -> should create
        action1 = resolve_write_action(file_exists=tracker_path.exists(), force=False)
        assert action1 == "created"

        # Create the tracker file
        content = render_tracker_markdown(job, plan)
        atomic_write(tracker_path, content)
        assert tracker_path.exists()

        # Second run: file exists, force=False -> should skip
        action2 = resolve_write_action(file_exists=tracker_path.exists(), force=False)
        assert action2 == "skipped_exists"

        # Third run: file exists, force=True -> should overwrite
        action3 = resolve_write_action(file_exists=tracker_path.exists(), force=True)
        assert action3 == "overwritten"

        # Verify we can actually overwrite
        modified_content = content.replace("Backend Engineer", "Senior Backend Engineer")
        atomic_write(tracker_path, modified_content)
        assert tracker_path.read_text() == modified_content

    def test_batch_processing_with_mixed_actions(self, tmp_path):
        """Test batch processing with mixed create/skip/overwrite actions."""
        from utils.file_ops import resolve_write_action

        # Setup multiple jobs
        jobs = [
            {"id": 5001, "company": "Amazon", "captured_at": "2026-02-07T10:00:00"},
            {"id": 5002, "company": "Meta", "captured_at": "2026-02-07T11:00:00"},
            {"id": 5003, "company": "Apple", "captured_at": "2026-02-07T12:00:00"},
        ]

        trackers_dir = tmp_path / "trackers"
        trackers_dir.mkdir()

        # Pre-create one tracker file (Meta)
        meta_tracker = trackers_dir / "2026-02-07-meta-5002.md"
        meta_tracker.write_text("Existing tracker")

        # Process batch with force=False
        actions_no_force = []
        for job in jobs:
            tracker_path = trackers_dir / f"2026-02-07-{job['company'].lower()}-{job['id']}.md"
            action = resolve_write_action(file_exists=tracker_path.exists(), force=False)
            actions_no_force.append(action)

        # Verify actions
        assert actions_no_force[0] == "created"  # Amazon - new
        assert actions_no_force[1] == "skipped_exists"  # Meta - exists
        assert actions_no_force[2] == "created"  # Apple - new

        # Process batch with force=True
        actions_with_force = []
        for job in jobs:
            tracker_path = trackers_dir / f"2026-02-07-{job['company'].lower()}-{job['id']}.md"
            action = resolve_write_action(file_exists=tracker_path.exists(), force=True)
            actions_with_force.append(action)

        # Verify actions with force
        assert actions_with_force[0] == "created"  # Amazon - still new
        assert actions_with_force[1] == "overwritten"  # Meta - now overwrite
        assert actions_with_force[2] == "created"  # Apple - still new
