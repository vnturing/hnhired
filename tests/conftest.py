"""
Shared pytest fixtures.

The `client` fixture gives every test a fresh TestClient backed by the real
FastAPI app.  We import the app here — not in each test file — so tests stay
focused on behaviour, not plumbing.
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client() -> TestClient:
    """Return a synchronous TestClient wrapping the FastAPI app."""
    return TestClient(app)
