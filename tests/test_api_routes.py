"""Tests for the JSON API routes added in improvement #2.

Each test exercises a new /api/* endpoint that the React SPA calls.
All tests use TEST_MODE=1 so no real PostgreSQL connection is required.
"""

import json

from book_lamp.app import get_storage

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _json(resp):
    """Decode a Flask test response as JSON."""
    return json.loads(resp.data)


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
    storage.add_reading_record(b["id"], "Completed", "2024-01-01", "2024-01-15", 4)

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


# ---------------------------------------------------------------------------
# Reading records – create
# ---------------------------------------------------------------------------


def test_api_create_reading_record_success(authenticated_client):
    """POST /api/books/<id>/reading-records creates a record and returns 201."""
    storage = get_storage()
    book = storage.add_book(isbn13="666", title="Book", author="Author")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/reading-records",
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


def test_api_create_reading_record_missing_fields(authenticated_client):
    """POST /api/books/<id>/reading-records without required fields returns 400."""
    storage = get_storage()
    book = storage.add_book(isbn13="777", title="B", author="A")

    resp = authenticated_client.post(
        f"/api/books/{book['id']}/reading-records",
        json={"status": "Completed"},  # missing start_date
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Reading records – update
# ---------------------------------------------------------------------------


def test_api_update_reading_record_success(authenticated_client):
    """POST /api/reading-records/<id>/edit updates and returns success."""
    storage = get_storage()
    book = storage.add_book(isbn13="888", title="B", author="A")
    record = storage.add_reading_record(book["id"], "In Progress", "2024-01-01")

    resp = authenticated_client.post(
        f"/api/reading-records/{record['id']}/edit",
        json={
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "rating": 5,
        },
    )
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


# ---------------------------------------------------------------------------
# Reading records – delete
# ---------------------------------------------------------------------------


def test_api_delete_reading_record_success(authenticated_client):
    """POST /api/reading-records/<id>/delete removes the record."""
    storage = get_storage()
    book = storage.add_book(isbn13="999", title="B", author="A")
    record = storage.add_reading_record(book["id"], "In Progress", "2024-01-01")

    resp = authenticated_client.post(f"/api/reading-records/{record['id']}/delete")
    assert resp.status_code == 200
    assert _json(resp) == {"success": True}


def test_api_delete_reading_record_not_found(authenticated_client):
    """POST /api/reading-records/<id>/delete for missing record returns 404."""
    resp = authenticated_client.post("/api/reading-records/99999/delete")
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
