"""
ingest.py — Fetch HN 'Who's Hiring' threads and persist parsed jobs.

We use only the standard library (urllib.request, json, re) so this module
adds zero dependencies.  The HN Firebase REST API is public and requires no
auth.

Public interface
────────────────
ingest(conn, thread_id)  — fetch one thread, parse all top-level comments,
                           insert into DB.  Safe to call repeatedly.

HN API shape (relevant fields only)
────────────────────────────────────
Thread:  { id, title, kids: [comment_id, ...] }
Comment: { id, type, text, parent }

`text` is HTML-escaped and may contain <p> tags for paragraph breaks.
We strip HTML before passing to the parser.
"""

import argparse
import json
import logging
import re
import sqlite3
import sys
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from app.db import insert_job
from app.parser import extract_company, extract_role, classify_remote, extract_tech_tags

log = logging.getLogger(__name__)

HN_BASE_URL = "https://hacker-news.firebaseio.com/v0"


# ── HTML stripping ────────────────────────────────────────────────────────────


class _HTMLStripper(HTMLParser):
    """Minimal HTML stripper — turns <p> into newlines, drops all other tags."""

    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag == "p":
            self._parts.append("\n")

    def get_text(self) -> str:
        return "".join(self._parts).strip()


def _strip_html(html: str) -> str:
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


# ── HN API helpers ────────────────────────────────────────────────────────────


def _fetch_item(item_id: int) -> dict | None:
    """Fetch one HN item, returning None on network/JSON errors."""
    url = f"{HN_BASE_URL}/item/{item_id}.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
        return data  # None if item was deleted
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to fetch HN item %d: %s", item_id, exc)
        return None


# ── Pipeline ──────────────────────────────────────────────────────────────────


def _process_comment(comment: dict) -> dict:
    """Parse a raw HN comment dict into keyword args for insert_job."""
    raw_html = comment.get("text", "") or ""
    text = _strip_html(raw_html)
    return dict(
        hn_item_id=comment["id"],
        company=extract_company(text),
        role=extract_role(text),
        remote_type=classify_remote(text),
        tech_tags=extract_tech_tags(text),
        raw_text=text,
    )


def extract_month_from_thread(thread: dict) -> str:
    """Extract month string (e.g. 'October 2026') from thread title or timestamp."""
    title = thread.get("title", "")
    match = re.search(
        r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})\b",
        title,
        re.IGNORECASE,
    )
    if match:
        month_name = match.group(1).capitalize()
        year = match.group(2)
        return f"{month_name} {year}"

    thread_time = thread.get("time")
    if thread_time:
        return datetime.fromtimestamp(thread_time, tz=timezone.utc).strftime("%B %Y")

    return ""


def ingest(
    conn: sqlite3.Connection, *, thread_id: int, month: str | None = None
) -> int:
    """Fetch *thread_id* from HN and insert all top-level comments as jobs.

    Returns the number of new rows inserted (duplicates are skipped silently).
    """
    thread = _fetch_item(thread_id)
    if not thread:
        return 0

    thread_month = month or extract_month_from_thread(thread)

    child_ids: list[int] = thread.get("kids", [])
    inserted = 0

    for comment_id in child_ids:
        try:
            comment = _fetch_item(comment_id)
            if not comment or comment.get("type") != "comment":
                continue
            kwargs = _process_comment(comment)
            insert_job(conn, **kwargs, month=thread_month)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping comment %d due to error: %s", comment_id, exc)

    return inserted


def find_hiring_threads(limit: int = 1) -> list[int]:
    """Find the IDs of recent 'Ask HN: Who is hiring?' threads."""
    url = f"{HN_BASE_URL}/user/whoishiring.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            user_data = json.loads(resp.read())
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        return []

    submitted = user_data.get("submitted", [])
    threads: list[int] = []

    for item_id in submitted:
        item = _fetch_item(item_id)
        if not item or item.get("type") != "story":
            continue

        title = item.get("title", "")
        if title.startswith("Ask HN: Who is hiring?"):
            threads.append(item_id)
            if len(threads) >= limit:
                break

    return threads


def find_latest_hiring_thread() -> int | None:
    """Find the ID of the most recent 'Ask HN: Who is hiring?' thread."""
    threads = find_hiring_threads(limit=1)
    return threads[0] if threads else None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest HN 'Who is hiring?' threads.")
    parser.add_argument(
        "thread_id",
        type=int,
        nargs="?",
        help="Specific thread ID to ingest. If omitted, finds recent threads automatically.",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=1,
        help="Number of recent monthly threads to ingest (default: 1).",
    )
    args = parser.parse_args()

    # We must construct the path reliably regardless of cwd.
    db_path = Path(__file__).parent.parent / "data" / "jobs.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    from app.db import init_db

    conn = sqlite3.connect(db_path)
    init_db(conn)

    if args.thread_id:
        threads_to_ingest = [args.thread_id]
    else:
        print(f"Looking for the latest {args.months} 'Who is hiring?' thread(s)...")
        threads_to_ingest = find_hiring_threads(limit=args.months)
        if not threads_to_ingest:
            print("Error: Could not find any recent 'Who is hiring?' threads.")
            sys.exit(1)

    total_inserted = 0
    for tid in threads_to_ingest:
        print(f"Ingesting thread {tid}...")
        n = ingest(conn, thread_id=tid)
        print(f"  → Inserted {n} new jobs from thread {tid}.")
        total_inserted += n

    print(f"Done! Total inserted: {total_inserted} new jobs.")
    conn.close()
