# Implementation Plan: bulk_read_new_jobs

## Overview

This plan implements a read-only MCP tool for retrieving jobs with `status='new'` from SQLite in deterministic batches with cursor-based pagination. The implementation follows a layered architecture with strict read-only guarantees and comprehensive error handling.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create Python MCP server directory structure (`mcp-server-python/`)
  - Set up virtual environment and install dependencies (`mcp`, `pydantic`, test deps; `sqlite3` is built-in)
  - Create package structure: `tools/`, `db/`, `utils/`, `models/`
  - Configure Python path and imports
  - _Requirements: 6.1, 6.2_

- [x] 2. Implement error model and validation utilities
  - [x] 2.1 Create error model with structured error codes
    - Implement `models/errors.py` with error codes: `VALIDATION_ERROR`, `DB_NOT_FOUND`, `DB_ERROR`, `INTERNAL_ERROR`
    - Include `code`, `message`, and `retryable` fields in error schema
    - Implement error sanitization to remove sensitive details (paths, SQL, stack traces)
    - _Requirements: 5.1, 5.2, 5.3, 5.5_

  - [x] 2.2 Implement input validation functions
    - Create validation for `limit` parameter (1-1000 range, default 50)
    - Create validation for `db_path` parameter (string type check)
    - Create validation for `cursor` parameter (format validation)
    - Return structured `VALIDATION_ERROR` for invalid inputs
    - _Requirements: 1.3, 1.4, 6.3_

  - [x]* 2.3 Write unit tests for validation
    - Test `limit` validation: default, valid range, below 1, above 1000
    - Test `db_path` validation: valid paths, invalid types
    - Test `cursor` validation: valid format, malformed cursors
    - Test error message clarity and sanitization
    - _Requirements: 1.3, 1.4, 5.3_

- [x] 3. Implement cursor encoding/decoding module
  - [x] 3.1 Create cursor codec in `utils/cursor.py`
    - Implement `encode_cursor(captured_at, id)` returning opaque string
    - Implement `decode_cursor(cursor_str)` returning `(captured_at, id)` tuple
    - Use base64 encoding for cursor opacity
    - Handle malformed cursor strings with `VALIDATION_ERROR`
    - _Requirements: 1.5, 2.4, 6.3_

  - [x]* 3.2 Write property test for cursor round-trip
    - **Property 1: Cursor round-trip consistency**
    - **Validates: Requirements 1.5**
    - For any valid `(captured_at, id)` pair, `decode_cursor(encode_cursor(captured_at, id))` should return the original values

  - [ ]* 3.3 Write unit tests for cursor edge cases
    - Test cursor with null/empty values
    - Test cursor with special characters in timestamp
    - Test cursor decoding with invalid base64
    - _Requirements: 1.5, 6.3_

- [x] 4. Implement database reader layer
  - [x] 4.1 Create `db/jobs_reader.py` with connection management
    - Implement context manager for SQLite connections
    - Resolve database path with default `data/capture/jobs.db`
    - Handle `db_path` override parameter
    - Return `DB_NOT_FOUND` error when database file doesn't exist
    - Return `DB_ERROR` for connection failures
    - Ensure connections are always closed via context management
    - _Requirements: 2.1, 2.2, 2.5, 2.6, 4.5_

  - [x] 4.2 Implement deterministic query function
    - Create `query_new_jobs(conn, limit, cursor)` function
    - Filter by `status='new'` using parameterized SQL
    - Order by `captured_at DESC, id DESC` for deterministic results
    - Implement cursor boundary predicate: `(captured_at < c_ts) OR (captured_at = c_ts AND id < c_id)`
    - Query `limit + 1` rows to compute `has_more` flag
    - Return list of row dictionaries with fixed schema fields
    - _Requirements: 2.2, 2.3, 2.4

  - [ ]* 4.3 Write unit tests for database reader
    - Test connection with valid database path
    - Test connection with non-existent database (expect `DB_NOT_FOUND`)
    - Test query with empty result set
    - Test query returns only `status='new'` jobs
    - Test deterministic ordering (repeated queries return same order)
    - _Requirements: 2.1, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 4.4 Write property test for read-only guarantee
    - **Property 2: Read-only operations**
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**
    - For any database state, calling `query_new_jobs` should not modify any records (snapshot DB before/after and verify no changes)

- [x] 5. Checkpoint - Ensure core components work independently
  - Run all unit tests for validation, cursor, and database reader
  - Verify error handling produces structured, sanitized errors
  - Ensure database connections are properly closed
  - Ask the user if questions arise

- [x] 6. Implement pagination logic
  - [x] 6.1 Create pagination helper functions
    - Implement `compute_has_more(rows, limit)` returning boolean
    - Implement `build_next_cursor(last_row)` returning cursor string or None
    - Implement `paginate_results(rows, limit)` returning `(page, has_more, next_cursor)`
    - Handle edge case when result set is empty
    - _Requirements: 1.5, 2.4, 6.4

  - [ ]* 6.2 Write property test for pagination determinism
    - **Property 3: Pagination determinism**
    - **Validates: Requirements 1.5, 2.4**
    - For any database state, paginating through all results should produce deterministic, non-overlapping pages that union to the complete result set

  - [ ]* 6.3 Write unit tests for pagination edge cases
    - Test pagination with exactly `limit` results (no more pages)
    - Test pagination with `limit + 1` results (one more page)
    - Test pagination with fewer than `limit` results
    - Test `next_cursor` is null on terminal page
    - _Requirements: 1.5, 6.4

- [x] 7. Implement job schema mapping
  - [x] 7.1 Create schema mapper in `models/job.py`
    - Implement `to_job_schema(row)` function
    - Map database row to fixed output schema with fields: `id`, `job_id`, `title`, `company`, `description`, `url`, `location`, `source`, `status`, `captured_at`
    - Handle missing values consistently (return `null` or empty string)
    - Ensure all fields are JSON-serializable
    - Do not include arbitrary additional database columns
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ]* 7.2 Write unit tests for schema mapping
    - Test complete row mapping with all fields present
    - Test row mapping with missing/null fields
    - Test JSON serializability of output
    - Test schema stability (no extra fields)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 8. Implement main MCP tool handler
  - [x] 8.1 Create `tools/bulk_read_new_jobs.py` with tool logic
    - Implement `bulk_read_new_jobs(args: dict) -> dict` function
    - Extract and validate parameters: `limit`, `cursor`, `db_path`
    - Call database reader with validated parameters
    - Apply pagination logic to results
    - Map rows to job schema
    - Build response with `jobs`, `count`, `has_more`, `next_cursor` fields
    - Wrap all errors in structured error format
    - _Requirements: 1.1, 1.2, 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 8.2 Write integration tests for tool handler
    - Test tool with default parameters (limit=50, no cursor)
    - Test tool with custom limit
    - Test tool with cursor for second page
    - Test tool with non-existent database
    - Test tool with invalid parameters
    - Test tool returns empty result set without error when no new jobs exist
    - _Requirements: 1.1, 1.2, 1.5, 5.4, 6.3_

- [x] 9. Integrate tool into MCP server
  - [x] 9.1 Create or update MCP server entry point
    - Create `server.py` if it doesn't exist
    - Register `bulk_read_new_jobs` tool with MCP server
    - Define tool input schema matching design specification
    - Define tool output schema matching design specification
    - Wire tool handler to MCP server invocation
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 9.2 Add tool metadata and documentation
    - Set tool name: `bulk_read_new_jobs`
    - Set tool description for LLM agents
    - Document input parameters with types and constraints
    - Document output structure
    - _Requirements: 6.1, 6.2_

- [x] 10. Checkpoint - End-to-end validation
  - Run full integration test suite
  - Test tool invocation through MCP server interface
  - Verify pagination works across multiple pages
  - Verify read-only guarantee (no database modifications)
  - Verify error handling for all error scenarios
  - Ensure all tests pass, ask the user if questions arise

- [ ]* 11. Write comprehensive property-based tests
  - [ ]* 11.1 Write property test for batch size bounds
    - **Property 4: Batch size validation**
    - **Validates: Requirements 1.3, 1.4**
    - For any limit value outside [1, 1000], the tool should return `VALIDATION_ERROR`

  - [ ]* 11.2 Write property test for result count accuracy
    - **Property 5: Result count accuracy**
    - **Validates: Requirements 6.5**
    - For any query result, `count` field should equal `len(jobs)` array

  - [ ]* 11.3 Write property test for schema stability
    - **Property 6: Schema stability**
    - **Validates: Requirements 3.1, 3.2, 3.5**
    - For any job record returned, it should contain exactly the fixed schema fields and no additional fields

  - [ ]* 11.4 Write property test for JSON serializability
    - **Property 7: JSON serializability**
    - **Validates: Requirements 3.4**
    - For any tool response, all fields should be JSON-serializable without errors

- [x] 12. Add configuration and deployment support
  - Create configuration file for database path defaults
  - Add environment variable support for `JOBWORKFLOW_ROOT`
  - Create startup script for MCP server
  - Add logging configuration for debugging
  - Document deployment steps in README

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties across all inputs
- Unit tests validate specific examples, edge cases, and error conditions
- The implementation maintains strict read-only guarantees throughout
- All database operations use parameterized SQL to prevent injection
- Error messages are sanitized to avoid exposing sensitive system details
