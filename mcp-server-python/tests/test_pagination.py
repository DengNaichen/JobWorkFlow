"""
Unit tests for pagination helper functions.

Tests pagination logic, cursor building, and edge cases.
"""

from utils.pagination import compute_has_more, build_next_cursor, paginate_results
from utils.cursor import decode_cursor


class TestComputeHasMore:
    """Tests for compute_has_more function."""

    def test_has_more_when_rows_exceed_limit(self):
        """Test has_more is True when rows exceed limit."""
        rows = [{"id": i} for i in range(51)]  # 51 rows
        limit = 50

        result = compute_has_more(rows, limit)

        assert result is True

    def test_no_more_when_rows_equal_limit(self):
        """Test has_more is False when rows equal limit."""
        rows = [{"id": i} for i in range(50)]  # 50 rows
        limit = 50

        result = compute_has_more(rows, limit)

        assert result is False

    def test_no_more_when_rows_less_than_limit(self):
        """Test has_more is False when rows less than limit."""
        rows = [{"id": i} for i in range(25)]  # 25 rows
        limit = 50

        result = compute_has_more(rows, limit)

        assert result is False

    def test_no_more_when_empty_result(self):
        """Test has_more is False when result is empty."""
        rows = []
        limit = 50

        result = compute_has_more(rows, limit)

        assert result is False

    def test_has_more_with_small_limit(self):
        """Test has_more with small limit."""
        rows = [{"id": i} for i in range(2)]  # 2 rows
        limit = 1

        result = compute_has_more(rows, limit)

        assert result is True

    def test_has_more_boundary_case(self):
        """Test has_more at exact boundary (limit + 1)."""
        rows = [{"id": i} for i in range(11)]  # 11 rows
        limit = 10

        result = compute_has_more(rows, limit)

        assert result is True


class TestBuildNextCursor:
    """Tests for build_next_cursor function."""

    def test_build_cursor_from_valid_row(self):
        """Test building cursor from a valid row."""
        row = {"id": 123, "captured_at": "2026-02-04T03:47:36.966Z", "title": "Test Job"}

        cursor = build_next_cursor(row)

        assert cursor is not None
        assert isinstance(cursor, str)
        assert len(cursor) > 0

    def test_build_cursor_contains_correct_values(self):
        """Test that built cursor contains correct captured_at and id."""
        row = {"id": 456, "captured_at": "2026-02-04T03:47:36.966Z", "title": "Test Job"}

        cursor = build_next_cursor(row)

        # Decode to verify contents
        decoded_ts, decoded_id = decode_cursor(cursor)
        assert decoded_ts == "2026-02-04T03:47:36.966Z"
        assert decoded_id == 456

    def test_build_cursor_from_none_returns_none(self):
        """Test that None row returns None cursor."""
        cursor = build_next_cursor(None)

        assert cursor is None

    def test_build_cursor_with_different_timestamps(self):
        """Test building cursors with different timestamps."""
        row1 = {"id": 1, "captured_at": "2026-01-01T00:00:00.000Z"}
        row2 = {"id": 1, "captured_at": "2026-12-31T23:59:59.999Z"}

        cursor1 = build_next_cursor(row1)
        cursor2 = build_next_cursor(row2)

        # Different timestamps should produce different cursors
        assert cursor1 != cursor2

    def test_build_cursor_with_different_ids(self):
        """Test building cursors with different IDs."""
        row1 = {"id": 1, "captured_at": "2026-02-04T03:47:36.966Z"}
        row2 = {"id": 999, "captured_at": "2026-02-04T03:47:36.966Z"}

        cursor1 = build_next_cursor(row1)
        cursor2 = build_next_cursor(row2)

        # Different IDs should produce different cursors
        assert cursor1 != cursor2

    def test_build_cursor_ignores_extra_fields(self):
        """Test that cursor only uses captured_at and id, ignoring other fields."""
        row = {
            "id": 789,
            "captured_at": "2026-02-04T03:47:36.966Z",
            "title": "Test Job",
            "company": "Test Company",
            "description": "Long description...",
        }

        cursor = build_next_cursor(row)

        # Decode to verify only captured_at and id are used
        decoded_ts, decoded_id = decode_cursor(cursor)
        assert decoded_ts == "2026-02-04T03:47:36.966Z"
        assert decoded_id == 789


class TestPaginateResults:
    """Tests for paginate_results function."""

    def test_paginate_empty_results(self):
        """Test pagination with empty result set."""
        rows = []
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert page == []
        assert has_more is False
        assert next_cursor is None

    def test_paginate_results_less_than_limit(self):
        """Test pagination when results are less than limit."""
        rows = [{"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"} for i in range(25)]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 25
        assert page == rows
        assert has_more is False
        assert next_cursor is None

    def test_paginate_results_equal_to_limit(self):
        """Test pagination when results equal limit (no more pages)."""
        rows = [{"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"} for i in range(50)]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 50
        assert page == rows
        assert has_more is False
        assert next_cursor is None

    def test_paginate_results_exceed_limit(self):
        """Test pagination when results exceed limit (more pages exist)."""
        rows = [
            {"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"}
            for i in range(51)  # limit + 1
        ]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        # Should return first 50 rows
        assert len(page) == 50
        assert page == rows[:50]
        assert has_more is True
        assert next_cursor is not None

    def test_paginate_next_cursor_uses_last_page_row(self):
        """Test that next_cursor is built from the last row of the page."""
        rows = [{"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"} for i in range(51)]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        # Decode cursor to verify it uses the last row of the page (not the extra row)
        decoded_ts, decoded_id = decode_cursor(next_cursor)
        assert decoded_id == 49  # Last row in page (0-indexed)
        assert decoded_ts == "2026-02-04T03:47:49.000Z"

    def test_paginate_with_small_limit(self):
        """Test pagination with small limit."""
        rows = [
            {"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"}
            for i in range(3)  # limit + 1
        ]
        limit = 2

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 2
        assert page == rows[:2]
        assert has_more is True
        assert next_cursor is not None

    def test_paginate_single_row_with_limit_one(self):
        """Test pagination with single row and limit of 1."""
        rows = [{"id": 1, "captured_at": "2026-02-04T03:47:00.000Z"}]
        limit = 1

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 1
        assert page == rows
        assert has_more is False
        assert next_cursor is None

    def test_paginate_two_rows_with_limit_one(self):
        """Test pagination with two rows and limit of 1."""
        rows = [
            {"id": 1, "captured_at": "2026-02-04T03:47:00.000Z"},
            {"id": 2, "captured_at": "2026-02-04T03:47:01.000Z"},
        ]
        limit = 1

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 1
        assert page == rows[:1]
        assert has_more is True
        assert next_cursor is not None

    def test_paginate_preserves_row_data(self):
        """Test that pagination preserves all row data."""
        rows = [
            {
                "id": i,
                "job_id": f"job_{i}",
                "title": f"Job {i}",
                "company": f"Company {i}",
                "captured_at": f"2026-02-04T03:47:{i:02d}.000Z",
            }
            for i in range(51)
        ]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        # Verify all fields are preserved
        for i, row in enumerate(page):
            assert row["id"] == i
            assert row["job_id"] == f"job_{i}"
            assert row["title"] == f"Job {i}"
            assert row["company"] == f"Company {i}"


class TestPaginationEdgeCases:
    """Tests for pagination edge cases."""

    def test_paginate_exactly_limit_plus_one(self):
        """Test pagination with exactly limit+1 rows (boundary case)."""
        rows = [
            {"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"}
            for i in range(11)  # limit + 1
        ]
        limit = 10

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 10
        assert has_more is True
        assert next_cursor is not None

        # Verify cursor is from last page row
        decoded_ts, decoded_id = decode_cursor(next_cursor)
        assert decoded_id == 9

    def test_paginate_with_large_limit(self):
        """Test pagination with large limit (1000)."""
        rows = [
            {"id": i, "captured_at": f"2026-02-04T03:47:36.{i:03d}Z"}
            for i in range(1001)  # limit + 1
        ]
        limit = 1000

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert len(page) == 1000
        assert has_more is True
        assert next_cursor is not None

    def test_paginate_cursor_is_opaque(self):
        """Test that pagination cursor is opaque (not human-readable)."""
        rows = [
            {"id": 123, "captured_at": "2026-02-04T03:47:36.966Z"},
            {"id": 124, "captured_at": "2026-02-04T03:47:37.000Z"},
        ]
        limit = 1

        page, has_more, next_cursor = paginate_results(rows, limit)

        # Cursor should not contain raw values
        assert "123" not in next_cursor
        assert "2026-02-04" not in next_cursor

    def test_paginate_multiple_pages_produce_different_cursors(self):
        """Test that different pages produce different cursors."""
        # Simulate first page
        rows1 = [{"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"} for i in range(51)]
        page1, has_more1, cursor1 = paginate_results(rows1, 50)

        # Simulate second page (different rows)
        rows2 = [{"id": i, "captured_at": f"2026-02-04T03:46:{i:02d}.000Z"} for i in range(51, 102)]
        page2, has_more2, cursor2 = paginate_results(rows2, 50)

        # Cursors should be different
        assert cursor1 != cursor2

    def test_paginate_terminal_page_has_no_cursor(self):
        """Test that terminal page (last page) has no next_cursor."""
        # Simulate terminal page with fewer rows than limit
        rows = [{"id": i, "captured_at": f"2026-02-04T03:47:{i:02d}.000Z"} for i in range(30)]
        limit = 50

        page, has_more, next_cursor = paginate_results(rows, limit)

        assert has_more is False
        assert next_cursor is None


class TestPaginationIntegration:
    """Integration tests for pagination workflow."""

    def test_pagination_workflow_first_page(self):
        """Test complete pagination workflow for first page."""
        # Simulate database query result (limit + 1)
        rows = [
            {
                "id": i,
                "job_id": f"job_{i}",
                "title": f"Job {i}",
                "captured_at": f"2026-02-04T03:47:{i:02d}.000Z",
            }
            for i in range(51)
        ]
        limit = 50

        # Apply pagination
        page, has_more, next_cursor = paginate_results(rows, limit)

        # Verify first page results
        assert len(page) == 50
        assert page[0]["id"] == 0
        assert page[-1]["id"] == 49
        assert has_more is True
        assert next_cursor is not None

        # Verify cursor can be decoded
        decoded_ts, decoded_id = decode_cursor(next_cursor)
        assert decoded_id == 49
        assert decoded_ts == "2026-02-04T03:47:49.000Z"

    def test_pagination_workflow_middle_page(self):
        """Test complete pagination workflow for middle page."""
        # Simulate database query result for middle page
        rows = [
            {
                "id": i,
                "job_id": f"job_{i}",
                "title": f"Job {i}",
                "captured_at": f"2026-02-04T03:46:{i:02d}.000Z",
            }
            for i in range(50, 101)
        ]
        limit = 50

        # Apply pagination
        page, has_more, next_cursor = paginate_results(rows, limit)

        # Verify middle page results
        assert len(page) == 50
        assert page[0]["id"] == 50
        assert page[-1]["id"] == 99
        assert has_more is True
        assert next_cursor is not None

    def test_pagination_workflow_last_page(self):
        """Test complete pagination workflow for last page."""
        # Simulate database query result for last page (fewer than limit)
        rows = [
            {
                "id": i,
                "job_id": f"job_{i}",
                "title": f"Job {i}",
                "captured_at": f"2026-02-04T03:45:{i:02d}.000Z",
            }
            for i in range(100, 125)
        ]
        limit = 50

        # Apply pagination
        page, has_more, next_cursor = paginate_results(rows, limit)

        # Verify last page results
        assert len(page) == 25
        assert page[0]["id"] == 100
        assert page[-1]["id"] == 124
        assert has_more is False
        assert next_cursor is None

    def test_pagination_workflow_empty_page(self):
        """Test complete pagination workflow for empty result."""
        rows = []
        limit = 50

        # Apply pagination
        page, has_more, next_cursor = paginate_results(rows, limit)

        # Verify empty page results
        assert len(page) == 0
        assert has_more is False
        assert next_cursor is None
