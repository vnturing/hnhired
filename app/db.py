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

from datetime import datetime
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
    raw_text    TEXT    NOT NULL DEFAULT '',
    month       TEXT    NOT NULL DEFAULT ''
);
"""


def init_db(conn: sqlite3.Connection) -> None:
    """Create the jobs table if it does not already exist."""
    conn.executescript(_SCHEMA)
    # Ensure 'month' column exists if table was created by older schema
    columns = [row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()]
    if "month" not in columns:
        conn.execute("ALTER TABLE jobs ADD COLUMN month TEXT NOT NULL DEFAULT ''")
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
    month: str = "",
) -> int:
    """Insert one job row.

    Uses INSERT OR IGNORE so re-running ingestion on the same thread is safe.
    Returns the rowid of the inserted (or existing) row.
    """
    tags_str = ",".join(tech_tags)
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO jobs (hn_item_id, company, role, remote_type, tech_tags, raw_text, month)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (hn_item_id, company, role, remote_type, tags_str, raw_text, month),
    )
    conn.commit()
    # If the row was ignored (duplicate), update month if empty, and fetch existing id.
    if cursor.lastrowid == 0:
        if month:
            conn.execute(
                "UPDATE jobs SET month = ? WHERE hn_item_id = ? AND (month IS NULL OR month = '')",
                (month, hn_item_id),
            )
            conn.commit()
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
    month: str | None = None,
) -> list[Job]:
    """Query jobs with optional filters.

    remote_type — exact match.
    tech        — case-insensitive substring match against the stored tag string.
    month       — exact match against month string (e.g. "October 2026").
    """
    query = "SELECT id, hn_item_id, company, role, remote_type, tech_tags, raw_text, month FROM jobs WHERE 1=1"
    params: list = []

    if remote_type:
        query += " AND remote_type = ?"
        params.append(remote_type)

    if tech:
        # SQLite's LIKE is case-insensitive for ASCII by default.
        query += " AND LOWER(tech_tags) LIKE ?"
        params.append(f"%{tech.lower()}%")

    if month:
        query += " AND month = ?"
        params.append(month)

    rows = conn.execute(query, params).fetchall()
    return [_row_to_job(row) for row in rows]


def _month_sort_key(month_str: str) -> tuple[int, int]:
    try:
        dt = datetime.strptime(month_str.strip(), "%B %Y")
        return (dt.year, dt.month)
    except Exception:
        return (0, 0)


def sort_months(months: list[str]) -> list[str]:
    """Sort a list of month strings (e.g. 'October 2026') newest first."""
    return sorted(months, key=_month_sort_key, reverse=True)


def get_months(conn: sqlite3.Connection) -> list[str]:
    """Return distinct months present in the database, newest first."""
    rows = conn.execute("SELECT DISTINCT month FROM jobs WHERE month != ''").fetchall()
    months = [row[0] for row in rows]
    return sort_months(months)


def _row_to_job(row: tuple) -> Job:
    id_, hn_item_id, company, role, remote_type, tech_tags_str, raw_text, month = row
    return Job(
        id=id_,
        hn_item_id=hn_item_id,
        company=company,
        role=role,
        remote_type=remote_type,
        tech_tags=tech_tags_str.split(",") if tech_tags_str else [],
        raw_text=raw_text,
        month=month,
    )
