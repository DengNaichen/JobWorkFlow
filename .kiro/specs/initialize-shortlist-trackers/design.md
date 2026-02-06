# Design Document: initialize_shortlist_trackers

## Overview

`initialize_shortlist_trackers` is a projection-oriented MCP tool that reads `status='shortlist'` jobs from SQLite and initializes deterministic tracker markdown files under `trackers/` with linked application workspace paths.

This design is aligned with:

- `.kiro/specs/initialize-shortlist-trackers/requirements.md`

Core design goals:

1. Deterministic shortlist reads and tracker naming
2. Idempotent file initialization with explicit `force` semantics
3. Atomic per-file writes with partial-failure tolerance across batch items
4. Strict DB read-only behavior (DB remains SSOT)
5. Stable tracker structure for Obsidian + downstream MCP tools

## Scope

In scope:

- MCP tool interface for `initialize_shortlist_trackers`
- Shortlist selection from SQLite (`status='shortlist'`)
- Deterministic tracker filename and application slug generation
- Workspace directory bootstrap (`resume/`, `cover/`)
- Tracker markdown rendering and atomic write semantics
- Dry-run planning mode and structured per-item results

Out of scope:

- Any DB status mutation or write-back
- Resume/Cover letter content generation
- PDF compilation
- Tracker status progression beyond initialization

## Architecture

### Components

1. MCP Server (`server.py`)
2. Tool Handler (`tools/initialize_shortlist_trackers.py`)
3. DB Reader (`db/jobs_reader.py`) - shortlist query function
4. Tracker Planner (`utils/tracker_planner.py`) - deterministic filename/slug/path planning
5. Tracker Renderer (`utils/tracker_renderer.py`) - stable markdown/frontmatter rendering
6. Atomic Writer (`utils/file_ops.py`) - temp-file + rename writing
7. Error Model (`models/errors.py`) - structured/sanitized errors (shared)

### Runtime Flow

1. LLM agent calls `initialize_shortlist_trackers` with optional `limit`, `db_path`, `trackers_dir`, `force`, `dry_run`
2. Tool validates all parameters
3. Tool reads shortlist jobs ordered by `captured_at DESC, id DESC`
4. For each selected job:
   - compute deterministic `application_slug`
   - compute deterministic tracker path
   - compute action (`created`, `skipped_exists`, `overwritten`) based on file existence + `force`
   - render tracker content
   - if not dry-run and action is write: create workspace dirs and atomically write tracker file
5. Tool aggregates ordered results and returns counts

## Interfaces

### MCP Tool Name

- `initialize_shortlist_trackers`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200,
      "description": "Number of shortlisted jobs to process. Default: 50."
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override. Default: data/capture/jobs.db."
    },
    "trackers_dir": {
      "type": "string",
      "description": "Optional trackers directory override. Default: trackers/."
    },
    "force": {
      "type": "boolean",
      "default": false,
      "description": "If true, overwrite deterministic tracker files when they already exist."
    },
    "dry_run": {
      "type": "boolean",
      "default": false,
      "description": "If true, compute outcomes without creating directories or writing files."
    }
  },
  "additionalProperties": false
}
```

### Output Schema

```json
{
  "created_count": 12,
  "skipped_count": 3,
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
      "id": 3630,
      "job_id": "4368669999",
      "tracker_path": "trackers/2026-02-04-meta-3630.md",
      "action": "skipped_exists",
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

Notes:

- `results` order matches shortlist selection order.
- `tracker_path` can be omitted for hard failures before path planning.
- Response remains structured on partial item failures.

### Error Schema (Top-Level)

```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error",
    "retryable": false
  }
}
```

## Deterministic Planning

### Shortlist Query

Read path query:

```sql
SELECT id, job_id, title, company, description, url, captured_at, status
FROM jobs
WHERE status = 'shortlist'
ORDER BY captured_at DESC, id DESC
LIMIT :limit;
```

### Application Slug

Deterministic slug:

- Base: normalized company (`lower`, non-alnum -> `_`, collapsed separators)
- Suffix: job database ID (`id`)
- Final: `<company_slug>-<id>`

Example:

- company=`General Motors`, id=`3711`
- slug=`general_motors-3711`

This prevents cross-job collisions for same company names.

### Tracker Filename

Deterministic filename:

- `<captured_date>-<company_slug>-<id>.md`
- `captured_date` derived from job `captured_at` in UTC `YYYY-MM-DD`

Example:

- `trackers/2026-02-04-general_motors-3711.md`

### Linked Artifact Paths

- `resume_path`: `[[data/applications/<slug>/resume/resume.pdf]]`
- `cover_letter_path`: `[[data/applications/<slug>/cover/cover-letter.pdf]]`

Workspace directories created when writing:

- `data/applications/<slug>/resume/`
- `data/applications/<slug>/cover/`

## Tracker Content Design

### Frontmatter Fields

Required stable fields:

- `job_db_id`
- `job_id`
- `company`
- `position`
- `status`
- `application_date`
- `reference_link`
- `resume_path`
- `cover_letter_path`

Compatibility fields (kept for current tracker ecosystem):

- `next_action`
- `salary`
- `website`

Initialization defaults:

- tracker `status`: `Reviewed`
- `next_action`: `["Wait for feedback"]`
- `salary`: `0`
- `website`: empty string
- `application_date`: derived date string `YYYY-MM-DD`

### Body Sections

Required section headers:

1. `## Job Description` (exact header)
2. `## Notes`

`## Job Description` content:

- job description text if present
- fallback text if missing (for example: `No description available.`)

## Idempotency and Write Semantics

Per item decision matrix:

1. File missing + `force=false` -> `created`
2. File exists + `force=false` -> `skipped_exists`
3. File exists + `force=true` -> `overwritten`
4. Any planning/write exception -> `failed`

`dry_run=true`:

- same action decision matrix and counts are computed
- no directory creation
- no file writes

## Atomic File Write Strategy

Per tracker write:

1. Ensure parent directory exists
2. Render markdown payload
3. Write payload to temp file in same directory
4. `fsync` temp file
5. Atomic rename (`os.replace`) temp -> final
6. Cleanup temp file on error

Failure handling:

- single item failure does not abort the batch
- failed item recorded with `action='failed'`, `success=false`, sanitized error message

## Validation Rules

1. `limit` default = `50`; must be integer in `[1, 200]`
2. `db_path` optional string, non-empty
3. `trackers_dir` optional string, non-empty
4. `force` optional bool, default `false`
5. `dry_run` optional bool, default `false`
6. reject unknown input properties

## Database Boundary Guarantees

The tool only executes read operations:

- `SELECT` shortlist rows

The tool must not execute:

- `INSERT`
- `UPDATE`
- `DELETE`
- schema mutations

DB connection is always closed via context manager.

## Error Handling Strategy

### Mapping

- Request validation failures -> `VALIDATION_ERROR`
- DB path missing/inaccessible -> `DB_NOT_FOUND`
- SQLite connection/query failures -> `DB_ERROR`
- Unexpected runtime failures -> `INTERNAL_ERROR`
- Per-item filesystem/planning failures -> item in `results` with `failed`

### Sanitization Policy

Sanitize all returned error messages:

- no stack traces
- no SQL fragments
- no sensitive absolute paths

Keep:

- actionable high-level cause
- stable error code
- retry hint (`retryable`)

## Pseudocode

```python
def initialize_shortlist_trackers(args: dict) -> dict:
    limit, db_path, trackers_dir, force, dry_run = validate_initialize_args(args)

    with get_connection(db_path) as conn:
        jobs = query_shortlist_jobs(conn, limit)

    results = []
    for job in jobs:
        try:
            plan = plan_tracker(job, trackers_dir)

            if plan.exists and not force:
                results.append(result(plan, action="skipped_exists", success=True))
                continue

            action = "overwritten" if plan.exists else "created"

            if not dry_run:
                ensure_workspace_dirs(plan.application_slug)
                content = render_tracker_markdown(job, plan)
                atomic_write(plan.tracker_path, content)

            results.append(result(plan, action=action, success=True))
        except Exception as e:
            results.append(failure_result(job, e))

    return summarize_results(results)
```

## Testing Strategy

### Unit Tests

1. input validation for `limit`, `trackers_dir`, `force`, `dry_run`
2. deterministic slug generation and filename generation
3. markdown rendering includes required frontmatter and exact `## Job Description`
4. idempotency matrix (`created`, `skipped_exists`, `overwritten`)
5. dry-run mode produces counts/results without writes

### Integration Tests

1. reads only `status='shortlist'` jobs
2. creates tracker files and workspace directories for selected jobs
3. preserves DB (no row mutations before/after)
4. continues processing when one item fails
5. returns deterministic result order

### Failure/Resilience Tests

1. missing DB path -> `DB_NOT_FOUND`
2. malformed request -> `VALIDATION_ERROR`
3. file write permission issue -> per-item `failed`
4. atomic write leaves no partial files on interruption simulation

## Requirement Traceability

- Requirement 1 (shortlist source): Shortlist Query + Validation sections
- Requirement 2 (tracker generation): Tracker Content + Deterministic Planning sections
- Requirement 3 (workspace linking): Linked Artifact Paths section
- Requirement 4 (idempotency): Idempotency and Write Semantics section
- Requirement 5 (atomic writes): Atomic File Write Strategy section
- Requirement 6 (DB/FS boundary): Database Boundary Guarantees section
- Requirement 7 (response): Output Schema + summarize pseudocode
- Requirement 8 (errors): Error Handling Strategy section
- Requirement 9 (MCP interface): Input/Output schema sections
- Requirement 10 (compatibility): Tracker Content Design section
