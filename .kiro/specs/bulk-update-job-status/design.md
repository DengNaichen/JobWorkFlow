# Design Document: bulk_update_job_status

## Overview

`bulk_update_job_status` is a write-only MCP tool that performs atomic batch status updates on job records in SQLite. This tool is the write counterpart to `bulk_read_new_jobs`, handling the persistence layer after LLM triage evaluation.

This design is aligned with:

- `.kiro/specs/bulk-update-job-status/requirements.md`

Core design goals:

1. Atomic all-or-nothing batch updates
2. Status validation against the defined status model
3. Idempotent update semantics for safe retries
4. Structured error reporting with per-job granularity
5. Timestamp tracking for audit trails
6. Write-only operation guarantees

## Scope

In scope:

- MCP tool interface for `bulk_update_job_status`
- SQLite write path (UPDATE operations only)
- Transaction management with rollback on failure
- Input validation (status values, job IDs, batch size)
- Timestamp tracking (`updated_at` field)
- Structured success/failure reporting per job

Out of scope:

- Status transition validation (state machine enforcement) - deferred to future iteration
- Reading job data (use `bulk_read_new_jobs` instead)
- Creating or deleting job records
- Updating fields other than `status` and `updated_at`
- Audit logging beyond timestamp updates

## Architecture

### Components

1. **MCP Server** (`server.py`) - Tool registration and invocation
2. **Tool Handler** (`tools/bulk_update_job_status.py`) - Main orchestration logic
3. **DB Writer Layer** (`db/jobs_writer.py`) - Transaction management and UPDATE execution
4. **Validation Module** (`utils/validation.py`) - Input validation and status checking
5. **Error Model** (`models/errors.py`) - Structured error types (shared with read tool)

### Runtime Flow

1. LLM agent calls `bulk_update_job_status` with `updates` array and optional `db_path`
2. Tool validates request-level parameters:
   - Batch size (0-100 updates)
   - Request shape (`updates` present, items are objects with required keys)
   - No duplicate job IDs in the same batch
3. Tool opens database connection and begins transaction
4. Tool performs schema preflight (`updated_at` column must exist)
5. Tool validates per-item business rules and job existence:
   - `id` is positive integer
   - `status` in allowed set and no surrounding whitespace
   - job exists in database
6. If any per-item failures exist: rollback transaction and return structured failure results
7. If all items are valid: execute UPDATE statements with one shared timestamp
8. Commit transaction and return success results
9. Tool closes database connection

## Components and Interfaces

### MCP Tool Name

- `bulk_update_job_status`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "updates": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "integer",
            "minimum": 1,
            "description": "Job ID to update"
          },
          "status": {
            "type": "string",
            "enum": ["new", "shortlist", "reviewed", "reject", "resume_written", "applied"],
            "description": "Target status value"
          }
        },
        "required": ["id", "status"],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 100,
      "description": "Array of status updates to apply"
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override. Default: data/capture/jobs.db"
    }
  },
  "required": ["updates"],
  "additionalProperties": false
}
```

Additional semantic rule:
- `updates[*].id` values must be unique within one request batch.

### Output Schema (Success)

```json
{
  "updated_count": 3,
  "failed_count": 0,
  "results": [
    {
      "id": 123,
      "success": true
    },
    {
      "id": 456,
      "success": true
    },
    {
      "id": 789,
      "success": true
    }
  ]
}
```

### Output Schema (Validation Failure)

```json
{
  "updated_count": 0,
  "failed_count": 2,
  "results": [
    {
      "id": 123,
      "success": false,
      "error": "Job ID 123 does not exist"
    },
    {
      "id": 456,
      "success": false,
      "error": "Invalid status value: 'invalid_status'"
    }
  ]
}
```

### Error Schema (System Failure)

```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "retryable": false
  }
}
```

### Validation Module Interface

```python
def validate_batch_size(updates: list) -> None:
    """Raises ValidationError if batch size is invalid (>100)"""

def validate_unique_job_ids(updates: list[dict]) -> None:
    """Raises ValidationError if duplicate job IDs are present in one batch"""

def validate_update_item(update: dict) -> None:
    """Raises ValidationError if update item is malformed"""

def validate_job_id(job_id: any) -> int:
    """Returns validated integer job_id or raises ValidationError"""

def validate_status(status: any) -> str:
    """Returns validated status string or raises ValidationError"""

ALLOWED_STATUSES = {"new", "shortlist", "reviewed", "reject", "resume_written", "applied"}
```

### DB Writer Interface

```python
class JobsWriter:
    def __init__(self, db_path: str):
        """Initialize writer with database path"""
    
    def __enter__(self):
        """Open connection and begin transaction"""
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Rollback on exception, close connection"""
    
    def validate_jobs_exist(self, job_ids: list[int]) -> list[int]:
        """Returns list of missing job IDs (empty if all exist)"""

    def ensure_updated_at_column(self) -> None:
        """Raises schema error if jobs.updated_at column is missing"""
    
    def update_job_status(self, job_id: int, status: str, timestamp: str) -> None:
        """Execute UPDATE for single job. Raises on DB error."""
    
    def commit(self) -> None:
        """Commit transaction"""
    
    def rollback(self) -> None:
        """Rollback transaction"""
```

## Data Models

### Update Request Item

```python
{
    "id": int,        # Job ID (positive integer)
    "status": str     # Target status (validated against ALLOWED_STATUSES)
}
```

### Result Item

```python
{
    "id": int,           # Job ID
    "success": bool,     # True if updated, False if failed
    "error": str | None  # Error message if success=False
}
```

### Database Schema (Reference)

The tool operates on the `jobs` table:

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL UNIQUE,
    title TEXT,
    description TEXT,
    source TEXT,
    job_id TEXT,
    location TEXT,
    company TEXT,
    captured_at TEXT,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new',
    updated_at TEXT  -- Required for this tool; preflight fails if missing
);
```

Fields modified by this tool:
- `status` - Updated to new status value
- `updated_at` - Set to current UTC timestamp

## Validation Rules

### Batch Size Validation

- Empty batch (0 updates): Success with `updated_count=0`
- Batch size 1-100: Proceed with validation
- Batch size > 100: Return `VALIDATION_ERROR` immediately

### Update Item Validation

For each update in the batch:

1. **Job ID validation**:
   - Must be present (not null/undefined)
   - Must be an integer
   - Must be positive (>= 1)
   - Violation: failure entry in `results` with `success=false` and validation message

2. **Status validation**:
   - Must be present (not null/undefined/empty string)
   - Must be a string
   - Must be in `ALLOWED_STATUSES` set (case-sensitive)
   - Must not have leading/trailing whitespace
   - Violation: failure entry in `results` with `success=false` and validation message

3. **Job existence validation**:
   - Job ID must exist in database
   - Checked after input validation, before UPDATE execution
   - Violation: Include in `results` array with `success=false` and error message

### Validation Order

1. Batch size and request shape checks (fail fast if invalid)
2. Duplicate ID check (fail fast if duplicates exist)
3. Database connection (fail if DB not found)
4. Schema preflight (`updated_at` exists)
5. Per-item semantic validation (id/status rules)
6. Job existence check (query all IDs in batch)
7. If any per-item failure exists: rollback and return detailed failure results
8. If all pass: execute updates and commit

## Transaction Management

### Transaction Lifecycle

```python
with JobsWriter(db_path) as writer:
    # Transaction begins automatically

    # Schema preflight
    writer.ensure_updated_at_column()

    # Build per-item validation/existence failures
    failures = collect_item_failures(updates, writer)
    if failures:
        writer.rollback()
        return build_failure_response(updates, failures)

    # Execute all updates
    timestamp = get_current_utc_timestamp()
    for update in updates:
        writer.update_job_status(update["id"], update["status"], timestamp)
    
    # Commit if all succeed
    writer.commit()
    
# Rollback automatically on exception via __exit__
```

### Atomicity Guarantees

- All updates in a batch execute within a single transaction
- If any validation fails: rollback entire batch
- If any UPDATE fails: rollback entire batch
- No partial updates are committed
- Concurrent readers see either old state or new state, never partial state

### Idempotency Handling

- Updating a job to its current status is allowed (no-op)
- The UPDATE statement executes regardless of current status
- `updated_at` timestamp is refreshed even for no-op updates
- This ensures retry safety: same batch can be submitted multiple times

## SQL Implementation

### Job Existence Check

```sql
SELECT id FROM jobs WHERE id IN (?, ?, ?, ...)
```

Compare returned IDs with requested IDs to find missing ones.

### Status Update Statement

```sql
UPDATE jobs
SET status = ?,
    updated_at = ?
WHERE id = ?
```

Parameters:
- `status`: Validated status string
- `updated_at`: ISO 8601 UTC timestamp
- `id`: Validated job ID

### Timestamp Generation

```python
from datetime import datetime, timezone

def get_current_utc_timestamp() -> str:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")
```

Example output: `2026-02-04T03:47:36.966Z`

## Error Handling Strategy

### Error Categories

1. **VALIDATION_ERROR** (`retryable=false`)
   - Batch size > 100
   - Missing required top-level fields
   - Malformed input structure
   - Duplicate IDs in one batch

2. **DB_NOT_FOUND** (`retryable=false`)
   - Database file doesn't exist at specified path
   - Path is not accessible

3. **DB_ERROR** (`retryable=true` for transient errors, `false` for schema/constraint failures)
   - Connection failure
   - Missing `updated_at` schema column
   - Transaction failure
   - UPDATE execution failure
   - Commit failure

4. **INTERNAL_ERROR** (`retryable=true`)
   - Unexpected exceptions
   - Programming errors

### Error Response Patterns

**Request-level validation errors**:
- Return error immediately with `VALIDATION_ERROR` code
- Include descriptive message identifying the problem
- Do not open database connection

**Per-item validation/existence errors**:
- Return success response with `failed_count > 0`
- Include per-job results with `success=false` and item-level error message
- Transaction is rolled back

**Database errors during execution**:
- Return error with `DB_ERROR` code
- Include sanitized error message (no SQL fragments, no stack traces)
- Transaction is automatically rolled back

### Error Message Sanitization

Remove from error messages:
- Full file system paths (keep basename only)
- SQL statement fragments
- Stack traces
- Internal variable names

Keep in error messages:
- Error type/category
- Which validation rule failed
- Which job IDs were affected
- Actionable guidance for fixing the issue

## Write-Only Guarantees

The tool must never execute:

- `SELECT` queries that return job data (except for existence/schema validation)
- `INSERT` statements
- `DELETE` statements
- DDL statements (CREATE, ALTER, DROP)

Only allowed:
- `SELECT id FROM jobs WHERE id IN (...)` for existence validation
- `PRAGMA table_info(jobs)` (or equivalent schema metadata query) for `updated_at` preflight
- `UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?` for status updates

Database connections must always be closed via context management.

## Pseudocode

```python
async def bulk_update_job_status(args: dict) -> dict:
    # Request-level validation
    updates = args.get("updates")
    validate_request_shape(args)
    validate_batch_size(updates)
    validate_unique_job_ids(updates)

    if len(updates) == 0:
        return {"updated_count": 0, "failed_count": 0, "results": []}

    # Resolve database path
    db_path = resolve_db_path(args.get("db_path"))

    # Execute updates in transaction
    try:
        with JobsWriter(db_path) as writer:
            writer.ensure_updated_at_column()

            # Per-item business validation + existence checks
            failures = collect_item_failures(updates, writer)
            if failures:
                writer.rollback()
                return build_failure_response(updates, failures)

            # Execute all updates with same timestamp
            timestamp = get_current_utc_timestamp()
            for update in updates:
                writer.update_job_status(
                    update["id"],
                    update["status"],
                    timestamp
                )
            
            # Commit transaction
            writer.commit()
            
            return build_success_response(updates)
    
    except RequestValidationError as e:
        return build_validation_error(e)
    except DatabaseError as e:
        return build_db_error(e)
    except Exception as e:
        return build_internal_error(e)
```


## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Atomic batch updates

*For any* batch of valid status updates, either all updates are committed to the database or none are committed (no partial updates).

**Validates: Requirements 1.1, 4.1, 4.2, 4.3**

### Property 2: Batch size validation

*For any* batch with more than 100 updates, the tool should return a `VALIDATION_ERROR` without touching the database.

**Validates: Requirements 1.4**

### Property 3: Valid batch processing

*For any* batch of 1 to 100 updates with valid job IDs and status values, all updates should be processed successfully.

**Validates: Requirements 1.3, 1.5**

### Property 4: Status value validation

*For any* status value that is not in the allowed set `{new, shortlist, reviewed, reject, resume_written, applied}` (case-sensitive, no whitespace), the tool should return a per-item failure entry in `results`.

**Validates: Requirements 2.1, 2.2, 2.4, 2.5**

### Property 5: Job ID validation

*For any* job ID that is not a positive integer, the tool should return a per-item failure entry in `results`.

**Validates: Requirements 3.4**

### Property 6: Job existence validation

*For any* update referencing a non-existent job ID, the tool should rollback the entire batch and include that job ID in the failure response.

**Validates: Requirements 3.1, 3.2, 3.3**

### Property 7: Idempotent updates

*For any* job, updating it to its current status should succeed and be counted in `updated_count`, with the `updated_at` timestamp refreshed.

**Validates: Requirements 5.1, 5.3, 5.4, 5.5**

### Property 8: Batch idempotency

*For any* valid batch of updates, submitting the same batch multiple times should produce the same final `status` state.

**Validates: Requirements 5.2**

### Property 9: Timestamp consistency

*For any* batch of updates, all jobs in that batch should receive the same `updated_at` timestamp in ISO 8601 format.

**Validates: Requirements 6.1, 6.2, 6.3**

### Property 10: Timestamp field isolation

*For any* job update, only the `status` and `updated_at` fields should be modified; all other fields (including `created_at`, `captured_at`) should remain unchanged.

**Validates: Requirements 6.5, 11.5**

### Property 11: Database path override

*For any* valid database path provided via `db_path` parameter, the tool should use that path instead of the default.

**Validates: Requirements 7.2**

### Property 12: Connection cleanup

*For any* tool invocation (success or failure), the database connection should be properly closed after operations complete.

**Validates: Requirements 7.5**

### Property 13: SQL injection prevention

*For any* status value or job ID containing SQL special characters, the tool should treat them as literal data values, not SQL code.

**Validates: Requirements 7.6**

### Property 14: Write-only operations

*For any* tool invocation, the only SQL statements executed should be: (1) schema metadata query (`PRAGMA table_info(jobs)` or equivalent), (2) `SELECT id FROM jobs WHERE id IN (...)` for existence validation, and (3) `UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?` for status updates. No INSERT or DELETE should be executed, and no job detail rows should be returned to callers.

**Validates: Requirements 7.7, 11.1, 11.2, 11.3, 11.4, 11.5**

### Property 15: Response structure completeness

*For any* tool invocation, the response should contain `updated_count`, `failed_count`, and `results` array with one entry per input update, each containing `id`, `success`, and optional `error` fields.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4**

### Property 16: Result ordering preservation

*For any* batch of updates, the order of entries in the `results` array should match the order of updates in the input.

**Validates: Requirements 8.5**

### Property 17: Validation before execution

*For any* request-level invalid input (malformed structure, missing top-level parameters, duplicate IDs, out-of-range batch size), the tool should return a validation error without opening a database connection or executing any SQL.

**Validates: Requirements 10.2**

### Property 18: JSON serializability

*For any* tool response (success or error), all fields should be JSON-serializable without errors.

**Validates: Requirements 10.3**

### Property 19: Graceful error handling

*For any* malformed or missing input parameters, the tool should return a structured validation error (not crash or throw unhandled exceptions).

**Validates: Requirements 10.6**

### Property 20: Error code consistency

*For any* request-level validation failure, the error response should include code `VALIDATION_ERROR`, a descriptive message, and `retryable=false`.

**Validates: Requirements 9.1, 9.5**

### Property 21: Error message sanitization

*For any* error response, the message should not contain SQL fragments, full file paths (beyond basename), or stack traces.

**Validates: Requirements 9.6**

## Testing Strategy

### Dual Testing Approach

This feature requires both unit tests and property-based tests for comprehensive coverage:

- **Unit tests**: Verify specific examples, edge cases, and error conditions
- **Property tests**: Verify universal properties across randomized inputs

Both approaches are complementary and necessary. Unit tests catch concrete bugs in specific scenarios, while property tests verify general correctness across a wide input space.

### Unit Testing Focus

Unit tests should cover:

1. **Specific examples**:
   - Empty batch (0 updates) returns success with counts of 0
   - Single update to existing job succeeds
   - Database not found returns `DB_NOT_FOUND` error
   - Missing `updated_at` column returns schema error before any updates

2. **Edge cases**:
   - Null or empty status values rejected
   - Null or missing job IDs rejected
   - Status values with whitespace rejected
   - Batch of exactly 100 updates succeeds
   - Batch of 101 updates fails

3. **Error conditions**:
   - Non-existent job IDs reported in results
   - Invalid status and invalid job ID values reported as per-item failures
   - Malformed input structure produces request-level validation errors

4. **Integration points**:
   - MCP server tool registration
   - Database connection management
   - Transaction commit/rollback behavior

### Property-Based Testing Focus

Property tests should verify universal behaviors across randomized inputs:

1. **Atomicity**: Generate random batches with one invalid update; verify nothing is committed
2. **Validation**: Generate random invalid inputs; verify all produce appropriate errors
3. **Idempotency**: Generate random valid batches; submit twice; verify same final state
4. **Timestamp consistency**: Generate random batches; verify all jobs get same timestamp
5. **Field isolation**: Generate random updates; verify only `status` and `updated_at` change
6. **Response structure**: Generate random inputs; verify response always has required fields
7. **Ordering**: Generate random batches; verify result order matches input order

### Property Test Configuration

- **Minimum iterations**: 100 per property test (due to randomization)
- **Test tagging**: Each property test must reference its design document property
- **Tag format**: `# Feature: bulk-update-job-status, Property {number}: {property_text}`

### Testing Library Selection

For Python implementation:
- **Property testing**: Use `hypothesis` library for property-based testing
- **Unit testing**: Use `pytest` for unit tests
- **Database testing**: Use in-memory SQLite (`:memory:`) or temporary files for test isolation

### Test Data Generation

For property tests, generate:
- Random job IDs (positive integers, negative integers, zero, non-integers)
- Random status values (valid statuses, invalid strings, null, empty, with whitespace)
- Random batch sizes (0, 1-100, >100)
- Random database states (empty, with jobs, with various statuses)

### Read-Only Verification

Verify write-only guarantees by:
1. Capturing all SQL statements executed during test runs
2. Asserting only allowed statements are executed
3. Verifying no job data is returned in responses (only success/failure indicators)

## Security Considerations

1. **Parameterized SQL**: All SQL statements use parameter binding to prevent SQL injection
2. **Input validation**: All inputs validated before database operations
3. **Error sanitization**: Error messages sanitized to avoid information disclosure
4. **Transaction isolation**: SQLite default isolation prevents dirty reads
5. **Bounded batch size**: Maximum 100 updates prevents resource exhaustion
6. **Write-only access**: Tool cannot read sensitive job data, only update status

## Performance Considerations

1. **Batch efficiency**: Single transaction for all updates reduces overhead
2. **Existence check**: Single `SELECT id FROM jobs WHERE id IN (...)` query for all IDs
3. **Timestamp reuse**: Single timestamp generation for entire batch
4. **Connection pooling**: Not required for SQLite (file-based, no network overhead)
5. **Index usage**: `id` is primary key, so lookups are O(log n)

## Future Enhancements (Out of Scope)

1. **State machine validation**: Enforce legal status transitions (e.g., `new` → `shortlist` allowed, `applied` → `new` forbidden)
2. **Audit logging**: Detailed audit trail beyond timestamp (who, why, previous value)
3. **Partial success mode**: Option to commit successful updates even if some fail
4. **Bulk read-back**: Option to return updated job records in response
5. **Optimistic locking**: Version field to detect concurrent modifications
6. **Rate limiting**: Throttle update frequency per job or globally

## Requirement Traceability

- **Requirement 1** (batch updates): Covered by Input Schema, Transaction Management, Properties 1-3
- **Requirement 2** (status validation): Covered by Validation Rules, Property 4
- **Requirement 3** (job existence): Covered by Validation Rules, Property 6
- **Requirement 4** (atomicity): Covered by Transaction Management, Property 1
- **Requirement 5** (idempotency): Covered by Idempotency Handling, Properties 7-8
- **Requirement 6** (timestamps): Covered by SQL Implementation, Properties 9-10
- **Requirement 7** (database operations): Covered by DB Writer Interface, Properties 11-14
- **Requirement 8** (response format): Covered by Output Schema, Properties 15-16
- **Requirement 9** (error handling): Covered by Error Handling Strategy, Properties 20-21
- **Requirement 10** (MCP interface): Covered by Interfaces, Properties 17-19
- **Requirement 11** (write-only): Covered by Write-Only Guarantees, Property 14
