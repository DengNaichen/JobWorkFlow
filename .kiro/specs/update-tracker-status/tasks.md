# Implementation Plan: update_tracker_status

## Overview

This plan implements `update_tracker_status` as a tracker-only projection tool with transition checks and `Resume Written` guardrails. The implementation updates only tracker frontmatter `status`, supports dry-run, and preserves DB-as-SSOT boundaries.

## Tasks

- [ ] 1. Add input validation for tracker status updates
  - [x] 1.1 Extend `utils/validation.py` with `validate_update_tracker_status_parameters(...)`
    - Validate required `tracker_path` and `target_status`
    - Validate optional `dry_run` and `force` booleans
    - Reject unknown payload properties
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 1.2 Add status vocabulary validation helper
    - Enforce canonical statuses and case-sensitive matching
    - Reject leading/trailing whitespace
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 1.3 Add validation tests
    - Missing params, bad types, unknown props, invalid statuses
    - _Requirements: 1.5, 3.2, 10.1_

- [ ] 2. Implement tracker parsing and frontmatter utilities
  - [x] 2.1 Create/extend `utils/tracker_parser.py`
    - Parse frontmatter + body
    - Require `status` field presence
    - _Requirements: 2.3, 2.4_

  - [x] 2.2 Add tracker read error mapping
    - Missing/unreadable tracker -> `FILE_NOT_FOUND`
    - Malformed frontmatter -> `VALIDATION_ERROR`
    - _Requirements: 2.1, 2.2, 10.1, 10.2_

  - [ ]* 2.3 Add parser tests
    - Valid tracker parse
    - Missing status and malformed YAML cases
    - _Requirements: 2.4, 2.5_

- [ ] 3. Implement transition policy module
  - [x] 3.1 Add transition policy helper in `utils/tracker_policy.py`
    - Support `noop` when target == current
    - Enforce core transitions (`Reviewed -> Resume Written`, `Resume Written -> Applied`)
    - Allow terminal outcomes (`Rejected`, `Ghosted`) from any status
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 3.2 Add force-bypass behavior
    - If policy violation and `force=true`, allow update with warning
    - _Requirements: 4.4, 4.5, 9.3_

  - [ ]* 3.3 Add transition policy tests
    - Allowed transitions, blocked transitions, force override
    - _Requirements: 4.2, 4.4, 4.5_

- [ ] 4. Implement Resume Written guardrails
  - [x] 4.1 Add artifact path resolution helper
    - Parse `resume_path` from tracker frontmatter
    - Support wiki-link and plain path formats
    - Resolve companion `resume.tex` path
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 4.2 Add guardrail validator in `utils/finalize_validators.py` (or dedicated module)
    - Verify `resume.pdf` exists and non-zero size
    - Verify `resume.tex` exists
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 4.3 Reuse placeholder scanner from `utils/latex_guardrails.py`
    - Block if any placeholder token remains
    - Return matched token summary
    - _Requirements: 5.4, 5.5, 5.6_

  - [ ]* 4.4 Add guardrail tests
    - Missing PDF, zero-byte PDF, missing TEX, placeholder present
    - _Requirements: 5.1, 5.5, 8.4_

- [ ] 5. Implement atomic tracker status writer
  - [x] 5.1 Create/extend `utils/tracker_sync.py`
    - Update only frontmatter `status`
    - Preserve non-status frontmatter fields and body
    - _Requirements: 7.1, 7.3, 7.4_

  - [x] 5.2 Add atomic write mechanics
    - Temp file + fsync + os.replace
    - Preserve original file on failure
    - _Requirements: 7.2, 7.5_

  - [x] 5.3 Harden temp-file write path against symlink clobber
    - Use unique temp file names in target directory (no predictable static temp path)
    - Add regression test for pre-existing temp symlink scenario
    - _Requirements: 7.2, 7.5_

  - [ ]* 5.4 Add writer tests
    - Content-preservation and failure-rollback behavior
    - _Requirements: 7.3, 7.5_

- [ ] 6. Implement main MCP tool handler
  - [x] 6.1 Create `tools/update_tracker_status.py`
    - Orchestrate validation, parsing, transition checks, guardrails, and write flow
    - _Requirements: 1.6, 4.1, 5.1_

  - [x] 6.2 Implement dry-run branch
    - Perform full checks with no write
    - Return predicted action
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [x] 6.3 Build structured response payload
    - Include paths/status/action/success/guardrail flags/warnings
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 6.4 Implement blocked-failure vs top-level-fatal mapping
    - Policy/guardrail failures as structured blocked response
    - Request/init/runtime failures as top-level error object
    - _Requirements: 10.3, 10.4, 10.5, 10.6_

- [ ] 7. Register tool in MCP server
  - [x] 7.1 Update `server.py` tool registration
    - Add `update_tracker_status` signature and description
    - _Requirements: 1.1, 9.1_

  - [x] 7.2 Update server instructions/docstrings
    - Document `Resume Written` guardrail behavior
    - _Requirements: 5.1, 5.4_

- [ ] 8. Add integration tests
  - [x] 8.1 Create `tests/test_update_tracker_status.py`
    - successful update and noop scenarios
    - transition blocked and force override scenarios
    - _Requirements: 4.1, 4.4, 4.5_

  - [x] 8.2 Add Resume Written guardrail tests
    - missing artifact and placeholder block cases
    - _Requirements: 5.1, 5.5, 6.4_

  - [x] 8.3 Add dry-run and atomic write tests
    - no mutation in dry-run
    - original file unchanged on write failure
    - _Requirements: 8.2, 7.5_

  - [ ]* 8.4 Add server integration test
    - invoke tool through MCP registration path and verify schema
    - _Requirements: 9.5, 10.5_

- [ ] 9. Update documentation
  - [x] 9.1 Update `mcp-server-python/README.md`
    - add tool parameters, response schema, and guardrail examples
    - _Requirements: 9.1, 10.6_

  - [x] 9.2 Update root `README.md` progress when implemented
    - move `update_tracker_status` from planned to implemented
    - _Requirements: 11.1, 11.5_

- [ ] 10. Checkpoint - End-to-end verification
  - [x] 10.1 Run targeted test suite for tracker-status tool
    - validate transition policy, guardrails, dry-run, and write semantics
    - _Requirements: 4.2, 5.4, 8.1_

  - [x] 10.2 Manual smoke test with real tracker
    - block `Resume Written` without valid artifacts
    - allow update after artifacts are valid
    - _Requirements: 5.1, 5.5, 7.1_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Tool intentionally does not touch DB; tracker remains projection layer
- `Resume Written` guardrails mirror README quality constraints
