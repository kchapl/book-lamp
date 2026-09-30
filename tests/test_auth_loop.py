"""Regression tests for the anonymous auth-redirect loop.

The SPA polls /api/sync/diagnostics on every route. When that endpoint
required authentication it returned 401 to anonymous visitors, the API
client redirected them to /unauthorised (served by the SPA catch-all),
and the freshly booted app polled again - an endless loop. These tests
pin the backend half of the contract that breaks that cycle.
"""


def test_sync_diagnostics_is_public_for_anonymous(client):
    """Anonymous visitors must not receive 401 from the polled endpoint."""
    resp = client.get("/api/sync/diagnostics")
    assert resp.status_code == 200
    assert resp.json["status"] == "unauthenticated"


def test_sync_diagnostics_reports_health_when_authenticated(authenticated_client):
    resp = authenticated_client.get("/api/sync/diagnostics")
    assert resp.status_code == 200
    assert resp.json["status"] == "ok"


def test_anonymous_home_does_not_require_auth(client):
    """The landing page is public; only its data endpoints are protected."""
    resp = client.get("/")
    assert resp.status_code == 200


def test_anonymous_protected_api_returns_json_401_not_redirect(monkeypatch):
    """A 401 (not a 3xx) keeps the client on the SPA shell rather than bouncing."""
    import os

    from book_lamp.app import create_app

    os.environ["SECRET_KEY"] = "test-secret-key"
    monkeypatch.setenv("TEST_MODE", "0")
    app = create_app()
    client = app.test_client()

    resp = client.get("/api/recommendations")
    assert resp.status_code == 401
    assert resp.json == {"error": "Unauthorized"}
    assert "Location" not in resp.headers


def test_unauthorised_route_serves_shell_without_redirect_chain(client):
    """The redirect target must render the shell, not redirect again."""
    resp = client.get("/unauthorised")
    assert resp.status_code == 200
    assert b'id="root"' in resp.data
    assert "Location" not in resp.headers
