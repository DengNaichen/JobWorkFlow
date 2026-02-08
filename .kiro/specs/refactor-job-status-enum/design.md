# Design Document: Refactor Job Status to Enum

## Overview

This design outlines the migration from using hardcoded 'magic strings' for job statuses to centralized, type-safe Enums.

This refactoring will significantly improve code clarity, reduce the risk of typo-related bugs, and enhance maintainability by creating a single source of truth for status definitions.

## Scope

**In scope:**

*   Refactoring all Python code (`.py` files) within the `mcp-server-python` directory to replace hardcoded status strings with Enum members.
*   Defining two distinct Enums for the two status systems (database vs. tracker).
*   Updating all associated tests to use the new Enums.

**Out of scope:**

*   Changes to the database schema itself.
*   Changes to the semantic meaning or lifecycle of existing statuses.
*   Modifying any frontend or external client-side logic that consumes statuses. The API contract will continue to accept and return plain strings.

## Current State Summary

The codebase currently contains two separate and inconsistent systems for managing job statuses, both relying on hardcoded strings:

1.  **Database Statuses:** A set of lowercase strings (`new`, `shortlist`, `reviewed`, etc.) used in the `jobs` database and related data access logic.
2.  **Tracker Statuses:** A set of capitalized strings (`Reviewed`, `Resume Written`, etc.) used in the frontmatter of Markdown tracker files and the business logic that governs them.

This duplication and inconsistency is spread across numerous files, including `utils/validation.py`, `db/*.py`, `utils/tracker_policy.py`, and the entire `tests/` suite, making the code brittle and difficult to maintain.

## Target Architecture

### 1) Centralized Enum Definitions

A new file will be introduced to act as the single source of truth for all status definitions:

*   **File:** `mcp-server-python/models/status.py`

This file will contain two distinct Enum classes:

```python
from enum import Enum

class JobDbStatus(str, Enum):
    """Enum for statuses used in the 'jobs' database table."""
    NEW = "new"
    SHORTLIST = "shortlist"
    REVIEWED = "reviewed"
    REJECT = "reject"
    RESUME_WRITTEN = "resume_written"
    APPLIED = "applied"

class JobTrackerStatus(str, Enum):
    """Enum for statuses used in the frontmatter of Markdown tracker files."""
    REVIEWED = "Reviewed"
    RESUME_WRITTEN = "Resume Written"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"
    GHOSTED = "Ghosted"
```
Inheriting from `(str, Enum)` ensures that the Enums are compatible with string operations and can be easily serialized to JSON/string format at the API boundaries.

### 2) Refactoring Pattern

All application logic will be updated to import and use these Enums.

**Example (Before):**
```python
# in db/jobs_reader.py
def query_new_jobs(conn):
    return conn.execute("SELECT * FROM jobs WHERE status = 'new'")
```

**Example (After):**
```python
# in db/jobs_reader.py
from models.status import JobDbStatus

def query_new_jobs(conn):
    return conn.execute("SELECT * FROM jobs WHERE status = ?", (JobDbStatus.NEW,))
```

Pydantic models used at the API boundary will automatically handle the conversion between incoming strings and the internal Enum types, preserving the external contract.

## Migration Phases

### Phase 1: Foundation
- Create the `status.py` file and define the `JobDbStatus` and `JobTrackerStatus` Enums.

### Phase 2: Core Logic
- Refactor `utils/validation.py` to use the new Enums, removing the hardcoded `ALLOWED_STATUSES` lists.
- Refactor `utils/tracker_policy.py` and the database layer (`db/*.py`).

### Phase 3: Tools and API
- Refactor all scripts in the `tools/` directory.
- Update `server.py` and any related API documentation or examples.

### Phase 4: Tests
- Systematically update the entire `tests/` suite to use the Enums for test setup and assertions. This is the largest phase.

### Phase 5: Verification & Cleanup
- Perform a final, full-codebase search for any remaining hardcoded strings to ensure none were missed.
- Ensure all tests pass and the application functions correctly.

## Risks and Mitigations

1.  **Risk:** A hardcoded status string is missed during refactoring.
    *   **Mitigation:** The final verification phase (Phase 5) involves using `grep` or a similar search tool to comprehensively scan for remaining instances. A passing test suite is the primary gate.

2.  **Risk:** Confusion between `JobDbStatus` and `JobTrackerStatus` during development.
    *   **Mitigation:** The clear and explicit naming of the Enums is designed to prevent this. Code reviews should pay special attention to ensuring the correct Enum is used in the correct context.
