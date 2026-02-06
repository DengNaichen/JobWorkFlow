# Design Document: bulk_read_new_jobs (v2)

## Overview

`bulk_read_new_jobs` is a read-only MCP tool that retrieves jobs with `status='new'` from SQLite in deterministic batches for downstream LLM triage.

This design is aligned with:

- `/Users/nd/Developer/JobWorkFlow/.kiro/specs/bulk-read-new-jobs/requirements.md`

Core design goals:

1. Deterministic queue reads
2. Cursor-based pagination
3. Stable response schema for agent consumers
4. Strict read-only behavior
5. Structured, sanitized errors

## Scope

In scope:

- MCP tool interface for `bulk_read_new_jobs`
- SQLite read path (`status='new'` only)
- Cursor pagination with deterministic order
- Input validation and structured error outputs

Out of scope:

- Any status write-back
- Tracker creation
- Triage logic itself

## Architecture

### Components

1. MCP Server (`server.py`)
2. Tool Handler (`tools/bulk_read_new_jobs.py`)
3. DB Access Layer (`db/jobs_reader.py`)
4. Cursor Codec (`utils/cursor.py`)
5. Error Model (`models/errors.py`)

### Runtime Flow

1. LLM agent calls `bulk_read_new_jobs` with optional `limit`, `cursor`, `db_path`
2. Tool validates parameters
3. Tool resolves DB path (`db_path` override or default)
4. Reader executes deterministic query:
   - filter: `status='new'`
   - order: `captured_at DESC, id DESC`
   - page: cursor boundary + `LIMIT`
5. Tool computes `has_more` and `next_cursor`
6. Tool returns stable JSON output

## Interfaces

### MCP Tool Name

- `bulk_read_new_jobs`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000,
      "description": "Batch size. Default: 50."
    },
    "cursor": {
      "type": "string",
      "description": "Opaque pagination cursor returned by previous call."
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override. Default: data/capture/jobs.db."
    }
  },
  "additionalProperties": false
}
```

### Output Schema

```json
{
  "jobs": [
    {
      "id": 123,
      "job_id": "4368663835",
      "title": "Machine Learning Engineer",
      "company": "Example Corp",
      "description": "...",
      "url": "https://www.linkedin.com/jobs/view/4368663835/",
      "location": "Toronto, ON",
      "source": "linkedin",
      "status": "new",
      "captured_at": "2026-02-04T03:47:36.966Z"
    }
  ],
  "count": 1,
  "has_more": false,
  "next_cursor": null
}
```

### Error Schema

```json
{
  "error": {
    "code": "VALIDATION_ERROR | DB_NOT_FOUND | DB_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error",
    "retryable": false
  }
}
```

Notes:

- Messages must be descriptive but sanitized.
- No secrets, credentials, full stack traces, or SQL internals in user-facing output.

## Data Model Mapping

Returned `jobs[*]` fields are fixed to:

- `id`
- `job_id`
- `title`
- `company`
- `description`
- `url`
- `location`
- `source`
- `status`
- `captured_at`

Behavior for missing values:

- Return `null` or empty string consistently per implementation convention.
- Do not append arbitrary DB columns to the contract.

## Deterministic Pagination Design

### Sort Order

All pages are sorted by:

1. `captured_at DESC`
2. `id DESC` (tie-breaker)

### Cursor Contents

Cursor is opaque externally; internally it encodes:

- `captured_at`
- `id`

Example internal payload before encoding:

```json
{"captured_at":"2026-02-04T03:47:36.966Z","id":3629}
```

### Page Boundary Predicate

Given cursor `(c_ts, c_id)` and sort `(captured_at DESC, id DESC)`, next page predicate is:

```sql
(captured_at < :c_ts) OR (captured_at = :c_ts AND id < :c_id)
```

### SQL Template

Without cursor:

```sql
SELECT id, job_id, title, company, description, url, location, source, status, captured_at
FROM jobs
WHERE status = 'new'
ORDER BY captured_at DESC, id DESC
LIMIT :limit_plus_one;
```

With cursor:

```sql
SELECT id, job_id, title, company, description, url, location, source, status, captured_at
FROM jobs
WHERE status = 'new'
  AND (
    captured_at < :cursor_ts
    OR (captured_at = :cursor_ts AND id < :cursor_id)
  )
ORDER BY captured_at DESC, id DESC
LIMIT :limit_plus_one;
```

Implementation note:

- Query `limit + 1` rows to compute `has_more`.
- Return first `limit` rows in `jobs`.
- `next_cursor` is built from the last returned row when `has_more=true`.

## Validation Rules

1. `limit` default = `50`
2. `limit < 1` => `VALIDATION_ERROR`
3. `limit > 1000` => `VALIDATION_ERROR`
4. malformed cursor => `VALIDATION_ERROR`
5. non-string `db_path` => `VALIDATION_ERROR`

## Read-Only Guarantees

The tool must never execute:

- `INSERT`
- `UPDATE`
- `DELETE`
- DDL statements

Only `SELECT` is allowed in this tool path.

DB connections must always be closed via context management.

## Error Handling Strategy

### Error Mapping

- Path does not exist / inaccessible -> `DB_NOT_FOUND` (`retryable=false`)
- SQLite operational/query failure -> `DB_ERROR` (`retryable` depends on subtype)
- Invalid input/cursor -> `VALIDATION_ERROR` (`retryable=false`)
- Unexpected uncaught exception -> `INTERNAL_ERROR` (`retryable=true`)

### Sanitization Policy

Sanitize:

- absolute filesystem paths (except requested `db_path` basename where useful)
- SQL fragments
- stack traces

Keep:

- actionable reason
- stable error code
- retry hint (`retryable`)

## Pseudocode

```python
async def bulk_read_new_jobs(args: dict) -> dict:
    limit = validate_limit(args.get("limit", 50))
    db_path = resolve_db_path(args.get("db_path"))
    cursor = decode_cursor(args.get("cursor"))

    with open_connection(db_path) as conn:
        rows = query_new_jobs(conn, limit=limit + 1, cursor=cursor)

    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1]) if has_more and page else None

    return {
        "jobs": [to_job_schema(r) for r in page],
        "count": len(page),
        "has_more": has_more,
        "next_cursor": next_cursor
    }
```

## Testing Strategy

### Unit Tests

1. default `limit=50`
2. invalid `limit` low/high
3. malformed cursor
4. DB not found via bad `db_path`
5. empty result set (`jobs=[]`, `count=0`, `has_more=false`)
6. schema field presence and type checks

### Pagination Tests

1. multi-page traversal has no duplicates
2. union of pages equals deterministic reference query
3. stable ordering across repeated runs on unchanged DB
4. `next_cursor` null only on terminal page

### Read-Only Tests

1. snapshot DB before/after; verify no row changes
2. verify no write statements are executed in reader path

### Property Tests (optional but recommended)

For randomized DB states:

- page results are deterministic
- no overlap across successive pages
- `count == len(jobs)`
- output remains JSON serializable

## Security Considerations

1. Parameterized SQL only
2. No dynamic SQL composition from untrusted input
3. Sanitized error output
4. Read-only operation path
5. Bounded `limit` prevents unbounded memory use

## Requirement Traceability

- Requirement 1 (batch + bounds + empty set): covered by Input/Validation + Pagination sections
- Requirement 2 (db path + filter + deterministic order): covered by Query + Deterministic Pagination sections
- Requirement 3 (stable schema + metadata): covered by Output Schema + Data Model Mapping
- Requirement 4 (read-only): covered by Read-Only Guarantees + tests
- Requirement 5 (structured errors): covered by Error Schema + Error Handling Strategy
- Requirement 6 (MCP interface compliance): covered by Interfaces + pseudocode + tests
