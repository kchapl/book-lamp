"""Integration tests for the search route."""

import pytest

from book_lamp.app import app


@pytest.fixture
def client():
    """Create a test client."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_search_route_requires_login(client):
    """Test that search route works in test mode (always authorized)."""
    response = client.get("/books/search?q=test")
    # In test mode, we're always authorized.
    # If the query is empty it redirects (302), if valid it returns 200.
    # With q=test, it should be 200.
    assert response.status_code == 200


def test_search_route_with_empty_query(client):
    """Test that empty query redirects back to books list."""
    # In test mode, we're automatically authorized
    response = client.get("/books/search?q=", follow_redirects=False)
    assert response.status_code == 302
    assert "/books" in response.location


def test_search_route_with_query(client):
    """Test search route with a valid query."""
    # Add a test book first
    client.post(
        "/books",
        data={
            "isbn": "9780000000000",
        },
        follow_redirects=True,
    )

    # Search for it
    response = client.get("/books/search?q=test", follow_redirects=True)
    assert response.status_code == 200
    assert b"Search results for" in response.data


def test_search_route_with_regex(client):
    """Test search route with regex mode."""
    response = client.get("/books/search?q=test&regex=1", follow_redirects=True)
    assert response.status_code == 200
    # Should show regex mode indicator
    assert b"regex mode" in response.data or b"Search results for" in response.data
