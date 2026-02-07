# Implementation Plan: bulk_update_job_status

## Overview

This plan implements a write-only MCP tool for performing atomic batch status updates on job records in SQLite. The implementation follows a layered architecture with strict atomicity guarantees, comprehensive validation, and structured error handling. The tool is the write counterpart to `bulk_read_new_jobs` and integrates into the existing MCP server infrastructure.

## Tasks

- [x] 1. Extend validation module for write operations
  - [x] 1.1 Add status validation functions to `utils/validation.py`
    - Implement `validate_status(status)` function that checks against allowed set
    - Implement `ALLOWED_STATUSES` constant with the six valid status values
    - Check for case-sensitivity, whitespace, null/empty values
    - Return per-item validation messages for invalid statuses (not top-level error object)
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [x] 1.2 Add job ID validation function
    - Implement `validate_job_id(job_id)` function that validates positive integers
    - Check for null, non-integer, zero, and negative values
    - Return per-item validation messages for invalid job IDs (not top-level error object)
    - _Requirements: 3.4, 3.5_

  - [x] 1.3 Add batch size validation function
    - Implement `validate_batch_size(updates)` function that checks 0-100 range
    - Return early for empty batches (valid case)
    - Raise `ValidationError` for batches > 100
    - _Requirements: 1.2, 1.4_

  - [x] 1.4 Add duplicate ID validation function
    - Implement `validate_unique_job_ids(updates)` to reject duplicate job IDs within one batch
    - Raise `ValidationError` with descriptive message listing duplicate IDs
    - _Requirements: 3.6, 9.1_

  - [ ]* 1.5 Write unit tests for new validation functions
    - Test status validation with valid statuses, invalid statuses, case variations, whitespace
    - Test job ID validation with positive integers, negative, zero, null, non-integers
    - Test batch size validation with 0, 1, 50, 100, 101, 200 updates
    - Test duplicate ID validation with repeated job IDs
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 3.4, 3.5, 3.6, 1.4, 9.1_

- [x] 2. Implement database writer layer
  - [x] 2.1 Create `db/jobs_writer.py` with transaction management
    - Implement `JobsWriter` class with context manager protocol (`__enter__`, `__exit__`)
    - Accept `db_path` parameter in constructor
    - Open SQLite connection in `__enter__` and begin transaction
    - Rollback on exception in `__exit__`, close connection always
    - Handle `DB_NOT_FOUND` error when database file doesn't exist
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 4.1, 4.2_

  - [x] 2.2 Implement schema preflight for `updated_at`
    - Create `ensure_updated_at_column()` method
    - Check table schema before applying any updates
    - If missing, return schema error and do not execute updates
    - _Requirements: 6.4, 4.1_

  - [x] 2.3 Implement job existence validation method
    - Create `validate_jobs_exist(job_ids: list[int]) -> list[int]` method
    - Execute `SELECT id FROM jobs WHERE id IN (...)` with parameterized SQL
    - Return list of missing job IDs (empty if all exist)
    - Use parameterized queries to prevent SQL injection
    - _Requirements: 3.1, 3.2, 3.3, 7.6_

  - [x] 2.4 Implement status update method
    - Create `update_job_status(job_id: int, status: str, timestamp: str)` method
    - Execute `UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?`
    - Use parameterized SQL for all values
    - Raise exception on database errors
    - _Requirements: 6.1, 7.6, 7.7_

  - [x] 2.5 Implement transaction control methods
    - Create `commit()` method to commit transaction
    - Create `rollback()` method to rollback transaction
    - Ensure proper error handling for commit/rollback failures
    - _Requirements: 4.3, 4.1, 4.2_

  - [ ]* 2.6 Write unit tests for database writer
    - Test connection with valid database path
    - Test connection with non-existent database (expect `DB_NOT_FOUND`)
    - Test schema preflight with and without `updated_at` column
    - Test job existence validation with existing and missing IDs
    - Test status update execution
    - Test transaction commit and rollback
    - Test connection cleanup on success and failure
    - _Requirements: 7.1, 7.2, 7.3, 7.5, 6.4, 3.1, 3.2, 3.3, 4.1, 4.2, 4.3_

- [x] 3. Implement timestamp utilities
  - [x] 3.1 Add timestamp generation function to `utils/validation.py` or new module
    - Implement `get_current_utc_timestamp() -> str` function
    - Use UTC and format `YYYY-MM-DDTHH:MM:SS.mmmZ`
    - Return string like `2026-02-04T03:47:36.966Z`
    - _Requirements: 6.1, 6.3_

  - [ ]* 3.2 Write unit tests for timestamp generation
    - Test timestamp format matches ISO 8601 UTC with `Z` suffix and millisecond precision
    - Test timestamp is in UTC
    - Test timestamp includes milliseconds
    - _Requirements: 6.3_

- [x] 4. Checkpoint - Ensure core components work independently
  - Run all unit tests for validation and database writer
  - Verify transaction rollback works correctly
  - Verify error handling produces structured, sanitized errors
  - Ensure database connections are properly closed
  - Ask the user if questions arise

- [x] 5. Implement main MCP tool handler
  - [x] 5.1 Create `tools/bulk_update_job_status.py` with tool logic
    - Implement `bulk_update_job_status(args: dict) -> dict` function
    - Extract `updates` array and optional `db_path` from args
    - Validate batch size (handle empty batch as success)
    - Validate request shape and reject duplicate IDs
    - Validate each update item structure and values
    - Resolve database path (default or override)
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.6, 7.1, 7.2, 10.1, 10.2_

  - [x] 5.2 Implement transaction orchestration
    - Open `JobsWriter` context manager
    - Run `updated_at` schema preflight before update execution
    - Validate per-item semantic rules and job existence before executing updates
    - If any per-item validation/existence failure exists: build failure response and rollback
    - Generate single timestamp for entire batch
    - Execute all updates with same timestamp
    - Commit transaction on success
    - Rollback automatically on any failure via context manager
    - _Requirements: 4.1, 4.2, 4.3, 6.1, 6.2, 6.4, 3.1, 3.2, 3.3_

  - [x] 5.3 Implement response building
    - Create `build_success_response(updates)` helper function
    - Create `build_failure_response(updates, failures)` helper function
    - Build response with `updated_count`, `failed_count`, `results` array
    - Each result entry has `id`, `success`, and optional `error` fields
    - Maintain input order in results array
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 5.4 Implement error handling and sanitization
    - Wrap all operations in try-except blocks
    - Catch request-level `ValidationError` and return structured top-level error response
    - Catch database errors and return sanitized `DB_ERROR` response
    - Catch unexpected exceptions and return `INTERNAL_ERROR` response
    - Sanitize error messages (remove SQL, paths, stack traces)
    - Include `retryable` boolean in error responses
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [ ]* 5.5 Write integration tests for tool handler
    - Test successful batch update (all jobs exist, valid statuses)
    - Test empty batch returns success with zero counts
    - Test batch with non-existent job IDs returns failure response
    - Test batch with invalid status values returns failure response entries
    - Test batch with invalid job IDs returns failure response entries
    - Test duplicate IDs returns top-level `VALIDATION_ERROR`
    - Test batch > 100 updates returns validation error
    - Test missing `updated_at` column returns schema/database error before any writes
    - Test idempotent updates (same status) succeed
    - Test database not found returns `DB_NOT_FOUND` error
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.1, 3.2, 3.3, 3.6, 5.1, 6.4, 7.3, 8.1, 8.2, 8.3, 9.1_

- [x] 6. Integrate tool into MCP server
  - [x] 6.1 Register tool in `server.py`
    - Add `bulk_update_job_status` tool registration to MCP server
    - Define input schema matching design specification
    - Define output schema matching design specification
    - Wire tool handler to MCP server invocation
    - _Requirements: 10.1, 10.4, 10.5_

  - [x] 6.2 Add tool metadata and documentation
    - Set tool name: `bulk_update_job_status`
    - Set tool description for LLM agents
    - Document input parameters: `updates` (required array), `db_path` (optional string)
    - Document output structure: `updated_count`, `failed_count`, `results`
    - Document error codes: `VALIDATION_ERROR`, `DB_NOT_FOUND`, `DB_ERROR`, `INTERNAL_ERROR`
    - _Requirements: 10.1, 10.4, 10.5_

  - [ ]* 6.3 Write MCP server integration test
    - Test tool can be invoked through MCP server interface
    - Test tool registration and metadata are correct
    - Test input/output schemas are enforced
    - _Requirements: 10.1, 10.2, 10.3_

- [x] 7. Checkpoint - End-to-end validation
  - Run full integration test suite
  - Test tool invocation through MCP server interface
  - Verify atomicity: failed updates rollback entire batch
  - Verify idempotency: same batch can be submitted multiple times
  - Verify timestamp consistency: all jobs in batch get same timestamp
  - Verify write-only guarantee: no job data returned, only success/failure
  - Ensure all tests pass, ask the user if questions arise

- [ ]* 8. Write property-based tests
  - [ ]* 8.1 Write property test for atomic batch updates
    - **Property 1: Atomic batch updates**
    - **Validates: Requirements 1.1, 4.1, 4.2, 4.3**
    - For any batch with one invalid update, verify no updates are committed

  - [ ]* 8.2 Write property test for batch size validation
    - **Property 2: Batch size validation**
    - **Validates: Requirements 1.4**
    - For any batch > 100 updates, verify `VALIDATION_ERROR` is returned

  - [ ]* 8.3 Write property test for status validation
    - **Property 4: Status value validation**
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.5**
    - For any invalid status value, verify a per-item failure result is returned

  - [ ]* 8.4 Write property test for job ID validation
    - **Property 5: Job ID validation**
    - **Validates: Requirements 3.4**
    - For any non-positive-integer job ID, verify a per-item failure result is returned

  - [ ]* 8.5 Write property test for idempotency
    - **Property 7: Idempotent updates**
    - **Validates: Requirements 5.1, 5.3, 5.4, 5.5**
    - For any job, updating to current status should succeed and refresh timestamp

  - [ ]* 8.6 Write property test for batch idempotency
    - **Property 8: Batch idempotency**
    - **Validates: Requirements 5.2**
    - For any valid batch, submitting twice should produce same final `status` state

  - [ ]* 8.7 Write property test for timestamp consistency
    - **Property 9: Timestamp consistency**
    - **Validates: Requirements 6.1, 6.2, 6.3**
    - For any batch, all jobs should get same ISO 8601 timestamp

  - [ ]* 8.8 Write property test for field isolation
    - **Property 10: Timestamp field isolation**
    - **Validates: Requirements 6.5, 11.5**
    - For any update, only `status` and `updated_at` should change

  - [ ]* 8.9 Write property test for response structure
    - **Property 15: Response structure completeness**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4**
    - For any invocation, response should have required fields with correct types

  - [ ]* 8.10 Write property test for result ordering
    - **Property 16: Result ordering preservation**
    - **Validates: Requirements 8.5**
    - For any batch, result order should match input order

  - [ ]* 8.11 Write property test for JSON serializability
    - **Property 18: JSON serializability**
    - **Validates: Requirements 10.3**
    - For any response, all fields should be JSON-serializable

  - [ ]* 8.12 Write property test for SQL injection prevention
    - **Property 13: SQL injection prevention**
    - **Validates: Requirements 7.6**
    - For any status/ID with SQL special characters, treat as literal data
- [x] 9. Update documentation
  - Update `mcp-server-python/README.md` with new tool description
  - Add usage examples for `bulk_update_job_status`
  - Document input/output schemas
  - Document error codes and retry guidance
  - Add to tool list in main README.md
  - _Requirements: 10.4, 10.5_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across randomized inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation reuses existing infrastructure from `bulk_read_new_jobs` (error model, validation utilities, MCP server)
- All database operations use parameterized SQL to prevent injection
- Transaction management ensures atomic all-or-nothing semantics
- Error messages are sanitized to avoid exposing sensitive system details
