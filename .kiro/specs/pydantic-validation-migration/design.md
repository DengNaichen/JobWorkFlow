# Design Document: pydantic-validation-migration

## Overview

This design migrates the current function-heavy validation approach to Pydantic v2 request/response schemas while preserving external MCP behavior.

The key principle is: keep runtime contract stable, change internal validation structure.

## Scope

In scope:

- Pydantic v2 request models for MCP tools currently validated via `utils/validation.py`
- Pydantic v2 response models for structured success payloads
- Adapter/mapping layer from Pydantic exceptions to `ToolError`
- Tool-by-tool phased migration with parity checks
- Spec alignment matrix across existing feature specs

Out of scope:

- Database schema changes
- New business rules unrelated to validation architecture
- Rewriting tool orchestration logic beyond validation boundary needs

## Current State Summary

Current validation is mostly centralized in:

- `mcp-server-python/utils/validation.py`

Error behavior is centralized through:

- `mcp-server-python/models/errors.py`

Current model style is function-based with many `validate_*` helpers and tuple returns. No Pydantic `BaseModel` usage is currently present in `mcp-server-python`.

## Target Architecture

### 1) Validation Package Structure

Introduce a dedicated schema package:

- `mcp-server-python/schemas/`
- `mcp-server-python/schemas/common.py`
- `mcp-server-python/schemas/<tool_name>.py`

Proposed file mapping:

- `schemas/bulk_read_new_jobs.py`
- `schemas/bulk_update_job_status.py`
- `schemas/scrape_jobs.py`
- `schemas/initialize_shortlist_trackers.py`
- `schemas/career_tailor.py`
- `schemas/update_tracker_status.py`
- `schemas/finalize_resume_batch.py`

### 2) Model Roles

For each tool:

- `*Request`: Input payload schema + field constraints + model validators
- `*Response`: Structured success output schema
- Optional nested models for per-item payloads/results

Example naming:

- `BulkReadNewJobsRequest`
- `BulkReadNewJobsResponse`
- `BulkUpdateJobStatusRequest`
- `BulkUpdateJobStatusResultItem`
- `BulkUpdateJobStatusResponse`

### 3) Validation Execution Flow

1. Tool handler receives raw `args: dict`
2. Tool handler calls request model validation (`model_validate`)
3. Pydantic exceptions are converted by adapter into existing `ToolError`
4. Business logic executes with typed model values
5. Success payload is built through response model and dumped to plain dict (`model_dump`)

### 4) Error Mapping Layer

Add dedicated mapper utility:

- `mcp-server-python/utils/pydantic_error_mapper.py`

Interface:

```python
from pydantic import ValidationError
from models.errors import ToolError

def map_pydantic_validation_error(err: ValidationError) -> ToolError:
    ...
```

Mapping rules:

- Pydantic validation issues -> `VALIDATION_ERROR`
- Keep sanitized, concise messages
- Preserve existing top-level error shape emitted by tools
- Do not expose raw stack traces or internal schema internals

### 5) Compatibility Strategy

During migration, existing helper validators remain available.

Pattern:

- Phase A: Pydantic models introduced, tools still call old validators
- Phase B: Tool switched to Pydantic input validation, old validators retained for fallback
- Phase C: Old validator functions removed only after parity and test completion

## Spec Alignment Matrix (Initial)

| Spec Scope | Primary Validation Surface | Planned Pydantic Module | Verification Method |
| --- | --- | --- | --- |
| bulk-read-new-jobs | limit/cursor/db_path | `schemas/bulk_read_new_jobs.py` | existing + migrated integration tests |
| bulk-update-job-status | batch updates + per-item id/status | `schemas/bulk_update_job_status.py` | existing suite + parity assertions |
| scrape-jobs-mcp | scrape query/limits/options | `schemas/scrape_jobs.py` | existing tool tests + invalid payload tests |
| initialize-shortlist-trackers | limit/path/flags | `schemas/initialize_shortlist_trackers.py` | existing tool tests |
| career-tailor | items + optional paths/flags | `schemas/career_tailor.py` | existing tool tests |
| update-tracker-status | tracker_path/target_status/flags | `schemas/update_tracker_status.py` | existing tool tests |
| finalize-resume-batch | items/run_id/db_path/dry_run | `schemas/finalize_resume_batch.py` | existing tool tests + edge regressions |

Status values per row:

- `Not Started`
- `In Progress`
- `Parity Confirmed`
- `Intentional Change Approved`

## Migration Phases

### Phase 1: Foundation

- Create schema package and shared constrained types
- Create error mapper and tests
- Add first migrated tool as reference implementation (`bulk_read_new_jobs` preferred)

Exit criteria:

- New schema package merged
- Mapper tests passing
- Reference tool parity validated

### Phase 2: Core Batch Tools

- Migrate `bulk_update_job_status`
- Migrate `finalize_resume_batch`

Exit criteria:

- Existing integration tests passing
- No external response contract regressions

### Phase 3: Pipeline Tools

- Migrate `scrape_jobs`
- Migrate `initialize_shortlist_trackers`
- Migrate `career_tailor`
- Migrate `update_tracker_status`

Exit criteria:

- Full tool suite green
- Alignment matrix updated to parity status per scope

### Phase 4: Cleanup

- Remove unused legacy validators from `utils/validation.py`
- Update docs and architecture references

Exit criteria:

- Dead code removed
- Documentation updated
- Final migration checklist complete

## Risks and Mitigations

1. Risk: subtle error message drift breaks clients that parse messages
   - Mitigation: preserve codes/shape as hard contract, only allow wording drift when approved

2. Risk: one-pass migration creates large blast radius
   - Mitigation: phased tool-by-tool rollout with fallback path

3. Risk: mixed validation paths increase temporary complexity
   - Mitigation: strict per-tool migration status and removal checklist

4. Risk: implicit coercion differs from legacy validators
   - Mitigation: use strict types/config in models for parity

## Observability and Verification

- Add migration status table in docs
- Compare old/new validation behavior with representative fixtures
- Keep CI gate on existing test suite (`uv run pytest -q`)
- Track unresolved parity gaps as explicit issues before cleanup phase
