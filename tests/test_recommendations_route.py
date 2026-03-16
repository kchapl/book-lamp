"""Tests for the /api/recommendations Flask route."""

from unittest.mock import MagicMock, patch

import pytest

from book_lamp.app import app


@pytest.fixture()
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


@pytest.fixture(autouse=True)
def test_mode(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")


def _authorise(app):
    """Flip MockStorage into the authorised state."""
    from book_lamp.app import _mock_storage_singleton

    _mock_storage_singleton.set_authorised(True)
    return _mock_storage_singleton


def test_recommendations_returns_empty_when_no_llm_key(client, monkeypatch):
    """Without LLM_API_KEY the route should return an empty list and an error hint."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    _authorise(app)
    resp = client.get("/api/recommendations")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["recommendations"] == []
    assert "LLM_API_KEY" in data.get("error", "")


def test_recommendations_returns_cached_recs(client, monkeypatch):
    """Cached (fresh) recommendations should be returned without calling the LLM."""
    from datetime import datetime, timezone

    monkeypatch.setenv("LLM_API_KEY", "test-key")
    storage = _authorise(app)

    # Pre-populate the cache
    now = datetime.now(timezone.utc).isoformat()
    storage.recommendations = [
        {
            "id": 1,
            "title": "Foundation",
            "author": "Isaac Asimov",
            "isbn13": "9780553293357",
            "justification": "Classic sci-fi.",
            "created_at": now,
        }
    ]

    with patch("book_lamp.app.get_llm_client") as mock_get_llm:
        mock_llm = MagicMock()
        mock_llm.client = MagicMock()  # Simulate a configured client
        mock_get_llm.return_value = mock_llm

        resp = client.get("/api/recommendations")

    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Foundation"
    # LLM should not have been called since the cache was fresh
    mock_llm.generate_recommendations.assert_not_called()
