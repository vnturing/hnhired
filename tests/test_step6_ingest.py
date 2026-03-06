"""
Step 6 — ingest.py: fetch + parse + persist.

RED  → fails because app/ingest.py doesn't exist.
GREEN → implement fetch_thread(), process_comment(), ingest().

We NEVER hit the real HN API in tests.  Instead we use unittest.mock to
intercept urllib.request calls and return canned JSON.  This makes the tests:
  - Fast (no network latency).
  - Hermetic (no dependency on external services).
  - Deterministic (same data every run).

The mock data mirrors the real HN API shape so tests exercise the full
parsing pipeline.
"""

import json
import sqlite3
from unittest.mock import patch, MagicMock

import pytest

from app.db import init_db, get_jobs
from app.ingest import ingest, find_latest_hiring_thread, HN_BASE_URL

# ── Fixtures ──────────────────────────────────────────────────────────────────

FAKE_THREAD_ID = 39000000

# Shape mirrors https://hacker-news.firebaseio.com/v0/item/{id}.json
FAKE_THREAD = {
    "id": FAKE_THREAD_ID,
    "type": "story",
    "title": "Ask HN: Who is hiring? (March 2024)",
    "kids": [39000001, 39000002, 39000003],
}

FAKE_COMMENTS = {
    39000001: {
        "id": 39000001,
        "type": "comment",
        "text": "Acme Corp | Senior Python Engineer | Remote (Global) | Python, FastAPI, PostgreSQL<p>Great team, fully remote.",
        "parent": FAKE_THREAD_ID,
    },
    39000002: {
        "id": 39000002,
        "type": "comment",
        "text": "Initech | Backend Engineer | Remote (US only) | Go, Kubernetes<p>Seed-stage startup.",
        "parent": FAKE_THREAD_ID,
    },
    39000003: {
        "id": 39000003,
        "type": "comment",
        "text": "We are hiring! See our website for details.",  # no pipe → minimal parse
        "parent": FAKE_THREAD_ID,
    },
}

FAKE_USER = {
    "id": "whoishiring",
    "submitted": [39000008, 39000007, FAKE_THREAD_ID, 39000005],  # Newest first
}

FAKE_OTHER_STORIES = {
    39000008: {
        "id": 39000008,
        "type": "story",
        "title": "Who is hiring? (April 2024)",
    },  # Not starting with "Ask HN:"
    39000007: {
        "id": 39000007,
        "type": "story",
        "title": "Ask HN: Freelancer? Seeking freelancer? (March 2024)",
    },
    39000005: {
        "id": 39000005,
        "type": "story",
        "title": "Ask HN: Who wants to be hired? (March 2024)",
    },
}


def _make_mock_urlopen(thread_id: int):
    """Return a mock for urllib.request.urlopen that returns canned HN JSON."""

    def urlopen_side_effect(url: str):
        mock_response = MagicMock()
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        if "whoishiring.json" in url:
            mock_response.read.return_value = json.dumps(FAKE_USER).encode()
            return mock_response

        if str(thread_id) in url and "kids" not in url:
            # Requesting the thread itself
            if any(str(cid) in url for cid in FAKE_COMMENTS):
                # Requesting a comment
                for cid, comment in FAKE_COMMENTS.items():
                    if str(cid) in url:
                        mock_response.read.return_value = json.dumps(comment).encode()
                        return mock_response
            mock_response.read.return_value = json.dumps(FAKE_THREAD).encode()
        else:
            # Requesting something else
            for cid, comment in FAKE_COMMENTS.items():
                if str(cid) in url:
                    mock_response.read.return_value = json.dumps(comment).encode()
                    return mock_response

            for sid, story in FAKE_OTHER_STORIES.items():
                if str(sid) in url:
                    mock_response.read.return_value = json.dumps(story).encode()
                    return mock_response

            mock_response.read.return_value = b"null"
        return mock_response

    return urlopen_side_effect


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    init_db(conn)
    yield conn
    conn.close()


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestIngest:
    def test_inserts_jobs_from_thread(self, db):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            ingest(db, thread_id=FAKE_THREAD_ID)

        jobs = get_jobs(db)
        assert len(jobs) == 3

    def test_parses_company_correctly(self, db):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            ingest(db, thread_id=FAKE_THREAD_ID)

        jobs = get_jobs(db)
        companies = {j.company for j in jobs}
        assert "Acme Corp" in companies
        assert "Initech" in companies

    def test_classifies_remote_correctly(self, db):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            ingest(db, thread_id=FAKE_THREAD_ID)

        jobs = get_jobs(db)
        by_company = {j.company: j for j in jobs}
        assert by_company["Acme Corp"].remote_type == "global"
        assert by_company["Initech"].remote_type == "us-only"

    def test_extracts_tech_tags(self, db):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            ingest(db, thread_id=FAKE_THREAD_ID)

        jobs = get_jobs(db)
        by_company = {j.company: j for j in jobs}
        assert "Python" in by_company["Acme Corp"].tech_tags

    def test_idempotent_on_second_run(self, db):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            ingest(db, thread_id=FAKE_THREAD_ID)
            ingest(db, thread_id=FAKE_THREAD_ID)  # second run

        jobs = get_jobs(db)
        assert len(jobs) == 3  # no duplicates


class TestFindLatestHiringThread:
    def test_finds_correct_thread(self):
        with patch(
            "urllib.request.urlopen", side_effect=_make_mock_urlopen(FAKE_THREAD_ID)
        ):
            latest_id = find_latest_hiring_thread()

        # Should skip 39000008 (wrong title) and 39000007 (Freelancer thread)
        # Should land on FAKE_THREAD_ID
        assert latest_id == FAKE_THREAD_ID
