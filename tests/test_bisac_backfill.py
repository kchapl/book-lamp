from unittest.mock import patch

import pytest

from book_lamp.app import _background_backfill_categories
from book_lamp.services.book_lookup import enhance_books_batch, lookup_book_by_isbn13
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.mock_storage import MockStorage
from book_lamp.utils.books import normalise_bisac_category, normalise_major_bisac


@pytest.fixture
def mock_storage():
    return MockStorage()


def test_normalisation_rules():
    # 1. Test reject cases (should return None)
    reject_cases = [
        "823.92",
        "823/.914",
        "623.45119",
        "en",
        "EN",
        "eng",
        "book",
        "books",
        "ebook",
        "e-book",
        "print",
        "audio",
        "paperback",
        "hardcover",
        "416",
        "123",
        "Unknown",
        "",
        None,
    ]
    for case in reject_cases:
        assert normalise_major_bisac(case) is None, f"Should have rejected '{case}'"

    # 2. Test accept and normalize cases (STABLE_CATEGORIES)
    assert normalise_major_bisac("fiction") == "FICTION"
    assert normalise_major_bisac("Fiction") == "FICTION"
    assert normalise_major_bisac("HISTORY") == "HISTORY"
    assert normalise_major_bisac("Biography") == "BIOGRAPHY & AUTOBIOGRAPHY"
    assert (
        normalise_major_bisac("Biography & Autobiography")
        == "BIOGRAPHY & AUTOBIOGRAPHY"
    )
    assert normalise_major_bisac("Political Science") == "POLITICAL SCIENCE"

    # 3. Short valid category names that should NOT be confused with language codes
    # These are checked against STABLE_CATEGORIES BEFORE the language code filter
    assert normalise_major_bisac("art") == "ART"
    assert normalise_major_bisac("ART") == "ART"
    assert normalise_major_bisac("poetry") == "POETRY"
    assert normalise_major_bisac("drama") == "DRAMA"

    # 4. Unknown category falls back to uppercase for unlisted categories
    assert normalise_major_bisac("random valid category") == "RANDOM VALID CATEGORY"

    # 5. Full category string parsing and subcategory filtering
    assert normalise_bisac_category("FICTION / Literary") == (
        "FICTION / Literary",
        "FICTION",
        "Literary",
    )
    assert normalise_bisac_category("History / Europe") == (
        "HISTORY / Europe",
        "HISTORY",
        "Europe",
    )
    # Subcategory is a digit -> should be filtered out
    assert normalise_bisac_category("FICTION / 416") == ("FICTION", "FICTION", None)
    # Subcategory is a language code -> should be filtered out
    assert normalise_bisac_category("HISTORY / en") == ("HISTORY", "HISTORY", None)
    # Invalid major category -> should return all Nones
    assert normalise_bisac_category("823.92 / Literary") == (None, None, None)
    # Pure language code -> should return all Nones
    assert normalise_bisac_category("en") == (None, None, None)


def test_lookup_prioritization_and_progressive_fallback():
    # Setup: Google Books has valid category, Open Library has different category
    # Google Books should be prioritized
    with (
        patch("book_lamp.services.book_lookup._lookup_google_books") as mock_gb,
        patch("book_lamp.services.book_lookup._lookup_open_library") as mock_ol,
    ):
        mock_gb.return_value = {
            "title": "GB Book",
            "bisac_category": "FICTION / General",
            "bisac_main_category": "FICTION",
            "bisac_sub_category": "General",
        }
        mock_ol.return_value = {
            "title": "OL Book",
            "bisac_category": "HISTORY / General",
            "bisac_main_category": "HISTORY",
            "bisac_sub_category": "General",
            "thumbnail_url": "http://example.com/ol.jpg",
        }

        res = lookup_book_by_isbn13("9780000000001")
        assert res is not None
        assert res["bisac_category"] == "FICTION / General"
        assert res["bisac_main_category"] == "FICTION"
        assert (
            res["thumbnail_url"] == "http://example.com/ol.jpg"
        )  # Merged other fields

    # Setup: Google Books has NO category, Open Library has valid category
    # Open Library category should be used as fallback
    with (
        patch("book_lamp.services.book_lookup._lookup_google_books") as mock_gb,
        patch("book_lamp.services.book_lookup._lookup_open_library") as mock_ol,
    ):
        mock_gb.return_value = {
            "title": "GB Book",
            "bisac_category": None,
            "bisac_main_category": None,
            "bisac_sub_category": None,
        }
        mock_ol.return_value = {
            "title": "OL Book",
            "bisac_category": "HISTORY / General",
            "bisac_main_category": "HISTORY",
            "bisac_sub_category": "General",
        }

        res = lookup_book_by_isbn13("9780000000001")
        assert res is not None
        assert res["bisac_category"] == "HISTORY / General"
        assert res["bisac_main_category"] == "HISTORY"


def test_enhance_books_replaces_dewey_with_bisac(mock_storage):
    # Setup: A book with a Dewey category
    book = mock_storage.add_book(
        isbn13="9780000000001",
        title="Test Book",
        author="Test Author",
        bisac_category="823.914",  # Dewey decimal
    )

    books = [book]

    # Mock lookup result returning a BISAC category
    mock_lookup_result = {
        "9780000000001": {
            "title": "Test Book",
            "author": "Test Author",
            "bisac_category": "FICTION / General",
            "bisac_main_category": "FICTION",
            "bisac_sub_category": "General",
            "thumbnail_url": "http://example.com/cover.jpg",
        }
    }

    with patch(
        "book_lamp.services.book_lookup.lookup_books_batch",
        return_value=mock_lookup_result,
    ):
        # Action: Enhance with force_refresh
        updated_count = enhance_books_batch(books, force_refresh=True)

        # Action: Save back to storage (simulating _background_fetch_missing_data)
        items_to_update = [{"book": b, "record": None} for b in books]
        mock_storage.bulk_import(items_to_update)

    # Verify
    assert updated_count == 1
    updated_book = mock_storage.get_book_by_id(book["id"])
    assert updated_book["bisac_category"] == "FICTION / General"
    assert updated_book["bisac_main_category"] == "FICTION"
    assert updated_book["bisac_sub_category"] == "General"


def test_enhance_books_preserves_bisac(mock_storage):
    # Setup: A book already has a BISAC category
    book = mock_storage.add_book(
        isbn13="9780000000002",
        title="BISAC Book",
        author="Author",
        bisac_category="HISTORY / Ancient / General",
        bisac_main_category="HISTORY",
        bisac_sub_category="Ancient / General",
    )

    books = [book]

    # Mock lookup result returning a DIFFERENT BISAC
    mock_lookup_result = {
        "9780000000002": {
            "title": "BISAC Book",
            "author": "Author",
            "bisac_category": "NEW CATEGORY / Sub",
            "bisac_main_category": "NEW CATEGORY",
            "bisac_sub_category": "Sub",
            "thumbnail_url": "http://example.com/cover.jpg",
        }
    }

    with patch(
        "book_lamp.services.book_lookup.lookup_books_batch",
        return_value=mock_lookup_result,
    ):
        enhance_books_batch(books, force_refresh=True)
        items_to_update = [{"book": b, "record": None} for b in books]
        mock_storage.bulk_import(items_to_update)

    # Verify: Should favor the new non-Dewey category
    updated_book = mock_storage.get_book_by_id(book["id"])
    assert updated_book["bisac_category"] == "NEW CATEGORY / Sub"
    assert updated_book["bisac_main_category"] == "NEW CATEGORY"


def test_is_dewey_logic_in_storage(mock_storage):
    # This specifically tests the logic in bulk_import/update_book

    # 1. Dewey to BISAC - SHOULD UPDATE
    mock_storage.books = []
    book1 = mock_storage.add_book(
        isbn13="1", title="B1", author="A1", bisac_category="123.45"
    )
    mock_storage.update_book(
        book_id=book1["id"], isbn13="1", title="B1", author="A1", bisac_category="BISAC"
    )
    assert mock_storage.books[0]["bisac_category"] == "BISAC"

    # 2. BISAC to Dewey - SHOULD PRESERVE BISAC
    mock_storage.books = []
    book2 = mock_storage.add_book(
        isbn13="2", title="B2", author="A2", bisac_category="BISAC"
    )
    mock_storage.update_book(
        book_id=book2["id"], isbn13="2", title="B2", author="A2", bisac_category="999.9"
    )
    assert mock_storage.books[0]["bisac_category"] == "BISAC"

    # 3. BISAC to BISAC - SHOULD UPDATE (force refresh scenario)
    mock_storage.books = []
    book3 = mock_storage.add_book(
        isbn13="3", title="B3", author="A3", bisac_category="BISAC OLD"
    )
    mock_storage.update_book(
        book_id=book3["id"],
        isbn13="3",
        title="B3",
        author="A3",
        bisac_category="BISAC NEW",
    )
    assert mock_storage.books[0]["bisac_category"] == "BISAC NEW"


def test_backfill_categories_sets_every_book_to_major_bisac_or_unknown(
    authenticated_client,
):
    from book_lamp.app import get_storage

    storage = get_storage()
    # A book with a Dewey category
    storage.add_book(
        isbn13="9780000000001",
        title="Dewey Book",
        author="Author",
        bisac_category="823.914",
    )
    # A book with existing correct category
    storage.add_book(
        isbn13="9780000000002",
        title="Existing BISAC Book",
        author="Author",
        bisac_category="HISTORY / Europe / Great Britain",
        bisac_main_category="HISTORY",
        bisac_sub_category="Europe / Great Britain",
    )
    # A book with no ISBN
    storage.add_book(
        isbn13="",
        title="No ISBN Book",
        author="Author",
        bisac_category=None,
    )

    batch_result = {
        "9780000000001": {
            "title": "Dewey Book",
            "author": "Author",
            "bisac_category": "FICTION / Literary",
            "bisac_main_category": "FICTION",
            "bisac_sub_category": "Literary",
            "thumbnail_url": "http://example.com/cover.jpg",
        }
    }

    with (
        patch(
            "book_lamp.services.book_lookup.lookup_books_batch",
            return_value=batch_result,
        ),
        patch(
            "book_lamp.services.book_lookup.lookup_book_by_isbn13", return_value=None
        ),
    ):
        result = _background_backfill_categories("test-job", user_id=1)

    assert "2 known, 1 unknown" in result
    books = storage.get_all_books()
    # Order of books might vary, let's verify each book correctly
    # Book 1 (Dewey) should be resolved to full category "FICTION / Literary"
    book1 = next(b for b in books if b["isbn13"] == "9780000000001")
    assert book1["bisac_category"] == "FICTION / Literary"
    assert book1["bisac_main_category"] == "FICTION"
    assert book1["bisac_sub_category"] == "Literary"

    # Book 2 (Existing) should keep its full category
    book2 = next(b for b in books if b["isbn13"] == "9780000000002")
    assert book2["bisac_category"] == "HISTORY / Europe / Great Britain"
    assert book2["bisac_main_category"] == "HISTORY"
    assert book2["bisac_sub_category"] == "Europe / Great Britain"

    # Book 3 (No ISBN) should fall back to Unknown
    book3 = next(b for b in books if b["isbn13"] == "")
    assert book3["bisac_category"] == "Unknown"
    assert book3["bisac_main_category"] == "Unknown"
    assert book3["bisac_sub_category"] is None


def test_fetch_missing_categories_route_runs_backfill(authenticated_client):
    from book_lamp.app import get_storage

    storage = get_storage()
    # Add a book with Dewey code to be reprocessed
    storage.add_book(
        isbn13="9780000000003",
        title="Route Book",
        author="Author",
        bisac_category="100.1",
    )

    batch_result = {
        "9780000000003": {
            "title": "Route Book",
            "author": "Author",
            "bisac_category": "SCIENCE / General",
            "bisac_main_category": "SCIENCE",
            "bisac_sub_category": "General",
            "thumbnail_url": "http://example.com/cover.jpg",
        }
    }

    with (
        patch(
            "book_lamp.services.book_lookup.lookup_books_batch",
            return_value=batch_result,
        ),
        patch(
            "book_lamp.services.book_lookup.lookup_book_by_isbn13", return_value=None
        ),
    ):
        resp = authenticated_client.get("/stats/backfill-categories")
        assert resp.status_code == 302
        job_id = resp.location.split("job_id=")[1]
        job = get_job_queue().get_job(job_id)
        assert job is not None
        assert job.wait_for_completion(timeout=5)
        assert job.status.value == "completed"

    books = storage.get_all_books()
    updated_book = next(b for b in books if b["isbn13"] == "9780000000003")
    assert updated_book["bisac_category"] == "SCIENCE / General"
    assert updated_book["bisac_main_category"] == "SCIENCE"
    assert updated_book["bisac_sub_category"] == "General"
