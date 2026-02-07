# MCP Server - JobWorkFlow Tools

Python MCP server for JobWorkFlow operations: scraping and ingesting jobs, triaging status, initializing trackers, tailoring resume artifacts, and finalizing completion state.

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
│   ├── scrape_jobs.py                      # Ingestion tool
│   ├── bulk_read_new_jobs.py              # Read tool handler
│   ├── bulk_update_job_status.py          # Write tool handler
│   ├── initialize_shortlist_trackers.py   # Tracker initialization tool
│   ├── career_tailor.py                   # Batch full-tailor artifact tool
│   ├── update_tracker_status.py           # Tracker status projection tool
│   └── finalize_resume_batch.py           # Commit/finalization tool
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

Initialize deterministic tracker markdown files for jobs with `status='shortlist'`. This projection-oriented tool reads from the database (SSOT) and creates file-based tracker notes under repo-root `trackers/` with linked application workspace paths. The tool does NOT modify database records.

**Parameters:**
- `limit` (int, optional): Number of shortlist jobs to process (1-200, default 50)
- `db_path` (str, optional): Database path override (default: data/capture/jobs.db)
- `trackers_dir` (str, optional): Trackers directory override (default: `<repo_root>/trackers`)
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
- Compatibility dedupe: if a legacy tracker already exists with the same `reference_link`, it is treated as existing (no duplicate tracker is created)
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

#### career_tailor (Artifact Tool)

Run batch full-tailoring for tracker items. For each item, the tool parses tracker context, bootstraps workspace artifacts, regenerates `ai_context.md`, compiles `resume.tex` to `resume.pdf`, and returns `successful_items` for downstream `finalize_resume_batch`.

**Parameters:**
- `items` (array, required, 1-100): each item contains:
  - `tracker_path` (str, required)
  - `job_db_id` (int, optional)
- `force` (bool, optional): overwrite existing `resume.tex` from template (default: false)
- `full_resume_path` (str, optional): full resume markdown override
- `resume_template_path` (str, optional): resume template override
- `applications_dir` (str, optional): workspace root override
- `pdflatex_cmd` (str, optional): compile command override (default: `pdflatex`)

**Response (Success or Partial Success):**
```json
{
  "run_id": "tailor_20260207_ab12cd34",
  "total_count": 3,
  "success_count": 2,
  "failed_count": 1,
  "results": [
    {
      "tracker_path": "trackers/2026-02-06-amazon-3629.md",
      "job_db_id": 3629,
      "application_slug": "amazon-3629",
      "workspace_dir": "data/applications/amazon-3629",
      "resume_tex_path": "data/applications/amazon-3629/resume/resume.tex",
      "ai_context_path": "data/applications/amazon-3629/resume/ai_context.md",
      "resume_pdf_path": "data/applications/amazon-3629/resume/resume.pdf",
      "resume_tex_action": "preserved",
      "success": true
    }
  ],
  "successful_items": [
    {
      "id": 3629,
      "tracker_path": "trackers/2026-02-06-amazon-3629.md",
      "resume_pdf_path": "data/applications/amazon-3629/resume/resume.pdf"
    }
  ]
}
```

**Boundary:**
- Does NOT update DB status
- Does NOT update tracker status
- Does NOT call `finalize_resume_batch` internally

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

#### scrape_jobs (Ingestion Tool)

Scrape fresh job postings from external sources (JobSpy-backed), normalize records, and insert them into SQLite as `status='new'` items for downstream triage. This ingestion-focused tool provides step-1 pipeline automation with idempotent dedupe semantics.

**Parameters:**
- `terms` (array of strings, optional): Search terms (default: `['ai engineer','backend engineer','machine learning']`)
- `location` (str, optional): Search location (default: `'Ontario, Canada'`)
- `sites` (array of strings, optional): Source sites list (default: `['linkedin']`)
- `results_wanted` (int, optional): Requested scrape results per term (1-200, default: 20)
- `hours_old` (int, optional): Recency window in hours (1-168, default: 2)
- `db_path` (str, optional): Database path override (default: `data/capture/jobs.db`)
- `status` (str, optional): Initial status for inserted rows (default: `'new'`, must be one of: `new`, `shortlist`, `reviewed`, `reject`, `resume_written`, `applied`)
- `require_description` (bool, optional): Skip records without descriptions (default: true)
- `preflight_host` (str, optional): DNS preflight host (default: `'www.linkedin.com'`)
- `retry_count` (int, optional): Preflight retry count (1-10, default: 3)
- `retry_sleep_seconds` (number, optional): Base retry sleep seconds (0-300, default: 30)
- `retry_backoff` (number, optional): Retry backoff multiplier (1-10, default: 2)
- `save_capture_json` (bool, optional): Persist per-term raw JSON capture files (default: true)
- `capture_dir` (str, optional): Capture output directory (default: `data/capture`)
- `dry_run` (bool, optional): Compute counts only; no DB writes (default: false)

**Response (Success or Partial Success):**
```json
{
  "run_id": "scrape_20260206_abcdef12",
  "started_at": "2026-02-06T18:40:12.001Z",
  "finished_at": "2026-02-06T18:40:44.337Z",
  "duration_ms": 32336,
  "dry_run": false,
  "results": [
    {
      "term": "backend engineer",
      "success": true,
      "fetched_count": 20,
      "cleaned_count": 18,
      "inserted_count": 7,
      "duplicate_count": 11,
      "skipped_no_url": 1,
      "skipped_no_description": 1,
      "capture_path": "data/capture/jobspy_linkedin_backend_engineer_ontario_2h.json"
    },
    {
      "term": "ai engineer",
      "success": false,
      "fetched_count": 0,
      "cleaned_count": 0,
      "inserted_count": 0,
      "duplicate_count": 0,
      "skipped_no_url": 0,
      "skipped_no_description": 0,
      "error": "preflight DNS failed after retries"
    }
  ],
  "totals": {
    "term_count": 2,
    "successful_terms": 1,
    "failed_terms": 1,
    "fetched_count": 20,
    "cleaned_count": 18,
    "inserted_count": 7,
    "duplicate_count": 11,
    "skipped_no_url": 1,
    "skipped_no_description": 1
  }
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
- Processes multiple search terms in one run with per-term isolation
- Scrapes fresh postings from configured source sites (JobSpy adapter)
- Normalizes raw source records to stable field mapping (`url`, `title`, `description`, `source`, `job_id`, `location`, `company`, `captured_at`, `payload_json`)
- Filters records based on quality rules (empty URL, missing description)
- Optionally writes per-term JSON capture files for audit/reproducibility
- Inserts cleaned records into SQLite with idempotent dedupe by `url`
- Uses `INSERT OR IGNORE` semantics: duplicate URLs are counted but not re-inserted
- Existing rows are never updated during dedupe hits
- Continues processing remaining terms after one term fails (partial success)
- Preflight DNS checks with retry/backoff for transient network issues
- Database schema is bootstrapped automatically on first run

**Ingestion Boundaries:**
- Inserts only with `status='new'` (or validated override)
- Does NOT update status for existing rows
- Does NOT invoke tracker creation/finalization/status tools
- Does NOT perform triage decisions
- Strict ingestion-only boundary for pipeline step 1

**Validation Rules:**
- `terms`: Non-empty array of strings (max 20 terms per run)
- `results_wanted`: Integer in range 1-200
- `hours_old`: Integer in range 1-168
- `status`: Must be one of allowed DB status values
- `retry_count`: Integer in range 1-10
- `retry_sleep_seconds`: Number in range 0-300
- `retry_backoff`: Number in range 1-10
- Unknown request fields are rejected with `VALIDATION_ERROR`

**Error Codes:**
- `VALIDATION_ERROR` (retryable=false): Invalid input parameters, unknown fields, out-of-range values
- `DB_NOT_FOUND` (retryable=false): Database file doesn't exist at specified path
- `DB_ERROR` (retryable varies): Database operation failure, schema bootstrap failure
- `INTERNAL_ERROR` (retryable=true): Unexpected server error

**Retry Guidance:**
- `VALIDATION_ERROR`: Fix input parameters before retrying (not retryable)
- `DB_NOT_FOUND`: Verify database path and file existence (not retryable)
- `DB_ERROR`: Check error message for details; transient errors may be retryable
- `INTERNAL_ERROR`: Safe to retry after brief delay
- Per-term failures: Recorded in results, other terms continue processing
- Idempotent inserts: Safe to retry the same request multiple times (duplicates are ignored)

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

### scrape_jobs

Scrape and ingest job postings with idempotent dedupe:

```python
# Scrape with default parameters (3 default terms, Ontario location, LinkedIn source)
result = scrape_jobs_tool()
# Returns: {"run_id": "scrape_20260206_abcdef12", "started_at": "...", "finished_at": "...",
#           "duration_ms": 32336, "dry_run": false, "results": [...], "totals": {...}}

# Scrape with custom terms
result = scrape_jobs_tool(
    terms=["python developer", "data scientist"],
    location="Toronto, ON",
    results_wanted=50
)
# Returns: {"run_id": "scrape_20260206_xyz789", "results": [
#   {"term": "python developer", "success": true, "fetched_count": 50, "cleaned_count": 48,
#    "inserted_count": 35, "duplicate_count": 13, ...},
#   {"term": "data scientist", "success": true, "fetched_count": 50, "cleaned_count": 47,
#    "inserted_count": 42, "duplicate_count": 5, ...}
# ], "totals": {...}}

# Dry-run mode - compute counts without DB writes
result = scrape_jobs_tool(
    terms=["backend engineer"],
    dry_run=True
)
# Returns: {"run_id": "scrape_20260206_abc123", "dry_run": true, "results": [
#   {"term": "backend engineer", "success": true, "fetched_count": 20, "cleaned_count": 18,
#    "inserted_count": 0, "duplicate_count": 0, ...}
# ], "totals": {...}}

# Custom database and capture paths
result = scrape_jobs_tool(
    terms=["ai engineer"],
    db_path="custom/path/jobs.db",
    capture_dir="custom/capture"
)
# Returns: {"run_id": "scrape_20260206_def456", "results": [...], "totals": {...}}

# Disable capture file writes
result = scrape_jobs_tool(
    terms=["machine learning"],
    save_capture_json=False
)
# Returns: {"run_id": "scrape_20260206_ghi789", "results": [
#   {"term": "machine learning", "success": true, "fetched_count": 20, "cleaned_count": 18,
#    "inserted_count": 12, "duplicate_count": 6}
#   # Note: No capture_path field when save_capture_json=false
# ], "totals": {...}}

# Allow records without descriptions
result = scrape_jobs_tool(
    terms=["software engineer"],
    require_description=False
)
# Returns: {"run_id": "scrape_20260206_jkl012", "results": [
#   {"term": "software engineer", "success": true, "fetched_count": 20, "cleaned_count": 20,
#    "inserted_count": 15, "duplicate_count": 5, "skipped_no_url": 0, "skipped_no_description": 0}
# ], "totals": {...}}

# Custom status for inserted rows (default is 'new')
result = scrape_jobs_tool(
    terms=["devops engineer"],
    status="shortlist"
)
# Returns: {"run_id": "scrape_20260206_mno345", "results": [...], "totals": {...}}
# Note: Inserted rows will have status='shortlist' instead of 'new'

# Partial success - one term fails, others continue
result = scrape_jobs_tool(
    terms=["backend engineer", "frontend engineer", "fullstack engineer"]
)
# Returns: {"run_id": "scrape_20260206_pqr678", "results": [
#   {"term": "backend engineer", "success": true, "fetched_count": 20, "inserted_count": 15, ...},
#   {"term": "frontend engineer", "success": false, "fetched_count": 0, "inserted_count": 0,
#    "error": "preflight DNS failed after retries"},
#   {"term": "fullstack engineer", "success": true, "fetched_count": 20, "inserted_count": 18, ...}
# ], "totals": {"term_count": 3, "successful_terms": 2, "failed_terms": 1, ...}}

# Idempotent behavior - repeated runs yield duplicates not inserts
result = scrape_jobs_tool(terms=["ai engineer"])
# First run: {"results": [{"term": "ai engineer", "inserted_count": 15, "duplicate_count": 0}], ...}
result = scrape_jobs_tool(terms=["ai engineer"])
# Second run: {"results": [{"term": "ai engineer", "inserted_count": 0, "duplicate_count": 15}], ...}
# Note: Same URLs are detected as duplicates and not re-inserted

# Custom preflight and retry settings
result = scrape_jobs_tool(
    terms=["cloud engineer"],
    preflight_host="www.linkedin.com",
    retry_count=5,
    retry_sleep_seconds=10,
    retry_backoff=1.5
)
# Returns: {"run_id": "scrape_20260206_stu901", "results": [...], "totals": {...}}

# Validation error - invalid results_wanted
result = scrape_jobs_tool(
    terms=["backend engineer"],
    results_wanted=500  # Exceeds maximum of 200
)
# Returns: {"error": {"code": "VALIDATION_ERROR",
#           "message": "results_wanted must be between 1 and 200", "retryable": false}}

# Validation error - unknown field
result = scrape_jobs_tool(
    terms=["backend engineer"],
    unknown_field="value"
)
# Returns: {"error": {"code": "VALIDATION_ERROR",
#           "message": "Unknown parameter: unknown_field", "retryable": false}}

# Empty terms list - validation error
result = scrape_jobs_tool(terms=[])
# Returns: {"error": {"code": "VALIDATION_ERROR",
#           "message": "terms must be a non-empty array", "retryable": false}}
```

**Important Notes:**
- Tool is ingestion-focused: scrapes, normalizes, and inserts with `status='new'` (or override)
- Database is the SSOT (Single Source of Truth) for job records
- Does NOT update status for existing rows during dedupe hits
- Does NOT invoke tracker creation/finalization/status tools
- Does NOT perform triage decisions
- Idempotent inserts: safe to run multiple times (duplicates detected by URL)
- Per-term isolation: one term failure doesn't block other terms
- Preflight DNS checks with retry/backoff for transient network issues
- Optional capture files for audit/reproducibility
- Dry-run mode useful for previewing outcomes before actual writes
- Results array maintains term order from request

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

### scrape_jobs Input Schema

```json
{
  "type": "object",
  "properties": {
    "terms": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Search terms (default: ['ai engineer','backend engineer','machine learning'])"
    },
    "location": {
      "type": "string",
      "description": "Search location (default: 'Ontario, Canada')"
    },
    "sites": {
      "type": "array",
      "items": {"type": "string"},
      "description": "Source sites list (default: ['linkedin'])"
    },
    "results_wanted": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200,
      "description": "Requested scrape results per term (default: 20)"
    },
    "hours_old": {
      "type": "integer",
      "minimum": 1,
      "maximum": 168,
      "description": "Recency window in hours (default: 2)"
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override (default: data/capture/jobs.db)"
    },
    "status": {
      "type": "string",
      "enum": ["new", "shortlist", "reviewed", "reject", "resume_written", "applied"],
      "description": "Initial status for inserted rows (default: 'new')"
    },
    "require_description": {
      "type": "boolean",
      "description": "Skip records without descriptions (default: true)"
    },
    "preflight_host": {
      "type": "string",
      "description": "DNS preflight host (default: 'www.linkedin.com')"
    },
    "retry_count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "description": "Preflight retry count (default: 3)"
    },
    "retry_sleep_seconds": {
      "type": "number",
      "minimum": 0,
      "maximum": 300,
      "description": "Base retry sleep seconds (default: 30)"
    },
    "retry_backoff": {
      "type": "number",
      "minimum": 1,
      "maximum": 10,
      "description": "Retry backoff multiplier (default: 2)"
    },
    "save_capture_json": {
      "type": "boolean",
      "description": "Persist per-term raw JSON capture files (default: true)"
    },
    "capture_dir": {
      "type": "string",
      "description": "Capture output directory (default: data/capture)"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Compute counts only; no DB writes (default: false)"
    }
  },
  "additionalProperties": false
}
```

**Additional Semantic Rules:**
- `terms` must be non-empty array (max 20 terms per run)
- All numeric parameters must be within specified ranges
- `status` values are case-sensitive and must not have leading/trailing whitespace
- Unknown request fields are rejected with `VALIDATION_ERROR`

### scrape_jobs Output Schema (Success or Partial Success)

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "description": "Unique run identifier (format: scrape_YYYYMMDD_<8-char-hex>)"
    },
    "started_at": {
      "type": "string",
      "description": "ISO 8601 UTC timestamp when run started"
    },
    "finished_at": {
      "type": "string",
      "description": "ISO 8601 UTC timestamp when run finished"
    },
    "duration_ms": {
      "type": "integer",
      "description": "Total run duration in milliseconds"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Whether this was a dry-run (no DB writes)"
    },
    "results": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "term": {
            "type": "string",
            "description": "Search term processed"
          },
          "success": {
            "type": "boolean",
            "description": "Whether term processing succeeded"
          },
          "fetched_count": {
            "type": "integer",
            "description": "Number of raw records fetched from source"
          },
          "cleaned_count": {
            "type": "integer",
            "description": "Number of records after normalization and filtering"
          },
          "inserted_count": {
            "type": "integer",
            "description": "Number of new records inserted into database"
          },
          "duplicate_count": {
            "type": "integer",
            "description": "Number of records skipped as duplicates (URL already exists)"
          },
          "skipped_no_url": {
            "type": "integer",
            "description": "Number of records skipped due to missing URL"
          },
          "skipped_no_description": {
            "type": "integer",
            "description": "Number of records skipped due to missing description (when require_description=true)"
          },
          "capture_path": {
            "type": "string",
            "description": "Path to capture JSON file (only present when save_capture_json=true)"
          },
          "error": {
            "type": "string",
            "description": "Error message (only present when success=false)"
          }
        },
        "required": ["term", "success", "fetched_count", "cleaned_count", "inserted_count", "duplicate_count", "skipped_no_url", "skipped_no_description"]
      }
    },
    "totals": {
      "type": "object",
      "properties": {
        "term_count": {
          "type": "integer",
          "description": "Total number of terms processed"
        },
        "successful_terms": {
          "type": "integer",
          "description": "Number of terms that succeeded"
        },
        "failed_terms": {
          "type": "integer",
          "description": "Number of terms that failed"
        },
        "fetched_count": {
          "type": "integer",
          "description": "Total raw records fetched across all terms"
        },
        "cleaned_count": {
          "type": "integer",
          "description": "Total cleaned records across all terms"
        },
        "inserted_count": {
          "type": "integer",
          "description": "Total new records inserted across all terms"
        },
        "duplicate_count": {
          "type": "integer",
          "description": "Total duplicates skipped across all terms"
        },
        "skipped_no_url": {
          "type": "integer",
          "description": "Total records skipped for missing URL across all terms"
        },
        "skipped_no_description": {
          "type": "integer",
          "description": "Total records skipped for missing description across all terms"
        }
      },
      "required": ["term_count", "successful_terms", "failed_terms", "fetched_count", "cleaned_count", "inserted_count", "duplicate_count", "skipped_no_url", "skipped_no_description"]
    }
  },
  "required": ["run_id", "started_at", "finished_at", "duration_ms", "dry_run", "results", "totals"]
}
```

**Additional Semantic Rules:**
- Results array maintains term order from request
- Per-term failures are recorded in `results[*].error` while allowing partial success
- `capture_path` only present when `save_capture_json=true` and capture write succeeded
- `error` field only present when `success=false`
- In dry-run mode, `inserted_count` and `duplicate_count` are always 0
- Totals aggregate all per-term counters

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
