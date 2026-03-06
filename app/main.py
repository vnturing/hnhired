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

import sqlite3
from pathlib import Path

from fastapi import Depends, FastAPI, Query
from fastapi.staticfiles import StaticFiles

from app.db import get_jobs as db_get_jobs, init_db
from app.schemas import Job

app = FastAPI(title="HN Explorer")

# ── Database dependency ───────────────────────────────────────────────────────
# FastAPI's dependency injection system calls get_db() for each request that
# declares it as a parameter.  Tests can swap this out via
# app.dependency_overrides[get_db] = lambda: <test_conn>

_DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def get_db() -> sqlite3.Connection:
    """Open a SQLite connection for the lifetime of one request."""
    conn = sqlite3.connect(_DB_PATH)
    init_db(conn)
    try:
        yield conn
    finally:
        conn.close()


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
