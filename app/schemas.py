"""
schemas.py — Pydantic models.

These are the canonical shapes that flow between the API layer and the
outside world (the frontend, tests, and eventually the ingestion pipeline).

Keeping them in their own file means:
  - main.py imports schemas, not the other way around.
  - parser.py can import schemas without touching FastAPI.
  - Tests can construct Job instances directly for unit testing parsers.
"""

from __future__ import annotations

from pydantic import BaseModel


class Job(BaseModel):
    """A single job posting extracted from a HN 'Who's Hiring' comment."""

    id: int
    hn_item_id: int  # The HN comment ID — lets us link back to source.
    company: str
    role: str
    remote_type: str  # "global" | "us-only" | "eu-only" | "tz-limited" | "onsite"
    tech_tags: list[str]
    raw_text: str  # Original comment text, preserved for debugging.
