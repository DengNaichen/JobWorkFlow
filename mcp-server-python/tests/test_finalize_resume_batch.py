"""
Integration tests for finalize_resume_batch tool.

Tests verify the complete tool workflow including validation, artifact checks,
DB updates, tracker synchronization, compensation fallback, and dry-run mode.
"""

from pathlib import Path
import pytest
import sqlite3
from tools.finalize_resume_batch import (
    finalize_resume_batch,
    generate_run_id,
    sanitize_error_message,
)
from models.errors import ToolError


class TestGenerateRunId:
    """Tests for run_id generation."""

    def test_generate_run_id_format(self):
        """Test that generated run_id has correct format."""
        run_id = generate_run_id()

        # Should start with "run_"
        assert run_id.startswith("run_")

        # Should have 3 parts: run, date, hash
        parts = run_id.split("_")
        assert len(parts) == 3

        # Date part should be 8 digits (YYYYMMDD)
        assert len(parts[1]) == 8
        assert parts[1].isdigit()

        # Hash part should be 8 characters
        assert len(parts[2]) == 8

    def test_generate_run_id_uniqueness(self):
        """Test that consecutive calls generate different run_ids."""
        run_id1 = generate_run_id()
        run_id2 = generate_run_id()

        # Should be different due to microsecond precision
        assert run_id1 != run_id2


class TestFinalizeErrorSanitization:
    """Tests for finalize error sanitization helper."""

    def test_sanitize_error_message_redacts_absolute_path(self):
        error = RuntimeError("permission denied: /Users/nd/secret/jobs.db")
        sanitized = sanitize_error_message(error)

        assert "/Users/nd/secret/jobs.db" not in sanitized
        assert "[path]" in sanitized

    def test_sanitize_error_message_redacts_sql_and_stack_trace(self):
        error = RuntimeError("SELECT * FROM jobs WHERE id = 1\nTraceback ...")
        sanitized = sanitize_error_message(error)

        assert "SELECT" not in sanitized.upper()
        assert "Traceback" not in sanitized
        assert sanitized == "[SQL query]"


class TestFinalizeResumeBatchValidation:
    """Tests for request-level validation."""

    def test_empty_batch_success(self):
        """Test that empty batch returns success with zero counts."""
        result = finalize_resume_batch({"items": []})

        assert result["finalized_count"] == 0
        assert result["failed_count"] == 0
        assert result["dry_run"] is False
        assert result["results"] == []
        assert "run_id" in result
        assert result["run_id"].startswith("run_")

    def test_empty_batch_with_custom_run_id(self):
        """Test that empty batch uses provided run_id."""
        custom_run_id = "run_20260206_custom01"
        result = finalize_resume_batch({"items": [], "run_id": custom_run_id})

        assert result["run_id"] == custom_run_id

    def test_missing_items_parameter(self):
        """Test that missing items parameter raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "items" in str(exc_info.value.message).lower()

    def test_items_not_array(self):
        """Test that non-array items parameter raises VALIDATION_ERROR."""
        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": "not an array"})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "array" in str(exc_info.value.message).lower()

    def test_batch_size_exceeds_maximum(self):
        """Test that batch size > 100 raises VALIDATION_ERROR."""
        items = [{"id": i, "tracker_path": f"tracker{i}.md"} for i in range(1, 102)]

        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": items})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "100" in str(exc_info.value.message)

    def test_duplicate_item_ids(self):
        """Test that duplicate item IDs raise VALIDATION_ERROR."""
        items = [
            {"id": 1, "tracker_path": "tracker1.md"},
            {"id": 2, "tracker_path": "tracker2.md"},
            {"id": 1, "tracker_path": "tracker3.md"},  # Duplicate ID
        ]

        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": items})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "duplicate" in str(exc_info.value.message).lower()

    def test_duplicate_item_ids_mixed_types_raise_validation_error(self):
        """Test mixed-type duplicate IDs do not degrade into INTERNAL_ERROR."""
        items = [
            {"id": "abc", "tracker_path": "tracker1.md"},
            {"id": "abc", "tracker_path": "tracker2.md"},
            {"id": 1, "tracker_path": "tracker3.md"},
            {"id": 1, "tracker_path": "tracker4.md"},
        ]

        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": items})

        assert exc_info.value.code == "VALIDATION_ERROR"
        assert "duplicate" in str(exc_info.value.message).lower()


class TestFinalizeResumeBatchItemValidation:
    """Tests for per-item validation."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test_jobs.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Insert test job
        conn.execute("""
            INSERT INTO jobs (id, status, updated_at)
            VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')
        """)
        conn.commit()
        conn.close()

        return str(db_path)

    def test_item_missing_id(self, test_db):
        """Test that item missing id field fails validation."""
        items = [{"tracker_path": "tracker.md"}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "id" in result["results"][0]["error"].lower()

    def test_item_missing_tracker_path(self, test_db):
        """Test that item missing tracker_path field fails validation."""
        items = [{"id": 1}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "tracker_path" in result["results"][0]["error"].lower()

    def test_item_invalid_id_type(self, test_db):
        """Test that item with non-integer id fails validation."""
        items = [{"id": "not_an_int", "tracker_path": "tracker.md"}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "integer" in result["results"][0]["error"].lower()

    def test_item_negative_id(self, test_db):
        """Test that item with negative id fails validation."""
        items = [{"id": -1, "tracker_path": "tracker.md"}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "positive" in result["results"][0]["error"].lower()

    def test_item_empty_tracker_path(self, test_db):
        """Test that item with empty tracker_path fails validation."""
        items = [{"id": 1, "tracker_path": ""}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "empty" in result["results"][0]["error"].lower()


class TestFinalizeResumeBatchArtifactValidation:
    """Tests for artifact validation."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test_jobs.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Insert test jobs
        conn.execute("""
            INSERT INTO jobs (id, status, updated_at)
            VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')
        """)
        conn.execute("""
            INSERT INTO jobs (id, status, updated_at)
            VALUES (2, 'reviewed', '2026-02-06T10:00:00.000Z')
        """)
        conn.commit()
        conn.close()

        return str(db_path)

    def test_missing_tracker_file(self, test_db):
        """Test that missing tracker file fails validation."""
        items = [{"id": 1, "tracker_path": "nonexistent.md"}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "not found" in result["results"][0]["error"].lower()

    def test_missing_tracker_file_redacts_absolute_path(self, test_db, tmp_path):
        """Absolute tracker paths should be redacted in per-item errors."""
        missing_path = tmp_path / "secret" / "missing-tracker.md"
        items = [{"id": 1, "tracker_path": str(missing_path)}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        error_message = result["results"][0]["error"]
        assert str(missing_path) not in error_message
        assert missing_path.name in error_message

    def test_missing_resume_pdf(self, test_db, tmp_path):
        """Test that missing resume.pdf fails validation."""
        # Create tracker without resume artifacts
        tracker_path = tmp_path / "tracker.md"
        content = """---
status: Reviewed
company: Amazon
resume_path: "data/applications/missing/resume/resume.pdf"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        items = [{"id": 1, "tracker_path": str(tracker_path)}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "resume.pdf" in result["results"][0]["error"].lower()

    def test_zero_byte_resume_pdf(self, test_db, tmp_path):
        """Test that zero-byte resume.pdf fails validation."""
        # Create resume directory
        resume_dir = tmp_path / "data" / "applications" / "test" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create zero-byte PDF
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"")

        # Create tracker
        tracker_path = tmp_path / "tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
resume_path: "{str(pdf_path)}"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        items = [{"id": 1, "tracker_path": str(tracker_path)}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "empty" in result["results"][0]["error"].lower()

    def test_missing_resume_tex(self, test_db, tmp_path):
        """Test that missing resume.tex fails validation."""
        # Create resume directory with PDF only
        resume_dir = tmp_path / "data" / "applications" / "test" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create PDF
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest content")

        # Create tracker
        tracker_path = tmp_path / "tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
resume_path: "{str(pdf_path)}"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        items = [{"id": 1, "tracker_path": str(tracker_path)}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "resume.tex" in result["results"][0]["error"].lower()

    def test_resume_tex_with_placeholders(self, test_db, tmp_path):
        """Test that resume.tex with placeholders fails validation."""
        # Create resume directory
        resume_dir = tmp_path / "data" / "applications" / "test" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create PDF
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest content")

        # Create TEX with placeholder
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Experience}
PROJECT-AI-placeholder content here
\end{document}
"""
        tex_path.write_text(tex_content)

        # Create tracker
        tracker_path = tmp_path / "tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
resume_path: "{str(pdf_path)}"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        items = [{"id": 1, "tracker_path": str(tracker_path)}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        assert result["failed_count"] == 1
        assert result["finalized_count"] == 0
        assert result["results"][0]["success"] is False
        assert "placeholder" in result["results"][0]["error"].lower()


class TestFinalizeResumeBatchSuccessPath:
    """Tests for successful finalization."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test_jobs.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Insert test job
        conn.execute("""
            INSERT INTO jobs (id, status, updated_at)
            VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')
        """)
        conn.commit()
        conn.close()

        return str(db_path)

    @pytest.fixture
    def valid_tracker(self, tmp_path):
        """Create a valid tracker with resume artifacts."""
        # Create resume directory
        resume_dir = tmp_path / "data" / "applications" / "test" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create PDF
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest content")

        # Create TEX without placeholders
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Experience}
Real content here
\end{document}
"""
        tex_path.write_text(tex_content)

        # Create tracker
        tracker_path = tmp_path / "tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
resume_path: "{str(pdf_path)}"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        return str(tracker_path), str(pdf_path)

    def test_successful_finalization(self, test_db, valid_tracker):
        """Test successful finalization updates DB and tracker."""
        tracker_path, pdf_path = valid_tracker

        items = [{"id": 1, "tracker_path": tracker_path}]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        # Check response
        assert result["finalized_count"] == 1
        assert result["failed_count"] == 0
        assert result["dry_run"] is False
        assert len(result["results"]) == 1

        item_result = result["results"][0]
        assert item_result["id"] == 1
        assert item_result["tracker_path"] == tracker_path
        assert item_result["resume_pdf_path"] == pdf_path
        assert item_result["action"] == "finalized"
        assert item_result["success"] is True
        assert "error" not in item_result

        # Verify DB was updated
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["status"] == "resume_written"
        assert row["resume_pdf_path"] == pdf_path
        assert row["resume_written_at"] is not None
        assert row["run_id"] == result["run_id"]
        assert row["attempt_count"] == 1
        assert row["last_error"] is None

        # Verify tracker was updated
        tracker_content = Path(tracker_path).read_text()
        assert "status: Resume Written" in tracker_content
        assert "company: Amazon" in tracker_content  # Other fields preserved

    def test_nonexistent_job_id_fails_without_mutating_tracker(self, test_db, valid_tracker):
        """Missing DB job ID should fail item finalization and keep tracker unchanged."""
        tracker_path, _ = valid_tracker

        result = finalize_resume_batch(
            {"items": [{"id": 999, "tracker_path": tracker_path}], "db_path": test_db}
        )

        assert result["finalized_count"] == 0
        assert result["failed_count"] == 1
        assert result["results"][0]["success"] is False
        assert "no job found" in result["results"][0]["error"].lower()

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        missing = conn.execute("SELECT * FROM jobs WHERE id = 999").fetchone()
        original = conn.execute("SELECT status, attempt_count FROM jobs WHERE id = 1").fetchone()
        conn.close()

        assert missing is None
        assert original["status"] == "reviewed"
        assert original["attempt_count"] == 0

        tracker_content = Path(tracker_path).read_text()
        assert "status: Reviewed" in tracker_content

    def test_custom_run_id(self, test_db, valid_tracker):
        """Test that custom run_id is used in DB updates."""
        tracker_path, pdf_path = valid_tracker
        custom_run_id = "run_20260206_custom01"

        items = [{"id": 1, "tracker_path": tracker_path}]

        result = finalize_resume_batch(
            {"items": items, "run_id": custom_run_id, "db_path": test_db}
        )

        assert result["run_id"] == custom_run_id

        # Verify DB has custom run_id
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT run_id FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["run_id"] == custom_run_id


class TestFinalizeResumeBatchDryRun:
    """Tests for dry-run mode."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test_jobs.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Insert test job
        conn.execute("""
            INSERT INTO jobs (id, status, updated_at)
            VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')
        """)
        conn.commit()
        conn.close()

        return str(db_path)

    @pytest.fixture
    def valid_tracker(self, tmp_path):
        """Create a valid tracker with resume artifacts."""
        # Create resume directory
        resume_dir = tmp_path / "data" / "applications" / "test" / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)

        # Create PDF
        pdf_path = resume_dir / "resume.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\nTest content")

        # Create TEX without placeholders
        tex_path = resume_dir / "resume.tex"
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Experience}
Real content here
\end{document}
"""
        tex_path.write_text(tex_content)

        # Create tracker
        tracker_path = tmp_path / "tracker.md"
        content = f"""---
status: Reviewed
company: Amazon
resume_path: "{str(pdf_path)}"
---

## Job Description
Test job
"""
        tracker_path.write_text(content)

        return str(tracker_path), str(pdf_path)

    def test_dry_run_no_db_mutation(self, test_db, valid_tracker):
        """Test that dry-run does not mutate DB."""
        tracker_path, pdf_path = valid_tracker

        items = [{"id": 1, "tracker_path": tracker_path}]

        result = finalize_resume_batch({"items": items, "db_path": test_db, "dry_run": True})

        # Check response
        assert result["dry_run"] is True
        assert result["finalized_count"] == 1
        assert result["failed_count"] == 0
        assert result["results"][0]["action"] == "would_finalize"
        assert result["results"][0]["success"] is True

        # Verify DB was NOT updated
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM jobs WHERE id = 1")
        row = cursor.fetchone()
        conn.close()

        assert row["status"] == "reviewed"  # Unchanged
        assert row["resume_pdf_path"] is None  # Unchanged
        assert row["resume_written_at"] is None  # Unchanged
        assert row["run_id"] is None  # Unchanged
        assert row["attempt_count"] == 0  # Unchanged

    def test_dry_run_no_tracker_mutation(self, test_db, valid_tracker):
        """Test that dry-run does not mutate tracker."""
        tracker_path, pdf_path = valid_tracker

        # Read original tracker content
        original_content = Path(tracker_path).read_text()

        items = [{"id": 1, "tracker_path": tracker_path}]

        result = finalize_resume_batch({"items": items, "db_path": test_db, "dry_run": True})

        assert result["dry_run"] is True

        # Verify tracker was NOT updated
        current_content = Path(tracker_path).read_text()
        assert current_content == original_content
        assert "status: Reviewed" in current_content  # Still original status


class TestFinalizeResumeBatchOrdering:
    """Tests for result ordering."""

    @pytest.fixture
    def test_db(self, tmp_path):
        """Create a test database with required schema."""
        db_path = tmp_path / "test_jobs.db"

        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
        """)

        # Insert test jobs
        for i in range(1, 4):
            conn.execute(
                """
                INSERT INTO jobs (id, status, updated_at)
                VALUES (?, 'reviewed', '2026-02-06T10:00:00.000Z')
            """,
                (i,),
            )
        conn.commit()
        conn.close()

        return str(db_path)

    def test_result_order_matches_input_order(self, test_db, tmp_path):
        """Test that results are ordered exactly as input."""
        # Create trackers with different validation outcomes
        trackers = []

        # Tracker 1: Valid
        resume_dir1 = tmp_path / "data" / "applications" / "app1" / "resume"
        resume_dir1.mkdir(parents=True, exist_ok=True)
        pdf_path1 = resume_dir1 / "resume.pdf"
        pdf_path1.write_bytes(b"%PDF-1.4\nTest")
        tex_path1 = resume_dir1 / "resume.tex"
        tex_path1.write_text(r"\documentclass{article}\begin{document}Content\end{document}")
        tracker_path1 = tmp_path / "tracker1.md"
        tracker_path1.write_text(
            f'---\nstatus: Reviewed\nresume_path: "{str(pdf_path1)}"\n---\nTest'
        )
        trackers.append(str(tracker_path1))

        # Tracker 2: Missing (will fail)
        trackers.append("nonexistent.md")

        # Tracker 3: Valid
        resume_dir3 = tmp_path / "data" / "applications" / "app3" / "resume"
        resume_dir3.mkdir(parents=True, exist_ok=True)
        pdf_path3 = resume_dir3 / "resume.pdf"
        pdf_path3.write_bytes(b"%PDF-1.4\nTest")
        tex_path3 = resume_dir3 / "resume.tex"
        tex_path3.write_text(r"\documentclass{article}\begin{document}Content\end{document}")
        tracker_path3 = tmp_path / "tracker3.md"
        tracker_path3.write_text(
            f'---\nstatus: Reviewed\nresume_path: "{str(pdf_path3)}"\n---\nTest'
        )
        trackers.append(str(tracker_path3))

        items = [
            {"id": 1, "tracker_path": trackers[0]},
            {"id": 2, "tracker_path": trackers[1]},
            {"id": 3, "tracker_path": trackers[2]},
        ]

        result = finalize_resume_batch({"items": items, "db_path": test_db})

        # Verify order matches input
        assert len(result["results"]) == 3
        assert result["results"][0]["id"] == 1
        assert result["results"][1]["id"] == 2
        assert result["results"][2]["id"] == 3

        # Verify outcomes
        assert result["results"][0]["success"] is True
        assert result["results"][1]["success"] is False
        assert result["results"][2]["success"] is True

        # Verify counts
        assert result["finalized_count"] == 2
        assert result["failed_count"] == 1


class TestFinalizeResumeBatchCompensation:
    """Tests for compensation fallback when tracker sync fails."""

    @pytest.fixture
    def test_db(self, tmp_path):
        db_path = tmp_path / "test_jobs.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            """
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT,
                updated_at TEXT,
                resume_pdf_path TEXT,
                resume_written_at TEXT,
                run_id TEXT,
                attempt_count INTEGER DEFAULT 0,
                last_error TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO jobs (id, status, updated_at) VALUES (1, 'reviewed', '2026-02-06T10:00:00.000Z')"
        )
        conn.execute(
            "INSERT INTO jobs (id, status, updated_at) VALUES (2, 'reviewed', '2026-02-06T10:00:00.000Z')"
        )
        conn.commit()
        conn.close()
        return str(db_path)

    @staticmethod
    def _create_valid_tracker(tmp_path, name: str) -> str:
        resume_dir = tmp_path / "data" / "applications" / name / "resume"
        resume_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = resume_dir / "resume.pdf"
        tex_path = resume_dir / "resume.tex"
        pdf_path.write_bytes(b"%PDF-1.4\nTest")
        tex_path.write_text(r"\documentclass{article}\begin{document}Content\end{document}")

        tracker_path = tmp_path / f"{name}.md"
        tracker_path.write_text(f'---\nstatus: Reviewed\nresume_path: "{str(pdf_path)}"\n---\nBody')
        return str(tracker_path)

    def test_tracker_sync_failure_triggers_fallback_and_batch_continues(
        self, test_db, tmp_path, monkeypatch
    ):
        tracker1 = self._create_valid_tracker(tmp_path, "tracker1")
        tracker2 = self._create_valid_tracker(tmp_path, "tracker2")

        import tools.finalize_resume_batch as finalize_module

        original_sync = finalize_module.update_tracker_status

        def failing_sync(path: str, status: str):
            if path == tracker1:
                raise OSError("permission denied")
            return original_sync(path, status)

        monkeypatch.setattr(finalize_module, "update_tracker_status", failing_sync)

        result = finalize_resume_batch(
            {
                "items": [
                    {"id": 1, "tracker_path": tracker1},
                    {"id": 2, "tracker_path": tracker2},
                ],
                "db_path": test_db,
            }
        )

        assert result["finalized_count"] == 1
        assert result["failed_count"] == 1
        assert result["results"][0]["id"] == 1
        assert result["results"][0]["success"] is False
        assert result["results"][0]["action"] == "failed"
        assert "tracker sync failed" in result["results"][0]["error"].lower()
        assert result["results"][1]["id"] == 2
        assert result["results"][1]["success"] is True
        assert result["results"][1]["action"] == "finalized"

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row1 = conn.execute(
            "SELECT status, last_error, attempt_count FROM jobs WHERE id = 1"
        ).fetchone()
        row2 = conn.execute(
            "SELECT status, last_error, attempt_count FROM jobs WHERE id = 2"
        ).fetchone()
        conn.close()

        assert row1["status"] == "reviewed"
        assert row1["last_error"] is not None
        assert "Tracker sync failed" in row1["last_error"]
        assert row1["attempt_count"] == 1

        assert row2["status"] == "resume_written"
        assert row2["last_error"] is None
        assert row2["attempt_count"] == 1


class TestFinalizeResumeBatchSchemaValidation:
    """Tests for DB schema validation."""

    def test_missing_db_file(self):
        """Test that missing DB file raises DB_NOT_FOUND."""
        items = [{"id": 1, "tracker_path": "tracker.md"}]

        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": items, "db_path": "nonexistent.db"})

        assert exc_info.value.code == "DB_NOT_FOUND"

    def test_missing_required_columns(self, tmp_path):
        """Test that missing required columns raises DB_ERROR."""
        # Create DB with incomplete schema
        db_path = tmp_path / "incomplete.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE jobs (
                id INTEGER PRIMARY KEY,
                status TEXT
            )
        """)
        conn.close()

        items = [{"id": 1, "tracker_path": "tracker.md"}]

        with pytest.raises(ToolError) as exc_info:
            finalize_resume_batch({"items": items, "db_path": str(db_path)})

        assert exc_info.value.code == "DB_ERROR"
        assert "schema" in str(exc_info.value.message).lower()
        assert "migration" in str(exc_info.value.message).lower()
