"""
Step 5 — db.py: SQLite persistence.

RED  → fails because app/db.py doesn't exist.
GREEN → implement init_db(), insert_job(), get_jobs() backed by SQLite.

We use an in-memory SQLite database (:memory:) in tests so:
  1. Tests are hermetic — no file system side effects.
  2. Each test function gets a fresh DB via the fixture.
  3. Tests run fast — no disk I/O.

The `db` fixture creates a connection, initialises the schema, yields the
connection for the test to use, then closes it.  No state leaks between tests.
"""

import sqlite3
import pytest
from app.db import init_db, insert_job, get_jobs
from app.schemas import Job


@pytest.fixture
def db():
    """Yield an initialised in-memory SQLite connection."""
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()


def _sample_job(**overrides) -> dict:
    base = dict(
        hn_item_id=12345,
        company="TestCo",
        role="Engineer",
        remote_type="global",
        tech_tags=["Python", "FastAPI"],
        raw_text="TestCo | Engineer | Remote",
    )
    base.update(overrides)
    return base


class TestInitDb:
    def test_creates_jobs_table(self, db):
        cursor = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'"
        )
        assert cursor.fetchone() is not None


class TestInsertJob:
    def test_inserts_one_row(self, db):
        insert_job(db, **_sample_job())
        count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 1

    def test_returns_assigned_id(self, db):
        job_id = insert_job(db, **_sample_job())
        assert isinstance(job_id, int)
        assert job_id > 0

    def test_tech_tags_stored_as_comma_string(self, db):
        insert_job(db, **_sample_job(tech_tags=["Go", "Rust"]))
        row = db.execute("SELECT tech_tags FROM jobs").fetchone()
        assert row[0] == "Go,Rust"

    def test_duplicate_hn_item_id_is_ignored(self, db):
        insert_job(db, **_sample_job(hn_item_id=99))
        insert_job(db, **_sample_job(hn_item_id=99))  # duplicate
        count = db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 1  # still one row


class TestGetJobs:
    def test_returns_list_of_job_objects(self, db):
        insert_job(db, **_sample_job())
        jobs = get_jobs(db)
        assert isinstance(jobs, list)
        assert len(jobs) == 1
        assert isinstance(jobs[0], Job)

    def test_filter_by_remote_type(self, db):
        insert_job(db, **_sample_job(remote_type="global"))
        insert_job(db, **_sample_job(hn_item_id=2, remote_type="us-only"))
        jobs = get_jobs(db, remote_type="global")
        assert all(j.remote_type == "global" for j in jobs)
        assert len(jobs) == 1

    def test_filter_by_tech(self, db):
        insert_job(db, **_sample_job(tech_tags=["Python", "FastAPI"]))
        insert_job(db, **_sample_job(hn_item_id=2, tech_tags=["Go", "Kubernetes"]))
        jobs = get_jobs(db, tech="python")
        assert len(jobs) == 1
        assert "Python" in jobs[0].tech_tags

    def test_tech_tags_round_trip(self, db):
        insert_job(db, **_sample_job(tech_tags=["Python", "FastAPI", "PostgreSQL"]))
        jobs = get_jobs(db)
        assert jobs[0].tech_tags == ["Python", "FastAPI", "PostgreSQL"]
