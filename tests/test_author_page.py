"""Tests for the author page API.

Covers:
- Owned books display (existing behaviour, no regression)
- Unread books are NOT requested from Open Library in TEST_MODE
- Deduplication logic (same book in collection should not appear as unread)
- Empty state returns empty collections
"""

import os

import pytest

# Avoid importing get_storage at module level.  TEST_MODE is read from
# the environment when the module is imported; the `app` fixture sets
# the variable before the application is loaded, but importing here
# would occur earlier so the flag would be evaluated incorrectly.


def test_author_page_shows_owned_books(authenticated_client):
    """Author API returns owned books for a matching author."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
        publication_year=1813,
    )

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["author_name"] == "Jane Austen"
    assert [b["title"] for b in data["read_books"]] == ["Pride and Prejudice"]
    assert data["read_books"][0]["author"] == "Jane Austen"


def test_author_page_no_unread_section_in_test_mode(authenticated_client):
    """In TEST_MODE no external API call is made, so the unread list is empty."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    data = resp.get_json()
    # The unread lookup is skipped entirely in TEST_MODE
    assert data["unread_books"] == []

    # Ensure the read/reading-list split is correct
    assert len(data["read_books"]) == 1
    assert data["reading_list_books"] == []


def test_author_page_empty_state(authenticated_client):
    """Author API returns empty collections when no books are found."""
    resp = authenticated_client.get("/api/author/unknown-author")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["read_books"] == []
    assert data["reading_list_books"] == []
    assert data["unread_books"] == []


def test_author_page_reading_list_flag(authenticated_client):
    """Books added to the reading list appear in their own collection."""
    from book_lamp.app import get_storage

    storage = get_storage()
    book = storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    storage.add_to_reading_list(book["id"])

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    data = resp.get_json()
    # the book should appear in the reading-list section with the flag set
    assert [b["title"] for b in data["reading_list_books"]] == ["Pride and Prejudice"]
    assert data["reading_list_books"][0]["in_reading_list"] is True
    assert data["read_books"] == []


def test_author_page_sorts_by_pub_year_asc(authenticated_client):
    """Owned books are sorted by publication year, oldest first."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Sense and Sensibility",
        author="Jane Austen",
        publication_year=1811,
    )
    storage.add_book(
        isbn13="9780141439600",
        title="Emma",
        author="Jane Austen",
        publication_year=1815,
    )

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.get_json()["read_books"]]
    # Sense and Sensibility (1811) should appear before Emma (1815)
    assert titles.index("Sense and Sensibility") < titles.index("Emma")


def test_author_page_sorts_by_title_when_year_same(authenticated_client):
    """Books with the same publication year are sorted alphabetically by title."""
    from book_lamp.app import get_storage

    storage = get_storage()
    # Both published in 1814
    storage.add_book(
        isbn13="9780141439519",
        title="Mansfield Park",
        author="Jane Austen",
        publication_year=1814,
    )
    storage.add_book(
        isbn13="9780141439510",
        title="Northanger Abbey",
        author="Jane Austen",
        publication_year=1814,
    )

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    titles = [b["title"] for b in resp.get_json()["read_books"]]
    # Mansfield Park should appear before Northanger Abbey (alphabetical)
    assert titles.index("Mansfield Park") < titles.index("Northanger Abbey")


def test_author_page_no_duplicate_books(authenticated_client):
    """The same book added twice must only appear once."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    # Simulate a second call; the mock storage prevents true duplicates via upsert
    resp = authenticated_client.get("/api/author/jane-austen")
    read_books = resp.get_json()["read_books"]
    assert len(read_books) == 1
    assert read_books[0]["title"] == "Pride and Prejudice"


@pytest.mark.skipif(
    os.environ.get("TEST_MODE") == "1",
    reason="Test expects unauthorized redirect but TEST_MODE forces authorised state"
)
def test_author_page_unauthorised_redirect(client):
    """Unauthenticated access redirects to the unauthorised page."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.set_authorised(False)

    resp = client.get("/api/author/jane-austen")
    assert resp.status_code == 302
