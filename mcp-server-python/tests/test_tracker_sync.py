"""
Unit tests for tracker_sync module.

Tests verify:
- Status field updates while preserving other frontmatter
- Body content preservation
- Atomic write behavior
- Error handling
"""

import pytest
import os

from utils.tracker_sync import update_tracker_status


def test_update_status_preserves_frontmatter_and_body(tmp_path):
    """
    Test that updating status preserves all other frontmatter fields and body content.
    
    Requirements:
        - 7.1: Update only the status field in frontmatter
        - 7.3: Preserve original body content exactly
        - 7.4: Preserve original frontmatter keys/values except status
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
job_db_id: 3629
job_id: '4368663835'
company: Amazon
position: Software Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://example.com/job/123
resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/amazon-3629/cover/cover-letter.pdf]]'
next_action:
- Wait for feedback
salary: 0
website: ''
---

## Job Description

Build scalable distributed systems.

## Notes

Initial review completed.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Update status
    update_tracker_status(str(tracker_path), "Resume Written")
    
    # Read updated content
    updated_content = tracker_path.read_text(encoding='utf-8')
    
    # Verify status was updated
    assert "status: Resume Written" in updated_content
    assert "status: Reviewed" not in updated_content
    
    # Verify other frontmatter fields preserved
    assert "job_db_id: 3629" in updated_content
    assert "company: Amazon" in updated_content
    assert "position: Software Engineer" in updated_content
    assert "application_date: '2026-02-05'" in updated_content
    assert "resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'" in updated_content
    
    # Verify body content preserved exactly
    assert "## Job Description" in updated_content
    assert "Build scalable distributed systems." in updated_content
    assert "## Notes" in updated_content
    assert "Initial review completed." in updated_content


def test_update_status_to_same_value(tmp_path):
    """
    Test that updating status to the same value works correctly.
    
    Requirements:
        - 7.1: Update only the status field in frontmatter
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
status: Reviewed
company: Amazon
---

## Job Description

Test content.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Update status to same value
    update_tracker_status(str(tracker_path), "Reviewed")
    
    # Read updated content
    updated_content = tracker_path.read_text(encoding='utf-8')
    
    # Verify status is still correct
    assert "status: Reviewed" in updated_content
    assert "company: Amazon" in updated_content


def test_update_status_missing_file():
    """
    Test that updating a non-existent file raises FileNotFoundError.
    
    Requirements:
        - 7.5: When write fails, original tracker file remains intact
    """
    with pytest.raises(FileNotFoundError):
        update_tracker_status("nonexistent/tracker.md", "Applied")


def test_atomic_write_preserves_original_on_failure(tmp_path):
    """
    Test that if write fails, the original file remains intact.
    
    This test verifies atomic write behavior by checking that a failure
    during the write process doesn't corrupt the original file.
    
    Requirements:
        - 7.2: Tracker write is atomic (temporary file + rename)
        - 7.5: When write fails, original tracker file remains intact
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
status: Reviewed
company: Amazon
---

## Job Description

Original content.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Make directory read-only to simulate write failure
    # Note: This test is platform-dependent and may not work on all systems
    # On Unix-like systems, we can make the directory read-only
    if os.name != 'nt':  # Skip on Windows
        original_mode = tracker_path.parent.stat().st_mode
        try:
            os.chmod(tracker_path.parent, 0o444)
            
            # Attempt to update status (should fail)
            with pytest.raises((IOError, OSError, PermissionError)):
                update_tracker_status(str(tracker_path), "Applied")
            
            # Restore permissions
            os.chmod(tracker_path.parent, original_mode)
            
            # Verify original content is intact
            current_content = tracker_path.read_text(encoding='utf-8')
            assert current_content == original_content
            assert "status: Reviewed" in current_content
            assert "status: Applied" not in current_content
        finally:
            # Ensure permissions are restored
            try:
                os.chmod(tracker_path.parent, original_mode)
            except Exception:
                pass


def test_atomic_write_does_not_follow_preexisting_symlink_temp_file(tmp_path):
    """
    Test that pre-existing predictable temp-file symlink is not followed.

    This guards against clobbering arbitrary files via a crafted temp symlink.
    """
    # Symlink behavior is platform-dependent (privilege-gated on some systems)
    if not hasattr(os, "symlink"):
        pytest.skip("os.symlink not supported on this platform")

    tracker_path = tmp_path / "test-tracker.md"
    victim_path = tmp_path / "victim.txt"

    tracker_path.write_text(
        """---
status: Reviewed
company: Amazon
---
Body
""",
        encoding="utf-8",
    )
    victim_path.write_text("SECRET", encoding="utf-8")

    # Legacy predictable name that an attacker might pre-create as symlink.
    predictable_temp = tmp_path / f".{tracker_path.name}.tmp"
    try:
        os.symlink(victim_path, predictable_temp)
    except OSError:
        pytest.skip("Cannot create symlink in this environment")

    update_tracker_status(str(tracker_path), "Applied")

    # Victim file must remain unchanged.
    assert victim_path.read_text(encoding="utf-8") == "SECRET"
    # Tracker should be updated as a regular file.
    assert tracker_path.is_symlink() is False
    assert "status: Applied" in tracker_path.read_text(encoding="utf-8")


def test_update_status_with_complex_frontmatter(tmp_path):
    """
    Test that updating status works with complex frontmatter structures.
    
    Requirements:
        - 7.4: Preserve original frontmatter keys/values except status
    """
    # Create test tracker file with complex frontmatter
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
status: Reviewed
company: Amazon
next_action:
- Wait for feedback
- Follow up in 2 weeks
tags:
- backend
- distributed-systems
metadata:
  source: linkedin
  priority: high
---

## Job Description

Complex tracker content.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Update status
    update_tracker_status(str(tracker_path), "Applied")
    
    # Read updated content
    updated_content = tracker_path.read_text(encoding='utf-8')
    
    # Verify status was updated
    assert "status: Applied" in updated_content
    
    # Verify complex structures preserved
    assert "next_action:" in updated_content
    assert "- Wait for feedback" in updated_content
    assert "- Follow up in 2 weeks" in updated_content
    assert "tags:" in updated_content
    assert "- backend" in updated_content
    assert "- distributed-systems" in updated_content
    assert "metadata:" in updated_content
    assert "source: linkedin" in updated_content
    assert "priority: high" in updated_content


def test_update_status_preserves_body_whitespace(tmp_path):
    """
    Test that body content whitespace is preserved exactly.
    
    Requirements:
        - 7.3: Preserve original body content exactly
    """
    # Create test tracker file with specific whitespace
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
status: Reviewed
company: Amazon
---

## Job Description

Line 1

Line 2 with trailing spaces   

Line 3

## Notes

- Item 1
- Item 2
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Update status
    update_tracker_status(str(tracker_path), "Applied")
    
    # Read updated content
    updated_content = tracker_path.read_text(encoding='utf-8')
    
    # Verify body content preserved (including whitespace)
    assert "Line 1\n\nLine 2" in updated_content
    assert "Line 3\n\n## Notes" in updated_content
    assert "- Item 1\n- Item 2" in updated_content
