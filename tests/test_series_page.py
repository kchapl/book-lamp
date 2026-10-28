"""Tests for the series page API.

A series is a name carried by each Book rather than a record of its own, so the
page is whatever Books share that name. These cover the order it lists them in,
the spellings it treats as one series, and the Books that must still appear: an
unread volume with no Reading at all is the reason to open the page.
"""

from urllib.parse import quote

from book_lamp.app import get_storage


def _add(title: str, series: str | None, year: int | None = None, isbn: str = "") -> dict:
    return get_storage().add_book(
        isbn13=isbn or f"9780000000{abs(hash(title)) % 1000:03d}",
        title=title,
        authors=["An Author"],
        publication_year=year,
        series=series,
    )


def test_lists_every_book_in_the_series_in_publication_order(authenticated_client):
    _add("Leviathan Wakes", "The Expanse", 2011)
    _add("Caliban's War", "The Expanse", 2012)
    _add("Abaddon's Gate", "The Expanse", 2013)
    _add("Dune", "Dune Chronicles", 1965)

    response = authenticated_client.get("/api/series/The%20Expanse")

    assert response.status_code == 200
    body = response.get_json()
    assert body["series_name"] == "The Expanse"
    assert [book["title"] for book in body["books"]] == [
        "Leviathan Wakes",
        "Caliban's War",
        "Abaddon's Gate",
    ]


def test_same_year_falls_back_to_title_order(authenticated_client):
    _add("Nemesis Games", "The Expanse", 2015)
    _add("Babylon's Ashes", "The Expanse", 2015)

    body = authenticated_client.get("/api/series/The%20Expanse").get_json()

    assert [book["title"] for book in body["books"]] == ["Babylon's Ashes", "Nemesis Games"]


def test_a_book_with_no_year_sorts_last(authenticated_client):
    _add("A Book With No Year", "The Expanse")
    _add("Leviathan Wakes", "The Expanse", 2011)

    body = authenticated_client.get("/api/series/The%20Expanse").get_json()

    assert [book["title"] for book in body["books"]] == ["Leviathan Wakes", "A Book With No Year"]


def test_case_and_whitespace_spellings_are_one_series(authenticated_client):
    _add("Leviathan Wakes", "The Expanse", 2011)
    _add("Caliban's War", "the  expanse", 2012)

    body = authenticated_client.get("/api/series/the%20expanse").get_json()

    assert len(body["books"]) == 2
    # The page is named after one spelling rather than whichever was stored first.
    assert body["series_name"] == "The Expanse"


def test_a_name_with_punctuation_resolves(authenticated_client):
    _add("The Final Empire", "Mistborn: Era 1", 2006)
    _add("The Well of Ascension", "Mistborn: Era 1", 2007)

    response = authenticated_client.get(f"/api/series/{quote('Mistborn: Era 1', safe='')}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["series_name"] == "Mistborn: Era 1"
    assert len(body["books"]) == 2


def test_books_without_a_reading_still_appear(authenticated_client):
    """An unread volume is what the reader came for, so it cannot be filtered out."""
    storage = get_storage()
    read = _add("Leviathan Wakes", "The Expanse", 2011)
    _add("Caliban's War", "The Expanse", 2012)
    storage.add_reading(read["id"], "Completed", "2026-01-01", "2026-01-20")

    books = authenticated_client.get("/api/series/The%20Expanse").get_json()["books"]

    assert [book["title"] for book in books] == ["Leviathan Wakes", "Caliban's War"]
    assert books[0]["latest_status"] == "Completed"
    assert books[1]["latest_status"] is None


def test_books_on_the_reading_list_are_marked(authenticated_client):
    queued = _add("Caliban's War", "The Expanse", 2012)
    get_storage().add_to_reading_list(queued["id"])

    books = authenticated_client.get("/api/series/The%20Expanse").get_json()["books"]

    assert books[0]["in_reading_list"] is True
    assert books[0]["latest_status"] is None


def test_a_series_no_book_carries_is_not_found(authenticated_client):
    _add("Leviathan Wakes", "The Expanse", 2011)

    response = authenticated_client.get("/api/series/The%20Silmarillion")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Series not found"


def test_a_book_without_a_series_is_not_reachable_by_one(authenticated_client):
    _add("Dune", None, 1965)

    response = authenticated_client.get("/api/series/Dune")

    assert response.status_code == 404
