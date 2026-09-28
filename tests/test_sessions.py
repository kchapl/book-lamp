"""Tests for session persistence.

Flask's signed-cookie sessions carry no expiry by default, so a signed-in reader
is signed out the moment they close the browser.
"""

from book_lamp.services.pg_storage import PostgresStorage

SESSION_COOKIE = "session"


def _session_cookie(response) -> str:
    """Return the raw Set-Cookie header for the session, or fail loudly."""
    headers: list[str] = response.headers.getlist("Set-Cookie")
    for raw in headers:
        if raw.startswith(f"{SESSION_COOKIE}="):
            return raw
    raise AssertionError(f"no {SESSION_COOKIE} cookie was set: {headers}")


def _has_expiry(cookie: str) -> bool:
    return "Expires=" in cookie or "Max-Age=" in cookie


def _stub_google_sign_in(monkeypatch) -> None:
    """Replace the two process boundaries the sign-in route crosses."""
    monkeypatch.setattr(
        "google.oauth2.id_token.verify_oauth2_token",
        lambda *args, **kwargs: {"email": "user@example.com", "name": "Test User"},
    )
    monkeypatch.setattr(PostgresStorage, "upsert_user", lambda email, name: 42)


def test_sign_in_gives_the_session_cookie_an_expiry(client, monkeypatch):
    """A signed-in reader should stay signed in after closing the browser."""
    _stub_google_sign_in(monkeypatch)

    response = client.post("/api/auth/google", json={"credential": "stub"})

    assert response.status_code == 200
    cookie = _session_cookie(response)
    assert _has_expiry(cookie), f"cookie dies with the browser: {cookie}"
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie


def test_a_refreshed_session_keeps_its_expiry(client):
    """Flask drops `permanent` when it reloads a session from the cookie.

    Unless the flag is set again on the request, the refreshed cookie is written
    without an expiry and the session silently reverts to a browser session.
    """
    response = client.get("/api/csrf-token")

    assert response.status_code == 200
    assert _has_expiry(_session_cookie(response))


def test_a_signed_in_reader_is_still_signed_in_and_still_has_an_expiry(client, monkeypatch):
    _stub_google_sign_in(monkeypatch)
    client.post("/api/auth/google", json={"credential": "stub"})

    response = client.get("/api/auth/status")

    assert response.get_json()["is_authenticated"] is True
    assert _has_expiry(_session_cookie(response))
