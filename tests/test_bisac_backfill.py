from unittest.mock import patch

import pytest

from book_lamp.services.book_lookup import enhance_books_batch
from book_lamp.services.mock_storage import MockStorage


@pytest.fixture
def mock_storage():
    return MockStorage()


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

    # Mock lookup result returning a DIFFERENT BISAC (unlikely but to test prioritization)
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
