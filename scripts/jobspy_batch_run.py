#!/usr/bin/env python3
import argparse
import json
import random
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import jobspy


def log(message: str) -> None:
    print(message, flush=True)

DEFAULT_TERMS = ["ai engineer", "backend engineer", "machine learning"]


def parse_terms(value: str):
    terms = [term.strip() for term in value.split(",") if term.strip()]
    return terms or list(DEFAULT_TERMS)


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_") or "query"


def timestamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def resolve_host(host: str) -> bool:
    try:
        socket.getaddrinfo(host, 443)
        return True
    except OSError:
        return False


def preflight_dns(host: str, attempts: int, sleep_seconds: float, backoff: float) -> bool:
    if not host:
        return True
    attempts = max(1, attempts)
    for idx in range(attempts):
        if resolve_host(host):
            return True
        if idx < attempts - 1:
            wait = sleep_seconds * (backoff ** idx)
            log(f"[{timestamp()}] preflight-dns-failed: {host}; retry in {wait:.1f}s")
            time.sleep(wait)
    return False


def run_once(args) -> None:
    terms = parse_terms(args.terms)
    repo_root = Path(__file__).resolve().parents[1]
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = repo_root / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for idx, term in enumerate(terms):
        slug = slugify(term)
        output_path = output_dir / f"jobspy_linkedin_{slug}_ontario_{args.hours_old}h.json"
        log(f"[{timestamp()}] scrape: {term}")
        sites = [site.strip() for site in args.sites.split(",") if site.strip()]
        if not preflight_dns(args.preflight_host, args.retry_count, args.retry_sleep_seconds, args.retry_backoff):
            log(f"[{timestamp()}] preflight-skip: {term} (host={args.preflight_host})")
            continue

        df = jobspy.scrape_jobs(
            site_name=sites or None,
            search_term=term,
            location=args.location,
            results_wanted=args.results,
            hours_old=args.hours_old,
            linkedin_fetch_description=True,
            description_format="markdown",
        )
        if df is None or df.empty:
            log(f"[{timestamp()}] scrape-empty: {term}")
            records = []
        else:
            records = df.to_dict(orient="records")
        output_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")

        if not args.no_import:
            import_script = repo_root / "scripts" / "import_jobspy_to_db.py"
            import_cmd = [
                sys.executable,
                str(import_script),
                "--input",
                str(output_path),
                "--require-description",
            ]
            if args.db:
                import_cmd += ["--db", args.db]
            if args.status:
                import_cmd += ["--status", args.status]
            log(f"[{timestamp()}] import: {output_path}")
            subprocess.run(import_cmd, check=True)
        if args.term_jitter_seconds > 0 and idx < len(terms) - 1:
            sleep_for = random.uniform(0, args.term_jitter_seconds)
            log(f"[{timestamp()}] term-jitter: {sleep_for:.1f}s")
            time.sleep(sleep_for)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run JobSpy for multiple terms and import to SQLite.")
    parser.add_argument(
        "--terms",
        default=",".join(DEFAULT_TERMS),
        help="Comma-separated search terms.",
    )
    parser.add_argument(
        "--location",
        default="Ontario, Canada",
        help="Search location (default: Ontario, Canada).",
    )
    parser.add_argument(
        "--sites",
        default="linkedin",
        help="Comma-separated sites (default: linkedin).",
    )
    parser.add_argument(
        "--results",
        type=int,
        default=20,
        help="Results wanted per term (default: 20).",
    )
    parser.add_argument(
        "--hours-old",
        type=int,
        default=2,
        help="Only return jobs posted within the last N hours (default: 2).",
    )
    parser.add_argument(
        "--output-dir",
        default="data/capture",
        help="Directory for JSON outputs (default: data/capture).",
    )
    parser.add_argument(
        "--db",
        default="data/capture/jobs.db",
        help="SQLite DB path (default: data/capture/jobs.db).",
    )
    parser.add_argument(
        "--status",
        default="new",
        help="Status value for inserted rows (default: new).",
    )
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Skip importing JSON into SQLite.",
    )
    parser.add_argument(
        "--interval-hours",
        type=float,
        default=None,
        help="If set, run in a loop every N hours.",
    )
    parser.add_argument(
        "--interval-jitter-seconds",
        type=float,
        default=0,
        help="Random extra sleep (0..N seconds) added to each interval loop.",
    )
    parser.add_argument(
        "--term-jitter-seconds",
        type=float,
        default=0,
        help="Random sleep (0..N seconds) between each term scrape.",
    )
    parser.add_argument(
        "--preflight-host",
        default="www.linkedin.com",
        help="Host to resolve before scraping (default: www.linkedin.com).",
    )
    parser.add_argument(
        "--retry-count",
        type=int,
        default=3,
        help="Retry count for DNS preflight (default: 3).",
    )
    parser.add_argument(
        "--retry-sleep-seconds",
        type=float,
        default=30,
        help="Sleep seconds between DNS retries (default: 30).",
    )
    parser.add_argument(
        "--retry-backoff",
        type=float,
        default=2,
        help="Backoff multiplier for DNS retry sleep (default: 2).",
    )
    args = parser.parse_args()

    if args.interval_hours and args.interval_hours > 0:
        interval_seconds = args.interval_hours * 3600
        while True:
            run_once(args)
            sleep_for = interval_seconds
            if args.interval_jitter_seconds and args.interval_jitter_seconds > 0:
                sleep_for += random.uniform(0, args.interval_jitter_seconds)
            log(f"[{datetime.now().isoformat(timespec='seconds')}] sleep: {sleep_for:.1f}s")
            time.sleep(sleep_for)
    else:
        run_once(args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
