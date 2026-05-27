from unittest.mock import patch

import pytest


@pytest.fixture
def mock_google_verify():
    with patch("google.oauth2.id_token.verify_oauth2_token") as mock:
        yield mock


def test_google_auth_success(client, mock_google_verify):
    # Mock successful verification
    mock_google_verify.return_value = {
        "email": "user@example.com",
        "name": "Test User",
        "sub": "google-id-123",
    }

    # Mock PostgresStorage.upsert_user if it's used
    with patch(
        "book_lamp.services.pg_storage.PostgresStorage.upsert_user"
    ) as mock_upsert:
        mock_upsert.return_value = 1

        response = client.post("/api/auth/google", json={"credential": "valid-jwt"})

        assert response.status_code == 200
        assert response.get_json() == {"ok": True}

        with client.session_transaction() as sess:
            assert sess["user_id"] == 1
            assert sess["user_email"] == "user@example.com"


def test_google_auth_missing_credential(client):
    response = client.post("/api/auth/google", json={})
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_google_auth_invalid_credential(client, mock_google_verify):
    # Mock verification failure
    mock_google_verify.side_effect = ValueError("Invalid token")

    response = client.post("/api/auth/google", json={"credential": "invalid-jwt"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "Invalid credential"}
