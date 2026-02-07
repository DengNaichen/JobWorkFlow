"""
MCP tool handler for scrape_jobs ingestion.

Orchestrates multi-term job scraping with validation, preflight checks,
normalization, filtering, optional capture, and idempotent DB insertion.

This is the main entry point for the scrape_jobs MCP tool.

Requirements: 1.2, 1.3, 3.2, 5.4, 10.4, 11.5
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List

from pydantic import ValidationError

from db.jobs_ingest_writer import JobsIngestWriter
from models.errors import (
    ToolError,
    create_internal_error,
    sanitize_sql_error,
    sanitize_stack_trace,
)
from schemas.scrape_jobs import ScrapeJobsRequest, ScrapeJobsResponse
from utils.capture_writer import write_capture_file
from utils.jobspy_adapter import PreflightDNSError, preflight_dns_check, scrape_jobs_for_term
from utils.pydantic_error_mapper import map_pydantic_validation_error
from utils.scrape_normalizer import normalize_and_filter, serialize_payload
from utils.validation import validate_scrape_jobs_parameters


def generate_run_id() -> str:
    """
    Generate a unique run identifier.

    Format: scrape_YYYYMMDD_<8-char-hex>

    Returns:
        Unique run ID string

    **Validates: Requirements 10.1**
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y%m%d")
    unique_suffix = uuid.uuid4().hex[:8]
    return f"scrape_{date_str}_{unique_suffix}"


def get_utc_timestamp() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.

    Returns:
        ISO 8601 UTC timestamp string with Z suffix

    **Validates: Requirements 10.1**
    """
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sanitize_per_term_error(error: Exception) -> str:
    """
    Sanitize per-term error messages.

    Removes SQL fragments, stack traces, and sensitive paths from error messages
    to ensure safe error reporting in per-term results.

    Args:
        error: The exception to sanitize

    Returns:
        Sanitized error message string

    **Validates: Requirements 11.4, 11.5**
    """
    error_msg = str(error)
    # Apply SQL sanitization
    error_msg = sanitize_sql_error(error_msg)
    # Apply stack trace sanitization
    error_msg = sanitize_stack_trace(error_msg)
    return error_msg


def init_term_result(term: str) -> Dict[str, Any]:
    """
    Initialize a per-term result structure.

    Args:
        term: Search term

    Returns:
        Dictionary with default counters and success flag

    **Validates: Requirements 10.2**
    """
    return {
        "term": term,
        "success": False,
        "fetched_count": 0,
        "cleaned_count": 0,
        "inserted_count": 0,
        "duplicate_count": 0,
        "skipped_no_url": 0,
        "skipped_no_description": 0,
    }


def process_term(
    term: str,
    config: Dict[str, Any],
    dry_run: bool,
) -> Dict[str, Any]:
    """
    Process a single search term with full scrape pipeline.

    Pipeline stages:
    1. Preflight DNS check (if configured)
    2. Scrape source records
    3. Normalize and filter records
    4. Write capture file (if enabled)
    5. Insert to database (unless dry_run)

    Args:
        term: Search term to process
        config: Validated configuration parameters
        dry_run: Whether to skip DB writes

    Returns:
        Per-term result dictionary with success flag and counters

    **Validates: Requirements 1.3, 2.3, 2.4, 2.5, 3.1, 3.2, 5.4, 11.5**
    """
    result = init_term_result(term)

    try:
        # Stage 1: Preflight DNS check (Requirement 2.1, 2.2, 2.3)
        if config["preflight_host"]:
            try:
                preflight_dns_check(
                    host=config["preflight_host"],
                    retry_count=config["retry_count"],
                    retry_sleep_seconds=config["retry_sleep_seconds"],
                    retry_backoff=config["retry_backoff"],
                )
            except PreflightDNSError as e:
                # Mark term as failed and continue to next term (Requirement 2.3, 2.5)
                result["error"] = sanitize_per_term_error(e)
                return result

        # Stage 2: Scrape source records (Requirement 3.1, 3.3)
        raw_records = scrape_jobs_for_term(
            term=term,
            sites=config["sites"],
            location=config["location"],
            results_wanted=config["results_wanted"],
            hours_old=config["hours_old"],
        )
        result["fetched_count"] = len(raw_records)

        # Stage 3: Normalize and filter records (Requirement 4.1, 5.1, 5.2, 5.3)
        cleaned_records, skip_counts = normalize_and_filter(
            raw_records=raw_records,
            source_override=None,  # Use source from record
            require_description=config["require_description"],
        )
        result["cleaned_count"] = len(cleaned_records)
        result["skipped_no_url"] = skip_counts["skipped_no_url"]
        result["skipped_no_description"] = skip_counts["skipped_no_description"]

        # Add created_at timestamp and payload_json to each record
        created_at = get_utc_timestamp()
        for record in cleaned_records:
            record["created_at"] = created_at
            record["payload_json"] = serialize_payload(record)

        # Stage 4: Write capture file (Requirement 9.1, 9.3, 9.5)
        if config["save_capture_json"]:
            try:
                capture_path = write_capture_file(
                    records=cleaned_records,
                    term=term,
                    location=config["location"],
                    hours_old=config["hours_old"],
                    sites=config["sites"],
                    capture_dir=config["capture_dir"],
                )
                result["capture_path"] = capture_path
            except Exception:  # noqa: BLE001 - Intentionally broad to ensure term continues
                # Capture write failure doesn't fail the term (Requirement 9.5)
                # Continue to DB insertion
                pass

        # Stage 5: Insert to database (Requirement 7.1, 7.2, 7.3, 8.1)
        if not dry_run:
            with JobsIngestWriter(db_path=config["db_path"]) as writer:
                inserted, duplicates = writer.insert_cleaned_records(
                    records=cleaned_records,
                    status=config["status"],
                )
                writer.commit()

                result["inserted_count"] = inserted
                result["duplicate_count"] = duplicates

        # Mark term as successful
        result["success"] = True

    except Exception as e:  # noqa: BLE001 - Intentionally broad for partial success
        # Per-term error - record and continue (Requirement 3.2, 11.5)
        result["error"] = sanitize_per_term_error(e)

    return result


def aggregate_totals(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate per-term results into totals.

    Args:
        results: List of per-term result dictionaries

    Returns:
        Dictionary with aggregate totals

    **Validates: Requirements 10.3**
    """
    totals = {
        "term_count": len(results),
        "successful_terms": sum(1 for r in results if r["success"]),
        "failed_terms": sum(1 for r in results if not r["success"]),
        "fetched_count": sum(r["fetched_count"] for r in results),
        "cleaned_count": sum(r["cleaned_count"] for r in results),
        "inserted_count": sum(r["inserted_count"] for r in results),
        "duplicate_count": sum(r["duplicate_count"] for r in results),
        "skipped_no_url": sum(r["skipped_no_url"] for r in results),
        "skipped_no_description": sum(r["skipped_no_description"] for r in results),
    }
    return totals


def scrape_jobs(**kwargs) -> Dict[str, Any]:
    """
    MCP tool handler for scrape_jobs ingestion.

    Orchestrates multi-term job scraping with validation, preflight checks,
    normalization, filtering, optional capture, and idempotent DB insertion.

    This function implements the complete scrape_jobs pipeline:
    1. Validate all input parameters
    2. Initialize run metadata
    3. Process each term in order (with isolation)
    4. Aggregate results and return structured response

    Args:
        **kwargs: All scrape_jobs parameters (see design doc for full schema)

    Returns:
        Structured response with run metadata, per-term results, and totals

    Raises:
        ToolError: For top-level fatal errors (validation, DB bootstrap, etc.)

    **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 3.2, 5.4, 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3, 11.4, 11.5**
    """
    try:
        ScrapeJobsRequest.model_validate(kwargs)

        # Stage 1: Validate all parameters (Requirement 1.4, 1.5, 11.1)
        config = validate_scrape_jobs_parameters(**kwargs)

        # Stage 2: Initialize run metadata (Requirement 10.1)
        run_id = generate_run_id()
        started_at = get_utc_timestamp()
        start_time = datetime.now(timezone.utc)

        # Stage 3: Process each term in deterministic order (Requirement 1.3, 3.5)
        results = []
        for term in config["terms"]:
            term_result = process_term(
                term=term,
                config=config,
                dry_run=config["dry_run"],
            )
            results.append(term_result)

        # Stage 4: Aggregate totals (Requirement 10.3)
        totals = aggregate_totals(results)

        # Stage 5: Build response (Requirement 10.1, 10.2, 10.4, 10.5)
        finished_at = get_utc_timestamp()
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return ScrapeJobsResponse(
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            dry_run=config["dry_run"],
            results=results,
            totals=totals,
        ).model_dump(exclude_none=True)

    except ValidationError as e:
        raise map_pydantic_validation_error(e) from e

    except ToolError:
        # Re-raise ToolError as-is (already structured)
        raise

    except Exception as e:
        # Wrap unexpected exceptions (Requirement 11.3, 11.4)
        raise create_internal_error(str(e), original_error=e) from e
