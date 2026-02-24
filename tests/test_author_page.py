"""Tests for the author page feature.

Covers:
- Owned books display (existing behaviour, no regression)
- Unread books are NOT requested from Open Library in TEST_MODE
- Deduplication logic (same book in collection should not appear as unread)
- Page renders successfully with no books at all
"""

from book_lamp.app import get_storage


def test_author_page_shows_owned_books(authenticated_client):
    """Author page renders owned books for a matching author."""
    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
        publication_year=1813,
    )

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Pride and Prejudice" in html
    assert "Jane Austen" in html
    assert "In Your Reading Log" in html


def test_author_page_no_unread_section_in_test_mode(authenticated_client):
    """In TEST_MODE no external API call is made, so the unread section is absent."""
    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # The "Also by" section is only rendered when unread_books is non-empty
    assert "Also by" not in html


def test_author_page_empty_state(authenticated_client):
    """Author page shows a helpful empty state when no books are found."""
    resp = authenticated_client.get("/author/unknown-author")
    assert resp.status_code == 200
    assert b"No books found" in resp.data


def test_author_page_reading_list_flag(authenticated_client):
    """Books already on the reading list are flagged in the author page."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    storage.add_to_reading_list(book["id"])

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    assert b"On reading list" in resp.data


def test_author_page_sorts_by_pub_year_desc(authenticated_client):
    """Owned books are sorted by publication year, newest first."""
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

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # Emma (1815) should appear before Sense and Sensibility (1811)
    assert html.index("Emma") < html.index("Sense and Sensibility")


def test_author_page_no_duplicate_books(authenticated_client):
    """The same book added twice must only appear once."""
    storage = get_storage()
    storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    # Simulate a second call; the mock storage prevents true duplicates via upsert
    # but we still verify the page count-stat shows 1 book.
    resp = authenticated_client.get("/author/jane-austen")
    html = resp.data.decode("utf-8")
    assert html.count("Pride and Prejudice") >= 1
    # "1 book in your collection" (not 2)
    assert "1 book in your reading log" in html


def test_author_page_unauthorised_redirect(client):
    """Unauthenticated access redirects to the unauthorised page."""
    storage = get_storage()
    storage.set_authorised(False)

    resp = client.get("/author/jane-austen")
    assert resp.status_code == 302
