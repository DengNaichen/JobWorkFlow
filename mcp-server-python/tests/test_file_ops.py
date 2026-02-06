"""
Unit tests for atomic file operations.

Tests verify atomic write semantics, cleanup on failure, and directory creation.
"""

import pytest
from unittest.mock import patch
from utils.file_ops import (
    atomic_write,
    ensure_directory,
    ensure_workspace_directories,
    resolve_write_action
)


class TestAtomicWrite:
    """Test atomic_write function."""

    def test_atomic_write_creates_file(self, tmp_path):
        """Test that atomic_write creates a new file with correct content."""
        target = tmp_path / "test.md"
        content = "# Test Content\n\nThis is a test."

        atomic_write(target, content)

        assert target.exists()
        assert target.read_text() == content

    def test_atomic_write_overwrites_existing_file(self, tmp_path):
        """Test that atomic_write overwrites existing file atomically."""
        target = tmp_path / "existing.md"
        target.write_text("Old content")

        new_content = "New content"
        atomic_write(target, new_content)

        assert target.read_text() == new_content

    def test_atomic_write_creates_parent_directories(self, tmp_path):
        """Test that atomic_write creates parent directories if missing."""
        target = tmp_path / "nested" / "dirs" / "file.md"
        content = "Test content"

        atomic_write(target, content)

        assert target.exists()
        assert target.read_text() == content

    def test_atomic_write_handles_unicode(self, tmp_path):
        """Test that atomic_write handles unicode content correctly."""
        target = tmp_path / "unicode.md"
        content = "Unicode: 你好世界 🚀 café"

        atomic_write(target, content)

        assert target.read_text() == content

    def test_atomic_write_no_partial_file_on_failure(self, tmp_path):
        """Test that atomic_write leaves no partial file on write failure."""
        target = tmp_path / "test.md"

        # Mock os.write to fail
        with patch('os.write', side_effect=OSError("Write failed")):
            with pytest.raises(OSError, match="Write failed"):
                atomic_write(target, "content")

        # Target file should not exist
        assert not target.exists()

        # No temporary files should remain
        temp_files = list(tmp_path.glob(".test.md.*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_cleans_up_temp_on_fsync_failure(self, tmp_path):
        """Test that atomic_write cleans up temp file on fsync failure."""
        target = tmp_path / "test.md"

        # Mock os.fsync to fail
        with patch('os.fsync', side_effect=OSError("Fsync failed")):
            with pytest.raises(OSError, match="Fsync failed"):
                atomic_write(target, "content")

        # Target file should not exist
        assert not target.exists()

        # No temporary files should remain
        temp_files = list(tmp_path.glob(".test.md.*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_cleans_up_temp_on_rename_failure(self, tmp_path):
        """Test that atomic_write cleans up temp file on rename failure."""
        target = tmp_path / "test.md"

        # Mock os.replace to fail
        with patch('os.replace', side_effect=OSError("Rename failed")):
            with pytest.raises(OSError, match="Rename failed"):
                atomic_write(target, "content")

        # Target file should not exist
        assert not target.exists()

        # No temporary files should remain
        temp_files = list(tmp_path.glob(".test.md.*.tmp"))
        assert len(temp_files) == 0

    def test_atomic_write_with_path_object(self, tmp_path):
        """Test that atomic_write accepts Path objects."""
        target = tmp_path / "test.md"
        content = "Path object test"

        atomic_write(target, content)

        assert target.read_text() == content

    def test_atomic_write_with_string_path(self, tmp_path):
        """Test that atomic_write accepts string paths."""
        target = tmp_path / "test.md"
        content = "String path test"

        atomic_write(str(target), content)

        assert target.read_text() == content

    def test_atomic_write_empty_content(self, tmp_path):
        """Test that atomic_write handles empty content."""
        target = tmp_path / "empty.md"
        content = ""

        atomic_write(target, content)

        assert target.exists()
        assert target.read_text() == ""

    def test_atomic_write_large_content(self, tmp_path):
        """Test that atomic_write handles large content."""
        target = tmp_path / "large.md"
        # Create 1MB of content
        content = "x" * (1024 * 1024)

        atomic_write(target, content)

        assert target.read_text() == content


class TestEnsureDirectory:
    """Test ensure_directory function."""

    def test_ensure_directory_creates_new_directory(self, tmp_path):
        """Test that ensure_directory creates a new directory."""
        target = tmp_path / "new_dir"

        ensure_directory(target)

        assert target.exists()
        assert target.is_dir()

    def test_ensure_directory_creates_nested_directories(self, tmp_path):
        """Test that ensure_directory creates nested directories."""
        target = tmp_path / "level1" / "level2" / "level3"

        ensure_directory(target)

        assert target.exists()
        assert target.is_dir()

    def test_ensure_directory_idempotent_on_existing(self, tmp_path):
        """Test that ensure_directory is idempotent on existing directory."""
        target = tmp_path / "existing"
        target.mkdir()

        # Should not raise error
        ensure_directory(target)

        assert target.exists()
        assert target.is_dir()

    def test_ensure_directory_with_path_object(self, tmp_path):
        """Test that ensure_directory accepts Path objects."""
        target = tmp_path / "path_obj"

        ensure_directory(target)

        assert target.is_dir()

    def test_ensure_directory_with_string_path(self, tmp_path):
        """Test that ensure_directory accepts string paths."""
        target = tmp_path / "string_path"

        ensure_directory(str(target))

        assert target.is_dir()


class TestEnsureWorkspaceDirectories:
    """Test ensure_workspace_directories function."""

    def test_creates_resume_and_cover_directories(self, tmp_path):
        """Test that ensure_workspace_directories creates resume and cover directories."""
        base_dir = tmp_path / "applications"
        application_slug = "amazon-3629"

        ensure_workspace_directories(application_slug, str(base_dir))

        resume_dir = base_dir / application_slug / "resume"
        cover_dir = base_dir / application_slug / "cover"

        assert resume_dir.exists()
        assert resume_dir.is_dir()
        assert cover_dir.exists()
        assert cover_dir.is_dir()

    def test_creates_nested_workspace_structure(self, tmp_path):
        """Test that ensure_workspace_directories creates full nested structure."""
        base_dir = tmp_path / "data" / "applications"
        application_slug = "general_motors-3711"

        ensure_workspace_directories(application_slug, str(base_dir))

        workspace_root = base_dir / application_slug
        resume_dir = workspace_root / "resume"
        cover_dir = workspace_root / "cover"

        assert workspace_root.exists()
        assert resume_dir.exists()
        assert cover_dir.exists()

    def test_idempotent_on_existing_directories(self, tmp_path):
        """Test that ensure_workspace_directories is idempotent."""
        base_dir = tmp_path / "applications"
        application_slug = "meta-3630"

        # Create directories first time
        ensure_workspace_directories(application_slug, str(base_dir))

        # Create again - should not raise error
        ensure_workspace_directories(application_slug, str(base_dir))

        resume_dir = base_dir / application_slug / "resume"
        cover_dir = base_dir / application_slug / "cover"

        assert resume_dir.exists()
        assert cover_dir.exists()

    def test_does_not_create_content_files(self, tmp_path):
        """Test that ensure_workspace_directories does NOT create resume or cover letter files."""
        base_dir = tmp_path / "applications"
        application_slug = "google-4000"

        ensure_workspace_directories(application_slug, str(base_dir))

        workspace_root = base_dir / application_slug
        resume_file = workspace_root / "resume" / "resume.pdf"
        cover_file = workspace_root / "cover" / "cover-letter.pdf"

        # Directories should exist
        assert (workspace_root / "resume").exists()
        assert (workspace_root / "cover").exists()

        # But content files should NOT exist
        assert not resume_file.exists()
        assert not cover_file.exists()

    def test_uses_default_base_dir(self, tmp_path, monkeypatch):
        """Test that ensure_workspace_directories uses default base_dir."""
        # Change to tmp_path so default "data/applications" is created there
        monkeypatch.chdir(tmp_path)
        application_slug = "apple-5000"

        ensure_workspace_directories(application_slug)

        resume_dir = tmp_path / "data" / "applications" / application_slug / "resume"
        cover_dir = tmp_path / "data" / "applications" / application_slug / "cover"

        assert resume_dir.exists()
        assert cover_dir.exists()

    def test_handles_special_characters_in_slug(self, tmp_path):
        """Test that ensure_workspace_directories handles slugs with special characters."""
        base_dir = tmp_path / "applications"
        application_slug = "l_or_al-6000"

        ensure_workspace_directories(application_slug, str(base_dir))

        resume_dir = base_dir / application_slug / "resume"
        cover_dir = base_dir / application_slug / "cover"

        assert resume_dir.exists()
        assert cover_dir.exists()

    def test_multiple_applications_in_same_base(self, tmp_path):
        """Test creating multiple application workspaces in the same base directory."""
        base_dir = tmp_path / "applications"

        ensure_workspace_directories("amazon-1", str(base_dir))
        ensure_workspace_directories("google-2", str(base_dir))
        ensure_workspace_directories("meta-3", str(base_dir))

        # All three workspaces should exist independently
        assert (base_dir / "amazon-1" / "resume").exists()
        assert (base_dir / "amazon-1" / "cover").exists()
        assert (base_dir / "google-2" / "resume").exists()
        assert (base_dir / "google-2" / "cover").exists()
        assert (base_dir / "meta-3" / "resume").exists()
        assert (base_dir / "meta-3" / "cover").exists()



class TestResolveWriteAction:
    """Test resolve_write_action function for idempotent action resolution."""

    def test_missing_file_returns_created(self):
        """Test that missing file returns 'created' action."""
        action = resolve_write_action(file_exists=False, force=False)
        assert action == "created"

    def test_missing_file_with_force_returns_created(self):
        """Test that missing file with force=True still returns 'created'."""
        action = resolve_write_action(file_exists=False, force=True)
        assert action == "created"

    def test_existing_file_without_force_returns_skipped(self):
        """Test that existing file without force returns 'skipped_exists'."""
        action = resolve_write_action(file_exists=True, force=False)
        assert action == "skipped_exists"

    def test_existing_file_with_force_returns_overwritten(self):
        """Test that existing file with force=True returns 'overwritten'."""
        action = resolve_write_action(file_exists=True, force=True)
        assert action == "overwritten"

    def test_idempotent_behavior_matrix(self):
        """Test complete idempotent action resolution matrix."""
        # Matrix of (file_exists, force) -> expected_action
        test_cases = [
            (False, False, "created"),
            (False, True, "created"),
            (True, False, "skipped_exists"),
            (True, True, "overwritten"),
        ]

        for file_exists, force, expected_action in test_cases:
            action = resolve_write_action(file_exists, force)
            assert action == expected_action, (
                f"Expected {expected_action} for file_exists={file_exists}, "
                f"force={force}, but got {action}"
            )


    def test_requirements_validation(self):
        """
        Validate implementation against requirements 4.1, 4.2, 4.4, 5.4.

        Requirements:
        - 4.1: Existing file + force=false -> skipped_exists
        - 4.2: Existing file + force=true -> overwritten
        - 4.4: Include skipped items in results with explicit action reason
        - 5.4: Return per-item actions: created, skipped_exists, overwritten, failed
        """
        # Requirement 4.1: Existing file + force=false -> skipped_exists
        action_4_1 = resolve_write_action(file_exists=True, force=False)
        assert action_4_1 == "skipped_exists", "Requirement 4.1 failed"

        # Requirement 4.2: Existing file + force=true -> overwritten
        action_4_2 = resolve_write_action(file_exists=True, force=True)
        assert action_4_2 == "overwritten", "Requirement 4.2 failed"

        # Requirement 4.4 & 5.4: Explicit action reasons for all cases
        all_actions = [
            resolve_write_action(False, False),  # created
            resolve_write_action(False, True),   # created
            resolve_write_action(True, False),   # skipped_exists
            resolve_write_action(True, True),    # overwritten
        ]

        # Verify all actions are explicit and valid
        valid_actions = {"created", "skipped_exists", "overwritten"}
        for action in all_actions:
            assert action in valid_actions, (
                f"Requirement 4.4/5.4 failed: action '{action}' not in valid set"
            )

        # Verify we have all expected action types
        assert "created" in all_actions
        assert "skipped_exists" in all_actions
        assert "overwritten" in all_actions
