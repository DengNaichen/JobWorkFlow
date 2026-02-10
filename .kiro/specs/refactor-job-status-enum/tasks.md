# Implementation Plan: Refactor Job Status to Enum

## Overview

This plan provides a detailed checklist for migrating from hardcoded status strings to centralized Enums, based on the associated design and requirements documents.

## Tasks

- [x] **1. Foundation**
  - [x] 1.1. Create the new file `mcp-server-python/models/status.py`.
  - [x] 1.2. In `status.py`, define the `JobDbStatus(str, Enum)` with all lowercase database statuses.
  - [x] 1.3. In `status.py`, define the `JobTrackerStatus(str, Enum)` with all capitalized tracker file statuses.
  - _Requirements: 1.1, 1.2, 1.3_

- [x] **2. Refactor Core Definitions & Logic**
  - [x] 2.1. Refactor `mcp-server-python/utils/validation.py`:
    - [x] 2.1.1. Import the new Enums.
    - [x] 2.1.2. Remove the `ALLOWED_STATUSES` and `ALLOWED_TRACKER_STATUSES` lists (replaced with Enum-derived sets).
    - [x] 2.1.3. Update the `validate_status` and `validate_tracker_status` functions to validate against the Enums.
  - [x] 2.2. Refactor `mcp-server-python/utils/tracker_policy.py` to use `JobTrackerStatus` members instead of strings for defining transitions and terminal states.
  - _Requirements: 1.4, 2.2_

- [x] **3. Refactor Database Layer**
  - [x] 3.1. Refactor `mcp-server-python/db/jobs_ingest_writer.py` to use `JobDbStatus.NEW` for the default status.
  - [x] 3.2. Refactor `mcp-server-python/db/jobs_reader.py` to use `JobDbStatus` members in all SQL queries.
  - [x] 3.3. Refactor `mcp-server-python/db/jobs_writer.py` to use `JobDbStatus` members in all SQL queries.
  - _Requirements: 2.1_

- [x] **4. Refactor Tools and API Layer**
  - [x] 4.1. Systematically go through each script in `mcp-server-python/tools/` and replace any hardcoded status strings with the appropriate Enum.
  - [x] 4.2. Review `mcp-server-python/server.py` and update any internal logic that references status strings (docstring examples left as human-readable strings per API contract parity).
  - [x] 4.3. Refactor `mcp-server-python/utils/tracker_renderer.py` to use `JobTrackerStatus.REVIEWED` for initial tracker status.
  - [x] 4.4. Refactor `mcp-server-python/utils/tracker_sync.py` to safely convert Enum members to plain strings before YAML serialization.
  - [x] 4.5. Update `mcp-server-python/schemas/ingestion.py` to re-export `JobDbStatus` as `JobStatus` alias for backward compatibility.
  - _Requirements: 2.3_

- [x] **5. Refactor Tests**
  - [x] 5.1. Update `tests/test_validation.py` to assert against the new Enum-based logic.
  - [x] 5.2. Update `tests/test_validation_scrape_jobs.py` to use Enum members.
  - [x] 5.3. Update `tests/test_tracker_policy.py` to use `JobTrackerStatus` members.
  - [x] 5.4. Update `tests/test_bulk_update_job_status.py` to use `JobDbStatus` members.
  - [x] 5.5. Update `tests/test_bulk_read_new_jobs.py` to use `JobDbStatus` members.
  - [x] 5.6. Update `tests/test_checkpoint_task4.py` to use `JobDbStatus` members.
  - [x] 5.7. Update `tests/test_finalize_resume_batch.py` to use `JobDbStatus` and `JobTrackerStatus` members.
  - [x] 5.8. Update `tests/test_initialize_shortlist_trackers_tool.py` to use `JobDbStatus` members.
  - [x] 5.9. Update `tests/test_job_schema.py` to use `JobDbStatus` members.
  - [x] 5.10. Update `tests/test_career_tailor.py` to use `JobDbStatus` members.
  - [x] 5.11. Update `tests/test_bulk_update_job_status_schemas.py` to use `JobDbStatus` members.
  - [x] 5.12. Update `tests/test_server_bulk_update_integration.py` to use `JobDbStatus` members.
  - [x] 5.13. Update `tests/test_update_tracker_status_tool.py` to use `JobTrackerStatus` members.
  - [x] 5.14. Update `tests/test_tracker_sync.py` to use `JobTrackerStatus` members.
  - [x] 5.15. Update `tests/test_jobs_reader.py` to use `JobDbStatus` members.
  - [x] 5.16. Update `tests/test_jobs_writer.py` to use `JobDbStatus` members.
  - [x] 5.17. Update `tests/test_jobs_ingest_writer.py` to use `JobDbStatus` members.
    - _Note: This was the largest set of changes._
  - _Requirements: 2.4, 3.3_

- [x] **6. Verification and Cleanup**
  - [x] 6.1. Run the entire test suite (`uv run pytest`) and confirm that all tests pass (1272 passed, 2 skipped).
  - [x] 6.2. Run `uv run ruff format .` and `uv run ruff check . --fix` with no issues.
  - [x] 6.3. Perform a final, full-codebase search (`grep`) for any remaining hardcoded status strings in `.py` files — confirmed only enum definitions and docstrings remain.
  - [x] 6.4. Mark this task as complete.
  - _Requirements: 2.5, 3.1, 3.3_