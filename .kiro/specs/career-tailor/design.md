# Design Document: career_tailor (Batch Full-Only)

## Overview

`career_tailor` is a **batch artifact tool** for resume tailoring.

For each tracker item, it performs one fixed full run:

1. parse tracker context
2. initialize workspace artifacts
3. regenerate `ai_context.md`
4. compile `resume.tex` -> `resume.pdf`

This tool does not finalize status. Final state commit stays in `finalize_resume_batch`.

Design goals:

1. keep interface simple (batch + full-only)
2. preserve per-item isolation and deterministic ordering
3. keep strict boundaries (no DB status writes, no tracker status writes)
4. return direct handoff payload for downstream finalize

## Scope

In scope:

- MCP tool interface for `career_tailor`
- batch tracker processing (`items[]`)
- workspace bootstrap (`resume/`, `cover/`, `cv/`)
- `resume.tex` create/overwrite behavior
- deterministic `ai_context.md` rendering
- compile gate with placeholder check + `pdflatex`
- per-item structured results + top-level `successful_items`

Out of scope:

- any call to `finalize_resume_batch`
- any DB status write (`resume_written`, `reviewed`, etc.)
- any tracker frontmatter status update
- compensation/rollback logic beyond item failure reporting

## Architecture

### Components

1. MCP Server (`server.py`)  
   registers `career_tailor`
2. Tool Handler (`tools/career_tailor.py`)  
   orchestrates batch flow and response shaping
3. Validation (`utils/validation.py`)  
   validates batch request and item schema
4. Tracker Parsing (`utils/tracker_parser.py`)  
   extracts frontmatter + `## Job Description`
5. Workspace + Slug (`utils/workspace.py`, `utils/slug_resolver.py`)  
   deterministic paths and directory bootstrap
6. Context Rendering (`utils/ai_context_renderer.py`)  
   renders `ai_context.md`
7. Guardrails + Compile (`utils/latex_guardrails.py`, `utils/latex_compiler.py`)  
   placeholder scan and `pdflatex` execution
8. Error Model (`models/errors.py`)  
   structured error taxonomy + sanitization

### Runtime Flow

1. Validate top-level request and `items[]`
2. Generate `run_id`, initialize counters
3. For each item in input order:
   - parse tracker
   - resolve deterministic workspace paths
   - ensure workspace dirs
   - materialize `resume.tex` (`created|preserved|overwritten`)
   - regenerate `ai_context.md`
   - placeholder scan
   - compile and verify `resume.pdf`
   - append item result
4. Aggregate totals
5. Build `successful_items` payload for downstream finalize step
6. Return structured batch response

If one item fails, record error and continue.

## MCP Interface

### Tool Name

- `career_tailor`

### Input Schema (Batch + Full-Only)

```json
{
  "type": "object",
  "properties": {
    "items": {
      "type": "array",
      "minItems": 1,
      "maxItems": 100,
      "items": {
        "type": "object",
        "properties": {
          "tracker_path": { "type": "string" },
          "job_db_id": { "type": "integer", "minimum": 1 }
        },
        "required": ["tracker_path"],
        "additionalProperties": false
      }
    },
    "force": { "type": "boolean", "default": false },
    "full_resume_path": { "type": "string" },
    "resume_template_path": { "type": "string" },
    "applications_dir": { "type": "string" },
    "pdflatex_cmd": { "type": "string" }
  },
  "required": ["items"],
  "additionalProperties": false
}
```

Notes:

- no `mode` field
- no `compile` flag
- each item always runs full flow

### Success Output Schema

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
    },
    {
      "tracker_path": "trackers/2026-02-06-meta-3630.md",
      "success": false,
      "error_code": "VALIDATION_ERROR",
      "error": "resume.tex contains placeholder tokens: PROJECT-AI-1"
    }
  ],
  "successful_items": [
    {
      "id": 3629,
      "tracker_path": "trackers/2026-02-06-amazon-3629.md",
      "resume_pdf_path": "data/applications/amazon-3629/resume/resume.pdf"
    }
  ],
  "warnings": [
    "Item trackers/2026-02-06-nodbid.md succeeded but has no job_db_id; excluded from successful_items"
  ]
}
```

### Error Output Schema (Top-Level)

```json
{
  "error": {
    "code": "VALIDATION_ERROR | FILE_NOT_FOUND | TEMPLATE_NOT_FOUND | COMPILE_ERROR | INTERNAL_ERROR",
    "message": "Human-readable message",
    "retryable": false
  }
}
```

Top-level errors are only for request-level or fatal init failures.
Item-level failures stay inside `results`.

## Key Behavior Decisions

### 1) Batch Isolation Without Compensation

- item failure does not trigger any fallback DB/tracker writes
- item failure does not revert previous successful items
- retry is achieved by rerunning failed items in next batch

### 2) Full-Only Compile Contract

- compile is always attempted for every item that passes initialization
- placeholder detection blocks compile early
- compile success requires non-empty `resume.pdf`

### 3) Finalize Handoff

- tool returns `successful_items` directly consumable by `finalize_resume_batch`
- only items with available `job_db_id` are included
- missing `job_db_id` is warning-level, not tailoring failure

### 4) Boundary Guarantees

`career_tailor` must not:

- change DB status
- change tracker status
- call finalize tools internally

## Pseudocode

```python
def career_tailor(args: dict) -> dict:
    req = validate_career_tailor_batch_parameters(args)
    run_id = generate_run_id("tailor")

    results = []
    warnings = []

    for item in req.items:  # preserve input order
        try:
            tracker = parse_tracker(item.tracker_path)
            slug = resolve_slug(tracker, item.job_db_id)
            ws = ensure_workspace(slug, req.applications_dir)

            action = materialize_resume_tex(
                template=req.resume_template_path,
                target=ws.resume_tex_path,
                force=req.force,
            )
            render_ai_context(
                tracker=tracker,
                full_resume_path=req.full_resume_path,
                output=ws.ai_context_path,
            )

            assert_no_placeholders(ws.resume_tex_path)
            compile_pdf(ws.resume_tex_path, req.pdflatex_cmd)
            assert_pdf_nonzero(ws.resume_pdf_path)

            results.append(success_result(...))
        except ToolError as e:
            results.append(failure_result(item, e.code, sanitize(e)))
        except Exception as e:
            results.append(failure_result(item, "INTERNAL_ERROR", sanitize(e)))

    successful_items = []
    for r in results:
        if r["success"] and r.get("job_db_id"):
            successful_items.append({
                "id": r["job_db_id"],
                "tracker_path": r["tracker_path"],
                "resume_pdf_path": r["resume_pdf_path"],
            })
        elif r["success"]:
            warnings.append("...excluded from successful_items due to missing job_db_id...")

    return aggregate_response(run_id, results, successful_items, warnings)
```

