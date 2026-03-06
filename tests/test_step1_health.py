"""
Step 1 — FastAPI app with one route.

RED  → these tests fail because app/main.py doesn't exist yet.
GREEN → create the minimal main.py that makes them pass.

We test two things:
  1. The /api/health route responds 200.
  2. The JSON body has a "status" key set to "ok".

Nothing more.  If we tested more we'd be writing code we don't need yet.
"""


def test_health_returns_200(client):
    response = client.get("/api/health")
    assert response.status_code == 200


def test_health_body_has_status_ok(client):
    response = client.get("/api/health")
    data = response.json()
    assert data["status"] == "ok"
