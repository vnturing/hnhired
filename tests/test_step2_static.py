"""
Step 2 — Static file serving.

RED  → fails because StaticFiles mount doesn't exist yet and app/static/ is
       not wired in.
GREEN → mount StaticFiles in main.py, create a minimal index.html.

We deliberately keep the assertion loose: we just check that / returns HTML.
We don't assert on content because the HTML will grow and we don't want
these tests to become maintenance noise.
"""


def test_index_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200


def test_index_is_html(client):
    response = client.get("/")
    assert "text/html" in response.headers["content-type"]
