# JobWorkFlow Steering

This document defines project-wide steering rules for all Kiro specs under `.kiro/specs/`.

## 1) System Intent

JobWorkFlow is a local-first, self-hosted job operations pipeline.

- SSOT: SQLite `jobs` table status is the source of truth.
- Projection: Tracker markdown is a board-friendly projection of DB milestones.
- Execution boundary: MCP tools execute deterministic operations; policy decisions are made by the LLM layer.

## 2) Source-of-Truth and Boundaries

Every spec and implementation MUST preserve these boundaries:

- `bulk_read_new_jobs`: read-only DB access (`status=new` queue retrieval).
- `bulk_update_job_status`: DB status write-back only (atomic batch update).
- `initialize_shortlist_trackers`: creates tracker artifacts from DB shortlist set (idempotent with force flag).
- `career_tailor`: workspace preparation + optional LaTeX compile only; no DB/status finalization.
- `finalize_resume_batch`: commit step for DB + tracker milestone projection when resume compile is valid.
- `update_tracker_status`: tracker-only status updates with guardrails; cannot redefine DB authority.

Out-of-bound writes are not allowed (for example, tailoring tool writing DB state).

## 3) Canonical Status Model

Allowed DB statuses:

- `new`
- `shortlist`
- `reviewed`
- `reject`
- `resume_written`
- `applied`

Canonical transitions:

- `new -> shortlist | reviewed | reject`
- `shortlist -> resume_written` (only after successful finalize step)
- `shortlist -> reviewed` (on rewrite/compile/finalize failure with `last_error`)
- `resume_written -> applied` (manual or later automation)

Tracker statuses are projections and must not become competing truth.

## 4) Non-Negotiable Guardrails

- Compile gate: no placeholder tokens in `resume.tex` before compile.
- Resume gate: `Resume Written` tracker transition requires valid non-empty `resume.pdf`.
- Failure fallback: any finalization failure lands item in `reviewed` with actionable `last_error`.
- Determinism: no random/time-based IDs for slugs, cursor semantics, or generated paths.
- Idempotency: repeated runs with unchanged input should be safe and predictable.

## 5) File and Path Conventions

- Database default: `data/capture/jobs.db`
- Application workspace root: `data/applications/<application_slug>/`
- Tracker root: `trackers/`
- Resume assets:
  - `resume/resume.tex`
  - `resume/resume.pdf`
  - `resume/ai_context.md`
- Template defaults:
  - `data/templates/resume_skeleton.tex`
  - `data/templates/full_resume.md`

Paths returned by tools should be deterministic and JSON-serializable.

## 6) Tool Contract Rules

All MCP tools should follow common contract behavior:

- Strict input validation (type checks, unknown key rejection where specified).
- Typed error categories: `VALIDATION_ERROR`, `FILE_NOT_FOUND`, `TEMPLATE_NOT_FOUND`, `COMPILE_ERROR`, `INTERNAL_ERROR`.
- Include `retryable` for top-level errors.
- Sanitize error details (no sensitive paths/secrets, no raw stack traces).
- Keep success payload explicit and machine-consumable.

### 6.1) Unified Error Contract

Error responses should follow one stable shape across tools:

- `code`: machine-readable error code
- `message`: concise, user-readable summary
- `retryable`: boolean retry hint
- `details`: optional structured diagnostics (sanitized)

Rules:

- Do not rename/remove these top-level error fields per tool.
- Tool-specific diagnostics should be placed in `details`, not as ad-hoc top-level keys.
- Keep `code` values aligned with project taxonomy (for example `VALIDATION_ERROR`, `FILE_NOT_FOUND`, `COMPILE_ERROR`, `INTERNAL_ERROR`).

## 7) Dev Tooling and Quality Standards

### 7.1) Dev Tooling Standard

Project-wide Python tooling baseline:

- Dependency and task runner: `uv`
- Lint/format tool: `ruff`

Expected local workflow before commit:

1. `uv run ruff format .`
2. `uv run ruff check . --fix`
3. `uv run pytest -q`

Notes:

- CI and local commands should prefer `uv run ...` for consistency.
- If a submodule needs stricter scope, run commands from that directory (for example `mcp-server-python/`).
- Any spec that adds Python code should include task/checklist items for lint, format, and tests.

### 7.2) Observability Baseline

All tools should emit structured logs with consistent core fields:

- `tool_name`
- `run_id`
- `job_id` (when applicable)
- `duration_ms`
- `result` (`success` or `error`)

Guidelines:

- Log enough context for triage and latency tracking.
- Do not log full sensitive payloads; prefer identifiers and summaries.
- Keep log schema stable to preserve downstream analysis.

### 7.3) Testing and Quality Gates

Each spec implementation should include:

- Unit tests for validation, happy path, and edge conditions.
- Failure-mode tests for guardrails and error mapping.
- Idempotency/determinism checks for repeated execution.
- Boundary tests to ensure no cross-domain side effects (e.g., tracker tool does not touch DB unexpectedly).

Prefer targeted tests first, then broader integration coverage.

## 8) Delivery Sequence for Current Roadmap

Recommended merge order to reduce conflicts and preserve pipeline integrity:

1. `initialize_shortlist_trackers`
2. `update_tracker_status`
3. `career_tailor`
4. `finalize_resume_batch`
5. Follow-up hardening and automation wiring

If parallelized with worktrees, rebase frequently onto the same baseline and merge in this order.

## 9) PR / Spec Review Checklist

A spec or PR is not ready unless all are true:

- Boundaries are explicit and respected.
- State transitions are aligned with canonical model.
- Guardrails are test-backed.
- Error taxonomy is consistent with project contract.
- Determinism/idempotency claims are demonstrated.
- README and spec task status are updated accordingly.

## 10) Change Control

Any change to statuses, canonical transitions, or cross-tool boundaries requires:

1. Steering update in this file
2. Spec updates in impacted `.kiro/specs/*`
3. Test updates validating the new behavior

Treat this file as the constitution for project-level behavior.

## 11) Security and Secrets Hygiene

Sensitive data must not be persisted in tracker files, database error fields, or logs.

- Never commit secrets (API keys, tokens, cookies, credentials).
- Never write secrets or personal sensitive data into tracker frontmatter/body, `last_error`, or tool logs.
- Keep environment secrets in local env files/config outside versioned source when possible.
- Ensure `.env` and equivalent secret-bearing files are excluded from git.
