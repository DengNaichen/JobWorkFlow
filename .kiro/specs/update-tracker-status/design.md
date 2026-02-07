# Design Document: update_tracker_status

## Overview

`update_tracker_status` updates the `status` field in tracker frontmatter with transition policy checks and `Resume Written` artifact guardrails. It is a tracker-only projection tool and does not mutate DB state.

This design is aligned with:

- `.kiro/specs/update-tracker-status/requirements.md`

Core design goals:

1. Deterministic and safe tracker status mutation
2. Strict guardrails for `Resume Written`
3. Atomic file writes with content preservation
4. Clear transition validation with optional `force` bypass
5. Structured output for orchestration and auditability

## Scope

In scope:

- MCP interface for single tracker status update
- Frontmatter parsing and controlled `status` mutation
- Transition policy validation
- Resume artifact guardrails for `Resume Written`
- Dry-run preview mode

Out of scope:

- DB reads/writes
- Resume compile/rewrite
- Multi-file batch update
- Tracker creation/deletion

## Architecture

### Components

1. MCP Server (`server.py`)
2. Tool Handler (`tools/update_tracker_status.py`)
3. Tracker Parser (`utils/tracker_parser.py`)
4. Tracker Writer (`utils/tracker_sync.py`)
5. Guardrail Validator (`utils/finalize_validators.py`)
6. Placeholder Scanner (`utils/latex_guardrails.py`)
7. Error Model (`models/errors.py`)

### Runtime Flow

1. LLM agent calls `update_tracker_status` with `tracker_path`, `target_status`, optional `dry_run`, optional `force`
2. Tool validates request schema and status vocabulary
3. Tool loads tracker and extracts current status + resume path metadata
4. Tool evaluates transition policy
5. If `target_status='Resume Written'`, tool performs artifact guardrails
6. If `dry_run=true`, return predicted action without file write
7. If write mode and checks pass, update only frontmatter `status` atomically
8. Return structured response

## Interfaces

### MCP Tool Name

- `update_tracker_status`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "tracker_path": {
      "type": "string",
      "description": "Path to tracker markdown file."
    },
    "target_status": {
      "type": "string",
      "enum": ["Reviewed", "Resume Written", "Applied", "Interview", "Offer", "Rejected", "Ghosted"]
    },
    "dry_run": {
      "type": "boolean",
      "default": false
    },
    "force": {
      "type": "boolean",
      "default": false,
      "description": "Allow transition-policy bypass with warning."
    }
  },
  "required": ["tracker_path", "target_status"],
  "additionalProperties": false
}
```

### Output Schema

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

Blocked example:

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

### Error Schema (Top-Level)

```json
{
  "error": {
    "code": "VALIDATION_ERROR | FILE_NOT_FOUND | INTERNAL_ERROR",
    "message": "Human-readable error",
    "retryable": false
  }
}
```

## Transition Policy Design

### Allowed Status Vocabulary

- `Reviewed`
- `Resume Written`
- `Applied`
- `Interview`
- `Offer`
- `Rejected`
- `Ghosted`

### Policy Rules

1. Same status target -> `noop`
2. Core forward transitions:
   - `Reviewed -> Resume Written`
   - `Resume Written -> Applied`
3. Terminal outcomes allowed from any source:
   - `Rejected`
   - `Ghosted`
4. Other transitions are policy violations unless `force=true`

On `force=true`, update may continue with warning.

## Resume Written Guardrails

Applied only when `target_status='Resume Written'`.

### Artifact Resolution

1. Parse `resume_path` from tracker frontmatter
2. Support:
   - wiki-link path: `[[data/applications/<slug>/resume/resume.pdf]]`
   - plain path: `data/applications/<slug>/resume/resume.pdf`
3. Resolve companion tex path: same directory + `resume.tex`

### Guardrail Checks

1. `resume.pdf` exists
2. `resume.pdf` size > 0
3. `resume.tex` exists
4. `resume.tex` does not contain placeholders:
   - `PROJECT-AI-`
   - `PROJECT-BE-`
   - `WORK-BULLET-POINT-`

Any failure returns blocked response and no write.

## File Mutation Strategy

### Write Constraints

1. Update only `status` in frontmatter
2. Preserve all non-status frontmatter fields
3. Preserve body content byte-for-byte

### Atomic Write

1. render updated tracker content
2. write to temporary file in same directory
3. `fsync` temp file
4. atomic rename (`os.replace`) into final path
5. cleanup temp on error

## Dry-Run Strategy

When `dry_run=true`:

- run same parse, transition, and guardrail checks as write mode
- no file write
- return predicted `action`:
  - `noop`
  - `would_update`
  - `blocked`

## Error Handling Strategy

### Top-Level Fatal Errors

- request shape/parameter errors -> `VALIDATION_ERROR`
- tracker path unreadable at initialization -> `FILE_NOT_FOUND`
- uncaught exceptions -> `INTERNAL_ERROR`

### In-Response Blocked Failures

- transition-policy violations
- guardrail failures
- write precondition failures

These return `success=false` and `action='blocked'`, not top-level fatal errors.

### Sanitization Policy

Sanitize all returned error text:

- no stack traces
- no sensitive absolute paths
- concise actionable reason

## Pseudocode

```python
def update_tracker_status(args: dict) -> dict:
    req = validate_update_tracker_status_args(args)

    tracker = parse_tracker(req.tracker_path)
    current = tracker.frontmatter["status"]

    if req.target_status == current:
        return success_noop(tracker, req)

    policy = validate_transition(current, req.target_status, req.force)
    if not policy.ok:
        return blocked_response(tracker, req, policy.error)

    guardrail_passed = None
    if req.target_status == "Resume Written":
        check = validate_resume_written_guardrails(tracker)
        guardrail_passed = check.ok
        if not check.ok:
            return blocked_response(tracker, req, check.error, guardrail_passed=False)

    if req.dry_run:
        return predicted_response(tracker, req, guardrail_passed)

    update_frontmatter_status_atomic(req.tracker_path, req.target_status)
    return updated_response(tracker, req, guardrail_passed)
```

## Testing Strategy

### Unit Tests

1. request schema validation
2. status vocabulary and whitespace handling
3. transition policy checks (`force` on/off)
4. resume path resolution (wiki-link and plain path)
5. placeholder scanner behavior

### Integration Tests

1. successful status update preserves tracker content except `status`
2. `Resume Written` blocked when `resume.pdf` missing
3. `Resume Written` blocked when placeholder remains in `resume.tex`
4. dry-run returns predicted action with no file mutation
5. atomic write failure leaves original tracker unchanged

### Boundary Tests

1. verify no DB read/write side effects
2. verify tool touches only provided tracker file

## Requirement Traceability

- Requirement 1 (interface): Input Schema + runtime flow
- Requirement 2 (parsing): Tracker parsing + top-level errors
- Requirement 3 (status set): Allowed Status Vocabulary
- Requirement 4 (transition): Transition Policy Design
- Requirement 5 (guardrails): Resume Written Guardrails
- Requirement 6 (path resolution): Artifact Resolution section
- Requirement 7 (writes): File Mutation Strategy
- Requirement 8 (dry-run): Dry-Run Strategy
- Requirement 9 (response): Output Schema + response examples
- Requirement 10 (errors): Error Handling Strategy
- Requirement 11 (boundaries): Scope + Boundary Tests
