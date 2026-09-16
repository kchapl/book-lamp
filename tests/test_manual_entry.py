"""Tests for manual book entry via the JSON API."""

from unittest.mock import patch

from book_lamp.app import get_storage


def test_manual_entry_success(authenticated_client):
    """POST /api/books with title and author creates the book."""
    response = authenticated_client.post(
        "/api/books",
        json={
            "isbn": "9781234567890",
            "title": "Manual Book",
            "author": "Manual Author",
            "publisher": "Manual Publisher",
            "publication_year": "2024",
        },
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["title"] == "Manual Book"
    assert body["author"] == "Manual Author"

    storage = get_storage()
    book = storage.get_book_by_isbn("9781234567890")
    assert book is not None
    assert book["title"] == "Manual Book"


def test_isbn_lookup_fail_reports_no_book_data(authenticated_client):
    """POST /api/books with an unresolvable ISBN returns 404 with a clear error."""
    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13"
    ) as mock_lookup:
        mock_lookup.return_value = None

        response = authenticated_client.post(
            "/api/books", json={"isbn": "0000000000000"}
        )

        assert response.status_code == 404
        assert response.get_json()["error"] == (
            "No book data found for ISBN 0000000000000"
        )


def test_manual_entry_duplicate_isbn(authenticated_client):
    """Adding an ISBN that already exists returns the existing book unchanged."""
    storage = get_storage()
    storage.add_book(
        isbn13="9781234567890", title="First Entry", author="Author One"
    )

    response = authenticated_client.post(
        "/api/books",
        json={"isbn": "9781234567890", "title": "Second Entry", "author": "Author Two"},
    )

    assert response.status_code == 200
    body = response.get_json()
    # Should return the first entry, not create a second one
    assert body["title"] == "First Entry"
    assert body["author"] == "Author One"


def test_manual_entry_existing_isbn_added_to_reading_list(authenticated_client):
    """Re-adding an existing ISBN also queues the book on the reading list."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="9781234567890", title="First Entry", author="Author One"
    )

    response = authenticated_client.post(
        "/api/books",
        json={"isbn": "9781234567890", "title": "Second Entry", "author": "Author Two"},
    )

    assert response.status_code == 200
    reading_list = storage.get_reading_list()
    assert any(item["book_id"] == book["id"] for item in reading_list)
