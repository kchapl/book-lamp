from typing import Dict
from unittest.mock import patch

import pytest

from book_lamp.app import is_valid_isbn13, parse_publication_year, storage


@pytest.fixture(autouse=True)
def _storage_reset():
    """Reset mock storage before each test."""
    storage.books = []
    storage.next_id = 1
    yield


def test_isbn13_validation():
    assert is_valid_isbn13("9780306406157") is True  # known valid
    assert is_valid_isbn13("9780306406158") is False  # wrong checksum
    assert is_valid_isbn13("123") is False
    assert is_valid_isbn13("978030640615X") is False


def test_parse_publication_year():
    assert parse_publication_year("2001") == 2001
    assert parse_publication_year("July 2019") == 2019
    assert parse_publication_year("2019-05-02") == 2019
    assert parse_publication_year(None) is None
    assert parse_publication_year("") is None
    assert parse_publication_year("Not a date") is None


def _mock_open_library_response() -> Dict:
    return {
        "ISBN:9780306406157": {
            "title": "Example Book",
            "authors": [{"name": "Jane Doe"}],
            "publish_date": "2001",
            "cover": {"medium": "https://covers.openlibrary.org/b/id/12345-M.jpg"},
        }
    }


@patch("book_lamp.services.book_lookup.requests.get")
def test_add_book_success(mock_get, client):
    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return _mock_open_library_response()

    mock_get.return_value = MockResp()

    resp = client.post("/books", data={"isbn": "9780306406157"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"Book added successfully" in resp.data

    book = storage.get_book_by_isbn("9780306406157")
    assert book is not None
    assert book["title"] == "Example Book"
    assert book["author"] == "Jane Doe"
    assert book["publication_year"] == 2001
    assert book["thumbnail_url"] is not None


@patch("book_lamp.services.book_lookup.requests.get")
def test_add_book_duplicate(mock_get, client):
    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return _mock_open_library_response()

    mock_get.return_value = MockResp()

    # First add
    client.post("/books", data={"isbn": "9780306406157"})
    # Duplicate add
    resp = client.post("/books", data={"isbn": "9780306406157"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"already been added" in resp.data


def test_add_book_invalid_isbn(client):
    resp = client.post("/books", data={"isbn": "1234567890123"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"valid 13-digit ISBN" in resp.data


def test_delete_book_success(client):
    # Add a book to storage
    book = storage.add_book(
        isbn13="9780306406157", title="Test Book", author="Test Author"
    )
    book_id = book["id"]

    # Delete it via endpoint
    resp = client.post(f"/books/{book_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Book deleted" in resp.data

    # Ensure it's gone
    assert storage.get_book_by_id(book_id) is None


def test_delete_book_not_found(client):
    resp = client.post("/books/999/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Book not found" in resp.data


def test_list_books_authorized(client):
    """Verify books list is accessible in test mode."""
    resp = client.get("/books", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Your Library" in resp.data


def test_add_book_authorized(client):
    """Verify adding books is accessible in test mode."""
    resp = client.get("/books/new", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Add a Book" in resp.data
