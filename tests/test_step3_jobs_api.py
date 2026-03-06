"""
Step 3 — /api/jobs returns a JSON list.

RED  → fails because the route doesn't exist.
GREEN → add the route returning a hardcoded list.  No database yet.

We test three things:
  1. Status 200.
  2. Body is a list.
  3. Each item has the fields our frontend will expect.

We don't assert exact values — just shape.  That way the test survives
when we swap hardcoded data for real DB data in Step 4.
"""

EXPECTED_JOB_KEYS = {
    "id",
    "company",
    "role",
    "remote_type",
    "tech_tags",
    "raw_text",
    "hn_item_id",
}


def test_jobs_returns_200(client):
    response = client.get("/api/jobs")
    assert response.status_code == 200


def test_jobs_body_is_list(client):
    response = client.get("/api/jobs")
    data = response.json()
    assert isinstance(data, list)


def test_jobs_items_have_expected_shape(client):
    response = client.get("/api/jobs")
    jobs = response.json()
    # With mock data there is at least one job to inspect.
    assert len(jobs) >= 1
    for job in jobs:
        missing = EXPECTED_JOB_KEYS - job.keys()
        assert not missing, f"Job is missing keys: {missing}"


def test_jobs_filter_by_remote_type(client):
    """Filtering on ?remote_type= must return only matching jobs."""
    response = client.get("/api/jobs?remote_type=global")
    jobs = response.json()
    for job in jobs:
        assert job["remote_type"] == "global"


def test_jobs_filter_by_tech(client):
    """Filtering on ?tech= must return only jobs whose tech_tags contain it."""
    response = client.get("/api/jobs?tech=python")
    jobs = response.json()
    for job in jobs:
        assert "python" in [t.lower() for t in job["tech_tags"]]
