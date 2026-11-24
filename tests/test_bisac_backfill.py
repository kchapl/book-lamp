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
        authors=["Test Author"],
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


def test_a_combined_provider_title_is_split_before_it_is_stored():
    """The batch parser leaves a title whole; enhancement reads it as parts.

    Open Library's parsed title is not split, so a combined ``Piranesi: A
    Novel`` would otherwise be written as the title with no subtitle.
    """
    books = [{"isbn13": "9780000000006", "title": "Placeholder", "authors": ["An Author"]}]

    with patch(
        "book_lamp.services.book_lookup.lookup_books_batch",
        return_value={
            "9780000000006": {
                "title": "Piranesi: A Novel",
                "thumbnail_url": "http://example.com/cover.jpg",
            }
        },
    ):
        enhance_books_batch(books, force_refresh=True)

    assert (books[0]["title"], books[0]["subtitle"]) == ("Piranesi", "A Novel")


def test_the_metadata_backfill_keeps_the_stored_name(monkeypatch):
    """Refreshing metadata must not rename a Book the reader corrected.

    The reader kept ``Foo Bar: Baz`` whole by clearing its subtitle, and the
    provider knows a different name and subtitle. The backfill has to leave the
    stored pair alone while it refreshes everything else.
    """
    from book_lamp.routes.books import _background_fetch_missing_data
    from book_lamp.services.storage_factory import get_storage

    storage = get_storage()
    book = storage.add_book(isbn13="9780000000005", title="Foo Bar: Baz", authors=["An Author"])

    monkeypatch.setattr(
        "book_lamp.services.book_lookup.lookup_books_batch",
        lambda isbns, force_refresh=False: {
            "9780000000005": {
                "title": "Piranesi: A Novel",
                "subtitle": "A Novel",
                "bisac_category": "FICTION / General",
                "bisac_main_category": "FICTION",
                "bisac_sub_category": "General",
                "thumbnail_url": "http://example.com/cover.jpg",
            }
        },
    )

    _background_fetch_missing_data("job-1", user_id=1)

    stored = storage.get_book_by_id(book["id"])
    assert (stored["title"], stored["subtitle"]) == ("Foo Bar: Baz", None)
    assert stored["bisac_category"] == "FICTION / General"


def test_the_metadata_backfill_does_not_undo_a_split_that_lands_mid_run(monkeypatch):
    """A split that lands while providers run must survive the write back."""
    from book_lamp.routes.books import _background_fetch_missing_data
    from book_lamp.services.storage_factory import get_storage

    storage = get_storage()
    isbn = "9780000000008"
    book = storage.add_book(isbn13=isbn, title="Piranesi: A Novel", authors=["An Author"])

    def lookup(isbns, force_refresh=False):
        # The deferred subtitle backfill splits the row while the provider is
        # being asked, after the metadata refresh took its snapshot.
        storage.update_book(
            book_id=book["id"],
            isbn13=isbn,
            title="Piranesi",
            subtitle="A Novel",
            authors=["An Author"],
        )
        return {
            isbn: {
                "title": "Piranesi",
                "subtitle": "A Novel",
                "bisac_category": "FICTION / General",
                "bisac_main_category": "FICTION",
                "bisac_sub_category": "General",
                "thumbnail_url": "http://example.com/cover.jpg",
            }
        }

    monkeypatch.setattr("book_lamp.services.book_lookup.lookup_books_batch", lookup)

    _background_fetch_missing_data("job-split", user_id=1)

    stored = storage.get_book_by_id(book["id"])
    assert (stored["title"], stored["subtitle"]) == ("Piranesi", "A Novel")


def test_the_backfill_does_not_count_a_name_it_was_told_to_keep():
    """A Book whose only provider data is its name was not updated.

    The metadata backfill skips the stored title and subtitle, so a provider
    answer that changes nothing else must not be reported as an update.
    """
    books = [
        {
            "isbn13": "9780000000007",
            "title": "Foo Bar: Baz",
            "subtitle": None,
            "authors": ["An Author"],
            "publication_year": 2020,
            "publisher": "A Publisher",
            "description": "A description",
            "bisac_category": "FICTION / General",
            "thumbnail_url": "http://example.com/cover.jpg",
            "cover_url": "http://example.com/cover.jpg",
        }
    ]

    with (
        patch(
            "book_lamp.services.book_lookup.lookup_books_batch",
            return_value={
                "9780000000007": {
                    "title": "Piranesi: A Novel",
                    "subtitle": "A Novel",
                }
            },
        ),
        patch("book_lamp.services.book_lookup.lookup_book_by_isbn13", return_value=None),
    ):
        updated_count = enhance_books_batch(
            books,
            force_refresh=True,
            skip_fields=("title", "subtitle"),
        )

    assert updated_count == 0
    assert (books[0]["title"], books[0]["subtitle"]) == ("Foo Bar: Baz", None)


def test_enhance_books_adds_a_provider_subject_without_dropping_the_stored_one(mock_storage):
    """#407: a refresh adds the subjects it finds and never drops a stored one."""
    # Setup: A book already has a BISAC category
    book = mock_storage.add_book(
        isbn13="9780000000002",
        title="BISAC Book",
        authors=["Author"],
        bisac_category="HISTORY / Ancient / General",
        bisac_main_category="HISTORY",
        bisac_sub_category="Ancient / General",
    )

    books = [book]

    # A provider answer names a different category as a second subject.
    mock_lookup_result = {
        "9780000000002": {
            "title": "BISAC Book",
            "author": "Author",
            "bisac_category": "NEW CATEGORY / Sub",
            "bisac_main_category": "NEW CATEGORY",
            "bisac_sub_category": "Sub",
            "subjects": [
                {"category": "NEW CATEGORY / Sub", "main": "NEW CATEGORY", "sub": "Sub"},
            ],
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

    # The stored subject stays first, and the provider's joins it. The legacy
    # triple names the first entry, for the surfaces that predate the list.
    updated_book = mock_storage.get_book_by_id(book["id"])
    assert [subject["main"] for subject in updated_book["subjects"]] == ["HISTORY", "NEW CATEGORY"]
    assert updated_book["bisac_category"] == "HISTORY / Ancient / General"
    assert updated_book["bisac_main_category"] == "HISTORY"


def test_is_dewey_logic_in_storage(mock_storage):
    # This specifically tests the logic in bulk_import/update_book

    # 1. Dewey to BISAC - SHOULD UPDATE
    mock_storage.books = []
    book1 = mock_storage.add_book(isbn13="1", title="B1", authors=["A1"], bisac_category="123.45")
    mock_storage.update_book(book_id=book1["id"], isbn13="1", title="B1", authors=["A1"], bisac_category="BISAC")
    assert mock_storage.books[0]["bisac_category"] == "BISAC"

    # 2. BISAC to Dewey - SHOULD PRESERVE BISAC
    mock_storage.books = []
    book2 = mock_storage.add_book(isbn13="2", title="B2", authors=["A2"], bisac_category="BISAC")
    mock_storage.update_book(book_id=book2["id"], isbn13="2", title="B2", authors=["A2"], bisac_category="999.9")
    assert mock_storage.books[0]["bisac_category"] == "BISAC"

    # 3. BISAC to BISAC - SHOULD UPDATE (force refresh scenario)
    mock_storage.books = []
    book3 = mock_storage.add_book(isbn13="3", title="B3", authors=["A3"], bisac_category="BISAC OLD")
    mock_storage.update_book(
        book_id=book3["id"],
        isbn13="3",
        title="B3",
        authors=["A3"],
        bisac_category="BISAC NEW",
    )
    assert mock_storage.books[0]["bisac_category"] == "BISAC NEW"
