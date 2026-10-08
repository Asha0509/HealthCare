"""CORS only allows the known frontends and never reflects an arbitrary origin."""

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def _preflight(origin: str):
    return client.options(
        "/api/triage/assess",
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )


def test_deployed_frontend_is_allowed() -> None:
    r = _preflight("https://healthai-triage.onrender.com")
    assert r.headers.get("access-control-allow-origin") == "https://healthai-triage.onrender.com"


def test_unknown_origin_is_not_reflected_and_no_credentials() -> None:
    r = _preflight("https://evil.example")
    assert r.headers.get("access-control-allow-origin") is None
    assert r.headers.get("access-control-allow-credentials") is None
