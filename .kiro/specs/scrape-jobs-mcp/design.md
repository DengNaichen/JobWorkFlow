# Design Document: scrape_jobs

## Overview

`scrape_jobs` is an ingestion MCP tool that runs source scraping (JobSpy-backed), normalizes/filter records, and inserts new queue items into SQLite with idempotent dedupe by URL.

This design is aligned with:

- `/Users/nd/Developer/JobWorkFlow/.kiro/specs/scrape-jobs-mcp/requirements.md`
- `/Users/nd/Developer/JobWorkFlow/.kiro/steering.md`

Core design goals:

1. Single-call scrape + ingest execution for pipeline step 1
2. Idempotent inserts with deterministic dedupe
3. Structured per-term and aggregate run reporting
4. Strict boundary: ingestion only (no triage/tracker/finalize writes)
5. Safe partial success with sanitized errors

## Scope

In scope:

- MCP tool interface for `scrape_jobs`
- Multi-term source scraping using JobSpy adapter
- Record normalization/filtering
- SQLite bootstrap and insertion with dedupe
- Optional per-term capture JSON output
- Dry-run mode with no DB mutation

Out of scope:

- Triage decisions and status transitions beyond insertion default
- Tracker creation/status sync/finalization
- Resume compile/rewrite workflows
- Multi-provider plugin system beyond current JobSpy source set

## Architecture

### Components

1. **MCP Server** (`server.py`) - tool registration and wrapper
2. **Tool Handler** (`tools/scrape_jobs.py`) - orchestration and response shaping
3. **Source Adapter** (`utils/jobspy_adapter.py`) - calls JobSpy and returns raw records
4. **Normalizer** (`utils/scrape_normalizer.py`) - field mapping + filtering
5. **Ingestion Writer** (`db/jobs_ingest_writer.py`) - schema bootstrap + insert/dedupe
6. **Error Model** (`models/errors.py`) - structured/sanitized error output

### Runtime Flow

1. Client invokes `scrape_jobs` with optional request overrides
2. Tool validates all request parameters
3. Tool resolves DB/capture paths and generates `run_id`
4. For each term (deterministic order):
   - run preflight DNS retry (if configured)
   - scrape source records
   - normalize + filter records
   - optionally write capture file
   - insert cleaned records into DB (unless `dry_run=true`)
   - append per-term result entry
5. Tool aggregates totals and returns structured response
6. Tool returns top-level error only for request/bootstrap/fatal runtime failures

## Interfaces

### MCP Tool Name

- `scrape_jobs`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "terms": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Search terms. Default: ['ai engineer','backend engineer','machine learning']"
    },
    "location": {
      "type": "string",
      "description": "Search location. Default: 'Ontario, Canada'"
    },
    "sites": {
      "type": "array",
      "items": { "type": "string" },
      "description": "Source sites list. Default: ['linkedin']"
    },
    "results_wanted": {
      "type": "integer",
      "minimum": 1,
      "maximum": 200,
      "description": "Requested scrape results per term. Default: 20"
    },
    "hours_old": {
      "type": "integer",
      "minimum": 1,
      "maximum": 168,
      "description": "Recency window in hours. Default: 2"
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override. Default: data/capture/jobs.db"
    },
    "status": {
      "type": "string",
      "enum": ["new", "shortlist", "reviewed", "reject", "resume_written", "applied"],
      "description": "Initial status for inserted rows. Default: 'new'"
    },
    "require_description": {
      "type": "boolean",
      "description": "Skip records without descriptions. Default: true"
    },
    "preflight_host": {
      "type": "string",
      "description": "DNS preflight host. Default: 'www.linkedin.com'"
    },
    "retry_count": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10,
      "description": "Preflight retry count. Default: 3"
    },
    "retry_sleep_seconds": {
      "type": "number",
      "minimum": 0,
      "maximum": 300,
      "description": "Base retry sleep seconds. Default: 30"
    },
    "retry_backoff": {
      "type": "number",
      "minimum": 1,
      "maximum": 10,
      "description": "Retry backoff multiplier. Default: 2"
    },
    "save_capture_json": {
      "type": "boolean",
      "description": "Persist per-term raw JSON capture files. Default: true"
    },
    "capture_dir": {
      "type": "string",
      "description": "Capture output directory. Default: data/capture"
    },
    "dry_run": {
      "type": "boolean",
      "description": "Compute counts only; no DB writes. Default: false"
    }
  },
  "additionalProperties": false
}
```

### Output Schema (Success or Partial Success)

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

### Error Schema (Top-Level Fatal)

```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error",
    "retryable": false
  }
}
```

## Data Model Mapping

### Source to Cleaned Record

Raw source keys (JobSpy):

- `job_url`
- `job_url_direct`
- `title`
- `description`
- `company`
- `location`
- `site`
- `id`
- `date_posted`

Cleaned output mapping:

- `url` <- `job_url` else `job_url_direct`
- `title` <- `title`
- `description` <- `description`
- `company` <- `company`
- `location` <- `location`
- `source` <- request override else `site` else `"unknown"`
- `job_id` <- regex parse from LinkedIn URL else source `id`
- `captured_at` <- parsed `date_posted` UTC else current UTC
- `payload_json` <- serialized cleaned record for audit/debug

### DB Write

Target table:

- `jobs(url, title, description, source, job_id, location, company, captured_at, payload_json, created_at, status)`

Write behavior:

- `INSERT OR IGNORE` for dedupe by unique `url`
- ignore hit => `duplicate_count += 1`
- insert hit => `inserted_count += 1`

## Determinism and Idempotency

1. Term execution order follows request order
2. Per-term response ordering is stable
3. Same request against unchanged source state results in:
   - stable cleaned shape
   - additional inserts only for previously unseen URLs
4. Re-running after success is safe (duplicates are ignored)

## Boundaries and Side Effects

Permitted side effects:

- scrape source requests
- optional capture JSON writes
- `jobs` table insertions only

Forbidden side effects:

- status updates for existing rows
- tracker file writes
- finalize/resume side effects
- deletion of DB rows or files

## Validation Rules

1. Validate type/range for numeric parameters
2. Reject empty term list
3. Reject `results_wanted` outside bounds
4. Reject unknown request keys
5. Validate `status` in allowed DB status set
6. Validate retry/backoff values

## Error Handling Strategy

### Top-Level Fatal Errors

- request validation failure -> `VALIDATION_ERROR`
- DB path/bootstrap failure -> `DB_NOT_FOUND`/`DB_ERROR`
- uncaught runtime failures -> `INTERNAL_ERROR`

### Per-Term Errors (Partial Success)

- preflight failures
- scrape provider failure
- capture write failure (term can still succeed if DB ingest succeeds and capture is optional)

Per-term failures are recorded in `results[*].error` and reflected in totals, while the run still returns success payload unless request-level fatal.

### Sanitization

- remove stack traces
- redact sensitive absolute paths in error strings
- avoid raw SQL fragments in messages

## Pseudocode

```python
def scrape_jobs(args: dict) -> dict:
    req = validate_scrape_jobs_parameters(args)
    run = init_run_metadata(req)
    ensure_db_schema(req.db_path)

    term_results = []
    for term in req.terms:
        term_result = init_term_result(term)
        try:
            preflight_dns_or_raise(req)
            raw_records = scrape_source(term, req)
            term_result.fetched_count = len(raw_records)

            cleaned, skip_counts = normalize_and_filter(raw_records, req)
            term_result.apply_skip_counts(skip_counts)
            term_result.cleaned_count = len(cleaned)

            if req.save_capture_json:
                term_result.capture_path = write_capture(cleaned, run, term, req.capture_dir)

            if not req.dry_run:
                inserted, duplicates = insert_cleaned_records(cleaned, req.db_path, req.status)
                term_result.inserted_count = inserted
                term_result.duplicate_count = duplicates

            term_result.success = True
        except Exception as e:
            term_result.success = False
            term_result.error = sanitize_error_message(e)

        term_results.append(term_result)

    return build_run_response(run, term_results, req.dry_run)
```
