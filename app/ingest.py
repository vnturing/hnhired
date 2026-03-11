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
import sqlite3
import sys
import urllib.request
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


def ingest(conn: sqlite3.Connection, *, thread_id: int) -> int:
    """Fetch *thread_id* from HN and insert all top-level comments as jobs.

    Returns the number of new rows inserted (duplicates are skipped silently).
    """
    thread = _fetch_item(thread_id)
    if not thread:
        return 0

    child_ids: list[int] = thread.get("kids", [])
    inserted = 0

    for comment_id in child_ids:
        try:
            comment = _fetch_item(comment_id)
            if not comment or comment.get("type") != "comment":
                continue
            kwargs = _process_comment(comment)
            insert_job(conn, **kwargs)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            log.warning("Skipping comment %d due to error: %s", comment_id, exc)

    return inserted


def find_latest_hiring_thread() -> int | None:
    """Find the ID of the most recent 'Ask HN: Who is hiring?' thread.

    The HN 'whoishiring' account submits these automatically. We fetch their
    profile, iterate over their recent submissions, and return the first one
    whose title starts with 'Ask HN: Who is hiring?'.
    """
    url = f"{HN_BASE_URL}/user/whoishiring.json"
    try:
        with urllib.request.urlopen(url) as resp:
            user_data = json.loads(resp.read())
    except urllib.error.URLError:
        return None

    submitted = user_data.get("submitted", [])

    for item_id in submitted:
        item = _fetch_item(item_id)
        if not item or item.get("type") != "story":
            continue

        title = item.get("title", "")
        if title.startswith("Ask HN: Who is hiring?"):
            return item_id

    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest HN 'Who is hiring?' threads.")
    parser.add_argument(
        "thread_id",
        type=int,
        nargs="?",
        help="Specific thread ID to ingest. If omitted, finds the latest thread automatically.",
    )
    args = parser.parse_args()

    thread_id = args.thread_id
    if not thread_id:
        print("Looking for the latest 'Who is hiring?' thread...")
        thread_id = find_latest_hiring_thread()
        if not thread_id:
            print("Error: Could not find a recent 'Who is hiring?' thread.")
            sys.exit(1)

    print(f"Ingesting thread {thread_id}...")

    # We must construct the path reliably regardless of cwd.
    db_path = Path(__file__).parent.parent / "data" / "jobs.db"

    # Ensure data dir exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    from app.db import init_db

    conn = sqlite3.connect(db_path)
    init_db(conn)

    inserted = ingest(conn, thread_id=thread_id)
    print(f"Done! Inserted {inserted} new jobs.")
    conn.close()
