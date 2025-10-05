from typing import Dict
from unittest.mock import patch

import pytest

from app import Book, app, db, is_valid_isbn13, parse_publication_year


@pytest.fixture(autouse=True)
def _db_setup():
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()


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


@patch("services.book_lookup.requests.get")
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

    with app.app_context():
        book = Book.query.filter_by(isbn13="9780306406157").first()
        assert book is not None
        assert book.title == "Example Book"
        assert book.author == "Jane Doe"
        assert book.publication_year == 2001
        assert book.thumbnail_url is not None


@patch("services.book_lookup.requests.get")
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
