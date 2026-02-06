# Design Document: career_tailor

## Overview

`career_tailor` is a workspace-initialization and compile-validation MCP tool. It consumes one tracker note, resolves deterministic application workspace paths, prepares `resume.tex` and `ai_context.md`, and optionally compiles `resume.pdf` with placeholder guardrails.

This design is aligned with:

- `.kiro/specs/career-tailor/requirements.md`

Core design goals:

1. Deterministic workspace resolution from tracker metadata
2. Safe idempotent initialization with explicit `force` semantics
3. Strict compile guardrails (`resume.tex` placeholder detection before compile)
4. Clear separation from DB/tracker status write-back
5. Structured output for downstream orchestration (`update_tracker_status`, `finalize_resume_batch`)

## Scope

In scope:

- MCP tool interface for `career_tailor`
- Tracker parsing and job description extraction
- Workspace directory bootstrap (`resume/`, `cover/`, `cv/`)
- `resume.tex` initialization from template
- `ai_context.md` generation from full resume + tracker JD
- Optional compile and PDF validation

Out of scope:

- Any DB read/write operation
- Tracker status mutation
- DB status mutation (`resume_written`)
- LLM rewrite logic itself (agent policy layer)

## Architecture

### Components

1. MCP Server (`server.py`)
2. Tool Handler (`tools/career_tailor.py`)
3. Tracker Parser (`utils/tracker_parser.py`)
4. Slug Resolver (`utils/slug_resolver.py`)
5. Workspace Service (`utils/workspace.py`)
6. Context Renderer (`utils/ai_context_renderer.py`)
7. Placeholder Scanner (`utils/latex_guardrails.py`)
8. LaTeX Compiler (`utils/latex_compiler.py`)
9. Error Model (`models/errors.py`)

### Runtime Flow

1. LLM agent calls `career_tailor` with `tracker_path`, optional `compile`, optional `force`
2. Tool validates input schema and filesystem paths
3. Tool parses tracker frontmatter and `## Job Description`
4. Tool resolves `application_slug` and workspace directories
5. Tool initializes/updates artifacts:
   - `resume/resume.tex` from template (created/preserved/overwritten by `force`)
   - `resume/ai_context.md` regenerated
6. If `compile=true`:
   - scan placeholders in `resume.tex`
   - fail fast if placeholders remain
   - run `pdflatex` and validate `resume.pdf`
7. Tool returns structured result with paths, actions, compile state

## Interfaces

### MCP Tool Name

- `career_tailor`

### Input Schema

```json
{
  "type": "object",
  "properties": {
    "tracker_path": {
      "type": "string",
      "description": "Path to tracker markdown file."
    },
    "compile": {
      "type": "boolean",
      "default": false,
      "description": "If true, run LaTeX compilation after workspace preparation."
    },
    "force": {
      "type": "boolean",
      "default": false,
      "description": "If true, overwrite existing resume.tex from template."
    },
    "full_resume_path": {
      "type": "string",
      "description": "Optional path override for full_resume.md."
    },
    "resume_template_path": {
      "type": "string",
      "description": "Optional path override for resume_skeleton.tex."
    },
    "applications_dir": {
      "type": "string",
      "description": "Optional root override for application workspaces."
    },
    "pdflatex_cmd": {
      "type": "string",
      "description": "Optional compile command override. Default: pdflatex."
    }
  },
  "required": ["tracker_path"],
  "additionalProperties": false
}
```

### Output Schema (Success)

```json
{
  "application_slug": "amazon",
  "workspace_dir": "data/applications/amazon",
  "resume_tex_path": "data/applications/amazon/resume/resume.tex",
  "ai_context_path": "data/applications/amazon/resume/ai_context.md",
  "resume_pdf_path": "data/applications/amazon/resume/resume.pdf",
  "compiled": true,
  "placeholder_check_passed": true,
  "resume_tex_action": "preserved",
  "warnings": []
}
```

When `compile=false`, `resume_pdf_path` may be `null` and `compiled=false`.

### Error Schema

```json
{
  "error": {
    "code": "VALIDATION_ERROR | FILE_NOT_FOUND | TEMPLATE_NOT_FOUND | COMPILE_ERROR | INTERNAL_ERROR",
    "message": "Human-readable error",
    "retryable": false
  }
}
```

## Tracker Parsing and Slug Resolution

### Tracker Requirements

Tracker parser extracts:

- frontmatter: `company`, `position`, `resume_path`, `reference_link`, optional `job_db_id`
- body section: `## Job Description` content

### Slug Resolution Priority

1. Parse slug from tracker `resume_path` pattern:
   - `[[data/applications/<slug>/resume/resume.pdf]]`
2. Fallback deterministic slug from metadata:
   - normalized `company`
   - append `job_db_id` when available to avoid collisions
3. Final fallback:
   - normalized company + short hash from `reference_link`

All slug paths must be deterministic for same inputs.

## Workspace and File Design

### Directory Layout

For `application_slug = <slug>`:

- `data/applications/<slug>/resume/`
- `data/applications/<slug>/cover/`
- `data/applications/<slug>/cv/`

### File Outputs

1. `resume/resume.tex`
   - source: `data/templates/resume_skeleton.tex` (or override)
   - action:
     - missing -> `created`
     - exists + `force=false` -> `preserved`
     - exists + `force=true` -> `overwritten`

2. `resume/ai_context.md`
   - regenerated each run
   - built from:
     - `full_resume.md`
     - tracker `## Job Description`
     - deterministic tailoring instructions

Writes must use atomic temp-file + rename semantics.

## AI Context Rendering

Generated markdown format:

```md
# AI Context

## Full Resume Source (raw)
<full_resume.md raw content>

## Job Description
<tracker job description content>

## Notes
- Created from tracker: <tracker_path>

## Instructions
- Tailor resume bullet text to the job description.
- Keep all claims truthful and grounded in full resume source.
- Do not fabricate experiences, metrics, or technologies.
- Keep LaTeX structure intact and only edit bullet content.
```

## Compile and Guardrail Design

### Placeholder Detection

Before compile, scanner checks for token patterns such as:

- `PROJECT-AI-`
- `PROJECT-BE-`
- `WORK-BULLET-POINT-`

If any placeholder remains:

- fail with `VALIDATION_ERROR`
- skip `pdflatex` invocation

### Compile Command

Default command:

```bash
pdflatex -interaction=nonstopmode resume.tex
```

Compile runs inside `data/applications/<slug>/resume/`.

### Compile Validation

Success requires:

1. command exits successfully
2. `resume.pdf` exists
3. `resume.pdf` file size > 0

Cleanup aux files:

- `resume.aux`
- `resume.log`
- `resume.out`
- `resume.synctex.gz`

## Idempotency Rules

1. `force=false` never overwrites existing `resume.tex`
2. `force=true` resets `resume.tex` from template
3. `ai_context.md` is always refreshed
4. repeated `compile=false` runs produce deterministic `resume_tex_action` outcomes
5. repeated `compile=true` runs recompile current `resume.tex` without mutating tracker/DB state

## Boundary Guarantees

The tool must not:

- query or mutate SQLite (`jobs.db`)
- mutate tracker files
- update tracker status
- mark DB status `resume_written`

The tool only:

- reads tracker/template/source resume files
- writes workspace artifacts under application directories

## Error Handling Strategy

### Error Mapping

- invalid request shape/arguments -> `VALIDATION_ERROR`
- missing tracker/full_resume file -> `FILE_NOT_FOUND`
- missing template file -> `TEMPLATE_NOT_FOUND`
- compile or toolchain failure -> `COMPILE_ERROR`
- unexpected exception -> `INTERNAL_ERROR`

### Sanitization Policy

Return concise actionable errors without:

- full stack trace
- secrets
- full absolute sensitive paths

Compile errors should include short diagnostics (for example first LaTeX error line).

## Pseudocode

```python
def career_tailor(args: dict) -> dict:
    req = validate_career_tailor_args(args)

    tracker = parse_tracker(req.tracker_path)
    slug = resolve_application_slug(tracker)
    ws = ensure_workspace(req.applications_dir, slug)  # resume/cover/cv

    resume_tex_action = materialize_resume_tex(
        template_path=req.resume_template_path,
        target_path=ws.resume_tex_path,
        force=req.force,
    )

    ai_context = render_ai_context(
        full_resume_path=req.full_resume_path,
        tracker=tracker,
        tracker_path=req.tracker_path,
    )
    atomic_write(ws.ai_context_path, ai_context)

    compiled = False
    placeholder_ok = None
    resume_pdf_path = None

    if req.compile:
        placeholders = scan_placeholders(ws.resume_tex_path)
        if placeholders:
            raise validation_error_for_placeholders(placeholders)

        placeholder_ok = True
        run_pdflatex(ws.resume_dir, req.pdflatex_cmd)
        validate_pdf(ws.resume_pdf_path)
        cleanup_aux(ws.resume_dir)

        compiled = True
        resume_pdf_path = ws.resume_pdf_path

    return {
        "application_slug": slug,
        "workspace_dir": ws.workspace_dir,
        "resume_tex_path": ws.resume_tex_path,
        "ai_context_path": ws.ai_context_path,
        "resume_pdf_path": resume_pdf_path,
        "compiled": compiled,
        "placeholder_check_passed": placeholder_ok,
        "resume_tex_action": resume_tex_action,
        "warnings": [],
    }
```

## Testing Strategy

### Unit Tests

1. argument validation (`tracker_path`, `compile`, `force`, override paths)
2. tracker parsing and `## Job Description` extraction
3. slug resolution priority and determinism
4. `ai_context.md` rendering format and section presence
5. placeholder scanner correctness

### Integration Tests

1. initialize workspace with `compile=false`
2. preserve/overwrite `resume.tex` with `force=false/true`
3. compile success path with valid tailored `resume.tex`
4. compile blocked when placeholders remain
5. compile failure surfaces `COMPILE_ERROR`

### Boundary Tests

1. verify no DB connections or DB file mutations
2. verify tracker file contents unchanged
3. verify writes are constrained to workspace directories

## Requirement Traceability

- Requirement 1 (validation): Input Schema + Error Mapping
- Requirement 2 (tracker parsing): Tracker Parsing section
- Requirement 3 (slug resolution): Slug Resolution Priority section
- Requirement 4 (workspace init): Workspace and File Design section
- Requirement 5 (ai_context): AI Context Rendering section
- Requirement 6 (idempotency): Idempotency Rules section
- Requirement 7 (compile): Compile Command + Compile Validation sections
- Requirement 8 (placeholder guardrail): Placeholder Detection section
- Requirement 9 (boundaries): Boundary Guarantees section
- Requirement 10 (response): Output Schema + pseudocode return payload
- Requirement 11 (errors): Error Handling Strategy section

