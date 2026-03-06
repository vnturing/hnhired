"""
Shared pytest fixtures.

The `client` fixture gives every test a fresh TestClient backed by the real
FastAPI app.  We import the app here — not in each test file — so tests stay
focused on behaviour, not plumbing.

The lifespan (scheduler + auto-ingest) is disabled in tests via a null
lifespan patch so tests remain hermetic and fast (no real HN API calls).
"""

from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@asynccontextmanager
async def _null_lifespan(app):
    """Drop-in lifespan that does nothing — skips scheduler and auto-ingest."""
    yield


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient wrapping the FastAPI app.

    The scheduler lifespan is patched out so tests are hermetic.
    """
    with patch.object(app.router, "lifespan_context", _null_lifespan):
        with TestClient(app) as c:
            yield c
