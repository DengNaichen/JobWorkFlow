# Implementation Plan: pydantic-validation-migration

## Overview

This plan delivers a phased migration from function-based validation to Pydantic v2 models while preserving MCP contracts and existing spec behavior.

## Tasks

- [ ] 1. Build schema foundation
  - [ ] 1.1 Create `mcp-server-python/schemas/` package with `__init__.py`
  - [ ] 1.2 Add `schemas/common.py` for shared constrained types and config defaults
  - [ ] 1.3 Add `utils/pydantic_error_mapper.py` for `ValidationError -> ToolError` conversion
  - [ ] 1.4 Add unit tests for error mapping behavior and sanitization
  - _Requirements: 1.1, 1.2, 3.1, 3.2, 3.3, 3.4_

- [ ] 2. Migrate bulk-read-new-jobs as reference implementation
  - [ ] 2.1 Implement `schemas/bulk_read_new_jobs.py` with request/response models
  - [ ] 2.2 Update tool handler to validate via Pydantic model
  - [ ] 2.3 Preserve existing default and constraints (`limit`, `cursor`, `db_path`)
  - [ ] 2.4 Ensure top-level error contract remains unchanged
  - [ ] 2.5 Update or add tests for compatibility parity
  - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 6.1, 6.2, 6.3_

- [ ] 3. Migrate bulk-update-job-status
  - [ ] 3.1 Implement `schemas/bulk_update_job_status.py` including nested update/result models
  - [ ] 3.2 Preserve unique ID checks and status constraints
  - [ ] 3.3 Preserve per-item failure response behavior (not top-level error) for business validation
  - [ ] 3.4 Keep transaction and timestamp semantics unchanged
  - [ ] 3.5 Add/adjust tests for edge cases and parity
  - _Requirements: 2.1, 2.3, 2.5, 4.1, 4.2, 6.1, 6.2, 6.4_

- [ ] 4. Migrate finalize-resume-batch
  - [ ] 4.1 Implement `schemas/finalize_resume_batch.py` for batch item contracts
  - [ ] 4.2 Preserve duplicate item detection and `run_id` semantics
  - [ ] 4.3 Preserve current compensation/fallback response shape
  - [ ] 4.4 Add/adjust integration tests for invalid/partial item conditions
  - _Requirements: 2.1, 2.3, 3.1, 6.1, 6.2, 6.4_

- [ ] 5. Migrate pipeline tools
  - [ ] 5.1 Implement `schemas/scrape_jobs.py`
  - [ ] 5.2 Implement `schemas/initialize_shortlist_trackers.py`
  - [ ] 5.3 Implement `schemas/career_tailor.py`
  - [ ] 5.4 Implement `schemas/update_tracker_status.py`
  - [ ] 5.5 Switch each tool to Pydantic validation one-by-one with parity tests
  - _Requirements: 1.1, 2.1, 2.2, 2.4, 4.1, 4.2, 6.1, 6.2_

- [ ] 6. Produce and maintain spec alignment matrix
  - [ ] 6.1 Add alignment section in migration docs mapping each existing spec to migrated schema module
  - [ ] 6.2 Record parity status (`Not Started`, `In Progress`, `Parity Confirmed`, `Intentional Change Approved`)
  - [ ] 6.3 Log decision records for any intentional contract changes
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 7. Cleanup legacy validation code
  - [ ] 7.1 Remove unused `validate_*` helpers only after per-tool parity confirmation
  - [ ] 7.2 Keep shared domain validators that remain useful outside request parsing
  - [ ] 7.3 Ensure imports/call sites are cleaned and dead code removed
  - _Requirements: 1.3, 1.4, 5.5_

- [ ] 8. Documentation and handoff
  - [ ] 8.1 Update architecture and README docs with new schema locations and flow
  - [ ] 8.2 Add migration status by tool (legacy vs migrated)
  - [ ] 8.3 Add developer guide for adding new tools with Pydantic models
  - [ ] 8.4 Document rollback procedure for tool-level fallback
  - _Requirements: 5.3, 7.1, 7.2, 7.3, 7.4, 7.5_

## Checkpoints

- [ ] Checkpoint A (Foundation complete)
  - Schema package + error mapper merged
  - Tests for mapper pass

- [ ] Checkpoint B (Core tools complete)
  - `bulk_read_new_jobs`, `bulk_update_job_status`, `finalize_resume_batch` migrated
  - Core regression suite passes

- [ ] Checkpoint C (All target tools complete)
  - All seven targeted tool scopes migrated
  - Alignment matrix reaches parity or approved-intentional state for every row

- [ ] Checkpoint D (Cleanup + docs complete)
  - Legacy validator dead code removed
  - Docs updated and rollout notes finalized

## Notes

- Roll out per tool to reduce blast radius.
- Treat error code and response shape as hard compatibility boundaries.
- Keep migration decisions auditable with explicit records for any non-parity change.
