"""
db.py — SQLite persistence layer.

Three public functions cover everything the app needs:
  init_db(conn)           — create schema if not already present.
  insert_job(conn, ...)   — insert one job, ignoring duplicates.
  get_jobs(conn, ...)     — query jobs with optional filters.

We use the standard-library `sqlite3` directly (no ORM) because:
  • It ships with Python — zero extra dependencies.
  • The schema is simple and unlikely to change shape often.
  • Raw SQL is readable and easy to reason about.

The caller is responsible for opening and closing the connection.  This keeps
db.py testable (tests pass an :memory: connection) and lets main.py manage the
connection lifetime as a FastAPI dependency.

tech_tags serialisation
───────────────────────
SQLite has no array type.  We store tech tags as a comma-separated string and
deserialise on read.  This is intentionally simple; if querying by tag in SQL
becomes a bottleneck we can switch to a junction table later without changing
the public API of this module.
"""

import sqlite3

from app.schemas import Job

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    hn_item_id  INTEGER UNIQUE NOT NULL,
    company     TEXT    NOT NULL,
    role        TEXT    NOT NULL,
    remote_type TEXT    NOT NULL,
    tech_tags   TEXT    NOT NULL DEFAULT '',
    raw_text    TEXT    NOT NULL DEFAULT ''
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create the jobs table if it does not already exist."""
    conn.executescript(_SCHEMA)
    conn.commit()


def insert_job(
    conn: sqlite3.Connection,
    *,
    hn_item_id: int,
    company: str,
    role: str,
    remote_type: str,
    tech_tags: list[str],
    raw_text: str,
) -> int:
    """Insert one job row.

    Uses INSERT OR IGNORE so re-running ingestion on the same thread is safe.
    Returns the rowid of the inserted (or existing) row.
    """
    tags_str = ",".join(tech_tags)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO jobs (hn_item_id, company, role, remote_type, tech_tags, raw_text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (hn_item_id, company, role, remote_type, tags_str, raw_text),
    )
    conn.commit()
    # If the row was ignored (duplicate), fetch the existing id.
    if cursor.lastrowid == 0:
        row = conn.execute(
            "SELECT id FROM jobs WHERE hn_item_id = ?", (hn_item_id,)
        ).fetchone()
        return row[0]
    return cursor.lastrowid


def get_jobs(
    conn: sqlite3.Connection,
    *,
    remote_type: str | None = None,
    tech: str | None = None,
) -> list[Job]:
    """Query jobs with optional filters.

    remote_type — exact match.
    tech        — case-insensitive substring match against the stored tag string.
    """
    query = "SELECT id, hn_item_id, company, role, remote_type, tech_tags, raw_text FROM jobs WHERE 1=1"
    params: list = []

    if remote_type:
        query += " AND remote_type = ?"
        params.append(remote_type)

    if tech:
        # SQLite's LIKE is case-insensitive for ASCII by default.
        query += " AND LOWER(tech_tags) LIKE ?"
        params.append(f"%{tech.lower()}%")

    rows = conn.execute(query, params).fetchall()
    return [_row_to_job(row) for row in rows]


def _row_to_job(row: tuple) -> Job:
    id_, hn_item_id, company, role, remote_type, tech_tags_str, raw_text = row
    return Job(
        id=id_,
        hn_item_id=hn_item_id,
        company=company,
        role=role,
        remote_type=remote_type,
        tech_tags=tech_tags_str.split(",") if tech_tags_str else [],
        raw_text=raw_text,
    )
