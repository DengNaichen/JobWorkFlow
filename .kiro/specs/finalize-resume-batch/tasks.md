# Implementation Plan: finalize_resume_batch

## Overview

This plan implements `finalize_resume_batch` as the resume pipeline commit tool. It validates artifacts, writes DB completion/audit fields, synchronizes tracker status, and applies per-item fallback to `reviewed + last_error` when commit steps fail.

## Tasks

- [ ] 1. Extend validation utilities for finalize request
  - [x] 1.1 Add `validate_finalize_resume_batch_parameters(...)` in `utils/validation.py`
    - Validate `items` presence, batch size (0-100), and optional `run_id`, `db_path`, `dry_run`
    - Validate duplicate item IDs at request level
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 2.5, 11.1_

  - [x] 1.2 Add item-level validation helper
    - Validate `id` positive integer and `tracker_path` non-empty string
    - Validate optional `resume_pdf_path` type
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [ ]* 1.3 Add validation unit tests
    - Batch bounds, duplicate IDs, malformed items, unknown properties
    - _Requirements: 1.4, 2.5, 11.1_

  - [x] 1.4 Harden duplicate-ID validation for mixed value types
    - Ensure duplicate formatting never throws type-comparison runtime errors
    - Preserve request-level `VALIDATION_ERROR` classification
    - _Requirements: 2.5, 11.1_

- [ ] 2. Extend DB writer layer for finalization audit schema
  - [x] 2.1 Add schema preflight method in `db/jobs_writer.py`
    - Implement `ensure_finalize_columns()` for:
      - `status`, `updated_at`, `resume_pdf_path`, `resume_written_at`, `run_id`, `attempt_count`, `last_error`
    - Fail fast before item processing if columns missing
    - _Requirements: 4.4, 4.5_

  - [x] 2.2 Add finalize success write method
    - Implement `finalize_resume_written(...)` to update target fields and increment `attempt_count`
    - Clear `last_error` on success
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [x] 2.3 Add fallback write method
    - Implement `fallback_to_reviewed(...)` setting `status='reviewed'`, `last_error`, and `updated_at` while preserving attempt count (attempt is already counted in finalize step)
    - _Requirements: 7.1, 7.2, 7.3, 8.3_

  - [ ]* 2.4 Add DB writer tests for finalize methods
    - Schema preflight pass/fail
    - Success write field correctness
    - Fallback update correctness
    - _Requirements: 4.4, 5.1, 7.1_

- [ ] 3. Implement tracker sync utility
  - [x] 3.1 Create `utils/tracker_sync.py`
    - Load tracker markdown and update frontmatter `status` only
    - Preserve all other frontmatter/body content
    - Write atomically (temp + rename)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 3.2 Add tracker parsing helper reuse/extension
    - Resolve `resume_pdf_path` from tracker `resume_path` wiki-link when not provided by item
    - _Requirements: 3.6, 10.2_

  - [ ]* 3.3 Add tracker sync tests
    - Status update only
    - Preserve content
    - Atomic write behavior
    - _Requirements: 6.2, 6.3_

- [ ] 4. Implement artifact precondition validators
  - [x] 4.1 Create `utils/finalize_validators.py`
    - Validate tracker existence/readability
    - Validate resume.pdf exists and non-zero size
    - Validate resume.tex exists
    - _Requirements: 3.1, 3.2, 3.3_

  - [x] 4.2 Reuse placeholder guardrail scanning
    - Integrate `resume.tex` placeholder checks (PROJECT-AI, PROJECT-BE, WORK-BULLET-POINT)
    - Return concise token summary on failure
    - _Requirements: 3.4, 3.5_

  - [ ]* 4.3 Add validator tests
    - Missing files, zero-byte PDF, placeholder detections
    - _Requirements: 3.2, 3.5_

- [ ] 5. Implement main finalize tool handler
  - [x] 5.1 Create `tools/finalize_resume_batch.py`
    - Orchestrate request validation, run_id resolution, DB preflight, per-item processing
    - Preserve input order
    - _Requirements: 1.6, 2.6, 10.3_

  - [x] 5.2 Implement per-item success path
    - Execute preconditions, DB finalize update, tracker status sync
    - Record item action `finalized` or `already_finalized`
    - _Requirements: 5.1, 6.1, 8.1, 8.5_

  - [x] 5.3 Implement compensation path
    - On post-DB tracker sync failure, apply fallback DB update to `reviewed + last_error`
    - Mark item as failed and continue batch
    - _Requirements: 7.1, 7.2, 7.4, 7.5_

  - [x] 5.4 Implement dry-run mode
    - Perform full validation without DB/tracker writes
    - Return predicted actions and errors
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 5.5 Build structured response payload
    - Include `run_id`, counts, `dry_run`, ordered `results`, optional `warnings`
    - _Requirements: 10.1, 10.2, 10.4, 10.5_

- [ ] 6. Register finalize tool in MCP server
  - [x] 6.1 Update `server.py` with `finalize_resume_batch` tool registration
    - Add tool signature for `items`, `run_id`, `db_path`, `dry_run`
    - _Requirements: 1.1, 1.5, 10.1_

  - [x] 6.2 Update MCP tool descriptions/instructions
    - Document that tool is commit-only and does not compile resumes
    - _Requirements: 12.1, 12.2_

- [ ] 7. Add comprehensive tests
  - [x] 7.1 Create `tests/test_finalize_resume_batch.py`
    - Empty batch success
    - Mixed success/failure batch behavior
    - Input-order result preservation
    - _Requirements: 1.2, 2.6, 10.3_

  - [x] 7.2 Add success-path integration tests
    - DB updated to `resume_written` with audit fields
    - Tracker status set to `Resume Written`
    - _Requirements: 5.1, 5.2, 5.3, 6.1_

  - [x] 7.3 Add failure/compensation integration tests
    - Placeholder present blocks item finalize
    - Tracker sync failure triggers DB fallback `reviewed + last_error`
    - Batch continues after failure
    - _Requirements: 3.5, 7.1, 7.2, 7.4_

  - [x] 7.4 Add dry-run integration tests
    - No DB/tracker mutation in dry-run
    - Predicted outcomes returned
    - _Requirements: 9.2, 9.3, 9.4_

  - [ ]* 7.5 Add server integration test
    - Invoke finalize through MCP registration path
    - Validate response/error schemas
    - _Requirements: 10.1, 11.5_

  - [x] 7.6 Add duplicate-ID mixed-type regression test
    - Verify malformed duplicate sets still return `VALIDATION_ERROR` (not `INTERNAL_ERROR`)
    - _Requirements: 11.1_

- [ ] 8. Update documentation
  - [x] 8.1 Update `mcp-server-python/README.md`
    - Add `finalize_resume_batch` API contract and examples
    - Explain fallback behavior and dry-run usage
    - _Requirements: 10.1, 11.6, 12.1_

  - [x] 8.2 Update root `README.md` progress
    - Move `finalize_resume_batch` from planned to implemented when complete
    - Keep SSOT + board-projection explanation aligned
    - _Requirements: 12.5_

- [ ] 9. Checkpoint - End-to-end verification
  - [x] 9.1 Run targeted test suite for finalize tool
    - Validate preconditions, success commit, fallback, and dry-run
    - _Requirements: 3.1, 5.1, 7.1, 9.1_

  - [x] 9.2 Manual smoke test with one real tracker/workspace
    - Confirm DB + tracker sync on success
    - Confirm reviewed fallback on induced tracker failure
    - _Requirements: 6.1, 7.1, 7.2_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- This tool is intentionally commit-focused; compile/rewrite remain outside scope
- Per-item compensation fallback is required to satisfy `reviewed + last_error` retry semantics
