#!/usr/bin/env python3
"""
MCP Server entry point for JobWorkFlow bulk_read_new_jobs tool.

This server provides a read-only MCP tool for retrieving jobs with status='new'
from a SQLite database in deterministic batches with cursor-based pagination.

The server uses the FastMCP framework to expose the bulk_read_new_jobs tool
to LLM agents via the Model Context Protocol.

Usage:
    python server.py

The server runs in stdio mode by default, which is the standard transport
for MCP servers that are invoked by LLM agents.
"""

import logging
from mcp.server.fastmcp import FastMCP
from tools.bulk_read_new_jobs import bulk_read_new_jobs
from tools.bulk_update_job_status import bulk_update_job_status
from tools.initialize_shortlist_trackers import initialize_shortlist_trackers
from tools.update_tracker_status import update_tracker_status
from tools.finalize_resume_batch import finalize_resume_batch
from tools.scrape_jobs import scrape_jobs
from tools.career_tailor import career_tailor
from config import get_config

# Create FastMCP server instance
config = get_config()
mcp = FastMCP(
    name=config.server_name,
    instructions=(
        "This server provides tools for JobWorkFlow operations. "
        "\n\n"
        "INGESTION BOUNDARY:\n"
        "Use scrape_jobs to scrape fresh job postings from external sources and ingest them into the database. "
        "This tool is INGESTION-ONLY: it inserts new jobs with status='new' and performs idempotent dedupe by URL. "
        "It does NOT invoke tracker creation, finalization, or status tools. "
        "It does NOT perform triage decisions or update existing job statuses. "
        "Use this tool to feed the 'new' queue for downstream triage processing."
        "\n\n"
        "TRIAGE AND WORKFLOW TOOLS:\n"
        "Use bulk_read_new_jobs to retrieve jobs with status='new' from the database. "
        "Use bulk_update_job_status to update job statuses in atomic batches. "
        "Use initialize_shortlist_trackers to create tracker markdown files for shortlisted jobs. "
        "Use career_tailor to run batch full-tailoring (workspace bootstrap + ai_context generation + compile) without changing DB/tracker statuses. "
        "Use update_tracker_status to update tracker frontmatter status with transition policy checks and Resume Written guardrails. "
        "Use finalize_resume_batch to commit resume completion state by updating DB audit fields and synchronizing tracker status after successful resume compilation."
    ),
)


@mcp.tool(
    name="scrape_jobs",
    description=(
        "Scrape fresh job postings from external sources and ingest them into SQLite database. "
        "Supports multi-term scraping with preflight checks, normalization, filtering, and idempotent insertion. "
        "Returns structured run results with per-term outcomes and aggregate totals."
    ),
)
def scrape_jobs_tool(
    terms: list[str] | None = None,
    location: str | None = None,
    sites: list[str] | None = None,
    results_wanted: int | None = None,
    hours_old: int | None = None,
    db_path: str | None = None,
    status: str | None = None,
    require_description: bool | None = None,
    preflight_host: str | None = None,
    retry_count: int | None = None,
    retry_sleep_seconds: float | None = None,
    retry_backoff: float | None = None,
    save_capture_json: bool | None = None,
    capture_dir: str | None = None,
    dry_run: bool | None = None,
) -> dict:
    """
    Scrape fresh job postings from external sources and ingest them into SQLite database.

    This tool provides step-1 ingestion for JobWorkFlow: scrape fresh postings from
    external job sources (JobSpy-backed), normalize records, and insert them into
    SQLite as status='new' items for downstream triage. Supports multi-term scraping
    with per-term isolation, preflight DNS checks, optional capture artifacts, and
    idempotent dedupe by URL.

    Args:
        terms: Search terms array (default: ['ai engineer', 'backend engineer', 'machine learning']).
        location: Search location (default: 'Ontario, Canada').
        sites: Source sites list (default: ['linkedin']).
        results_wanted: Requested scrape results per term, 1-200 (default: 20).
        hours_old: Recency window in hours, 1-168 (default: 2).
        db_path: Optional SQLite path override (default: data/capture/jobs.db).
        status: Initial status for inserted rows (default: 'new').
            Must be one of: new, shortlist, reviewed, reject, resume_written, applied.
        require_description: Skip records without descriptions (default: true).
        preflight_host: DNS preflight host (default: 'www.linkedin.com').
        retry_count: Preflight retry count, 1-10 (default: 3).
        retry_sleep_seconds: Base retry sleep seconds, 0-300 (default: 30).
        retry_backoff: Retry backoff multiplier, 1-10 (default: 2).
        save_capture_json: Persist per-term raw JSON capture files (default: true).
        capture_dir: Capture output directory (default: data/capture).
        dry_run: Compute counts only; no DB writes (default: false).

    Returns:
        Dictionary with structure (success or partial success):
        {
            "run_id": str,              # Unique run identifier (scrape_YYYYMMDD_<hex>)
            "started_at": str,          # ISO 8601 UTC timestamp
            "finished_at": str,         # ISO 8601 UTC timestamp
            "duration_ms": int,         # Total run duration in milliseconds
            "dry_run": bool,            # Whether this was a dry-run
            "results": [                # Per-term results in input order
                {
                    "term": str,
                    "success": bool,
                    "fetched_count": int,
                    "cleaned_count": int,
                    "inserted_count": int,
                    "duplicate_count": int,
                    "skipped_no_url": int,
                    "skipped_no_description": int,
                    "capture_path": str,    # Optional, if save_capture_json=true
                    "error": str            # Optional, only on failure
                }
            ],
            "totals": {
                "term_count": int,
                "successful_terms": int,
                "failed_terms": int,
                "fetched_count": int,
                "cleaned_count": int,
                "inserted_count": int,
                "duplicate_count": int,
                "skipped_no_url": int,
                "skipped_no_description": int
            }
        }

        On top-level fatal error, returns:
        {
            "error": {
                "code": str,            # VALIDATION_ERROR, DB_NOT_FOUND, DB_ERROR, INTERNAL_ERROR
                "message": str,         # Human-readable error message
                "retryable": bool       # Whether operation can be retried
            }
        }

    Examples:
        # Scrape with default settings (3 default terms, Ontario Canada, LinkedIn, 2 hours)
        scrape_jobs_tool()

        # Scrape custom terms
        scrape_jobs_tool(
            terms=["python developer", "data scientist"],
            location="Toronto, ON"
        )

        # Scrape with custom limits and multiple sites
        scrape_jobs_tool(
            terms=["software engineer"],
            results_wanted=50,
            hours_old=24,
            sites=["linkedin", "indeed"]
        )

        # Dry-run to preview counts without DB writes
        scrape_jobs_tool(
            terms=["backend engineer"],
            dry_run=True
        )

        # Scrape without description requirement
        scrape_jobs_tool(
            terms=["frontend developer"],
            require_description=False
        )

        # Use custom paths
        scrape_jobs_tool(
            terms=["devops engineer"],
            db_path="custom/path/jobs.db",
            capture_dir="custom/capture"
        )

    Behavior:
        - Processes each term in deterministic order with isolation
        - Per-term failures do not block other terms (partial success)
        - Preflight DNS checks with configurable retry/backoff
        - Normalizes raw source records to stable schema
        - Filters records by URL presence and optional description requirement
        - Inserts with idempotent dedupe by URL (INSERT OR IGNORE)
        - Optionally writes per-term capture JSON files for audit
        - Dry-run mode performs all steps except DB writes
        - Returns structured response with per-term and aggregate metrics

    Validation Rules:
        - terms: Non-empty array of strings
        - results_wanted: 1-200
        - hours_old: 1-168
        - retry_count: 1-10
        - retry_sleep_seconds: 0-300
        - retry_backoff: 1-10
        - status: Must be in allowed DB status set
        - No unknown request properties allowed

    Database Behavior:
        - Creates jobs table and index if missing (bootstrap)
        - Uses INSERT OR IGNORE for idempotent dedupe by URL
        - Sets status='new' by default (or validated override)
        - Does NOT update existing rows on dedupe hits
        - Does NOT modify tracker files or perform triage decisions

    Requirements:
        - Requirement 1.1: MCP tool named 'scrape_jobs'
        - Requirement 1.2: Default parameters for terms, location, sites, time window
        - Requirement 1.3: Multi-term processing in one run
        - Requirement 1.4: Parameter validation before operations
        - Requirement 1.5: Reject unknown request fields
        - Requirement 2.1-2.5: Preflight DNS checks with retry
        - Requirement 3.1-3.5: Source retrieval with term isolation
        - Requirement 4.1-4.5: Record normalization
        - Requirement 5.1-5.5: Filtering rules
        - Requirement 6.1-6.5: Database path and schema bootstrap
        - Requirement 7.1-7.5: Insert with dedupe semantics
        - Requirement 8.1-8.5: Queue status and boundary rules
        - Requirement 9.1-9.5: Optional capture artifact output
        - Requirement 10.1-10.5: Structured response contract
        - Requirement 11.1-11.5: Error handling and sanitization
        - Requirement 12.1-12.5: MCP registration and operational limits
    """
    # Build arguments dictionary for the tool handler
    args = {}

    # Only include parameters that were explicitly provided
    if terms is not None:
        args["terms"] = terms
    if location is not None:
        args["location"] = location
    if sites is not None:
        args["sites"] = sites
    if results_wanted is not None:
        args["results_wanted"] = results_wanted
    if hours_old is not None:
        args["hours_old"] = hours_old
    if db_path is not None:
        args["db_path"] = db_path
    if status is not None:
        args["status"] = status
    if require_description is not None:
        args["require_description"] = require_description
    if preflight_host is not None:
        args["preflight_host"] = preflight_host
    if retry_count is not None:
        args["retry_count"] = retry_count
    if retry_sleep_seconds is not None:
        args["retry_sleep_seconds"] = retry_sleep_seconds
    if retry_backoff is not None:
        args["retry_backoff"] = retry_backoff
    if save_capture_json is not None:
        args["save_capture_json"] = save_capture_json
    if capture_dir is not None:
        args["capture_dir"] = capture_dir
    if dry_run is not None:
        args["dry_run"] = dry_run

    # Call the tool handler and return the result
    return scrape_jobs(**args)


@mcp.tool(
    name="bulk_read_new_jobs",
    description=(
        "Retrieve jobs with status='new' from SQLite database in configurable batches. "
        "Supports cursor-based pagination for efficient retrieval of large result sets. "
        "Returns job records with metadata including count, has_more flag, and next_cursor."
    ),
)
def bulk_read_new_jobs_tool(
    limit: int = 50,
    cursor: str | None = None,
    db_path: str | None = None,
) -> dict:
    """
    Retrieve jobs with status='new' in configurable batches with cursor-based pagination.
    
    This tool provides read-only batch retrieval of job records from a SQLite database
    for downstream LLM triage processing. It maintains deterministic ordering and
    supports pagination through large result sets.
    
    Args:
        limit: Batch size (1-1000, default 50). Number of jobs to retrieve in this page.
        cursor: Opaque pagination cursor returned by previous call. Use to retrieve next page.
        db_path: Optional database path override (default: data/capture/jobs.db).
    
    Returns:
        Dictionary with structure:
        {
            "jobs": [
                {
                    "id": int,
                    "job_id": str,
                    "title": str,
                    "company": str,
                    "description": str,
                    "url": str,
                    "location": str,
                    "source": str,
                    "status": str,
                    "captured_at": str
                },
                ...
            ],
            "count": int,            # Number of jobs in this page
            "has_more": bool,        # Whether more pages exist
            "next_cursor": str|None  # Cursor for next page, or None if terminal page
        }
        
        On error, returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }
    
    Examples:
        # Retrieve first page with default limit (50 jobs)
        bulk_read_new_jobs_tool()
        
        # Retrieve first page with custom limit
        bulk_read_new_jobs_tool(limit=100)
        
        # Retrieve next page using cursor from previous response
        bulk_read_new_jobs_tool(limit=50, cursor="eyJjYXB0dXJlZF9hdCI6...")
        
        # Use custom database path
        bulk_read_new_jobs_tool(db_path="custom/path/jobs.db")
    
    Requirements:
        - Requirement 1: Batch Job Retrieval with configurable size
        - Requirement 2: Database Query with deterministic ordering
        - Requirement 3: Job Data Structure with stable schema
        - Requirement 4: Read-Only Operations (no database modifications)
        - Requirement 5: Error Handling with structured errors
        - Requirement 6: MCP Tool Interface compliance
        - Requirement 7: Cursor-Based Pagination support
    """
    # Build arguments dictionary for the tool handler
    args = {}
    
    # Only include parameters that were explicitly provided
    # This allows the tool handler to apply its own defaults
    if limit != 50:  # Only include if non-default
        args["limit"] = limit
    if cursor is not None:
        args["cursor"] = cursor
    if db_path is not None:
        args["db_path"] = db_path
    
    # Call the tool handler and return the result
    return bulk_read_new_jobs(args)


@mcp.tool(
    name="bulk_update_job_status",
    description=(
        "Update multiple job statuses in a single atomic transaction. "
        "Validates status values, checks job existence, and ensures all-or-nothing semantics. "
        "Returns detailed success/failure results for each job in the batch."
    ),
)
def bulk_update_job_status_tool(
    updates: list[dict],
    db_path: str | None = None,
) -> dict:
    """
    Update multiple job statuses in a single atomic transaction.
    
    This tool provides write-only batch status updates for job records in SQLite.
    It validates all inputs, checks job existence, and applies updates atomically
    with all-or-nothing semantics. All jobs in a batch receive the same timestamp.
    
    Args:
        updates: Array of update items, each containing:
            - id (int): Job ID to update (must be positive integer)
            - status (str): Target status value (must be one of: new, shortlist, 
                           reviewed, reject, resume_written, applied)
        db_path: Optional database path override (default: data/capture/jobs.db).
    
    Returns:
        Dictionary with structure (success case):
        {
            "updated_count": int,    # Number of jobs successfully updated
            "failed_count": 0,       # Number of failed updates
            "results": [             # Per-job results in input order
                {
                    "id": int,
                    "success": true
                },
                ...
            ]
        }
        
        Dictionary with structure (validation failure case):
        {
            "updated_count": 0,
            "failed_count": int,
            "results": [
                {
                    "id": int,
                    "success": false,
                    "error": str     # Specific error message for this job
                },
                ...
            ]
        }
        
        On system error, returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }
    
    Examples:
        # Update single job status
        bulk_update_job_status_tool(
            updates=[{"id": 123, "status": "shortlist"}]
        )
        
        # Update multiple jobs in one atomic transaction
        bulk_update_job_status_tool(
            updates=[
                {"id": 123, "status": "shortlist"},
                {"id": 456, "status": "reviewed"},
                {"id": 789, "status": "reject"}
            ]
        )
        
        # Use custom database path
        bulk_update_job_status_tool(
            updates=[{"id": 123, "status": "applied"}],
            db_path="custom/path/jobs.db"
        )
    
    Validation Rules:
        - Batch size: 0-100 updates (empty batch returns success with zero counts)
        - Job IDs: Must be positive integers and exist in database
        - Status values: Must be one of the allowed statuses (case-sensitive, no whitespace)
        - No duplicate job IDs within one batch
        - All updates succeed or all fail (atomic transaction)
    
    Requirements:
        - Requirement 1: Batch Status Updates (1-100 items, atomic)
        - Requirement 2: Status Validation (allowed set, case-sensitive)
        - Requirement 3: Job Existence Validation (all IDs must exist)
        - Requirement 4: Atomic Transaction Semantics (all-or-nothing)
        - Requirement 5: Idempotent Updates (safe to retry)
        - Requirement 6: Timestamp Tracking (ISO 8601 UTC format)
        - Requirement 7: Database Operations (parameterized SQL)
        - Requirement 8: Structured Response Format (per-job results)
        - Requirement 9: Error Handling (sanitized messages)
        - Requirement 10: MCP Tool Interface (standard compliance)
        - Requirement 11: Write-Only Operations (no data returned)
    """
    # Build arguments dictionary for the tool handler
    args = {"updates": updates}
    
    # Only include db_path if explicitly provided
    if db_path is not None:
        args["db_path"] = db_path
    
    # Call the tool handler and return the result
    return bulk_update_job_status(args)


@mcp.tool(
    name="initialize_shortlist_trackers",
    description=(
        "Initialize tracker markdown files for jobs with status='shortlist'. "
        "Creates deterministic tracker notes with frontmatter and workspace directories. "
        "Supports idempotent operation with force overwrite and dry-run planning modes."
    ),
)
def initialize_shortlist_trackers_tool(
    limit: int = 50,
    db_path: str | None = None,
    trackers_dir: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Initialize tracker markdown files for jobs with status='shortlist'.

    This tool provides projection-oriented tracker initialization that reads shortlisted
    jobs from the database (SSOT) and creates deterministic tracker markdown files with
    stable frontmatter and linked workspace directories. It does NOT modify database records.

    Args:
        limit: Number of shortlist jobs to process (1-200, default 50).
        db_path: Optional database path override (default: data/capture/jobs.db).
        trackers_dir: Optional trackers directory override (default: trackers/).
        force: If True, overwrite existing tracker files (default: False).
        dry_run: If True, compute outcomes without writing files (default: False).

    Returns:
        Dictionary with structure:
        {
            "created_count": int,    # Number of trackers created/overwritten
            "skipped_count": int,    # Number of trackers skipped (already exist)
            "failed_count": int,     # Number of trackers that failed
            "results": [             # Per-item results in selection order
                {
                    "id": int,                    # Database job ID
                    "job_id": str,                # External job identifier
                    "tracker_path": str,          # Path to tracker file
                    "action": str,                # "created", "skipped_exists", "overwritten", "failed"
                    "success": bool,              # Whether operation succeeded
                    "error": str                  # Error message (optional, only on failure)
                }
            ]
        }

        On error, returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }

    Examples:
        # Initialize trackers for first 50 shortlisted jobs (default)
        initialize_shortlist_trackers_tool()

        # Initialize trackers with custom limit
        initialize_shortlist_trackers_tool(limit=100)

        # Overwrite existing tracker files
        initialize_shortlist_trackers_tool(force=True)

        # Dry-run to preview what would be created
        initialize_shortlist_trackers_tool(dry_run=True)

        # Use custom paths
        initialize_shortlist_trackers_tool(
            db_path="custom/path/jobs.db",
            trackers_dir="custom/trackers"
        )

    Behavior:
        - Reads jobs where status='shortlist' ordered by captured_at DESC, id DESC
        - Creates deterministic tracker filenames: YYYY-MM-DD-company_slug-id.md
        - Creates workspace directories: data/applications/<slug>/resume/ and cover/
        - Idempotent: skips existing files unless force=True
        - Atomic writes: uses temp file + rename to prevent partial writes
        - Continues batch on per-item failures
        - Dry-run mode computes outcomes without creating files/directories

    Requirements:
        - Requirement 1: Shortlist Source Selection (status='shortlist', deterministic order)
        - Requirement 2: Tracker File Generation (stable frontmatter, required sections)
        - Requirement 3: Workspace Linking (deterministic slug, linked artifact paths)
        - Requirement 4: Idempotent Initialization (force semantics, no duplicates)
        - Requirement 5: Atomic Per-File Writes (temp + rename, per-item failure handling)
        - Requirement 6: Database Boundaries (read-only, no status mutations)
        - Requirement 7: Structured Response Format (counts and per-item results)
        - Requirement 8: Error Handling (sanitized messages, categorized errors)
        - Requirement 9: MCP Tool Interface (validated inputs, dry-run support)
        - Requirement 10: Tracker Content Compatibility (Obsidian Dataview compatible)
    """
    # Build arguments dictionary for the tool handler
    args = {}

    # Only include parameters that were explicitly provided or differ from defaults
    if limit != 50:  # Only include if non-default
        args["limit"] = limit
    if db_path is not None:
        args["db_path"] = db_path
    if trackers_dir is not None:
        args["trackers_dir"] = trackers_dir
    if force:  # Only include if True
        args["force"] = force
    if dry_run:  # Only include if True
        args["dry_run"] = dry_run

    # Call the tool handler and return the result
    return initialize_shortlist_trackers(args)


@mcp.tool(
    name="update_tracker_status",
    description=(
        "Update tracker frontmatter status with transition policy checks and Resume Written guardrails. "
        "Validates status transitions, enforces artifact requirements for Resume Written status, "
        "and supports dry-run preview mode. Operates only on tracker files without modifying database."
    ),
)
def update_tracker_status_tool(
    tracker_path: str,
    target_status: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict:
    """
    Update tracker frontmatter status with transition policy and guardrails.

    This tool provides safe tracker status updates with transition validation and
    Resume Written artifact guardrails. It updates only the tracker frontmatter status
    field while preserving all other content. The tool enforces workflow progression
    rules and validates resume artifacts before allowing Resume Written status.

    Args:
        tracker_path: Path to tracker markdown file (required).
        target_status: Target status value (required). Must be one of:
            - Reviewed
            - Resume Written
            - Applied
            - Interview
            - Offer
            - Rejected
            - Ghosted
        dry_run: Preview mode without file write (default: False).
            When True, performs all validation checks but does not modify the file.
        force: Bypass transition policy with warning (default: False).
            When True, allows policy-violating transitions but includes warning in response.

    Returns:
        Dictionary with structure (success case):
        {
            "tracker_path": str,
            "previous_status": str,
            "target_status": str,
            "action": str,              # "updated", "noop", "would_update"
            "success": true,
            "dry_run": bool,
            "guardrail_check_passed": bool,  # Present if guardrails were evaluated
            "warnings": []              # List of warning messages
        }

        Dictionary with structure (blocked case):
        {
            "tracker_path": str,
            "previous_status": str,
            "target_status": str,
            "action": "blocked",
            "success": false,
            "dry_run": bool,
            "error": str,               # Reason for blocking
            "guardrail_check_passed": bool,  # Present if guardrails were evaluated
            "warnings": []
        }

        On system error, returns:
        {
            "error": {
                "code": str,            # VALIDATION_ERROR, FILE_NOT_FOUND, INTERNAL_ERROR
                "message": str,         # Human-readable error message
                "retryable": bool       # Whether operation can be retried
            }
        }

    Examples:
        # Update tracker status to Resume Written (with guardrail checks)
        update_tracker_status_tool(
            tracker_path="trackers/2026-02-05-amazon.md",
            target_status="Resume Written"
        )

        # Preview status update without writing (dry-run)
        update_tracker_status_tool(
            tracker_path="trackers/2026-02-05-amazon.md",
            target_status="Applied",
            dry_run=True
        )

        # Force a non-standard transition with warning
        update_tracker_status_tool(
            tracker_path="trackers/2026-02-05-amazon.md",
            target_status="Interview",
            force=True
        )

        # Update to terminal status (allowed from any status)
        update_tracker_status_tool(
            tracker_path="trackers/2026-02-05-amazon.md",
            target_status="Rejected"
        )

    Transition Policy:
        - Same status → noop (no change)
        - Standard forward transitions:
            • Reviewed → Resume Written
            • Resume Written → Applied
        - Terminal outcomes (allowed from any status):
            • Rejected
            • Ghosted
        - Other transitions require force=True

    Resume Written Guardrails:
        When target_status="Resume Written", the tool validates:
        1. resume.pdf exists and has non-zero size
        2. resume.tex exists
        3. resume.tex does not contain placeholder tokens:
            - PROJECT-AI-
            - PROJECT-BE-
            - WORK-BULLET-POINT-

        The tool resolves artifact paths from tracker frontmatter resume_path field,
        supporting both wiki-link format ([[path]]) and plain path format.

        If any guardrail check fails, the update is blocked and returns a detailed
        error message indicating which check failed.

    Behavior:
        - Updates only the status field in tracker frontmatter
        - Preserves all other frontmatter fields and body content
        - Uses atomic write (temp file + rename) to prevent corruption
        - Does NOT modify database records (tracker-only operation)
        - Dry-run mode performs all checks without writing
        - Force mode allows policy violations but adds warnings

    Requirements:
        - Requirement 1: Tool Input Interface (tracker_path, target_status, dry_run, force)
        - Requirement 2: Tracker File Parsing and Validation
        - Requirement 3: Allowed Tracker Status Set (7 canonical statuses)
        - Requirement 4: Transition Policy (forward progression and terminal outcomes)
        - Requirement 5: Resume Written Guardrails (artifact validation)
        - Requirement 6: Artifact Path Resolution (wiki-link and plain path support)
        - Requirement 7: File Write Semantics (atomic writes, content preservation)
        - Requirement 8: Dry-Run Behavior (preview without mutation)
        - Requirement 9: Structured Response Format (detailed outcomes)
        - Requirement 10: Error Handling (sanitized, categorized errors)
        - Requirement 11: System Boundaries (tracker-only, no DB writes)
    """
    # Build arguments dictionary for the tool handler
    args = {
        "tracker_path": tracker_path,
        "target_status": target_status
    }

    # Only include optional parameters if they differ from defaults
    if dry_run:
        args["dry_run"] = dry_run
    if force:
        args["force"] = force

    # Call the tool handler and return the result
    return update_tracker_status(args)


@mcp.tool(
    name="finalize_resume_batch",
    description=(
        "Finalize multiple resume compilation jobs in one atomic batch. "
        "Updates database completion audit fields and synchronizes tracker status to Resume Written. "
        "Validates artifacts before commit and applies compensation fallback on failure. "
        "Supports dry-run preview mode."
    ),
)
def finalize_resume_batch_tool(
    items: list[dict],
    run_id: str | None = None,
    db_path: str | None = None,
    dry_run: bool = False,
) -> dict:
    """
    Finalize multiple resume compilation jobs in one atomic batch.

    This tool performs the final write-back step after resume compile succeeds.
    It commits durable completion state by updating DB status/audit fields and
    synchronizing tracker frontmatter status in one operational step.

    This tool is commit-focused:
    - Database status remains the SSOT (Single Source of Truth).
    - Tracker status is a synchronized projection for Obsidian workflow.
    - Does NOT perform resume compilation or content rewriting.
    - Does NOT create new trackers or modify unrelated jobs.

    Args:
        items: Array of finalization entries (required). Each item contains:
            - id (int): Job database ID (must be positive integer)
            - tracker_path (str): Path to tracker markdown file
            - resume_pdf_path (str, optional): Override for resume PDF path
        run_id: Optional batch run identifier. Auto-generated if omitted.
        db_path: Optional database path override (default: data/capture/jobs.db).
        dry_run: Preview mode without writes (default: False).
            When True, performs all validation checks but does not modify DB or tracker files.

    Returns:
        Dictionary with structure (success case):
        {
            "run_id": str,              # Batch run identifier
            "finalized_count": int,     # Number of successfully finalized items
            "failed_count": int,        # Number of failed items
            "dry_run": bool,            # Whether this was a dry-run
            "warnings": [],             # List of non-fatal warnings (optional)
            "results": [                # Per-item results in input order
                {
                    "id": int,
                    "tracker_path": str,
                    "resume_pdf_path": str,
                    "action": str,      # "finalized", "would_finalize", "failed"
                    "success": bool,
                    "error": str        # Error message (optional, only on failure)
                }
            ]
        }

        On system error, returns:
        {
            "error": {
                "code": str,            # VALIDATION_ERROR, DB_NOT_FOUND, DB_ERROR, INTERNAL_ERROR
                "message": str,         # Human-readable error message
                "retryable": bool       # Whether operation can be retried
            }
        }

    Examples:
        # Finalize single job
        finalize_resume_batch_tool(
            items=[{
                "id": 3711,
                "tracker_path": "trackers/2026-02-05-amazon.md"
            }]
        )

        # Finalize multiple jobs in one batch
        finalize_resume_batch_tool(
            items=[
                {"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"},
                {"id": 3712, "tracker_path": "trackers/2026-02-05-meta.md"}
            ]
        )

        # Dry-run to preview outcomes without writes
        finalize_resume_batch_tool(
            items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}],
            dry_run=True
        )

        # Use custom run_id and db_path
        finalize_resume_batch_tool(
            items=[{"id": 3711, "tracker_path": "trackers/2026-02-05-amazon.md"}],
            run_id="run_20260206_custom",
            db_path="custom/path/jobs.db"
        )

        # Override resume_pdf_path for specific item
        finalize_resume_batch_tool(
            items=[{
                "id": 3711,
                "tracker_path": "trackers/2026-02-05-amazon.md",
                "resume_pdf_path": "custom/path/resume.pdf"
            }]
        )

    Validation Rules:
        - Batch size: 0-100 items (empty batch returns success with zero counts)
        - Each item requires id (positive integer) and tracker_path (non-empty string)
        - No duplicate job IDs within one batch
        - Tracker file must exist and be readable
        - resume.pdf must exist and have non-zero file size
        - resume.tex must exist
        - resume.tex must not contain placeholder tokens (PROJECT-AI-, PROJECT-BE-, WORK-BULLET-POINT-)

    Finalization Behavior:
        Success Path:
        1. Validate all item preconditions (tracker, artifacts, placeholders)
        2. Update DB: status='resume_written', set audit fields (resume_pdf_path, resume_written_at, run_id)
        3. Update tracker frontmatter: status='Resume Written'
        4. Mark item as finalized

        Failure Compensation:
        - If tracker sync fails after DB update, apply fallback:
          • Set DB status='reviewed'
          • Write last_error with failure reason
          • Mark item as failed
        - Batch continues processing remaining items after one item fails
        - Per-item failures are reported in results (not top-level fatal)

    Dry-Run Mode:
        - Performs full validation and planning
        - Does NOT mutate DB rows
        - Does NOT write tracker files
        - Returns predicted actions (would_finalize, would_fail)

    Requirements:
        - Requirement 1.1: Accept items as array of finalization entries
        - Requirement 1.5: Support optional run_id, db_path, dry_run parameters
        - Requirement 10.1: Return structured response with run_id, counts, results
    """
    # Build arguments dictionary for the tool handler
    args = {"items": items}

    # Only include optional parameters if explicitly provided
    if run_id is not None:
        args["run_id"] = run_id
    if db_path is not None:
        args["db_path"] = db_path
    if dry_run:
        args["dry_run"] = dry_run

    # Call the tool handler and return the result
    return finalize_resume_batch(args)


@mcp.tool(
    name="career_tailor",
    description=(
        "Run batch full-tailoring for tracker items. "
        "For each item: parse tracker context, bootstrap workspace, regenerate ai_context.md, "
        "compile resume.tex to resume.pdf, and return successful_items for downstream finalize_resume_batch. "
        "This tool does not write DB status or tracker status."
    ),
)
def career_tailor_tool(
    items: list[dict],
    force: bool | None = None,
    full_resume_path: str | None = None,
    resume_template_path: str | None = None,
    applications_dir: str | None = None,
    pdflatex_cmd: str | None = None,
) -> dict:
    """
    Run batch full-tailoring for tracker items.

    This tool executes one fixed full pipeline per item:
    1. parse tracker context
    2. initialize workspace artifacts
    3. regenerate ai_context.md
    4. compile resume.tex -> resume.pdf

    The tool is intentionally artifact-focused:
    - no DB status writes
    - no tracker status writes
    - no internal call to finalize_resume_batch
    - no compensation fallback writes

    Args:
        items: Array of tailoring items (required, 1-100). Each item contains:
            - tracker_path (str, required)
            - job_db_id (int, optional): used for finalize handoff payload
        force: If true, overwrite existing resume.tex from template.
        full_resume_path: Optional override path for full resume source markdown.
        resume_template_path: Optional override path for resume skeleton template.
        applications_dir: Optional override for application workspace root.
        pdflatex_cmd: Optional override compile command (default: pdflatex).

    Returns:
        Dictionary with structure (success/partial success):
        {
            "run_id": str,
            "total_count": int,
            "success_count": int,
            "failed_count": int,
            "results": [
                {
                    "tracker_path": str,
                    "job_db_id": int,                # optional
                    "application_slug": str,         # success only
                    "workspace_dir": str,            # success only
                    "resume_tex_path": str,          # success only
                    "ai_context_path": str,          # success only
                    "resume_pdf_path": str,          # success only
                    "resume_tex_action": str,        # success only
                    "success": bool,
                    "error_code": str,               # failure only
                    "error": str                     # failure only
                }
            ],
            "successful_items": [
                {
                    "id": int,
                    "tracker_path": str,
                    "resume_pdf_path": str
                }
            ],
            "warnings": [str]                        # optional
        }

        On top-level fatal error, returns:
        {
            "error": {
                "code": str,            # VALIDATION_ERROR, FILE_NOT_FOUND, TEMPLATE_NOT_FOUND, COMPILE_ERROR, INTERNAL_ERROR
                "message": str,
                "retryable": bool
            }
        }

    Behavior:
        - Processes items in input order with per-item isolation
        - Continues batch when one item fails
        - Always runs full flow (no mode switching)
        - Returns successful_items for downstream finalize_resume_batch
        - Excludes successful items without job_db_id from successful_items and emits warning
    """
    args = {"items": items}

    if force is not None:
        args["force"] = force
    if full_resume_path is not None:
        args["full_resume_path"] = full_resume_path
    if resume_template_path is not None:
        args["resume_template_path"] = resume_template_path
    if applications_dir is not None:
        args["applications_dir"] = applications_dir
    if pdflatex_cmd is not None:
        args["pdflatex_cmd"] = pdflatex_cmd

    return career_tailor(args)


def main():
    """
    Main entry point for the MCP server.
    
    Runs the server in stdio mode, which is the standard transport
    for MCP servers that are invoked by LLM agents.
    """
    # Load and setup configuration
    config.setup_logging()
    
    # Log startup information
    logger = logging.getLogger(__name__)
    logger.info("Starting JobWorkFlow MCP Server")
    logger.info(f"Server name: {config.server_name}")
    logger.info(f"Database path: {config.db_path}")
    
    # Validate configuration and log warnings
    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)
    
    # Start the server
    logger.info("Server starting in stdio mode")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
