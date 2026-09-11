# backend/tests/test_cors.py
"""Regression test for the CORS allowlist: both loopback spellings
(localhost and 127.0.0.1) must be accepted, since the frontend launchd
service binds 127.0.0.1 explicitly and some clients' DNS resolution
lands the browser on that literal origin instead of localhost. See
app/main.py's CORSMiddleware comment.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_cors_allows_localhost_origin():
    response = client.options(
        "/graph",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_allows_127_loopback_origin():
    response = client.options(
        "/graph",
        headers={"Origin": "http://127.0.0.1:3000", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"


def test_cors_rejects_unrelated_origin():
    response = client.options(
        "/graph",
        headers={"Origin": "http://evil.example.com", "Access-Control-Request-Method": "GET"},
    )
    assert response.headers.get("access-control-allow-origin") is None
