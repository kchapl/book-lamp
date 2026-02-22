import re
from unittest.mock import patch

from book_lamp.app import get_storage, is_valid_isbn13, parse_publication_year


def test_isbn13_validation():
    assert is_valid_isbn13("9780306406157") is True  # known valid
    assert is_valid_isbn13("9780306406158") is False  # wrong checksum
    assert is_valid_isbn13("123") is False


def test_parse_publication_year():
    assert parse_publication_year("2001") == 2001
    assert parse_publication_year("July 2019") == 2019
    assert parse_publication_year(None) is None


@patch("book_lamp.services.book_lookup._get_session")
def test_add_book_success(mock_session_factory, authenticated_client):
    storage = get_storage()

    class MockResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ISBN:9780306406157": {
                    "title": "Example Book",
                    "authors": [{"name": "Jane Doe"}],
                    "publish_date": "2001",
                    "cover": {
                        "medium": "https://covers.openlibrary.org/b/id/12345-M.jpg"
                    },
                }
            }

    mock_session = mock_session_factory.return_value
    mock_session.get.return_value = MockResp()
    mock_session.head.return_value = MockResp()

    resp = authenticated_client.post(
        "/books", data={"isbn": "9780306406157"}, follow_redirects=True
    )
    assert resp.status_code == 200
    assert b"Book added successfully" in resp.data

    book = storage.get_book_by_isbn("9780306406157")
    assert book["title"] == "Example Book"


def test_delete_book_success(authenticated_client):
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780306406157", title="Test Book", author="Test Author"
    )
    book_id = book["id"]

    resp = authenticated_client.post(f"/books/{book_id}/delete", follow_redirects=True)
    assert resp.status_code == 200
    assert storage.get_book_by_id(book_id) is None


def test_edit_book_success(authenticated_client):
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780306406157", title="Original Title", author="Original Author"
    )

    updated_data = {
        "isbn13": "9780306406157",
        "title": "Updated Title",
        "author": "Updated Author",
        "publication_year": "2022",
    }
    resp = authenticated_client.post(
        f"/books/{book['id']}/edit", data=updated_data, follow_redirects=True
    )
    assert resp.status_code == 200

    updated_book = storage.get_book_by_id(book["id"])
    assert updated_book["title"] == "Updated Title"


# --- UI and Button Tests ---


def _opening_tag_for_text(
    html: str, tag_text: str, tag_name: str = "button"
) -> str | None:
    pattern = rf"(<{tag_name}[^>]*>)(?:\s*{re.escape(tag_text)})"
    m = re.search(pattern, html, flags=re.IGNORECASE | re.DOTALL)
    return m.group(1) if m else None


def test_books_page_buttons_have_no_inline_styles(authenticated_client):
    resp = authenticated_client.get("/books")
    html = resp.data.decode("utf-8")

    fetch_tag = _opening_tag_for_text(html, "Fetch missing data")
    assert fetch_tag is not None
    assert "style=" not in fetch_tag
