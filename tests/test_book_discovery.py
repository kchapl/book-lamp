"""Finding a Book the reader does not own yet, by title or author.

External providers are stubbed throughout: the suite never calls them.
"""

import pytest
import requests

import book_lamp.services.book_lookup as lookup_module


def _candidate(isbn: str, title: str = "Dune", **extra):
    return {"isbn13": isbn, "title": title, "author": "Frank Herbert", **extra}


def test_search_books_merges_providers_and_dedupes_on_isbn(monkeypatch):
    """One edition described by two providers is one candidate."""
    monkeypatch.setattr(
        lookup_module,
        "_open_library_title_search",
        lambda *args, **kwargs: [_candidate("111"), _candidate("222")],
    )
    monkeypatch.setattr(
        lookup_module,
        "_google_books_title_search",
        lambda *args, **kwargs: [_candidate("222"), _candidate("333")],
    )
    monkeypatch.setattr(
        lookup_module,
        "lookup_books_by_author",
        lambda *args, **kwargs: [_candidate("444", title="Dune Messiah")],
    )

    results = lookup_module.search_books("Dune")

    assert [book["isbn13"] for book in results] == ["111", "222", "333", "444"]


def test_search_books_raises_when_every_provider_fails(monkeypatch):
    """A failed search is not the same answer as no matches."""

    def unavailable(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(lookup_module, "_open_library_title_search", unavailable)
    monkeypatch.setattr(lookup_module, "_google_books_title_search", unavailable)
    monkeypatch.setattr(lookup_module, "lookup_books_by_author", unavailable)

    with pytest.raises(lookup_module.BookSearchUnavailable):
        lookup_module.search_books("Dune")


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self) -> dict:
        return self._payload


class _Session:
    def __init__(self, *responses: _Response) -> None:
        self._responses = list(responses)

    def get(self, *args: object, **kwargs: object) -> _Response:
        return self._responses.pop(0)


def test_search_books_reports_an_outage_when_providers_return_http_errors(monkeypatch):
    """A 429 or 503 JSON body is a failed provider, not an empty result."""
    session = _Session(
        _Response({"docs": []}),
        _Response({"error": "rate limited"}, status=429),
        _Response({"error": {"code": 429}}, status=429),
        _Response({"error": "rate limited"}, status=503),
    )
    monkeypatch.setattr(lookup_module, "_get_session", lambda: session)

    with pytest.raises(lookup_module.BookSearchUnavailable):
        lookup_module.search_books("Dune")


def test_search_books_returns_nothing_when_a_provider_answers_empty(monkeypatch):
    """At least one provider was reachable, so an empty answer means no matches."""
    monkeypatch.setattr(lookup_module, "_open_library_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        lookup_module,
        "_google_books_title_search",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(
        lookup_module,
        "lookup_books_by_author",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
    )

    assert lookup_module.search_books("A Book That Does Not Exist") == []


def test_discover_route_returns_candidates(authenticated_client, monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "search_books",
        lambda query: [_candidate("111", "Dune", publication_year=1965)],
    )

    resp = authenticated_client.get("/api/books/discover?q=Dune")

    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["query"] == "Dune"
    assert [b["title"] for b in payload["books"]] == ["Dune"]
    assert payload["books"][0]["isbn13"] == "111"


def test_discover_route_omits_books_the_reader_already_has(authenticated_client, monkeypatch):
    from book_lamp.app import get_storage

    get_storage().add_book(isbn13="111", title="Dune", authors=["Frank Herbert"])
    monkeypatch.setattr(
        lookup_module,
        "search_books",
        lambda query: [_candidate("111"), _candidate("222", "Dune Messiah")],
    )

    payload = authenticated_client.get("/api/books/discover?q=Dune").get_json()

    assert [b["isbn13"] for b in payload["books"]] == ["222"]


def test_discover_route_says_when_nothing_matched(authenticated_client, monkeypatch):
    monkeypatch.setattr(lookup_module, "search_books", lambda query: [])

    resp = authenticated_client.get("/api/books/discover?q=nothing-matches")

    assert resp.status_code == 200
    assert resp.get_json()["books"] == []


def test_discover_route_reports_a_provider_failure(authenticated_client, monkeypatch):
    def unavailable(query):
        raise lookup_module.BookSearchUnavailable("down")

    monkeypatch.setattr(lookup_module, "search_books", unavailable)

    resp = authenticated_client.get("/api/books/discover?q=Dune")

    assert resp.status_code == 502
    assert "unavailable" in resp.get_json()["error"].lower()


def test_discover_route_requires_a_query(authenticated_client):
    resp = authenticated_client.get("/api/books/discover")

    assert resp.status_code == 400
