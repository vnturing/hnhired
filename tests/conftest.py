"""
Shared pytest fixtures.

The `client` fixture gives every test a fresh TestClient backed by the real
FastAPI app.  We import the app here — not in each test file — so tests stay
focused on behaviour, not plumbing.

The lifespan (scheduler + auto-ingest) is disabled in tests via a null
lifespan patch so tests remain hermetic and fast (no real HN API calls).
"""

import sqlite3
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db, insert_job
from app.main import app, get_db


@asynccontextmanager
async def _null_lifespan(app):
    """Drop-in lifespan that does nothing — skips scheduler and auto-ingest."""
    yield


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient wrapping the FastAPI app.

    The scheduler lifespan is patched out so tests are hermetic. An in-memory
    database with a sample job is injected so route tests don't touch disk.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    init_db(conn)
    insert_job(
        conn,
        hn_item_id=99999,
        company="Acme Corp",
        role="Senior Engineer",
        remote_type="global",
        tech_tags=["Python", "FastAPI"],
        raw_text="Acme Corp | Senior Engineer | Remote",
        month="October 2026",
    )
    app.dependency_overrides[get_db] = lambda: conn
    with patch.object(app.router, "lifespan_context", _null_lifespan):
        with TestClient(app) as c:
            yield c
    app.dependency_overrides.pop(get_db, None)
    conn.close()
