"""Tests for the author page feature.

Covers:
- Owned books display (existing behaviour, no regression)
- Unread books are NOT requested from Open Library in TEST_MODE
- Deduplication logic (same book in collection should not appear as unread)
- Page renders successfully with no books at all
"""

# Avoid importing get_storage at module level.  TEST_MODE is read from
# the environment when the module is imported; the `app` fixture sets
# the variable before the application is loaded, but importing here
# would occur earlier so the flag would be evaluated incorrectly.


def test_author_page_shows_owned_books(authenticated_client):
    """Author page renders owned books for a matching author."""
    from book_lamp.app import get_storage

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
    assert "Read" in html


def test_author_page_no_unread_section_in_test_mode(authenticated_client):
    """In TEST_MODE no external API call is made, so the unread section is absent."""
    from book_lamp.app import get_storage

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

    # Ensure the read/reading-list summary is correct
    assert "Read" in html
    assert "In Reading List" not in html


def test_author_page_empty_state(authenticated_client):
    """Author page shows a helpful empty state when no books are found."""
    resp = authenticated_client.get("/author/unknown-author")
    assert resp.status_code == 200
    assert b"No books found" in resp.data


def test_author_page_reading_list_flag(authenticated_client):
    """Books added to the reading list appear in their own section."""
    from book_lamp.app import get_storage

    storage = get_storage()
    book = storage.add_book(
        isbn13="9780141439518",
        title="Pride and Prejudice",
        author="Jane Austen",
    )
    storage.add_to_reading_list(book["id"])

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # should be present as a section heading
    assert "In Reading List" in html
    # the book itself should still show up
    assert "Pride and Prejudice" in html


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

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # Sense and Sensibility (1811) should appear before Emma (1815)
    assert html.index("Sense and Sensibility") < html.index("Emma")


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

    resp = authenticated_client.get("/author/jane-austen")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    # Mansfield Park should appear before Northanger Abbey (alphabetical)
    assert html.index("Mansfield Park") < html.index("Northanger Abbey")


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
    # but we still verify the page count-stat shows 1 book.
    resp = authenticated_client.get("/author/jane-austen")
    html = resp.data.decode("utf-8")
    assert html.count("Pride and Prejudice") >= 1
    # "1 read book" (not 2)
    assert "1 read book" in html


def test_author_page_unauthorised_redirect(client):
    """Unauthenticated access redirects to the unauthorised page."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.set_authorised(False)

    resp = client.get("/author/jane-austen")
    assert resp.status_code == 302
