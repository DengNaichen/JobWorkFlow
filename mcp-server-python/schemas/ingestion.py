"""
Ingestion schemas – re-exports canonical status enum from models.status.

The authoritative definition lives in ``models.status.JobDbStatus``.
``JobStatus`` is kept as a convenience alias so that any existing
imports (``from schemas.ingestion import JobStatus``) continue to work.
"""

from models.status import JobDbStatus as JobStatus

__all__ = ["JobStatus"]
