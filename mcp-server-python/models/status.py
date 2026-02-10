"""
Centralized, type-safe status definitions for the JobWorkFlow pipeline.

This module is the single source of truth for all status values used across
the application. It defines two distinct Enum classes:

- ``JobDbStatus``: Lowercase statuses stored in the ``jobs`` SQLite table.
- ``JobTrackerStatus``: Capitalized statuses used in Markdown tracker
  frontmatter (a board-friendly projection of DB milestones).

Both Enums inherit from ``(str, Enum)`` so that members are directly
comparable to plain strings and serialize naturally to JSON at API
boundaries, preserving the external contract.
"""

from enum import Enum


class JobDbStatus(str, Enum):
    """Enum for statuses used in the 'jobs' database table.

    Canonical transitions (see steering.md §3):
        new  ->  shortlist | reviewed | reject
        shortlist  ->  resume_written  (after successful finalize)
        shortlist  ->  reviewed        (on failure, with last_error)
        resume_written  ->  applied    (manual or later automation)
    """

    NEW = "new"
    SHORTLIST = "shortlist"
    REVIEWED = "reviewed"
    REJECT = "reject"
    RESUME_WRITTEN = "resume_written"
    APPLIED = "applied"


class JobTrackerStatus(str, Enum):
    """Enum for statuses used in the frontmatter of Markdown tracker files.

    Tracker statuses are projections of database milestones and must not
    become a competing source of truth.
    """

    REVIEWED = "Reviewed"
    RESUME_WRITTEN = "Resume Written"
    APPLIED = "Applied"
    INTERVIEW = "Interview"
    OFFER = "Offer"
    REJECTED = "Rejected"
    GHOSTED = "Ghosted"
