import os

import pytest

from book_lamp.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    os.environ["TEST_MODE"] = "1"
    with app.test_client() as client:
        with app.app_context():
            # Reset storage
            client.post("/test/reset")
            # Connect
            client.get("/test/connect")
        yield client


def test_manual_entry_success(client):
    # Submit manual entry form
    response = client.post(
        "/books",
        data={
            "isbn": "9781234567890",
            "title": "Manual Book",
            "author": "Manual Author",
            "publisher": "Manual Publisher",
            "publication_year": "2024",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Book added to your reading list." in response.data
    assert b"Manual Book" in response.data


def test_isbn_lookup_fail_redirects_to_manual(client):
    from unittest.mock import patch

    # Use patch to ensure lookup fails
    with patch("book_lamp.services.book_lookup.lookup_book_by_isbn13") as mock_lookup:
        mock_lookup.return_value = None

        response = client.post(
            "/books", data={"isbn": "0000000000000"}, follow_redirects=True
        )

        assert response.status_code == 200
        # Should see the message about entering manually
        assert b"No book data found for ISBN 0000000000000" in response.data
        # Should be on the new book page with ISBN prepopulated
        assert b'value="0000000000000"' in response.data
        assert b'id="manual-entry-section"' in response.data


def test_manual_entry_duplicate_isbn(client):
    # Add first book
    client.post(
        "/books",
        data={"isbn": "9781234567890", "title": "First Entry", "author": "Author One"},
    )

    # Try to add same ISBN manually
    response = client.post(
        "/books",
        data={"isbn": "9781234567890", "title": "Second Entry", "author": "Author Two"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Book moved to your reading list." in response.data
    # Should be the first entry title, not the second
    assert b"First Entry" in response.data
