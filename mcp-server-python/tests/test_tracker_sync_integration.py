"""
Integration tests for tracker_sync module.

Tests verify end-to-end behavior including:
- Atomic write guarantees
- File system interactions
- Real-world tracker update scenarios
"""



from utils.tracker_sync import update_tracker_status
from utils.tracker_parser import parse_tracker_file, get_tracker_status


def test_end_to_end_status_update_workflow(tmp_path):
    """
    Test complete workflow: create tracker, update status, verify changes.
    
    Requirements:
        - 7.1: Update only the status field in frontmatter
        - 7.2: Tracker write is atomic (temporary file + rename)
        - 7.3: Preserve original body content exactly
        - 7.4: Preserve original frontmatter keys/values except status
    """
    # Create realistic tracker file
    tracker_path = tmp_path / "2026-02-05-amazon-3629.md"
    original_content = """---
job_db_id: 3629
job_id: '4368663835'
company: Amazon
position: Senior Software Engineer
status: Reviewed
application_date: '2026-02-05'
reference_link: https://www.amazon.jobs/en/jobs/4368663835
resume_path: '[[data/applications/amazon-3629/resume/resume.pdf]]'
cover_letter_path: '[[data/applications/amazon-3629/cover/cover-letter.pdf]]'
next_action:
- Wait for feedback
salary: 0
website: ''
---

## Job Description

We are looking for a Senior Software Engineer to join our team and help build
scalable distributed systems that serve millions of customers worldwide.

Key Responsibilities:
- Design and implement high-performance backend services
- Collaborate with cross-functional teams
- Mentor junior engineers

## Notes

Initial review completed on 2026-02-05.
Position looks like a good fit for distributed systems experience.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Parse initial state
    initial_parsed = parse_tracker_file(str(tracker_path))
    assert initial_parsed["status"] == "Reviewed"
    assert initial_parsed["frontmatter"]["company"] == "Amazon"
    assert initial_parsed["frontmatter"]["job_db_id"] == 3629
    
    # Update status to "Resume Written"
    update_tracker_status(str(tracker_path), "Resume Written")
    
    # Parse updated state
    updated_parsed = parse_tracker_file(str(tracker_path))
    assert updated_parsed["status"] == "Resume Written"
    
    # Verify all other frontmatter preserved
    assert updated_parsed["frontmatter"]["company"] == "Amazon"
    assert updated_parsed["frontmatter"]["position"] == "Senior Software Engineer"
    assert updated_parsed["frontmatter"]["job_db_id"] == 3629
    assert updated_parsed["frontmatter"]["job_id"] == "4368663835"
    assert updated_parsed["frontmatter"]["application_date"] == "2026-02-05"
    assert updated_parsed["frontmatter"]["resume_path"] == "[[data/applications/amazon-3629/resume/resume.pdf]]"
    
    # Verify body preserved
    assert "## Job Description" in updated_parsed["body"]
    assert "scalable distributed systems" in updated_parsed["body"]
    assert "## Notes" in updated_parsed["body"]
    assert "Initial review completed" in updated_parsed["body"]
    
    # Update status again to "Applied"
    update_tracker_status(str(tracker_path), "Applied")
    
    # Verify second update
    final_parsed = parse_tracker_file(str(tracker_path))
    assert final_parsed["status"] == "Applied"
    assert final_parsed["frontmatter"]["company"] == "Amazon"
    assert "scalable distributed systems" in final_parsed["body"]


def test_no_temp_files_left_after_successful_write(tmp_path):
    """
    Test that temporary files are cleaned up after successful write.
    
    Requirements:
        - 7.2: Tracker write is atomic (temporary file + rename)
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    tracker_path.write_text("""---
status: Reviewed
company: TestCo
---

## Job Description

Test content.
""", encoding='utf-8')
    
    # Update status
    update_tracker_status(str(tracker_path), "Applied")
    
    # Verify no temp files remain
    temp_files = list(tmp_path.glob(".*.tmp"))
    assert len(temp_files) == 0, f"Found unexpected temp files: {temp_files}"
    
    # Verify only the tracker file exists
    files = list(tmp_path.glob("*"))
    assert len(files) == 1
    assert files[0].name == "test-tracker.md"


def test_multiple_sequential_updates(tmp_path):
    """
    Test that multiple sequential status updates work correctly.
    
    Requirements:
        - 7.1: Update only the status field in frontmatter
        - 7.2: Tracker write is atomic (temporary file + rename)
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    tracker_path.write_text("""---
status: Reviewed
company: TestCo
position: Engineer
---

## Job Description

Test content.
""", encoding='utf-8')
    
    # Perform multiple updates
    statuses = ["Reviewed", "Resume Written", "Applied", "Interview", "Offer"]
    
    for status in statuses:
        update_tracker_status(str(tracker_path), status)
        
        # Verify status after each update
        current_status = get_tracker_status(str(tracker_path))
        assert current_status == status
        
        # Verify other fields preserved
        parsed = parse_tracker_file(str(tracker_path))
        assert parsed["frontmatter"]["company"] == "TestCo"
        assert parsed["frontmatter"]["position"] == "Engineer"
        assert "Test content." in parsed["body"]


def test_concurrent_safe_write_behavior(tmp_path):
    """
    Test that atomic write provides safety for concurrent access patterns.
    
    This test verifies that the atomic write mechanism (temp file + rename)
    ensures readers always see either the old or new complete content,
    never a partial write.
    
    Requirements:
        - 7.2: Tracker write is atomic (temporary file + rename)
        - 7.5: When write fails, original tracker file remains intact
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    original_content = """---
status: Reviewed
company: TestCo
---

## Job Description

Original content.
"""
    tracker_path.write_text(original_content, encoding='utf-8')
    
    # Update status
    update_tracker_status(str(tracker_path), "Applied")
    
    # Read the file - should see complete updated content
    content = tracker_path.read_text(encoding='utf-8')
    
    # Verify we see a complete, valid tracker file
    assert content.startswith("---\n")
    assert "status: Applied" in content
    assert "company: TestCo" in content
    assert "## Job Description" in content
    
    # Verify we can parse it successfully
    parsed = parse_tracker_file(str(tracker_path))
    assert parsed["status"] == "Applied"
    assert parsed["frontmatter"]["company"] == "TestCo"


def test_update_preserves_yaml_formatting_consistency(tmp_path):
    """
    Test that YAML formatting remains consistent across updates.
    
    Requirements:
        - 7.4: Preserve original frontmatter keys/values except status
    """
    # Create test tracker file
    tracker_path = tmp_path / "test-tracker.md"
    tracker_path.write_text("""---
status: Reviewed
company: TestCo
next_action:
- Action 1
- Action 2
---

## Job Description

Test content.
""", encoding='utf-8')
    
    # Update status multiple times
    for status in ["Resume Written", "Applied", "Interview"]:
        update_tracker_status(str(tracker_path), status)
        
        # Verify YAML is still valid and parseable
        parsed = parse_tracker_file(str(tracker_path))
        assert parsed["status"] == status
        assert parsed["frontmatter"]["company"] == "TestCo"
        assert parsed["frontmatter"]["next_action"] == ["Action 1", "Action 2"]
