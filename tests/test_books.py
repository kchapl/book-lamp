from typing import Dict
from unittest.mock import patch

from book_lamp.app import get_storage, is_valid_isbn13, parse_publication_year


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
def test_add_book_success(mock_get, authenticated_client):
    storage = get_storage()

    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return _mock_open_library_response()

    mock_get.return_value = MockResp()

    resp = authenticated_client.post(
        "/books", data={"isbn": "9780306406157"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Book added successfully" in resp.data

    book = storage.get_book_by_isbn("9780306406157")
    assert book is not None
    assert book["title"] == "Example Book"
    assert book["author"] == "Jane Doe"
    assert book["publication_year"] == 2001
    assert book["thumbnail_url"] is not None


@patch("book_lamp.services.book_lookup.requests.get")
def test_add_book_multiple_authors(mock_get, authenticated_client):
    storage = get_storage()

    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ISBN:9780306406157": {
                    "title": "Collaborative Book",
                    "authors": [{"name": "Author One"}, {"name": "Author Two"}],
                    "publish_date": "2020",
                }
            }

    mock_get.return_value = MockResp()

    resp = authenticated_client.post(
        "/books", data={"isbn": "9780306406157"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Book added successfully" in resp.data

    book = storage.get_book_by_isbn("9780306406157")
    assert book is not None
    assert book["author"] == "Author One, Author Two"


@patch("book_lamp.services.book_lookup.requests.get")
def test_add_book_duplicate(mock_get, authenticated_client):
    class MockResp:
        def raise_for_status(self):
            return None

        def json(self):
            return _mock_open_library_response()

    mock_get.return_value = MockResp()

    # First add
    authenticated_client.post("/books", data={"isbn": "9780306406157"})
    # Duplicate add
    resp = authenticated_client.post(
        "/books", data={"isbn": "9780306406157"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"already been added" in resp.data


def test_add_book_invalid_isbn(authenticated_client):
    resp = authenticated_client.post(
        "/books", data={"isbn": "1234567890123"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"valid 13-digit ISBN" in resp.data


def test_delete_book_success(authenticated_client):
    # Add a book to storage
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780306406157", title="Test Book", author="Test Author"
    )
    book_id = book["id"]

    # Delete it via endpoint
    resp = authenticated_client.post(f"/books/{book_id}/delete", follow_redirects=True)
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
    assert b"Books" in resp.data


def test_add_book_authorized(client):
    """Verify adding books is accessible in test mode."""
    resp = client.get("/books/new", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Add a Book" in resp.data


def test_edit_book_success(authenticated_client):
    # Add a book to storage
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780306406157", title="Original Title", author="Original Author"
    )
    book_id = book["id"]

    # Update it via endpoint
    updated_data = {
        "isbn13": "9780306406157",
        "title": "Updated Title",
        "author": "Updated Author",
        "publication_year": "2022",
        "publisher": "Updated Publisher",
        "description": "Updated Description",
        "series": "Updated Series",
        "dewey_decimal": "123.456",
        "thumbnail_url": "https://example.com/cover.jpg",
        "cover_url": "https://example.com/large_cover.jpg",
    }
    resp = authenticated_client.post(
        f"/books/{book_id}/edit", data=updated_data, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Book updated successfully" in resp.data

    # Verify storage has updated info
    updated_book = storage.get_book_by_id(book_id)
    assert updated_book["title"] == "Updated Title"
    assert updated_book["author"] == "Updated Author"
    assert updated_book["publication_year"] == 2022
    assert updated_book["publisher"] == "Updated Publisher"
    assert updated_book["description"] == "Updated Description"
    assert updated_book["series"] == "Updated Series"
    assert updated_book["dewey_decimal"] == "123.456"
    assert updated_book["thumbnail_url"] == "https://example.com/cover.jpg"
    assert updated_book["cover_url"] == "https://example.com/large_cover.jpg"
