"""
Main MCP tool handler for initialize_shortlist_trackers.

Integrates validation, database reading, tracker planning, rendering,
and atomic file operations to provide a projection-oriented tool that
initializes deterministic tracker markdown files for shortlisted jobs.
"""

from typing import Dict, Any

from utils.validation import validate_initialize_shortlist_trackers_parameters
from db.jobs_reader import get_connection, query_shortlist_jobs
from utils.tracker_planner import plan_tracker
from utils.tracker_renderer import render_tracker_markdown
from utils.file_ops import atomic_write, ensure_workspace_directories, resolve_write_action
from models.errors import ToolError, create_internal_error


def initialize_shortlist_trackers(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Initialize tracker markdown files for jobs with status='shortlist'.
    
    This is the main entry point for the MCP tool. It orchestrates all components:
    1. Validates input parameters (limit, db_path, trackers_dir, force, dry_run)
    2. Queries database for shortlist jobs with deterministic ordering
    3. Plans tracker paths and workspace directories for each job
    4. Renders tracker markdown content with stable frontmatter
    5. Executes atomic writes when not in dry-run mode
    6. Continues batch processing on per-item failures
    7. Returns structured response with per-item results and counts
    
    This tool is projection-oriented: it reads from the database (SSOT) and
    creates file-based tracker projections. It does NOT modify database records.
    
    Args:
        args: Dictionary containing optional parameters:
            - limit (int): Number of shortlist jobs to process (1-200, default 50)
            - db_path (str): Database path override (default: data/capture/jobs.db)
            - trackers_dir (str): Trackers directory override (default: trackers/)
            - force (bool): Overwrite existing tracker files (default: False)
            - dry_run (bool): Compute outcomes without writing files (default: False)
    
    Returns:
        Dictionary with structure:
        {
            "created_count": int,    # Number of trackers created
            "skipped_count": int,    # Number of trackers skipped (already exist)
            "failed_count": int,     # Number of trackers that failed
            "results": [             # Per-item results in selection order
                {
                    "id": int,                    # Database job ID
                    "job_id": str,                # External job identifier
                    "tracker_path": str,          # Path to tracker file (optional on failure)
                    "action": str,                # "created", "skipped_exists", "overwritten", "failed"
                    "success": bool,              # Whether operation succeeded
                    "error": str                  # Error message (optional, only on failure)
                }
            ]
        }
        
        On top-level error (validation, DB connection), returns:
        {
            "error": {
                "code": str,         # Error code (VALIDATION_ERROR, DB_NOT_FOUND, etc.)
                "message": str,      # Human-readable error message
                "retryable": bool    # Whether operation can be retried
            }
        }
    
    Requirements:
        - 1.1: Select jobs where status='shortlist'
        - 1.6: Return success with zero created trackers when no shortlist jobs available
        - 4.1-4.4: Idempotent initialization with force semantics
        - 5.2-5.3: Continue batch on per-item failures
        - 6.1-6.5: Read-only database operations
        - 7.1-7.5: Structured response format with per-item results
        - 8.1-8.7: Error handling and sanitization
        - 9.1-9.5: MCP tool interface compliance
    """
    try:
        # Step 1: Extract and validate all input parameters
        limit = args.get("limit")
        db_path = args.get("db_path")
        trackers_dir = args.get("trackers_dir")
        force = args.get("force")
        dry_run = args.get("dry_run")
        
        # Validate parameters (raises ToolError on invalid input)
        validated_limit, validated_db_path, validated_trackers_dir, validated_force, validated_dry_run = \
            validate_initialize_shortlist_trackers_parameters(
                limit=limit,
                db_path=db_path,
                trackers_dir=trackers_dir,
                force=force,
                dry_run=dry_run
            )
        
        # Use defaults for optional parameters
        final_trackers_dir = validated_trackers_dir or "trackers"
        
        # Step 2: Query database for shortlist jobs
        # Uses context manager to ensure connection is always closed
        with get_connection(validated_db_path) as conn:
            jobs = query_shortlist_jobs(
                conn=conn,
                limit=validated_limit
            )
        
        # Step 3: Process each job and collect results
        results = []
        
        for job in jobs:
            plan = None
            try:
                # Plan tracker paths and workspace directories
                plan = plan_tracker(job, final_trackers_dir)
                
                # Resolve action based on file existence and force flag
                action = resolve_write_action(plan["exists"], validated_force)
                
                # Skip write if file exists and force is false
                if action == "skipped_exists":
                    results.append({
                        "id": job["id"],
                        "job_id": job["job_id"],
                        "tracker_path": str(plan["tracker_path"]),
                        "action": action,
                        "success": True
                    })
                    continue
                
                # Execute write operations when not in dry-run mode
                if not validated_dry_run:
                    # Create workspace directories
                    ensure_workspace_directories(plan["application_slug"])
                    
                    # Render tracker markdown content
                    content = render_tracker_markdown(job, plan)
                    
                    # Write tracker file atomically
                    atomic_write(plan["tracker_path"], content)
                
                # Record successful operation
                results.append({
                    "id": job["id"],
                    "job_id": job["job_id"],
                    "tracker_path": str(plan["tracker_path"]),
                    "action": action,
                    "success": True
                })
                
            except Exception as e:
                # Per-item failure - record and continue with next item
                # Sanitize error message to avoid exposing sensitive details
                error_msg = _sanitize_item_error(str(e))
                
                result = {
                    "id": job["id"],
                    "job_id": job.get("job_id", "unknown"),
                    "action": "failed",
                    "success": False,
                    "error": error_msg
                }
                
                # Include tracker_path if planning succeeded
                if plan is not None:
                    result["tracker_path"] = str(plan["tracker_path"])
                
                results.append(result)
        
        # Step 4: Compute summary counts
        created_count = sum(1 for r in results if r["action"] == "created")
        skipped_count = sum(1 for r in results if r["action"] == "skipped_exists")
        overwritten_count = sum(1 for r in results if r["action"] == "overwritten")
        failed_count = sum(1 for r in results if r["action"] == "failed")
        
        # Combine created and overwritten for created_count
        # (both represent successful writes)
        total_created = created_count + overwritten_count
        
        # Step 5: Build and return response
        return {
            "created_count": total_created,
            "skipped_count": skipped_count,
            "failed_count": failed_count,
            "results": results
        }
    
    except ToolError as e:
        # Known tool errors with structured error information
        # These are already sanitized and formatted correctly
        return e.to_dict()
    
    except Exception as e:
        # Unexpected errors - wrap in INTERNAL_ERROR
        # Sanitize to avoid exposing sensitive system details
        internal_error = create_internal_error(
            message=str(e),
            original_error=e
        )
        return internal_error.to_dict()


def _sanitize_item_error(error_msg: str) -> str:
    """
    Sanitize per-item error messages to remove sensitive details.
    
    Removes absolute paths, stack traces, and other sensitive information
    while keeping actionable error context.
    
    Args:
        error_msg: Original error message
        
    Returns:
        Sanitized error message
        
    Requirements:
        - 8.6: Sanitize error messages (no stack traces, no sensitive paths)
    """
    import re
    
    # Take only the first line (remove stack traces)
    lines = error_msg.split('\n')
    if lines:
        error_msg = lines[0].strip()
    
    # Remove absolute paths (keep only basenames)
    error_msg = re.sub(r'/[^\s]+/', '[path]/', error_msg)
    error_msg = re.sub(r'[A-Z]:\\[^\s]+\\', r'[path]\\', error_msg)
    
    # Limit message length
    if len(error_msg) > 200:
        error_msg = error_msg[:197] + "..."
    
    return error_msg
