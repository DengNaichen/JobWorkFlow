#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


JOB_URL_ID_RE = re.compile(r"/jobs/view/(\d+)")


def parse_args():
    parser = argparse.ArgumentParser(description="Clean JobSpy JSON and import into SQLite.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JobSpy JSON output (list of records).",
    )
    parser.add_argument(
        "--db",
        default="data/capture/jobs.db",
        help="SQLite DB path (default: data/capture/jobs.db).",
    )
    parser.add_argument(
        "--source",
        default=None,
        help="Override source value (default: record.site or 'unknown').",
    )
    parser.add_argument(
        "--require-description",
        action="store_true",
        help="Skip records without description.",
    )
    parser.add_argument(
        "--status",
        default="new",
        help="Status value for inserted rows (default: new).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print cleaned records; do not write to DB.",
    )
    return parser.parse_args()


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT,
            description TEXT,
            source TEXT,
            job_id TEXT,
            location TEXT,
            company TEXT,
            captured_at TEXT,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new'
        );
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        """
    )


def normalize_text(value):
    if value is None:
        return ""
    return str(value).strip()


def parse_job_id(url, fallback):
    if not url:
        return normalize_text(fallback)
    match = JOB_URL_ID_RE.search(url)
    if match:
        return match.group(1)
    return normalize_text(fallback)


def parse_captured_at(date_posted):
    if not date_posted:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(date_posted, str):
        try:
            dt = datetime.fromisoformat(date_posted.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc).isoformat()
        except ValueError:
            return datetime.now(timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def clean_record(record, source_override=None):
    url = normalize_text(record.get("job_url") or record.get("job_url_direct"))
    title = normalize_text(record.get("title"))
    company = normalize_text(record.get("company"))
    location = normalize_text(record.get("location"))
    description = normalize_text(record.get("description"))
    source = normalize_text(source_override or record.get("site") or "unknown")
    job_id = parse_job_id(url, record.get("id"))
    captured_at = parse_captured_at(record.get("date_posted"))

    return {
        "source": source,
        "company": company,
        "title": title,
        "location": location,
        "url": url,
        "description": description,
        "jobId": job_id,
        "capturedAt": captured_at,
        "id": str(uuid.uuid4()),
    }


def resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path
    repo_root = Path(__file__).resolve().parents[1]
    return repo_root / path


def main() -> int:
    args = parse_args()
    input_path = Path(args.input)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    cleaned = []
    for record in data:
        item = clean_record(record, source_override=args.source)
        if not item["url"]:
            continue
        if args.require_description and not item["description"]:
            continue
        cleaned.append(item)

    if args.dry_run:
        print(json.dumps(cleaned, ensure_ascii=False, indent=2))
        return 0

    db_path = Path(os.getenv("JOBWORKFLOW_DB", args.db))
    db_path = resolve_repo_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        ensure_schema(conn)
        now = datetime.now(timezone.utc).isoformat()
        inserted = 0
        duplicates = 0
        for item in cleaned:
            payload_json = json.dumps(item, ensure_ascii=False)
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO jobs (
                    url, title, description, source, job_id, location, company,
                    captured_at, payload_json, created_at, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["url"],
                    item["title"],
                    item["description"],
                    item["source"],
                    item["jobId"],
                    item["location"],
                    item["company"],
                    item["capturedAt"],
                    payload_json,
                    now,
                    args.status,
                ),
            )
            if cur.rowcount == 0:
                duplicates += 1
            else:
                inserted += 1
        conn.commit()
    finally:
        conn.close()

    print(f"cleaned: {len(cleaned)} inserted: {inserted} duplicates: {duplicates}")
    print(f"db: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
