# MCP Server - JobWorkFlow Tools

Python MCP server for JobWorkFlow operations: reading new jobs, updating job statuses, and initializing tracker files for shortlisted jobs in SQLite database.

## Quick Start

```bash
# From repository root
uv sync

# Start server
cd mcp-server-python
./start_server.sh
```

For detailed deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Setup

Install dependencies using uv (from repository root):

```bash
uv sync
```

This creates a virtual environment at `.venv/` in the repository root with all dependencies (MCP server + jobspy).

## Project Structure

```
mcp-server-python/
├── server.py       # MCP server entry point (FastMCP)
├── tools/          # MCP tool implementations
│   ├── bulk_read_new_jobs.py              # Read tool handler
│   ├── bulk_update_job_status.py          # Write tool handler
│   └── initialize_shortlist_trackers.py   # Tracker initialization tool
├── db/             # Database access layer
│   ├── jobs_reader.py              # SQLite read operations
│   └── jobs_writer.py              # SQLite write operations
├── utils/          # Utility functions
│   ├── cursor.py                   # Cursor encoding/decoding
│   ├── pagination.py               # Pagination logic
│   ├── validation.py               # Input validation
│   ├── tracker_planner.py          # Deterministic tracker path planning
│   ├── tracker_renderer.py         # Tracker markdown rendering
│   └── file_ops.py                 # Atomic file operations
├── models/         # Data models and schemas
│   ├── errors.py                   # Error codes and structured errors
│   └── job.py                      # Job schema mapping
├── tests/          # Test suite
│   ├── test_bulk_read_new_jobs.py                  # Read tool integration tests
│   ├── test_bulk_update_job_status.py              # Write tool integration tests
│   ├── test_initialize_shortlist_trackers_tool.py  # Tracker tool integration tests
│   ├── test_server_integration.py                  # Server integration tests
│   ├── test_server_bulk_update_integration.py      # Bulk update server tests
│   ├── test_cursor.py                              # Cursor unit tests
│   ├── test_cursor_properties.py                   # Cursor property tests
│   ├── test_errors.py                              # Error handling tests
│   ├── test_job_schema.py                          # Schema mapping tests
│   ├── test_jobs_reader.py                         # Database reader tests
│   ├── test_jobs_writer.py                         # Database writer tests
│   ├── test_pagination.py                          # Pagination tests
│   ├── test_validation.py                          # Validation tests
│   ├── test_tracker_planner.py                     # Tracker planner tests
│   ├── test_tracker_renderer.py                    # Tracker renderer tests
│   └── test_file_ops_integration.py                # File operations tests
└── requirements.txt
```

## Running the Server

### Quick Start (Recommended)

Use the startup script for easy configuration:

```bash
./start_server.sh
```

The startup script provides:
- Automatic virtual environment activation
- Configuration validation
- Helpful error messages
- Command-line options for common settings

### Startup Script Options

```bash
# Show help
./start_server.sh --help

# Custom database path
./start_server.sh --db-path /path/to/jobs.db

# Debug logging to file
./start_server.sh --log-level DEBUG --log-file logs/server.log
```

### Direct Execution

The server runs in stdio mode by default, which is the standard transport for MCP servers:

```bash
cd mcp-server-python
source ../.venv/bin/activate  # Activate root venv
python server.py
```

The server will start and wait for MCP protocol messages on stdin/stdout. This is typically used when the server is invoked by an LLM agent or MCP client.

## Configuration

The server supports configuration via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `JOBWORKFLOW_ROOT` | Root directory for JobWorkFlow data | Repository root |
| `JOBWORKFLOW_DB` | Database file path | `data/capture/jobs.db` |
| `JOBWORKFLOW_LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` |
| `JOBWORKFLOW_LOG_FILE` | Log file path (enables file logging) | None (stderr only) |

### Configuration Examples

```bash
# Use custom database path
export JOBWORKFLOW_DB=/path/to/jobs.db
python server.py

# Enable debug logging to file
export JOBWORKFLOW_LOG_LEVEL=DEBUG
export JOBWORKFLOW_LOG_FILE=logs/server.log
python server.py

# Use JOBWORKFLOW_ROOT for all paths
export JOBWORKFLOW_ROOT=/opt/jobworkflow
python server.py
```

For comprehensive deployment instructions, see [DEPLOYMENT.md](DEPLOYMENT.md).

### Available Tools

#### bulk_read_new_jobs (Read-Only)

Retrieve jobs with status='new' from SQLite database in configurable batches with cursor-based pagination.

**Parameters:**
- `limit` (int, optional): Batch size (1-1000, default 50)
- `cursor` (str, optional): Opaque pagination cursor for retrieving next page
- `db_path` (str, optional): Database path override (default: data/capture/jobs.db)

**Response:**
- `jobs`: Array of job records with fixed schema
- `count`: Number of jobs in this page
- `has_more`: Boolean indicating if more pages exist
- `next_cursor`: Cursor for next page (null on terminal page)

**Error Response:**
- `error`: Object with `code`, `message`, and `retryable` fields

#### bulk_update_job_status (Write-Only)

Update multiple job statuses in a single atomic transaction. Validates status values, checks job existence, and ensures all-or-nothing semantics.

**Parameters:**
- `updates` (array, required): Array of update items, each containing:
  - `id` (int): Job ID to update (must be positive integer)
  - `status` (str): Target status value (must be one of: `new`, `shortlist`, `reviewed`, `reject`, `resume_written`, `applied`)
- `db_path` (str, optional): Database path override (default: data/capture/jobs.db)

**Response (Success):**
```json
{
  "updated_count": 3,
  "failed_count": 0,
  "results": [
    {"id": 123, "success": true},
    {"id": 456, "success": true},
    {"id": 789, "success": true}
  ]
}
```

**Response (Validation Failure):**
```json
{
  "updated_count": 0,
  "failed_count": 2,
  "results": [
    {"id": 123, "success": false, "error": "Job ID 123 does not exist"},
    {"id": 456, "success": false, "error": "Invalid status value: 'invalid_status'"}
  ]
}
```

**Error Response (System Failure):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "retryable": false
  }
}
```

**Validation Rules:**
- Batch size: 0-100 updates (empty batch returns success with zero counts)
- Job IDs: Must be positive integers and exist in database
- Status values: Must be one of the allowed statuses (case-sensitive, no whitespace)
- No duplicate job IDs within one batch
- All updates succeed or all fail (atomic transaction)

**Error Codes:**
- `VALIDATION_ERROR` (retryable=false): Invalid input parameters, batch size > 100, duplicate IDs, malformed request
- `DB_NOT_FOUND` (retryable=false): Database file doesn't exist at specified path
- `DB_ERROR` (retryable varies): Database operation failure, missing schema column, transaction failure
- `INTERNAL_ERROR` (retryable=true): Unexpected server error

**Retry Guidance:**
- `VALIDATION_ERROR`: Fix input parameters before retrying (not retryable)
- `DB_NOT_FOUND`: Verify database path and file existence (not retryable)
- `DB_ERROR`: Check error message for details; transient errors may be retryable
- `INTERNAL_ERROR`: Safe to retry after brief delay
- Idempotent updates: Same batch can be submitted multiple times safely

#### initialize_shortlist_trackers (Projection Tool)

Initialize deterministic tracker markdown files for jobs with `status='shortlist'`. This projection-oriented tool reads from the database (SSOT) and creates file-based tracker notes under `trackers/` with linked application workspace paths. The tool does NOT modify database records.

**Parameters:**
- `limit` (int, optional): Number of shortlist jobs to process (1-200, default 50)
- `db_path` (str, optional): Database path override (default: data/capture/jobs.db)
- `trackers_dir` (str, optional): Trackers directory override (default: trackers/)
- `force` (bool, optional): Overwrite existing tracker files (default: false)
- `dry_run` (bool, optional): Compute outcomes without writing files (default: false)

**Response (Success):**
```json
{
  "created_count": 12,
  "skipped_count": 3,
  "failed_count": 0,
  "results": [
    {
      "id": 3629,
      "job_id": "4368663835",
      "tracker_path": "trackers/2026-02-04-amazon-3629.md",
      "action": "created",
      "success": true
    },
    {
      "id": 3630,
      "job_id": "4368669999",
      "tracker_path": "trackers/2026-02-04-meta-3630.md",
      "action": "skipped_exists",
      "success": true
    }
  ]
}
```

**Response (Partial Failure):**
```json
{
  "created_count": 2,
  "skipped_count": 0,
  "failed_count": 1,
  "results": [
    {
      "id": 3629,
      "job_id": "4368663835",
      "tracker_path": "trackers/2026-02-04-amazon-3629.md",
      "action": "created",
      "success": true
    },
    {
      "id": 3631,
      "job_id": "4368670000",
      "action": "failed",
      "success": false,
      "error": "Failed to write tracker file"
    }
  ]
}
```

**Error Response (System Failure):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "retryable": false
  }
}
```

**Behavior:**
- Reads only jobs with `status='shortlist'` ordered by `captured_at DESC, id DESC`
- Creates deterministic tracker filenames: `<captured_date>-<company_slug>-<id>.md`
- Creates workspace directories: `data/applications/<slug>/resume/` and `cover/`
- Tracker files include stable frontmatter and `## Job Description` / `## Notes` sections
- Initial tracker status is set to `Reviewed`
- Idempotent: existing files are skipped unless `force=true`
- Atomic writes: uses temporary file + rename to prevent partial writes
- Continues processing on per-item failures (partial success supported)
- Database remains read-only (no status updates or mutations)

**Validation Rules:**
- `limit`: Must be integer in range 1-200 (default: 50)
- `db_path`: Optional non-empty string
- `trackers_dir`: Optional non-empty string
- `force`: Optional boolean (default: false)
- `dry_run`: Optional boolean (default: false)
- No shortlist jobs available: Returns success with zero counts

**Error Codes:**
- `VALIDATION_ERROR` (retryable=false): Invalid input parameters (limit out of range, invalid types)
- `DB_NOT_FOUND` (retryable=false): Database file doesn't exist at specified path
- `DB_ERROR` (retryable varies): Database connection or query failure
- `INTERNAL_ERROR` (retryable=true): Unexpected server error

**Retry Guidance:**
- `VALIDATION_ERROR`: Fix input parameters before retrying (not retryable)
- `DB_NOT_FOUND`: Verify database path and file existence (not retryable)
- `DB_ERROR`: Check error message for details; transient errors may be retryable
- `INTERNAL_ERROR`: Safe to retry after brief delay
- Idempotent operation: Same parameters can be submitted multiple times safely with `force=false`

#### update_tracker_status (Projection Tool)

Update tracker frontmatter status with transition policy checks and Resume Written artifact guardrails. This projection-oriented tool operates only on tracker files and does NOT modify database records.

**Parameters:**
- `tracker_path` (str, required): Path to tracker markdown file
- `target_status` (str, required): Target status value (must be one of: `Reviewed`, `Resume Written`, `Applied`, `Interview`, `Offer`, `Rejected`, `Ghosted`)
- `dry_run` (bool, optional): Preview changes without writing files (default: false)
- `force` (bool, optional): Allow transition-policy bypass with warning (default: false)

**Response (Success):**
```json
{
  "tracker_path": "trackers/2026-02-05-amazon.md",
  "previous_status": "Reviewed",
  "target_status": "Resume Written",
  "action": "updated",
  "success": true,
  "dry_run": false,
  "guardrail_check_passed": true,
  "warnings": []
}
```

**Response (Blocked - Guardrail Failure):**
```json
{
  "tracker_path": "trackers/2026-02-05-amazon.md",
  "previous_status": "Reviewed",
  "target_status": "Resume Written",
  "action": "blocked",
  "success": false,
  "dry_run": false,
  "guardrail_check_passed": false,
  "error": "resume.pdf is missing",
  "warnings": []
}
```

**Response (No-op - Same Status):**
```json
{
  "tracker_path": "trackers/2026-02-05-amazon.md",
  "previous_status": "Reviewed",
  "target_status": "Reviewed",
  "action": "noop",
  "success": true,
  "dry_run": false,
  "warnings": []
}
```

**Error Response (System Failure):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR | FILE_NOT_FOUND | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "retryable": false
  }
}
```

**Behavior:**
- Updates only the `status` field in tracker frontmatter
- Preserves all non-status frontmatter fields and body content
- Enforces transition policy for forward progression:
  - `Reviewed -> Resume Written`
  - `Resume Written -> Applied`
- Allows terminal outcomes (`Rejected`, `Ghosted`) from any status
- Same status target returns `noop` action
- Atomic writes: uses temporary file + rename to prevent partial writes
- Database remains read-only (no DB mutations)

**Resume Written Guardrails:**

When `target_status='Resume Written'`, the tool performs strict artifact validation:
- Verifies `resume.pdf` exists and has non-zero size
- Verifies companion `resume.tex` exists
- Scans `resume.tex` for placeholder tokens:
  - `PROJECT-AI-`
  - `PROJECT-BE-`
  - `WORK-BULLET-POINT-`
- Any guardrail failure blocks the update and returns detailed error

**Validation Rules:**
- `tracker_path`: Required non-empty string, file must exist
- `target_status`: Must be one of the canonical statuses (case-sensitive, no whitespace)
- `dry_run`: Optional boolean (default: false)
- `force`: Optional boolean (default: false)
- Transition policy violations are blocked unless `force=true`
- Force mode allows policy bypass but includes warning in response

**Error Codes:**
- `VALIDATION_ERROR` (retryable=false): Invalid input parameters, unknown status, malformed tracker
- `FILE_NOT_FOUND` (retryable=false): Tracker file doesn't exist at specified path
- `INTERNAL_ERROR` (retryable=true): Unexpected server error

**Retry Guidance:**
- `VALIDATION_ERROR`: Fix input parameters or tracker content before retrying (not retryable)
- `FILE_NOT_FOUND`: Verify tracker path and file existence (not retryable)
- Guardrail failures: Fix artifacts (create PDF, remove placeholders) before retrying
- `INTERNAL_ERROR`: Safe to retry after brief delay
- Idempotent operation: Same parameters can be submitted multiple times safely

#### finalize_resume_batch (Commit Tool)

Finalize multiple resume compilation jobs in one atomic batch. This commit-focused tool updates database completion audit fields and synchronizes tracker status to `Resume Written` after successful resume compilation. Validates artifacts before commit and applies compensation fallback on failure.

**Parameters:**
- `items` (array, required): Array of finalization entries, each containing:
  - `id` (int): Job database ID (must be positive integer)
  - `tracker_path` (str): Path to tracker markdown file
  - `resume_pdf_path` (str, optional): Override for resume PDF path (resolved from tracker if omitted)
- `run_id` (str, optional): Batch run identifier (auto-generated if omitted)
- `db_path` (str, optional): Database path override (default: data/capture/jobs.db)
- `dry_run` (bool, optional): Preview mode without writes (default: false)

**Response (Success):**
```json
{
  "run_id": "run_20260206_8f2f8f1c",
  "finalized_count": 2,
  "failed_count": 1,
  "dry_run": false,
  "warnings": [],
  "results": [
    {
      "id": 3711,
      "tracker_path": "trackers/2026-02-05-amazon.md",
      "resume_pdf_path": "data/applications/amazon/resume/resume.pdf",
      "action": "finalized",
      "success": true
    },
    {
      "id": 3712,
      "tracker_path": "trackers/2026-02-05-meta.md",
      "resume_pdf_path": "data/applications/meta/resume/resume.pdf",
      "action": "failed",
      "success": false,
      "error": "resume.tex contains placeholder tokens"
    }
  ]
}
```

**Response (Dry-Run):**
```json
{
  "run_id": "run_20260206_8f2f8f1c",
  "finalized_count": 2,
  "failed_count": 0,
  "dry_run": true,
  "results": [
    {
      "id": 3711,
      "tracker_path": "trackers/2026-02-05-amazon.md",
      "resume_pdf_path": "data/applications/amazon/resume/resume.pdf",
      "action": "would_finalize",
      "success": true
    }
  ]
}
```

**Error Response (System Failure):**
```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error description",
    "retryable": false
  }
}
```

**Behavior:**
- Database status remains the SSOT (Single Source of Truth)
- Tracker status is a synchronized projection for Obsidian workflow
- Does NOT perform resume compilation or content rewriting
- Does NOT create new trackers or modify unrelated jobs
- Processes items in input order with per-item isolation
- Continues processing remaining items after one item fails
- Per-item failures are reported in results (not top-level fatal)

**Finalization Sequence (Success Path):**
1. Validate all item preconditions (tracker exists, artifacts valid, no placeholders)
2. Update DB: `status='resume_written'`, set audit fields (`resume_pdf_path`, `resume_written_at`, `run_id`, increment `attempt_count`, clear `last_error`)
3. Update tracker frontmatter: `status='Resume Written'`
4. Mark item as finalized

**Failure Compensation (Fallback):**
- If tracker sync fails after DB update, apply compensation fallback:
  - Set DB `status='reviewed'`
  - Write `last_error` with sanitized failure reason
  - Update `updated_at` timestamp
  - Mark item as failed
- This ensures failed finalization does not remain in `resume_written` status
- Fallback behavior is applied per-item (not all-or-nothing for entire batch)

**Artifact Validation (Preconditions):**
Before committing, the tool validates:
- Tracker file exists and is readable
- `resume.pdf` exists and has non-zero file size
- Companion `resume.tex` exists
- `resume.tex` does not contain placeholder tokens:
  - `PROJECT-AI-`
  - `PROJECT-BE-`
  - `WORK-BULLET-POINT-`
- Any validation failure blocks finalization for that item

**Dry-Run Mode:**
- When `dry_run=true`, performs full validation and planning
- Does NOT mutate DB rows
- Does NOT write tracker files
- Returns predicted actions (`would_finalize`, `would_fail`)
- Useful for previewing outcomes before committing

**Validation Rules:**
- Batch size: 0-100 items (empty batch returns success with zero counts)
- Each item requires `id` (positive integer) and `tracker_path` (non-empty string)
- No duplicate job IDs within one batch
- All validation checks must pass before commit
- Results array preserves input order

**Error Codes:**
- `VALIDATION_ERROR` (retryable=false): Invalid input parameters, batch size > 100, duplicate IDs, malformed request
- `DB_NOT_FOUND` (retryable=false): Database file doesn't exist at specified path
- `DB_ERROR` (retryable varies): Database operation failure, missing schema column, transaction failure
- `INTERNAL_ERROR` (retryable=true): Unexpected server error

**Retry Guidance:**
- `VALIDATION_ERROR`: Fix input parameters before retrying (not retryable)
- `DB_NOT_FOUND`: Verify database path and file existence (not retryable)
- `DB_ERROR`: Check error message for details; transient errors may be retryable
- `INTERNAL_ERROR`: Safe to retry after brief delay
- Per-item artifact failures: Fix artifacts (create PDF, remove placeholders) before retrying
- Idempotent: Re-running the same valid item keeps final status as `resume_written`

## Testing

Run all tests:
```bash
# From repository root
uv run pytest mcp-server-python/tests/

# Or from mcp-server-python/ with activated venv
source ../.venv/bin/activate
pytest tests/
```

Run specific test file:
```bash
uv run pytest mcp-server-python/tests/test_bulk_read_new_jobs.py -v
```

Run with coverage:
```bash
uv run pytest mcp-server-python/tests/ --cov=mcp-server-python --cov-report=html
```

## Logging and Debugging

### Enable Debug Logging

```bash
export JOBWORKFLOW_LOG_LEVEL=DEBUG
./start_server.sh
```

### Log to File

```bash
export JOBWORKFLOW_LOG_FILE=logs/server.log
./start_server.sh
```

### Log Format

Logs include timestamp, logger name, level, and message:

```
2024-02-04 10:30:15 - __main__ - INFO - Starting JobWorkFlow MCP Server
2024-02-04 10:30:15 - __main__ - INFO - Database path: /path/to/jobs.db
2024-02-04 10:30:15 - __main__ - INFO - Server starting in stdio mode
```

### Common Issues

**Database not found**: Check `JOBWORKFLOW_DB` environment variable and verify file exists.

**Permission denied**: Ensure read access to database and write access to log directory.

**Import errors**: Activate virtual environment and reinstall dependencies.

For detailed troubleshooting, see [DEPLOYMENT.md](DEPLOYMENT.md).

## Usage Examples

### bulk_read_new_jobs

The tool is designed to be invoked by MCP clients (LLM agents). Here's how the tool works:

```python
# First page - retrieve first 50 jobs (default limit)
result = bulk_read_new_jobs_tool()
# Returns: {"jobs": [...], "count": 50, "has_more": true, "next_cursor": "eyJ..."}

# Second page - use cursor from first page
result = bulk_read_new_jobs_tool(cursor="eyJ...")
# Returns: {"jobs": [...], "count": 50, "has_more": true, "next_cursor": "eyJ..."}

# Custom limit
result = bulk_read_new_jobs_tool(limit=100)
# Returns: {"jobs": [...], "count": 100, "has_more": false, "next_cursor": null}

# Custom database path
result = bulk_read_new_jobs_tool(db_path="custom/path/jobs.db")
# Returns: {"jobs": [...], "count": 10, "has_more": false, "next_cursor": null}
```

### bulk_update_job_status

Update job statuses in atomic batches:

```python
# Update single job status
result = bulk_update_job_status_tool(
    updates=[{"id": 123, "status": "shortlist"}]
)
# Returns: {"updated_count": 1, "failed_count": 0, "results": [{"id": 123, "success": true}]}

# Update multiple jobs in one atomic transaction
result = bulk_update_job_status_tool(
    updates=[
        {"id": 123, "status": "shortlist"},
        {"id": 456, "status": "reviewed"},
        {"id": 789, "status": "reject"}
    ]
)
# Returns: {"updated_count": 3, "failed_count": 0, "results": [...]}

# Empty batch (valid - returns success with zero counts)
result = bulk_update_job_status_tool(updates=[])
# Returns: {"updated_count": 0, "failed_count": 0, "results": []}

# Validation failure - non-existent job ID
result = bulk_update_job_status_tool(
    updates=[{"id": 999999, "status": "shortlist"}]
)
# Returns: {"updated_count": 0, "failed_count": 1, "results": [{"id": 999999, "success": false, "error": "Job ID 999999 does not exist"}]}

# Validation failure - invalid status
result = bulk_update_job_status_tool(
    updates=[{"id": 123, "status": "invalid_status"}]
)
# Returns: {"updated_count": 0, "failed_count": 1, "results": [{"id": 123, "success": false, "error": "Invalid status value: 'invalid_status'"}]}

# Custom database path
result = bulk_update_job_status_tool(
    updates=[{"id": 123, "status": "applied"}],
    db_path="custom/path/jobs.db"
)
# Returns: {"updated_count": 1, "failed_count": 0, "results": [{"id": 123, "success": true}]}

# Idempotent update - updating to current status succeeds
result = bulk_update_job_status_tool(
    updates=[{"id": 123, "status": "shortlist"}]  # Job 123 already has status='shortlist'
)
# Returns: {"updated_count": 1, "failed_count": 0, "results": [{"id": 123, "success": true}]}
```

**Important Notes:**
- All updates in a batch are atomic: either all succeed or all fail
- If any validation fails, the entire batch is rolled back
- Updates are idempotent: safe to retry the same batch multiple times
- All jobs in a batch receive the same `updated_at` timestamp
- Maximum batch size is 100 updates

### initialize_shortlist_trackers

Initialize tracker markdown files for shortlisted jobs:

```python
# Initialize trackers for first 50 shortlisted jobs (default limit)
result = initialize_shortlist_trackers_tool()
# Returns: {"created_count": 45, "skipped_count": 5, "failed_count": 0, "results": [...]}

# Initialize with custom limit
result = initialize_shortlist_trackers_tool(limit=100)
# Returns: {"created_count": 100, "skipped_count": 0, "failed_count": 0, "results": [...]}

# Dry-run mode - compute outcomes without writing files
result = initialize_shortlist_trackers_tool(limit=20, dry_run=True)
# Returns: {"created_count": 15, "skipped_count": 5, "failed_count": 0, "results": [...]}
# Note: No files or directories are created in dry-run mode

# Force overwrite existing tracker files
result = initialize_shortlist_trackers_tool(limit=10, force=True)
# Returns: {"created_count": 10, "skipped_count": 0, "failed_count": 0, "results": [...]}
# Note: All 10 trackers are overwritten even if they already exist

# Custom paths
result = initialize_shortlist_trackers_tool(
    db_path="custom/path/jobs.db",
    trackers_dir="custom/trackers"
)
# Returns: {"created_count": 50, "skipped_count": 0, "failed_count": 0, "results": [...]}

# Empty shortlist - returns success with zero counts
result = initialize_shortlist_trackers_tool()
# Returns: {"created_count": 0, "skipped_count": 0, "failed_count": 0, "results": []}

# Idempotent behavior - repeated runs skip existing files
result = initialize_shortlist_trackers_tool(limit=10)
# First run: {"created_count": 10, "skipped_count": 0, "failed_count": 0, "results": [...]}
result = initialize_shortlist_trackers_tool(limit=10)
# Second run: {"created_count": 0, "skipped_count": 10, "failed_count": 0, "results": [...]}

# Partial failure - continues processing other items
result = initialize_shortlist_trackers_tool(limit=20)
# Returns: {"created_count": 18, "skipped_count": 0, "failed_count": 2, "results": [
#   {"id": 123, "tracker_path": "trackers/2026-02-04-amazon-123.md", "action": "created", "success": true},
#   ...
#   {"id": 456, "action": "failed", "success": false, "error": "Failed to write tracker file"}
# ]}
```

**Important Notes:**
- Tool is projection-oriented: reads from database (SSOT) and creates file-based tracker projections
- Database records are never modified (read-only operations)
- Tracker files include stable frontmatter with job metadata and workspace links
- Workspace directories are created automatically: `data/applications/<slug>/resume/` and `cover/`
- Deterministic tracker filenames prevent collisions: `<date>-<company_slug>-<id>.md`
- Atomic writes prevent partial file corruption
- Idempotent with `force=false`: safe to run multiple times
- Dry-run mode useful for previewing outcomes before actual writes

### update_tracker_status

Update tracker status with transition policy and guardrail enforcement:

```python
# Successful status update
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Resume Written"
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Resume Written", 
#           "action": "updated", "success": true, "dry_run": false, "guardrail_check_passed": true, "warnings": []}

# No-op - same status
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Reviewed"  # Already at Reviewed
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Reviewed",
#           "action": "noop", "success": true, "dry_run": false, "warnings": []}

# Dry-run mode - preview without writing
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Resume Written",
    dry_run=True
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Resume Written",
#           "action": "would_update", "success": true, "dry_run": true, "guardrail_check_passed": true, "warnings": []}

# Blocked - guardrail failure (missing resume.pdf)
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Resume Written"
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Resume Written",
#           "action": "blocked", "success": false, "dry_run": false, "guardrail_check_passed": false,
#           "error": "resume.pdf is missing", "warnings": []}

# Blocked - placeholder tokens remain in resume.tex
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Resume Written"
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Resume Written",
#           "action": "blocked", "success": false, "dry_run": false, "guardrail_check_passed": false,
#           "error": "Placeholder tokens found in resume.tex: PROJECT-AI-1, WORK-BULLET-POINT-2", "warnings": []}

# Force mode - bypass transition policy with warning
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Applied",  # Skip Resume Written step
    force=True
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Applied",
#           "action": "updated", "success": true, "dry_run": false,
#           "warnings": ["Transition policy bypassed with force=true"]}

# Terminal outcome - allowed from any status
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="Rejected"
)
# Returns: {"tracker_path": "...", "previous_status": "Reviewed", "target_status": "Rejected",
#           "action": "updated", "success": true, "dry_run": false, "warnings": []}

# Validation error - invalid status
result = update_tracker_status_tool(
    tracker_path="trackers/2026-02-05-amazon.md",
    target_status="InvalidStatus"
)
# Returns: {"error": {"code": "VALIDATION_ERROR", "message": "Invalid status: InvalidStatus", "retryable": false}}

# File not found error
result = update_tracker_status_tool(
    tracker_path="trackers/nonexistent.md",
    target_status="Reviewed"
)
# Returns: {"error": {"code": "FILE_NOT_FOUND", "message": "Tracker file not found: trackers/nonexistent.md", "retryable": false}}
```

**Important Notes:**
- Tool is projection-oriented: operates only on tracker files, never modifies database
- Atomic writes prevent partial file corruption
- Preserves all frontmatter fields except `status` and entire body content
- Transition policy enforces safe forward progression
- Resume Written guardrails ensure quality before marking complete
- Dry-run mode useful for previewing outcomes before actual writes
- Force mode allows policy bypass but includes warning
- Idempotent: safe to run multiple times with same parameters

### finalize_resume_batch

Finalize resume compilation jobs with artifact validation and compensation fallback:

```python
# Finalize single job
result = finalize_resume_batch_tool(
    items=[{
        "id": 3711,
        "tracker_path": "trackers/2026-02-05-amazon.md"
    }]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 1, "failed_count": 0, 
#           "dry_run": false, "results": [{"id": 3711, "tracker_path": "...", 
#           "resume_pdf_path": "data/applications/amazon/resume/resume.pdf", 
#           "action": "finalized", "success": true}]}

# Finalize multiple jobs in one batch
result = finalize_resume_batch_tool(
    items=[
        {"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"},
        {"id": 3712, "tracker_path": "trackers/2026-02-05-meta.md"}
    ]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 2, "failed_count": 0, 
#           "dry_run": false, "results": [...]}

# Empty batch (valid - returns success with zero counts)
result = finalize_resume_batch_tool(items=[])
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 0, "failed_count": 0, 
#           "dry_run": false, "results": []}

# Dry-run to preview outcomes without writes
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}],
    dry_run=True
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 1, "failed_count": 0, 
#           "dry_run": true, "results": [{"id": 3711, "action": "would_finalize", "success": true}]}

# Use custom run_id and db_path
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}],
    run_id="run_20260206_custom",
    db_path="custom/path/jobs.db"
)
# Returns: {"run_id": "run_20260206_custom", "finalized_count": 1, "failed_count": 0, 
#           "dry_run": false, "results": [...]}

# Override resume_pdf_path for specific item
result = finalize_resume_batch_tool(
    items=[{
        "id": 3711,
        "tracker_path": "trackers/2026-02-05-amazon.md",
        "resume_pdf_path": "custom/path/resume.pdf"
    }]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 1, "failed_count": 0, 
#           "dry_run": false, "results": [...]}

# Item failure - missing resume.pdf
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 0, "failed_count": 1, 
#           "dry_run": false, "results": [{"id": 3711, "action": "failed", "success": false, 
#           "error": "resume.pdf is missing"}]}

# Item failure - placeholder tokens remain in resume.tex
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 0, "failed_count": 1, 
#           "dry_run": false, "results": [{"id": 3711, "action": "failed", "success": false, 
#           "error": "Placeholder tokens found in resume.tex: PROJECT-AI-1, WORK-BULLET-POINT-2"}]}

# Mixed batch - continues processing after one item fails
result = finalize_resume_batch_tool(
    items=[
        {"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"},  # Success
        {"id": 3712, "tracker_path": "trackers/2026-02-05-meta.md"},    # Fails (missing PDF)
        {"id": 3713, "tracker_path": "trackers/2026-02-05-google.md"}   # Success
    ]
)
# Returns: {"run_id": "run_20260206_8f2f8f1c", "finalized_count": 2, "failed_count": 1, 
#           "dry_run": false, "results": [
#               {"id": 3711, "action": "finalized", "success": true},
#               {"id": 3712, "action": "failed", "success": false, "error": "resume.pdf is missing"},
#               {"id": 3713, "action": "finalized", "success": true}
#           ]}

# Validation error - batch size exceeds 100
result = finalize_resume_batch_tool(items=[...])  # 101 items
# Returns: {"error": {"code": "VALIDATION_ERROR", "message": "Batch size exceeds maximum of 100", 
#           "retryable": false}}

# Validation error - duplicate job IDs
result = finalize_resume_batch_tool(
    items=[
        {"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"},
        {"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}  # Duplicate
    ]
)
# Returns: {"error": {"code": "VALIDATION_ERROR", "message": "Duplicate job IDs in batch: 3711", 
#           "retryable": false}}

# Idempotent - re-running same valid item keeps status as resume_written
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}]
)
# First run: {"finalized_count": 1, "failed_count": 0, "results": [{"action": "finalized", "success": true}]}
result = finalize_resume_batch_tool(
    items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}]
)
# Second run: {"finalized_count": 1, "failed_count": 0, "results": [{"action": "finalized", "success": true}]}
```

**Important Notes:**
- Tool is commit-focused: performs final write-back after resume compilation succeeds
- Database status remains the SSOT (Single Source of Truth)
- Tracker status is a synchronized projection for Obsidian workflow
- Does NOT perform resume compilation or content rewriting
- Validates artifacts before commit (tracker, PDF, TEX, placeholders)
- Applies compensation fallback on tracker sync failure (sets DB status='reviewed' with last_error)
- Batch continues processing remaining items after one item fails
- Per-item failures are reported in results (not top-level fatal)
- Dry-run mode useful for previewing outcomes before committing
- Idempotent: safe to retry the same batch multiple times
- Results array preserves input order

## Input/Output Schemas

### bulk_read_new_jobs Input Schema

```json
{
  "type": "object",
  "properties": {
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "default": 50,
      "description": "Number of jobs to retrieve in this page"
    },
    "cursor": {
      "type": "string",
      "description": "Opaque pagination cursor from previous response"
    },
    "db_path": {
      "type": "string",
      "description": "Optional database path override"
    }
  }
}
```

### bulk_read_new_jobs Output Schema

```json
{
  "type": "object",
  "properties": {
    "jobs": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "job_id": {"type": "string"},
          "title": {"type": "string"},
          "company": {"type": "string"},
          "description": {"type": "string"},
          "url": {"type": "string"},
          "location": {"type": "string"},
          "source": {"type": "string"},
          "status": {"type": "string"},
          "captured_at": {"type": "string"}
        }
      }
    },
    "count": {"type": "integer"},
    "has_more": {"type": "boolean"},
    "next_cursor": {"type": ["string", "null"]}
  }
}
```

### bulk_update_job_status Input Schema

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
      "description": "Optional database path override"
    }
  },
  "required": ["updates"],
  "additionalProperties": false
}
```

**Additional Semantic Rules:**
- `updates[*].id` values must be unique within one request batch
- All job IDs must exist in the database
- Status values are case-sensitive and must not have leading/trailing whitespace

### initialize_shortlist_trackers Input Schema

```json
{
  "type": "object",
  "properties": {
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200,
      "default": 50,
      "description": "Number of shortlist jobs to process"
    },
    "db_path": {
      "type": "string",
      "description": "Optional database path override"
    },
    "trackers_dir": {
      "type": "string",
      "description": "Optional trackers directory override (default: trackers/)"
    },
    "force": {
      "type": "boolean",
      "default": false,
      "description": "If true, overwrite existing tracker files"
    },
    "dry_run": {
      "type": "boolean",
      "default": false,
      "description": "If true, compute outcomes without writing files"
    }
  },
  "additionalProperties": false
}
```

### initialize_shortlist_trackers Output Schema (Success)

```json
{
  "type": "object",
  "properties": {
    "created_count": {
      "type": "integer",
      "description": "Number of trackers created (includes overwritten)"
    },
    "skipped_count": {
      "type": "integer",
      "description": "Number of trackers skipped (already exist, force=false)"
    },
    "failed_count": {
      "type": "integer",
      "description": "Number of trackers that failed"
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "integer",
            "description": "Database job ID"
          },
          "job_id": {
            "type": "string",
            "description": "External job identifier"
          },
          "tracker_path": {
            "type": "string",
            "description": "Path to tracker file (optional on hard failure)"
          },
          "action": {
            "type": "string",
            "enum": ["created", "skipped_exists", "overwritten", "failed"],
            "description": "Action taken for this job"
          },
          "success": {
            "type": "boolean",
            "description": "Whether operation succeeded"
          },
          "error": {
            "type": "string",
            "description": "Error message (only present on failure)"
          }
        },
        "required": ["id", "job_id", "action", "success"]
      }
    }
  },
  "required": ["created_count", "skipped_count", "failed_count", "results"]
}
```

**Additional Semantic Rules:**
- Results array maintains selection order (ordered by `captured_at DESC, id DESC`)
- `created_count` includes both newly created and overwritten trackers
- `tracker_path` may be omitted for hard failures before path planning
- Empty shortlist returns success with all counts at zero

### update_tracker_status Input Schema

```json
{
  "type": "object",
  "properties": {
    "tracker_path": {
      "type": "string",
      "description": "Path to tracker markdown file"
    },
    "target_status": {
      "type": "string",
      "enum": ["Reviewed", "Resume Written", "Applied", "Interview", "Offer", "Rejected", "Ghosted"],
      "description": "Target status value (case-sensitive)"
    },
    "dry_run": {
      "type": "boolean",
      "default": false,
      "description": "If true, preview changes without writing files"
    },
    "force": {
      "type": "boolean",
      "default": false,
      "description": "If true, allow transition-policy bypass with warning"
    }
  },
  "required": ["tracker_path", "target_status"],
  "additionalProperties": false
}
```

**Additional Semantic Rules:**
- `tracker_path` must point to existing tracker file with valid YAML frontmatter
- `target_status` is case-sensitive and must not have leading/trailing whitespace
- Transition policy enforces forward progression unless `force=true`
- Resume Written guardrails are always enforced (cannot be bypassed with force)

### update_tracker_status Output Schema (Success)

```json
{
  "type": "object",
  "properties": {
    "tracker_path": {
      "type": "string",
      "description": "Path to tracker file"
    },
    "previous_status": {
      "type": "string",
      "description": "Status before update"
    },
    "target_status": {
      "type": "string",
      "description": "Requested target status"
    },
    "action": {
      "type": "string",
      "enum": ["updated", "noop", "blocked", "would_update"],
      "description": "Action taken (would_update only in dry-run mode)"
    },
    "success": {
      "type": "boolean",
      "description": "Whether operation succeeded"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Whether this was a dry-run"
    },
    "guardrail_check_passed": {
      "type": "boolean",
      "description": "Whether guardrail checks passed (only present when evaluated)"
    },
    "warnings": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Optional warnings (e.g., force mode bypass)"
    },
    "error": {
      "type": "string",
      "description": "Error message (only present when action=blocked)"
    }
  },
  "required": ["tracker_path", "previous_status", "target_status", "action", "success", "dry_run"]
}
```

**Additional Semantic Rules:**
- `action=noop` when target status equals current status
- `action=blocked` when guardrails fail or transition policy violated without force
- `action=updated` when file was successfully written
- `action=would_update` only appears in dry-run mode
- `guardrail_check_passed` only present when Resume Written guardrails were evaluated
- `error` field only present when `success=false`

### bulk_update_job_status Output Schema (Success)

```json
{
  "type": "object",
  "properties": {
    "updated_count": {
      "type": "integer",
      "description": "Number of jobs successfully updated"
    },
    "failed_count": {
      "type": "integer",
      "description": "Number of failed updates (always 0 on success)"
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "success": {"type": "boolean"}
        },
        "required": ["id", "success"]
      }
    }
  },
  "required": ["updated_count", "failed_count", "results"]
}
```

### bulk_update_job_status Output Schema (Validation Failure)

```json
{
  "type": "object",
  "properties": {
    "updated_count": {
      "type": "integer",
      "description": "Number of jobs successfully updated (always 0 on failure)"
    },
    "failed_count": {
      "type": "integer",
      "description": "Number of failed updates"
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {"type": "integer"},
          "success": {"type": "boolean"},
          "error": {"type": "string", "description": "Error message for this job"}
        },
        "required": ["id", "success"]
      }
    }
  },
  "required": ["updated_count", "failed_count", "results"]
}
```

### finalize_resume_batch Input Schema

```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "integer",
            "minimum": 1,
            "description": "Job database ID"
          },
          "tracker_path": {
            "type": "string",
            "description": "Path to tracker markdown file"
          },
          "resume_pdf_path": {
            "type": "string",
            "description": "Optional override for resume PDF path"
          }
        },
        "required": ["id", "tracker_path"],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 100,
      "description": "Array of finalization entries to process"
    },
    "run_id": {
      "type": "string",
      "description": "Optional batch run identifier (auto-generated if omitted)"
    },
    "db_path": {
      "type": "string",
      "description": "Optional database path override"
    },
    "dry_run": {
      "type": "boolean",
      "default": false,
      "description": "If true, preview outcomes without writing"
    }
  },
  "required": ["items"],
  "additionalProperties": false
}
```

**Additional Semantic Rules:**
- `items[*].id` values must be unique within one request batch
- `items[*].tracker_path` must point to existing tracker file
- `resume_pdf_path` is resolved from tracker frontmatter if not provided in item
- Empty batch returns success with zero counts

### finalize_resume_batch Output Schema (Success)

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "description": "Batch run identifier"
    },
    "finalized_count": {
      "type": "integer",
      "description": "Number of successfully finalized items"
    },
    "failed_count": {
      "type": "integer",
      "description": "Number of failed items"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Whether this was a dry-run"
    },
    "warnings": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Optional non-fatal warnings"
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "integer",
            "description": "Job database ID"
          },
          "tracker_path": {
            "type": "string",
            "description": "Path to tracker file"
          },
          "resume_pdf_path": {
            "type": "string",
            "description": "Resolved resume PDF path (null on early failure)"
          },
          "action": {
            "type": "string",
            "enum": ["finalized", "would_finalize", "failed"],
            "description": "Action taken for this item"
          },
          "success": {
            "type": "boolean",
            "description": "Whether operation succeeded"
          },
          "error": {
            "type": "string",
            "description": "Error message (only present on failure)"
          }
        },
        "required": ["id", "tracker_path", "action", "success"]
      }
    }
  },
  "required": ["run_id", "finalized_count", "failed_count", "dry_run", "results"]
}
```

**Additional Semantic Rules:**
- Results array maintains input order
- `action=finalized` when both DB and tracker updates succeed
- `action=would_finalize` only appears in dry-run mode
- `action=failed` when preconditions fail or finalization fails
- `resume_pdf_path` may be null for items that fail early validation
- `error` field only present when `success=false`

### Error Response Schema (All Tools)

```json
{
  "type": "object",
  "properties": {
    "error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "enum": ["VALIDATION_ERROR", "DB_NOT_FOUND", "FILE_NOT_FOUND", "DB_ERROR", "INTERNAL_ERROR"],
          "description": "Error code identifying the error type"
        },
        "message": {
          "type": "string",
          "description": "Human-readable error description"
        },
        "retryable": {
          "type": "boolean",
          "description": "Whether the operation can be safely retried"
        }
      },
      "required": ["code", "message", "retryable"]
    }
  },
  "required": ["error"]
}
```

**Note:** `FILE_NOT_FOUND` is specific to `update_tracker_status` tool.

## Requirements

- Python 3.11+
- SQLite database at `data/capture/jobs.db` (or custom path)
- Database must have `jobs` table with required schema

## Architecture

The implementation follows a layered architecture:

1. **MCP Server Layer** (`server.py`): FastMCP server with tool registration
2. **Tool Handler Layer** (`tools/bulk_read_new_jobs.py`): Orchestrates all components
3. **Validation Layer** (`utils/validation.py`): Input parameter validation
4. **Database Layer** (`db/jobs_reader.py`): SQLite connection and queries
5. **Pagination Layer** (`utils/pagination.py`): Cursor-based pagination logic
6. **Schema Layer** (`models/job.py`): Job record schema mapping
7. **Error Layer** (`models/errors.py`): Structured error handling

All layers are thoroughly tested with unit tests, integration tests, and property-based tests.
