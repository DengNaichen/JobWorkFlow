# Requirements Document

## Introduction

The `bulk_update_job_status` MCP tool provides write-only batch status updates for job records in a SQLite database. This tool is part of the JobWorkFlow pipeline, specifically handling step 3: persisting status transitions after LLM triage evaluation. The tool enables atomic batch updates while maintaining data integrity through transaction management and validation.

## Glossary

- **MCP_Tool**: A Model Context Protocol tool that can be invoked by an LLM agent
- **Job_Database**: SQLite database located at `data/capture/jobs.db` containing job records
- **Status_Transition**: A change from one job status value to another following the defined status model
- **Batch_Update**: A collection of status updates applied atomically in a single transaction
- **Triage_Agent**: The upstream LLM agent that evaluates jobs and determines status outcomes
- **SSOT**: Single Source of Truth - the database status field is the authoritative record

## Requirements

### Requirement 1: Batch Status Updates

**User Story:** As a triage agent, I want to update multiple job statuses in a single operation, so that I can efficiently persist my evaluation results without making individual database calls.

#### Acceptance Criteria

1. WHEN the tool is invoked with a list of status updates, THE MCP_Tool SHALL apply all updates in a single database transaction
2. WHEN the tool is invoked with an empty update list, THE MCP_Tool SHALL return success with zero updates applied
3. WHEN the tool is invoked with 1 to 100 updates, THE MCP_Tool SHALL process all updates
4. WHEN the tool is invoked with more than 100 updates, THE MCP_Tool SHALL return an error indicating batch size too large
5. WHEN all updates succeed, THE MCP_Tool SHALL commit the transaction and return success results

### Requirement 2: Status Validation

**User Story:** As a system administrator, I want only valid status values to be persisted, so that the database maintains referential integrity and the status model is enforced.

#### Acceptance Criteria

1. WHEN an update specifies a status value, THE MCP_Tool SHALL validate it against the allowed status set: `new`, `shortlist`, `reviewed`, `reject`, `resume_written`, `applied`
2. WHEN an update specifies an invalid status value, THE MCP_Tool SHALL include a failure result entry for that item identifying the invalid status
3. WHEN an update specifies a null or empty status value, THE MCP_Tool SHALL include a failure result entry for that item
4. THE MCP_Tool SHALL perform case-sensitive status validation
5. THE MCP_Tool SHALL reject status values with leading or trailing whitespace

### Requirement 3: Job Existence Validation

**User Story:** As a triage agent, I want to know if a job ID doesn't exist, so that I can handle missing records appropriately and avoid silent failures.

#### Acceptance Criteria

1. WHEN an update references a job ID, THE MCP_Tool SHALL verify the job exists in the database before applying the update
2. WHEN an update references a non-existent job ID, THE MCP_Tool SHALL include that job ID in the `results` failure response entry
3. WHEN multiple updates reference non-existent job IDs, THE MCP_Tool SHALL report all missing job IDs
4. WHEN a job ID is not a positive integer, THE MCP_Tool SHALL include a failure result entry for that item with a validation message
5. WHEN a job ID is null or missing, THE MCP_Tool SHALL include a failure result entry for that item with a validation message
6. WHEN the same job ID appears multiple times in one batch, THE MCP_Tool SHALL reject the request with a `VALIDATION_ERROR`

### Requirement 4: Atomic Transaction Semantics

**User Story:** As a system administrator, I want batch updates to be all-or-nothing, so that partial failures don't leave the database in an inconsistent state.

#### Acceptance Criteria

1. WHEN any update in a batch fails validation, THE MCP_Tool SHALL rollback all updates in that batch
2. WHEN a database error occurs during update execution, THE MCP_Tool SHALL rollback all updates in that batch
3. WHEN all updates pass validation and execute successfully, THE MCP_Tool SHALL commit the entire batch atomically
4. WHEN a transaction is rolled back, THE MCP_Tool SHALL return a response indicating which validation or execution failure caused the rollback
5. THE MCP_Tool SHALL ensure no partial updates are visible to concurrent readers during transaction execution

### Requirement 5: Idempotent Updates

**User Story:** As a triage agent, I want to safely retry failed operations, so that transient errors don't prevent me from persisting status updates.

#### Acceptance Criteria

1. WHEN an update sets a job to its current status, THE MCP_Tool SHALL treat it as a successful no-op
2. WHEN the same batch is submitted multiple times, THE MCP_Tool SHALL produce the same final `status` values for all targeted jobs
3. WHEN an update is idempotent, THE MCP_Tool SHALL include it in the success count
4. THE MCP_Tool SHALL update the `updated_at` timestamp even for idempotent updates
5. THE MCP_Tool SHALL NOT return an error for idempotent status updates

### Requirement 6: Timestamp Tracking

**User Story:** As a system administrator, I want to track when job statuses were last updated, so that I can audit status changes and debug pipeline issues.

#### Acceptance Criteria

1. WHEN a job status is updated, THE MCP_Tool SHALL set the `updated_at` field to the current UTC timestamp
2. WHEN multiple jobs are updated in a batch, THE MCP_Tool SHALL use the same timestamp for all updates in that batch
3. THE MCP_Tool SHALL format timestamps as ISO 8601 UTC strings in `YYYY-MM-DDTHH:MM:SS.mmmZ` format (e.g., `2026-02-04T03:47:36.966Z`)
4. WHEN the `jobs` table does not have an `updated_at` column, THE MCP_Tool SHALL fail before applying updates and return a schema error indicating migration is required
5. THE MCP_Tool SHALL NOT modify any timestamp fields other than `updated_at`

### Requirement 7: Database Operations

**User Story:** As the MCP tool, I want to connect to the SQLite database and execute updates safely, so that I can persist status changes reliably.

#### Acceptance Criteria

1. WHEN connecting to the database, THE MCP_Tool SHALL use the default path `data/capture/jobs.db`
2. WHEN the tool is invoked with a `db_path` parameter, THE MCP_Tool SHALL use that path instead of the default
3. WHEN the database file does not exist, THE MCP_Tool SHALL return an error indicating the database is not found
4. WHEN the database connection fails, THE MCP_Tool SHALL return an error with connection details
5. WHEN database operations complete, THE MCP_Tool SHALL close the database connection properly
6. THE MCP_Tool SHALL use parameterized SQL statements to prevent SQL injection
7. THE MCP_Tool SHALL execute UPDATE statements for writes and MAY execute minimal read-only queries required for validation (existence/schema checks), but SHALL NOT execute INSERT or DELETE statements

### Requirement 8: Structured Response Format

**User Story:** As a triage agent, I want detailed results for each update, so that I can identify which jobs were updated successfully and which failed.

#### Acceptance Criteria

1. WHEN updates complete successfully, THE MCP_Tool SHALL return a response containing `updated_count`, `failed_count`, and `results` array
2. WHEN all updates succeed, THE MCP_Tool SHALL set `failed_count` to 0 and include success entries in `results`
3. WHEN any update fails validation, THE MCP_Tool SHALL set `updated_count` to 0 and include failure entries in `results` with error messages
4. WHEN returning results, THE MCP_Tool SHALL include an entry for each job ID with `id`, `success` boolean, and optional `error` message
5. THE MCP_Tool SHALL maintain the order of results matching the order of input updates

### Requirement 9: Error Handling

**User Story:** As a triage agent, I want clear error messages when operations fail, so that I can understand what went wrong and take corrective action.

#### Acceptance Criteria

1. WHEN request-level validation fails (malformed payload, missing required parameters, duplicate IDs, batch size too large), THE MCP_Tool SHALL return an error with code `VALIDATION_ERROR` and descriptive message
2. WHEN the database is not found, THE MCP_Tool SHALL return an error with code `DB_NOT_FOUND` and the attempted path
3. WHEN a database operation fails, THE MCP_Tool SHALL return an error with code `DB_ERROR` and sanitized failure reason
4. WHEN an unexpected error occurs, THE MCP_Tool SHALL return an error with code `INTERNAL_ERROR` and sanitized message
5. THE MCP_Tool SHALL include a `retryable` boolean in error responses indicating if the operation can be retried
6. THE MCP_Tool SHALL sanitize error messages to avoid exposing sensitive system details, SQL fragments, or full stack traces
7. WHEN per-item business validation fails after request parsing (for example, invalid status, invalid job ID, or non-existent job ID), THE MCP_Tool SHALL return a structured failure result using `updated_count`, `failed_count`, and `results`, not a top-level `error` object

### Requirement 10: MCP Tool Interface

**User Story:** As an MCP server, I want the tool to conform to MCP protocol standards, so that it can be invoked correctly by LLM agents.

#### Acceptance Criteria

1. THE MCP_Tool SHALL accept parameters as a structured input following MCP conventions
2. THE MCP_Tool SHALL validate all input parameters before executing database operations
3. WHEN returning results, THE MCP_Tool SHALL format responses as JSON-serializable structures
4. THE MCP_Tool SHALL define a clear input schema specifying required and optional parameters
5. THE MCP_Tool SHALL define a clear output schema specifying the response structure
6. THE MCP_Tool SHALL handle missing or malformed input parameters gracefully with validation errors

### Requirement 11: Write-Only Operations

**User Story:** As a system administrator, I want the tool to perform only write operations, so that concerns are properly separated and read operations use the dedicated read tool.

#### Acceptance Criteria

1. THE MCP_Tool SHALL NOT return job record data beyond confirmation of update success or failure
2. THE MCP_Tool SHALL only execute read queries required for validation (existence/schema checks) and SHALL NOT return job details to the caller
3. THE MCP_Tool SHALL NOT create new job records
4. THE MCP_Tool SHALL NOT delete job records
5. THE MCP_Tool SHALL only modify `status` and `updated_at` fields in UPDATE operations
