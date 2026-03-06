"""
Step 4 — parser.py: pure extraction functions.

RED  → fails because app/parser.py doesn't exist.
GREEN → implement each extractor with the minimum regex/heuristic needed.

These are UNIT tests — they test one function at a time with concrete strings.
That makes failures easy to diagnose and fixes easy to make without re-running
the full integration suite.

Each test group follows the same shape:
  - A "happy path" with a clear signal in the text.
  - At least one "edge case" or alternative phrasing.
  - A "default / fallback" case where no signal is found.
"""

import pytest
from app.parser import extract_company, extract_role, classify_remote, extract_tech_tags

# ── extract_company ───────────────────────────────────────────────────────────


class TestExtractCompany:
    def test_pipe_separated(self):
        text = "Acme Corp | Senior Engineer | Remote"
        assert extract_company(text) == "Acme Corp"

    def test_strips_whitespace(self):
        text = "  Hooli  | ML Engineer | Onsite"
        assert extract_company(text) == "Hooli"

    def test_no_pipe_returns_unknown(self):
        text = "We are hiring a great engineer to join our team"
        assert extract_company(text) == "Unknown"


# ── extract_role ──────────────────────────────────────────────────────────────


class TestExtractRole:
    def test_second_pipe_segment(self):
        text = "Acme Corp | Senior Python Engineer | Remote"
        assert extract_role(text) == "Senior Python Engineer"

    def test_strips_whitespace(self):
        text = "Acme | Software Engineer  | US only"
        assert extract_role(text) == "Software Engineer"

    def test_only_one_pipe_returns_unknown(self):
        text = "Acme Corp | Remote"
        assert extract_role(text) == "Unknown"


# ── classify_remote ───────────────────────────────────────────────────────────


class TestClassifyRemote:
    def test_global_remote(self):
        assert classify_remote("Remote (Worldwide)") == "global"
        assert classify_remote("fully remote, global") == "global"
        assert classify_remote("remote - anywhere") == "global"

    def test_us_only(self):
        assert classify_remote("Remote (US only)") == "us-only"
        assert classify_remote("remote, must be US-based") == "us-only"
        assert classify_remote("USA remote") == "us-only"
        assert classify_remote("Remote (U.S. only)") == "us-only"
        assert classify_remote("REMOTE (USA or Canada)") == "us-only"

    def test_eu_only(self):
        assert classify_remote("Remote (Europe)") == "eu-only"
        assert classify_remote("EU remote only") == "eu-only"
        assert classify_remote("remote, EMEA") == "eu-only"

    def test_tz_limited(self):
        assert classify_remote("Remote (overlap with CET required)") == "tz-limited"
        assert classify_remote("remote, timezone overlap needed") == "tz-limited"

    def test_onsite_default(self):
        assert classify_remote("Onsite in San Francisco") == "onsite"
        assert classify_remote("hybrid, NYC") == "onsite"
        assert classify_remote("no remote info whatsoever") == "onsite"

    def test_regional_remote_forces_onsite(self):
        assert classify_remote("Remote (India)") == "onsite"
        assert classify_remote("Remote, UK") == "onsite"
        assert classify_remote("Remote - LATAM") == "onsite"


# ── extract_tech_tags ─────────────────────────────────────────────────────────


class TestExtractTechTags:
    def test_finds_python(self):
        tags = extract_tech_tags("We use Python, FastAPI, and PostgreSQL")
        assert "Python" in tags

    def test_finds_multiple(self):
        tags = extract_tech_tags("Stack: Go, Kubernetes, gRPC, Postgres")
        assert "Go" in tags
        assert "Kubernetes" in tags

    def test_case_insensitive_match(self):
        tags = extract_tech_tags("experience with PYTHON and REACT preferred")
        assert "Python" in tags
        assert "React" in tags

    def test_returns_list(self):
        tags = extract_tech_tags("Python developer needed")
        assert isinstance(tags, list)

    def test_empty_text_returns_empty_list(self):
        tags = extract_tech_tags("")
        assert tags == []

    def test_no_known_tags_returns_empty(self):
        tags = extract_tech_tags("We value kindness and curiosity")
        assert tags == []
