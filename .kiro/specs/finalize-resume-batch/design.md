# Design Document: finalize_resume_batch

## Overview

`finalize_resume_batch` is the commit/close-loop MCP tool for the resume pipeline. After compile success, it writes durable DB completion state and synchronizes tracker status to `Resume Written`, with per-item compensation fallback to `reviewed` on failure.

This design is aligned with:

- `.kiro/specs/finalize-resume-batch/requirements.md`

Core design goals:

1. Deterministic batch commit semantics with per-item isolation
2. Strong precondition checks before state transition
3. DB-first commit + compensation fallback strategy
4. Tracker synchronization without violating DB-as-SSOT
5. Structured response for retry orchestration

## Scope

In scope:

- MCP tool interface for `finalize_resume_batch`
- Per-item artifact validation (tracker/resume.tex/resume.pdf)
- DB update to completion audit fields
- Tracker frontmatter status synchronization
- Failure fallback to `reviewed` with `last_error`
- Dry-run simulation mode

Out of scope:

- Resume compilation
- Resume content rewriting
- Tracker creation
- Status transitions outside provided batch items

## Architecture

### Components

1. MCP Server (`server.py`)
2. Tool Handler (`tools/finalize_resume_batch.py`)
3. DB Writer Extension (`db/jobs_writer.py`)
4. Tracker Parser/Updater (`utils/tracker_parser.py`, `utils/tracker_sync.py`)
5. Artifact Validator (`utils/finalize_validators.py`)
6. Placeholder Scanner (`utils/latex_guardrails.py`)
7. Error Model (`models/errors.py`)

### Runtime Flow

1. LLM agent calls `finalize_resume_batch` with `items`, optional `run_id`, optional `dry_run`
2. Tool validates request-level parameters and duplicate IDs
3. Tool preflights DB connection + required schema columns
4. For each item in input order:
   - validate item shape
   - validate tracker and artifact prerequisites
   - resolve effective PDF path
   - if dry-run: return predicted action only
   - else execute finalize sequence with compensation
5. Tool aggregates item outcomes and returns batch result

## Interfaces

### MCP Tool Name

- `finalize_resume_batch`

### Input Schema

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
            "minimum": 1
          },
          "tracker_path": {
            "type": "string"
          },
          "resume_pdf_path": {
            "type": "string"
          }
        },
        "required": ["id", "tracker_path"],
        "additionalProperties": false
      },
      "minItems": 0,
      "maxItems": 100
    },
    "run_id": {
      "type": "string",
      "description": "Optional batch run identifier."
    },
    "db_path": {
      "type": "string",
      "description": "Optional SQLite path override."
    },
    "dry_run": {
      "type": "boolean",
      "default": false
    }
  },
  "required": ["items"],
  "additionalProperties": false
}
```

### Output Schema

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

## Data Contract and Schema Preconditions

### Required Jobs Table Columns

Finalization preflight must verify:

- `status`
- `updated_at`
- `resume_pdf_path`
- `resume_written_at`
- `run_id`
- `attempt_count`
- `last_error`

If any required column is missing, the tool fails before item processing.

### Status Transition Rules

Allowed finalize sources:

- `shortlist`
- `reviewed` (retry path)

Target on success:

- `resume_written`

Fallback target on item failure:

- `reviewed` with populated `last_error`

## Precondition Validation Design

For each item:

1. Validate item fields (`id`, `tracker_path`)
2. Load tracker and parse frontmatter
3. Resolve `resume_pdf_path`:
   - item override if provided
   - else from tracker frontmatter `resume_path` wiki-link
4. Verify `resume.pdf` exists and size > 0
5. Derive and verify `resume.tex` path exists
6. Scan `resume.tex` for placeholder tokens:
   - `PROJECT-AI-`
   - `PROJECT-BE-`
   - `WORK-BULLET-POINT-`

Any failure becomes per-item `failed` result and skips commit for that item.

## Finalization Commit Strategy

### Per-Item Sequence (non-dry-run)

1. Start DB transaction
2. Increment attempt counter
3. Update DB row to success target:
   - `status='resume_written'`
   - `resume_pdf_path=<validated path>`
   - `resume_written_at=<now_utc>`
   - `run_id=<batch_run_id>`
   - `attempt_count=attempt_count+1`
   - `last_error=NULL`
   - `updated_at=<now_utc>`
4. Commit DB transaction
5. Update tracker frontmatter `status` to `Resume Written` (atomic file write)
6. If tracker update succeeds: item `finalized`
7. If tracker update fails: execute compensation fallback

### Compensation Fallback

On tracker-sync failure after DB success:

1. Open new DB transaction
2. Set:
   - `status='reviewed'`
   - `last_error=<sanitized tracker sync error>`
   - `updated_at=<now_utc>`
3. Commit fallback
4. Return item as `failed`

This ensures failed finalization does not remain in `resume_written`.

## Dry-Run Strategy

When `dry_run=true`:

- perform full validation and planning
- do not mutate DB
- do not mutate tracker files
- return predicted `action` per item (`would_finalize`, `would_fail`, `already_finalized`)

## Determinism and Ordering

1. Results array preserves input order
2. Batch-level `run_id` is single value shared across all successful items in one call
3. Dry-run and non-dry-run use identical validation logic for consistent outcomes

## Error Handling Strategy

### Top-Level Fatal Errors

- malformed request -> `VALIDATION_ERROR`
- DB missing/unopenable -> `DB_NOT_FOUND`
- DB schema/query failures preventing processing -> `DB_ERROR`
- uncaught internal runtime errors -> `INTERNAL_ERROR`

### Per-Item Errors

- missing tracker
- missing/invalid resume artifacts
- placeholder remains
- tracker sync failure
- unknown job ID/status precondition failure

Per-item failures are reported in `results` and do not abort the batch.

### Sanitization Policy

Sanitize all reported errors:

- remove stack traces
- remove raw SQL fragments
- avoid sensitive absolute paths

Keep actionable summary for retry.

## Pseudocode

```python
def finalize_resume_batch(args: dict) -> dict:
    req = validate_finalize_request(args)
    run_id = req.run_id or generate_run_id()

    if req.items is empty:
        return empty_success(run_id, req.dry_run)

    with JobsWriter(req.db_path) as writer:
        writer.ensure_finalize_columns()

        results = []
        for item in req.items:
            pre = validate_finalize_item(item)
            if not pre.ok:
                results.append(item_failed(item, pre.error))
                continue

            artifact = validate_artifacts(item)
            if not artifact.ok:
                results.append(item_failed(item, artifact.error))
                continue

            if req.dry_run:
                results.append(item_predicted(item, artifact))
                continue

            try:
                writer.begin_item_tx()
                writer.finalize_success(
                    id=item.id,
                    run_id=run_id,
                    resume_pdf_path=artifact.resume_pdf_path,
                )
                writer.commit_item_tx()

                sync_tracker_status(item.tracker_path, "Resume Written")
                results.append(item_success(item, artifact.resume_pdf_path))

            except Exception as e:
                writer.finalize_fallback_reviewed(
                    id=item.id,
                    last_error=sanitize(str(e)),
                )
                results.append(item_failed(item, sanitize(str(e))))

    return summarize(run_id, req.dry_run, results)
```

## Testing Strategy

### Unit Tests

1. request/item validation and duplicate-ID checks
2. tracker parsing and resume path resolution
3. placeholder scanner and artifact validators
4. response aggregation/count correctness

### Integration Tests

1. successful finalize updates DB audit fields + tracker status
2. missing artifacts produce item failure without DB success write
3. tracker sync failure triggers DB fallback to `reviewed` + `last_error`
4. dry-run produces predicted outcomes with no writes
5. mixed batch continues processing after one item failure

### Schema and Boundary Tests

1. missing required DB columns fails preflight
2. only provided IDs are updated
3. no compile/rewrite side effects in finalize tool

## Requirement Traceability

- Requirement 1 (batch interface): Input Schema + runtime flow
- Requirement 2 (item validation): Precondition Validation Design
- Requirement 3 (artifact gate): Precondition Validation Design
- Requirement 4 (schema preflight): Data Contract and Schema Preconditions
- Requirement 5 (DB success writes): Finalization Commit Strategy
- Requirement 6 (tracker sync): Finalization Commit Strategy
- Requirement 7 (fallback): Compensation Fallback
- Requirement 8 (idempotency/retry): Status rules + commit behavior
- Requirement 9 (dry-run): Dry-Run Strategy
- Requirement 10 (response): Output Schema + summarize pseudocode
- Requirement 11 (errors): Error Handling Strategy
- Requirement 12 (boundaries): Scope (out-of-scope) + Boundary tests
