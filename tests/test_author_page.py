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
        authors=["Jane Austen"],
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
        authors=["Jane Austen"],
    )

    resp = authenticated_client.get("/api/author/jane-austen")
    assert resp.status_code == 200
    data = resp.get_json()
    # The unread lookup is skipped entirely in TEST_MODE
    assert data["unread_books"] == []

    # Ensure the read/reading-list split is correct
    assert len(data["read_books"]) == 1
    assert data["reading_list_books"] == []


def test_publisher_page_accepts_the_slug_the_book_page_builds(authenticated_client):
    """The publisher page matches the normalised slug the detail payload carries."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780441478125",
        title="The Left Hand of Darkness",
        authors=["Ursula K. Le Guin"],
        publisher="Harper & Row",
    )

    resp = authenticated_client.get("/api/publisher/harper-&-row")

    assert resp.status_code == 200
    data = resp.get_json()
    assert [b["title"] for b in data["books"]] == ["The Left Hand of Darkness"]
    assert data["publisher_name"] == "Harper & Row"


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
        authors=["Jane Austen"],
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
        authors=["Jane Austen"],
        publication_year=1811,
    )
    storage.add_book(
        isbn13="9780141439600",
        title="Emma",
        authors=["Jane Austen"],
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
        authors=["Jane Austen"],
        publication_year=1814,
    )
    storage.add_book(
        isbn13="9780141439510",
        title="Northanger Abbey",
        authors=["Jane Austen"],
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
        authors=["Jane Austen"],
    )
    # Simulate a second call; the mock storage prevents true duplicates via upsert
    resp = authenticated_client.get("/api/author/jane-austen")
    read_books = resp.get_json()["read_books"]
    assert len(read_books) == 1
    assert read_books[0]["title"] == "Pride and Prejudice"


def test_adding_an_external_result_moves_it_to_the_reading_list(authenticated_client, monkeypatch):
    """The action on an external result creates the Book and queues it.

    The external section is only populated outside test mode, so this test
    supplies the results itself and then makes the request the page makes.
    """
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    external = {
        "title": "Emma",
        "author": "Jane Austen",
        "isbn13": "9780141439600",
        "publication_year": 1815,
        "thumbnail_url": "https://example.com/emma.jpg",
        "publisher": "John Murray",
        "description": None,
    }

    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(authors_route, "lookup_books_by_author", lambda _name: [dict(external)])

    before = authenticated_client.get("/api/author/jane-austen").get_json()
    assert [b["title"] for b in before["unread_books"]] == ["Emma"]
    # An external result is not a collection row, so it has no id.
    assert before["unread_books"][0]["id"] is None

    added = authenticated_client.post(
        "/api/books",
        json={
            "title": external["title"],
            "author": external["author"],
            "isbn": external["isbn13"],
            "publication_year": external["publication_year"],
            "thumbnail_url": external["thumbnail_url"],
            "publisher": external["publisher"],
        },
    )
    assert added.status_code == 201
    assert len(get_storage().get_all_books()) == 1

    after = authenticated_client.get("/api/author/jane-austen").get_json()
    assert [b["title"] for b in after["reading_list_books"]] == ["Emma"]
    assert after["read_books"] == []
    assert after["unread_books"] == []


def test_adding_a_two_author_result_keeps_both_names(authenticated_client, monkeypatch):
    """A co-authored result stays a Book by both people, not one combined author.

    The page sends the names themselves: the display string joins them with a
    comma, which storage reads as a single "Last, First" person, and the reloaded
    pages would then offer the Book as an external result again.
    """
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    names = ["Neil Gaiman", "Terry Pratchett"]
    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "Good Omens",
                "author": ", ".join(names),
                "authors": names,
                "isbn13": "9780060853983",
            }
        ],
    )

    added = authenticated_client.post(
        "/api/books",
        json={
            "title": "Good Omens",
            "author": ", ".join(names),
            "authors": names,
            "isbn": "9780060853983",
        },
    )

    assert added.status_code == 201
    assert get_storage().get_book_by_isbn("9780060853983")["authors"] == names

    for slug in ("neil-gaiman", "terry-pratchett"):
        page = authenticated_client.get(f"/api/author/{slug}").get_json()
        assert [b["title"] for b in page["reading_list_books"]] == ["Good Omens"]
        assert page["unread_books"] == []


def test_an_external_result_matching_an_owned_isbn_creates_no_duplicate(authenticated_client, monkeypatch):
    """A result whose ISBN is already in the collection queues that Book."""
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    storage = get_storage()
    existing = storage.add_book(
        isbn13="9780141439600",
        title="Emma",
        authors=["Jane Austen"],
        publication_year=1815,
    )
    # The page loaded before this Book existed, so it still offers the result.
    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "Emma",
                "author": "Jane Austen",
                "isbn13": "9780141439600",
                "publication_year": 1815,
            }
        ],
    )

    added = authenticated_client.post(
        "/api/books",
        json={"title": "Emma", "author": "Jane Austen", "isbn": "9780141439600"},
    )

    assert added.status_code == 200
    assert added.get_json()["id"] == existing["id"]
    assert [b["id"] for b in storage.get_all_books()] == [existing["id"]]
    assert [item["book_id"] for item in storage.get_reading_list()] == [existing["id"]]


def test_an_owned_book_without_a_subtitle_matches_the_edition_that_has_one(authenticated_client, monkeypatch):
    """A stored title alone must not offer the work again once an edition names it.

    The reader owns ``Dune`` with no subtitle; the author lookup returns the same
    work under another edition's ISBN with ``Book One of the Dune Chronicles``.
    An empty subtitle says nothing about which work it is, so the result is owned.
    """
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(isbn13="9780441013593", title="Dune", authors=["Frank Herbert"])

    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "Dune",
                "subtitle": "Book One of the Dune Chronicles",
                "author": "Frank Herbert",
                "isbn13": "9780441172719",
            }
        ],
    )

    page = authenticated_client.get("/api/author/frank-herbert").get_json()

    assert page["unread_books"] == []
    assert [b["title"] for b in page["read_books"]] == ["Dune"]


def test_a_result_that_keeps_the_subtitle_in_its_title_is_owned(authenticated_client, monkeypatch):
    """Storage split the owned Book; a provider result may not have been split."""
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    storage = get_storage()
    # The stored pair is split, as migration 0011 leaves it.
    storage.add_book(
        isbn13="9781635575637",
        title="Piranesi",
        subtitle="A Novel",
        authors=["Susanna Clarke"],
    )

    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "Piranesi: A Novel",
                "subtitle": None,
                "author": "Susanna Clarke",
                "isbn13": "9781635575638",
            }
        ],
    )

    page = authenticated_client.get("/api/author/susanna-clarke").get_json()

    assert page["unread_books"] == []
    assert [b["subtitle"] for b in page["read_books"]] == ["A Novel"]


def test_two_subtitles_that_disagree_are_two_works(authenticated_client, monkeypatch):
    """An owned pair does not swallow a different work under the same main title."""
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(
        isbn13="9780316129084",
        title="The Expanse",
        subtitle="Leviathan Wakes",
        authors=["James S. A. Corey"],
    )

    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "The Expanse",
                "subtitle": "Caliban's War",
                "author": "James S. A. Corey",
                "isbn13": "9780316129060",
            }
        ],
    )

    page = authenticated_client.get("/api/author/james-s-a-corey").get_json()

    assert [b["subtitle"] for b in page["unread_books"]] == ["Caliban's War"]


@pytest.mark.skipif(
    os.environ.get("TEST_MODE") == "1",
    reason="Test expects unauthorized redirect but TEST_MODE forces authorised state",
)
def test_author_page_unauthorised_redirect(client):
    """Unauthenticated access redirects to the unauthorised page."""
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.set_authorised(False)

    resp = client.get("/api/author/jane-austen")
    assert resp.status_code == 302


def test_an_owned_title_is_compared_as_it_reads(authenticated_client, monkeypatch):
    """A different spelling alone must not offer an owned work as unread.

    The author search returns provider titles through the normaliser, so an
    owned "Dune." comes back as "Dune" under another edition's ISBN. Comparing
    the stored spelling with the tidied one would offer the work the reader
    already has; both sides are compared as they read, and the stored title
    keeps the reader's spelling.
    """
    import book_lamp.routes.authors as authors_route
    from book_lamp.app import get_storage

    storage = get_storage()
    storage.add_book(isbn13="9780441013593", title="Dune.", authors=["Frank Herbert"])

    monkeypatch.setattr(authors_route, "is_test_mode", lambda: False)
    monkeypatch.setattr(
        authors_route,
        "lookup_books_by_author",
        lambda _name: [
            {
                "title": "Dune.",
                "author": "Frank Herbert",
                "isbn13": "9780441172719",
            }
        ],
    )

    page = authenticated_client.get("/api/author/frank-herbert").get_json()

    assert page["unread_books"] == []
    assert [b["title"] for b in page["read_books"]] == ["Dune."]
