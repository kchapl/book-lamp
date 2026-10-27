"""Tests for the JSON API routes added in improvement #2.

Each test exercises a new /api/* endpoint that the React SPA calls.
All tests use TEST_MODE=1 so no real PostgreSQL connection is required.
"""

import csv
import io
import json
from unittest.mock import patch

import pytest

from book_lamp.app import get_storage

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _json(resp):
    """Decode a Flask test response as JSON."""
    return json.loads(resp.data)


# ---------------------------------------------------------------------------
# Data export
# ---------------------------------------------------------------------------


def test_api_export_csv_includes_books_readings_and_reading_list(authenticated_client):
    """The authenticated CSV export contains catalogue, history, and list data."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780306406157",
        title="Exported Book",
        author="Jane Doe, John Smith",
        publication_year=2020,
        publisher="Example Press",
        description="A book for export",
        series="Example Series",
        bisac_category="FICTION / General",
        language="eng",
        page_count=240,
        physical_format="Paperback",
        edition="2nd",
        thumbnail_url="https://example.com/thumb.jpg",
        cover_url="https://example.com/cover.jpg",
    )
    storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-10", 5)
    storage.add_reading(book["id"], "In Progress", "2025-02-03")
    storage.add_to_reading_list(book["id"])

    response = authenticated_client.get("/api/export/csv")

    assert response.status_code == 200
    assert response.mimetype == "text/csv"
    assert response.headers["Content-Disposition"] == "attachment; filename=book-lamp-export.csv"
    assert response.headers["Cache-Control"] == "private, no-store"
    assert response.data.startswith(b"\xef\xbb\xbf")

    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
    assert len(rows) == 2
    assert rows[0]["ISBN-13"] == "9780306406157"
    assert rows[0]["Title"] == "Exported Book"
    assert rows[0]["Author"] == "Jane Doe, John Smith"
    assert rows[0]["Description"] == "A book for export"
    assert rows[0]["Reading status"] == "Completed"
    assert rows[0]["Start date"] == "2024-01-01"
    assert rows[0]["Rating"] == "5"
    assert rows[0]["On reading list"] == "Yes"
    assert rows[0]["Reading list position"] == "1"
    assert rows[1]["Reading status"] == "In Progress"
    assert rows[1]["End date"] == ""


def test_api_export_csv_escapes_spreadsheet_formulas(authenticated_client):
    """Exported user-controlled text cannot execute as a spreadsheet formula."""
    storage = get_storage()
    storage.add_book(isbn13="9780306406157", title='=HYPERLINK("https://example.com")', author="+SUM(1,1)")

    response = authenticated_client.get("/api/export/csv")
    rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))

    assert rows[0]["Title"] == '\'=HYPERLINK("https://example.com")'
    assert rows[0]["Author"] == "'+SUM(1,1)"


def test_api_export_csv_requires_authentication(client, monkeypatch):
    """CSV export does not expose a reader's data to anonymous requests."""
    monkeypatch.setattr("book_lamp.middleware.auth.is_test_mode", lambda: False)
    response = client.get("/api/export/csv")

    assert response.status_code == 401
    assert response.json == {"error": "Unauthorized"}


# ---------------------------------------------------------------------------
# Books – create
# ---------------------------------------------------------------------------


def test_api_create_book_manual_entry(authenticated_client):
    """POST /api/books with title+author creates a book and returns 201."""
    resp = authenticated_client.post(
        "/api/books",
        json={"title": "My New Book", "author": "Some Author", "isbn": ""},
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert body["title"] == "My New Book"
    assert body["author"] == "Some Author"


def test_api_create_book_upgrades_isbn10(authenticated_client):
    """POST /api/books with an ISBN-10 stores the equivalent ISBN-13."""
    resp = authenticated_client.post(
        "/api/books",
        json={"title": "Ten Digit", "author": "Someone", "isbn": "0143127741"},
    )
    assert resp.status_code == 201
    assert resp.get_json()["isbn13"] == "9780143127741"
    assert get_storage().get_book_by_isbn("9780143127741") is not None


def test_api_create_book_isbn_test_mode(authenticated_client):
    """POST /api/books with the special TEST_ISBN returns the test book."""
    resp = authenticated_client.post(
        "/api/books",
        json={"isbn": "9780000000000"},
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert body["title"] == "Test Book"


def test_api_create_book_missing_isbn_and_title(authenticated_client):
    """POST /api/books with neither isbn nor title+author returns 400."""
    resp = authenticated_client.post("/api/books", json={})
    assert resp.status_code == 400


def test_api_create_book_deduplication(authenticated_client):
    """POST /api/books for an existing ISBN returns 200 with existing book."""
    storage = get_storage()
    storage.add_book(isbn13="9780306406157", title="Existing", author="Author")

    resp = authenticated_client.post(
        "/api/books",
        json={"isbn": "9780306406157"},
    )
    assert resp.status_code == 200
    body = _json(resp)
    assert body["title"] == "Existing"


# ---------------------------------------------------------------------------
# Books – update
# ---------------------------------------------------------------------------


def test_api_update_book_success(authenticated_client):
    """POST /api/books/<id>/edit updates the book and returns success."""
    storage = get_storage()
    book = storage.add_book(isbn13="111", title="Old Title", author="Old Author")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/edit",
        json={"title": "New Title", "author": "New Author"},
    )
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}

    updated = storage.get_book_by_id(book["id"])
    assert updated["title"] == "New Title"


def test_api_update_book_rewrites_the_category_pair(authenticated_client):
    """A new category from the edit form brings its major and sub with it.

    The form sends the full category and nothing else, so the pair is derived
    from it rather than left behind on the category being replaced (ADR-0002).
    """
    storage = get_storage()
    book = storage.add_book(
        isbn13="444",
        title="T",
        author="A",
        bisac_category="HISTORY / Ancient / General",
        bisac_main_category="HISTORY",
        bisac_sub_category="Ancient / General",
    )

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/edit",
        json={"title": "T", "author": "A", "bisac_category": "FICTION / Literary"},
    )
    assert resp.status_code == 200

    updated = storage.get_book_by_id(book["id"])
    assert updated["bisac_category"] == "FICTION / Literary"
    assert updated["bisac_main_category"] == "FICTION"
    assert updated["bisac_sub_category"] == "Literary"


def test_api_update_book_missing_fields(authenticated_client):
    """POST /api/books/<id>/edit without title+author returns 400."""
    storage = get_storage()
    book = storage.add_book(isbn13="222", title="T", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/edit",
        json={"title": ""},
    )
    assert resp.status_code == 400


def test_api_update_book_invalid_isbn(authenticated_client):
    """POST /api/books/<id>/edit with a bad ISBN-13 returns 400."""
    storage = get_storage()
    book = storage.add_book(isbn13="333", title="T", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/edit",
        json={"title": "T", "author": "A", "isbn13": "000"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Books – delete
# ---------------------------------------------------------------------------


def test_api_delete_book_success(authenticated_client):
    """POST /api/books/<id>/delete removes the book and returns success."""
    storage = get_storage()
    book = storage.add_book(isbn13="444", title="To Delete", author="A")
    book_id = book["id"]

    resp = authenticated_client.post(f"/api/books/{book_id}/delete")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}
    assert storage.get_book_by_id(book_id) is None


def test_api_delete_book_not_found(authenticated_client):
    """POST /api/books/<id>/delete for a missing book returns 404."""
    resp = authenticated_client.post("/api/books/99999/delete")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Books – search
# ---------------------------------------------------------------------------


def test_api_search_books_empty_query(authenticated_client):
    """GET /api/books/search with no query returns empty list."""
    resp = authenticated_client.get("/api/books/search")
    assert resp.status_code == 200
    body = _json(resp)
    assert body["books"] == []


def test_api_search_books_with_results(authenticated_client):
    """GET /api/books/search?q=... returns matching books."""
    storage = get_storage()
    b = storage.add_book(isbn13="555", title="Searchable Title", author="An Author")
    storage.add_reading(b["id"], "Completed", "2024-01-01", "2024-01-15", 4)

    resp = authenticated_client.get("/api/books/search?q=Searchable")
    assert resp.status_code == 200
    body = _json(resp)
    assert any(bk["title"] == "Searchable Title" for bk in body["books"])


# ---------------------------------------------------------------------------
# Books – ISBN lookup
# ---------------------------------------------------------------------------


def test_api_lookup_isbn_test_mode(authenticated_client):
    """GET /api/books/lookup?isbn=TEST_ISBN returns test book data."""
    resp = authenticated_client.get("/api/books/lookup?isbn=9780000000000")
    assert resp.status_code == 200
    body = _json(resp)
    assert body["title"] == "Test Book"


def test_api_lookup_isbn_missing_param(authenticated_client):
    """GET /api/books/lookup without isbn returns 400."""
    resp = authenticated_client.get("/api/books/lookup")
    assert resp.status_code == 400


@patch("book_lamp.services.book_lookup.lookup_book_by_isbn13")
def test_api_lookup_isbn_adds_publication_year(mock_lookup, authenticated_client):
    """The lookup response exposes publication_year parsed from publish_date."""
    mock_lookup.return_value = {
        "isbn13": "9780306406157",
        "title": "Example Book",
        "author": "Jane Doe",
        "publish_date": "Sep 08, 2015",
    }

    resp = authenticated_client.get("/api/books/lookup?isbn=9780306406157")

    assert resp.status_code == 200
    body = _json(resp)
    assert body["publication_year"] == 2015
    assert body["title"] == "Example Book"


# ---------------------------------------------------------------------------
# Readings – create
# ---------------------------------------------------------------------------


def test_api_create_reading_success(authenticated_client):
    """POST /api/books/<id>/readings creates a record and returns 201."""
    storage = get_storage()
    book = storage.add_book(isbn13="666", title="Book", author="Author")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/readings",
        json={
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-10",
            "rating": 4,
        },
    )
    assert resp.status_code == 201
    body = _json(resp)
    assert body["status"] == "Completed"


def test_api_create_reading_missing_fields(authenticated_client):
    """POST /api/books/<id>/readings without required fields returns 400."""
    storage = get_storage()
    book = storage.add_book(isbn13="777", title="B", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/readings",
        json={"status": "Completed"},  # missing start_date
    )
    assert resp.status_code == 400


@pytest.mark.parametrize("status", ["Completed", "Abandoned"])
def test_api_create_reading_ended_without_an_end_date(authenticated_client, status):
    """A status that ends a Reading is refused when it carries no end date."""
    storage = get_storage()
    book = storage.add_book(isbn13="778", title="B", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/readings",
        json={"status": status, "start_date": "2024-01-01"},
    )

    assert resp.status_code == 400
    assert "end date" in _json(resp)["error"]


def test_api_create_reading_in_progress_needs_no_end_date(authenticated_client):
    """An open Reading is writable without an end date."""
    storage = get_storage()
    book = storage.add_book(isbn13="779", title="B", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/readings",
        json={"status": "In Progress", "start_date": "2024-01-01"},
    )

    assert resp.status_code == 201


def test_api_create_reading_again_with_the_same_status_and_start_date(authenticated_client):
    """A second Reading that matches the first is still a second Reading.

    A Reading is one attempt at a Book, so the same status and start date is a
    re-read rather than a duplicate: the route must store it and answer 201 with
    its own id, not hand back the record it matched.
    """
    storage = get_storage()
    book = storage.add_book(isbn13="782", title="B", author="A")

    payload = {"status": "In Progress", "start_date": "2024-01-01", "rating": 5}
    first = authenticated_client.post(f"/api/books/{book['id']}/readings", json=payload)
    second = authenticated_client.post(f"/api/books/{book['id']}/readings", json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert _json(second)["id"] != _json(first)["id"]

    records = storage.get_readings(book_id=book["id"])
    assert len(records) == 2
    assert {record["rating"] for record in records} == {5}


# ---------------------------------------------------------------------------
# Readings – update
# ---------------------------------------------------------------------------


def test_api_update_reading_success(authenticated_client):
    """POST /api/readings/<id>/edit updates and returns success."""
    storage = get_storage()
    book = storage.add_book(isbn13="888", title="B", author="A")
    record = storage.add_reading(book["id"], "In Progress", "2024-01-01")

    resp = authenticated_client.post(
        f"/api/readings/{record['id']}/edit",
        json={
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "rating": 5,
        },
    )
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_update_reading_refuses_completed_without_an_end_date(authenticated_client):
    """Ending a Reading through the edit route is refused without an end date."""
    storage = get_storage()
    book = storage.add_book(isbn13="781", title="B", author="A")
    record = storage.add_reading(book["id"], "In Progress", "2024-01-01")

    resp = authenticated_client.post(
        f"/api/readings/{record['id']}/edit",
        json={"status": "Completed", "start_date": "2024-01-01"},
    )

    assert resp.status_code == 400
    assert "end date" in _json(resp)["error"]


# ---------------------------------------------------------------------------
# Readings – delete
# ---------------------------------------------------------------------------


def test_api_delete_reading_success(authenticated_client):
    """POST /api/readings/<id>/delete removes the record."""
    storage = get_storage()
    book = storage.add_book(isbn13="999", title="B", author="A")
    record = storage.add_reading(book["id"], "In Progress", "2024-01-01")

    resp = authenticated_client.post(f"/api/readings/{record['id']}/delete")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_delete_reading_not_found(authenticated_client):
    """POST /api/readings/<id>/delete for missing record returns 404."""
    resp = authenticated_client.post("/api/readings/99999/delete")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Reading list – reorder, remove, start-reading, add-to-reading-list
# ---------------------------------------------------------------------------


def test_api_reorder_reading_list(authenticated_client):
    """POST /api/reading-list/reorder accepts a JSON list of book IDs."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="r1", title="B1", author="A")
    b2 = storage.add_book(isbn13="r2", title="B2", author="A")
    storage.add_to_reading_list(b1["id"])
    storage.add_to_reading_list(b2["id"])

    resp = authenticated_client.post(
        "/api/reading-list/reorder",
        json={"book_ids": [b2["id"], b1["id"]]},
    )
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_remove_from_reading_list(authenticated_client):
    """POST /api/reading-list/remove/<id> removes the book and returns success."""
    storage = get_storage()
    book = storage.add_book(isbn13="rm1", title="B", author="A")
    storage.add_to_reading_list(book["id"])

    resp = authenticated_client.post(f"/api/reading-list/remove/{book['id']}")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_start_reading(authenticated_client):
    """POST /api/books/<id>/start-reading moves a book to the reading log."""
    storage = get_storage()
    book = storage.add_book(isbn13="sr1", title="B", author="A")
    storage.add_to_reading_list(book["id"])

    resp = authenticated_client.post(f"/api/books/{book['id']}/start-reading")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_add_to_reading_list(authenticated_client):
    """POST /api/books/<id>/add-to-reading-list adds a book to the reading list."""
    storage = get_storage()
    book = storage.add_book(isbn13="al1", title="B", author="A")

    resp = authenticated_client.post(f"/api/books/{book['id']}/add-to-reading-list")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}
