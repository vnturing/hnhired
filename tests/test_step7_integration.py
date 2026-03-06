"""
Step 7 — Integration: /api/jobs reads from the database.

RED  → fails because main.py still returns stub data.
GREEN → replace _STUB_JOBS with a real DB dependency.

We use FastAPI's dependency_overrides to inject an in-memory DB connection
during tests.  This avoids touching the filesystem and keeps tests fast.

This is the most important integration test: it exercises the full stack
from HTTP request → route → DB query → JSON response.
"""

import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app, get_db
from app.db import init_db, insert_job


@pytest.fixture
def db_conn():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()


@pytest.fixture
def client_with_db(db_conn):
    """TestClient whose /api/jobs reads from an in-memory DB."""
    app.dependency_overrides[get_db] = lambda: db_conn
    yield TestClient(app)
    app.dependency_overrides.clear()


def _insert(conn, *, hn_item_id, company, role, remote_type, tech_tags):
    insert_job(
        conn,
        hn_item_id=hn_item_id,
        company=company,
        role=role,
        remote_type=remote_type,
        tech_tags=tech_tags,
        raw_text=f"{company} | {role}",
    )


class TestJobsRouteWithDb:
    def test_returns_db_rows(self, client_with_db, db_conn):
        _insert(
            db_conn,
            hn_item_id=1,
            company="RealCo",
            role="Eng",
            remote_type="global",
            tech_tags=["Python"],
        )
        jobs = client_with_db.get("/api/jobs").json()
        assert any(j["company"] == "RealCo" for j in jobs)

    def test_filter_remote_type_from_db(self, client_with_db, db_conn):
        _insert(
            db_conn,
            hn_item_id=1,
            company="GlobalCo",
            role="Eng",
            remote_type="global",
            tech_tags=[],
        )
        _insert(
            db_conn,
            hn_item_id=2,
            company="USCo",
            role="Eng",
            remote_type="us-only",
            tech_tags=[],
        )
        jobs = client_with_db.get("/api/jobs?remote_type=global").json()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "GlobalCo"

    def test_filter_tech_from_db(self, client_with_db, db_conn):
        _insert(
            db_conn,
            hn_item_id=1,
            company="PyCo",
            role="Eng",
            remote_type="global",
            tech_tags=["Python", "FastAPI"],
        )
        _insert(
            db_conn,
            hn_item_id=2,
            company="GoCo",
            role="Eng",
            remote_type="global",
            tech_tags=["Go"],
        )
        jobs = client_with_db.get("/api/jobs?tech=python").json()
        assert len(jobs) == 1
        assert jobs[0]["company"] == "PyCo"
