"""
main.py — FastAPI application entry point.

Final shape after Step 7.  The evolution was:
  Step 1 — health route.
  Step 2 — static file serving (html=True catch-all mount).
  Step 3 — /api/jobs returning stub data.
  Step 7 — /api/jobs reading from SQLite via a FastAPI dependency.

IMPORTANT ordering rule: API routes must be registered BEFORE the StaticFiles
mount.  FastAPI matches routes in registration order, and the StaticFiles mount
acts as a catch-all for /.  If it came first, it would swallow /api/* requests.
"""

import logging
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import Depends, FastAPI, Query
from fastapi.staticfiles import StaticFiles

from app.db import get_jobs as db_get_jobs, init_db
from app.ingest import find_latest_hiring_thread, ingest
from app.schemas import Job

log = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


# ── Database dependency ───────────────────────────────────────────────────────


def get_db() -> sqlite3.Connection:
    """Open a SQLite connection for the lifetime of one request."""
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


# ── Scheduled ingestion ───────────────────────────────────────────────────────


def _run_ingest() -> None:
    """Find and ingest the latest 'Who is hiring?' thread."""
    log.info("Scheduled ingest: starting")
    thread_id = find_latest_hiring_thread()
    if not thread_id:
        log.warning("Scheduled ingest: could not find a hiring thread")
        return
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    init_db(conn)
    try:
        n = ingest(conn, thread_id=thread_id)
        log.info("Scheduled ingest: inserted %d new jobs from thread %d", n, thread_id)
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background scheduler; run an initial ingest if the DB is empty."""
    scheduler = BackgroundScheduler()

    # Daily cron: every day at 09:00 system time. The thread ID search
    # ensures we always grab the current month's thread and pull new comments.
    scheduler.add_job(_run_ingest, "cron", hour=9, minute=0)
    scheduler.start()

    # On first boot (empty DB), populate immediately so the UI isn't blank.
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    init_db(conn)
    try:
        jobs = db_get_jobs(conn)
        if not jobs:
            log.info("Database is empty — running initial ingest")
            _run_ingest()
    finally:
        conn.close()

    yield

    scheduler.shutdown(wait=False)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="HN Explorer", lifespan=lifespan)


# ── Step 1: health ────────────────────────────────────────────────────────────


@app.get("/api/health")
def health() -> dict:
    """Liveness probe.  Returns {"status": "ok"}."""
    return {"status": "ok"}


# ── Step 3 → 7: jobs ─────────────────────────────────────────────────────────


@app.get("/api/jobs", response_model=list[Job])
def list_jobs(
    remote_type: str | None = Query(default=None),
    tech: str | None = Query(default=None),
    conn: sqlite3.Connection = Depends(get_db),
) -> list[Job]:
    """Return job listings from the database, optionally filtered.

    Query params:
      remote_type — exact match against job.remote_type
      tech        — case-insensitive substring match against tech_tags
    """
    return db_get_jobs(conn, remote_type=remote_type, tech=tech)


# ── Step 2: static files ──────────────────────────────────────────────────────
# Must come LAST — it is a catch-all for everything not matched above.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
