"""The title-and-author lookup that supplies an ISBN the reader does not have."""

from unittest.mock import patch


def _candidate(title, author, isbn13, **extra):
    return {
        "title": title,
        "author": author,
        "authors": [author],
        "isbn13": isbn13,
        **extra,
    }


def test_lookup_by_title_and_author_returns_editions_with_isbns(authenticated_client):
    """The endpoint answers with the editions, so the form can fill an ISBN in."""
    with (
        patch("book_lamp.services.book_lookup._open_library_title_search") as open_library,
        patch("book_lamp.services.book_lookup._google_books_title_search") as google,
    ):
        open_library.return_value = [_candidate("Emma", "Jane Austen", "9780141439600")]
        google.return_value = [
            # The same edition the other provider already gave: one answer, not two.
            _candidate("Emma", "Jane Austen", "9780141439600"),
            _candidate("Emma", "Jane Austen", "9780141439587"),
        ]

        response = authenticated_client.get("/api/books/matches?title=Emma&author=Jane%20Austen")

    assert response.status_code == 200
    isbns = [book["isbn13"] for book in response.get_json()["books"]]
    assert isbns == ["9780141439600", "9780141439587"]
    assert open_library.call_args[0] == ("Emma", "Jane Austen")


def test_a_title_is_required_because_an_author_search_is_a_different_question(authenticated_client):
    response = authenticated_client.get("/api/books/matches?author=Jane%20Austen")

    assert response.status_code == 400
    assert response.get_json()["error"] == "title query parameter is required"


def test_a_provider_failure_is_reported_so_the_form_can_ask_for_the_isbn(authenticated_client):
    """A failed search must not look like "no such book"."""
    with (
        patch(
            "book_lamp.services.book_lookup._open_library_title_search",
            side_effect=Exception("Open Library is down"),
        ),
        patch(
            "book_lamp.services.book_lookup._google_books_title_search",
            side_effect=Exception("Google Books is down"),
        ),
    ):
        response = authenticated_client.get("/api/books/matches?title=Emma&author=Jane%20Austen")

    assert response.status_code == 502
    assert response.get_json()["error"] == "Lookup failed"


def test_the_reader_not_the_provider_decides_which_edition(authenticated_client):
    """Titles the reader asked for are ranked ahead of looser matches."""
    with (
        patch("book_lamp.services.book_lookup._open_library_title_search") as open_library,
        patch("book_lamp.services.book_lookup._google_books_title_search", return_value=[]),
    ):
        open_library.return_value = [
            _candidate("Emma: A Modern Retelling", "Alexander McCall Smith", "9780804172745"),
            _candidate("Emma", "Jane Austen", "9780141439600"),
        ]

        response = authenticated_client.get("/api/books/matches?title=Emma&author=Jane%20Austen")

    assert [book["isbn13"] for book in response.get_json()["books"]] == [
        "9780141439600",
        "9780804172745",
    ]
