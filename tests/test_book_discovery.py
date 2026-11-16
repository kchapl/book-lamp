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
    # Open Library is asked twice — the exact title field, then free text — and
    # the provider has only failed when both of its searches did.
    session = _Session(
        _Response({"error": "rate limited"}, status=429),
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


def test_open_library_title_search_merges_structured_and_free_text(monkeypatch):
    """A structured lookup with results must not suppress the free-text one.

    Open Library's `title` field is exact: it matches the edition that keeps the
    leading article and misses the one that drops it. The free-text search finds
    that edition, so both answers belong to the reader.
    """
    structured = {
        "docs": [
            {
                "title": "A History of England in 100 Places: From Stonehenge to the Gherkin",
                "author_name": ["John Julius Norwich"],
                "isbn": ["9781848546073"],
                "first_publish_year": 2011,
            },
            {
                "title": "A History of England in 100 Places",
                "author_name": ["John Julius Norwich"],
                "isbn": ["9781848546066"],
                "first_publish_year": 2011,
            },
        ]
    }
    free_text = {
        "docs": [
            {
                "title": "History of England in 100 Places",
                "author_name": ["Philip Wilkinson"],
                "isbn": ["9781848025097"],
                "first_publish_year": 2018,
                "publisher": ["Historic England Publishing"],
            },
            {
                "title": "The History of Tom Jones",
                "author_name": ["Henry Fielding"],
                "isbn": ["9780140430097"],
            },
        ]
    }

    class _TwoQueries:
        def get(self, url, params=None, **kwargs):
            params = params or {}
            if "title" in params:
                return _Response(structured)
            if "q" in params:
                return _Response(free_text)
            return _Response({"docs": []})  # the author search

    monkeypatch.setattr(lookup_module, "_get_session", lambda: _TwoQueries())

    results = lookup_module.search_books("A history of England in 100 places")

    isbns = [candidate["isbn13"] for candidate in results]
    assert "9781848546066" in isbns
    assert "9781848546073" in isbns
    assert "9781848025097" in isbns
    # A loose search returns near-misses; they are not answers to this question.
    assert "9780140430097" not in isbns
    # The exact title first, then the article-dropped and subtitled forms.
    assert isbns[0] == "9781848546066"


@pytest.mark.parametrize(
    "candidate_title, expected_rank",
    [
        ("A history of England in 100 places", 0),
        ("A HISTORY OF ENGLAND IN 100 PLACES", 0),
        ("History of England in 100 Places", 1),
        ("A History of England in 100 Places From Stonehenge To The Gherkin", 1),
        ("The History of Tom Jones", 3),
        ("The Picture of Dorian Gray", 3),
    ],
)
def test_title_match_rank_folds_articles_punctuation_and_subtitles(candidate_title, expected_rank):
    rank = lookup_module._title_match_rank(
        {"title": candidate_title, "authors": ["Philip Wilkinson"]},
        "A history of England in 100 places",
        "",
    )

    assert rank[0] == expected_rank


@pytest.mark.parametrize(
    "candidate_title, expected_rank",
    [
        ("Hail Mary", 0),
        ("Hail Mary: The Story of Apollo", 1),
        # The query is the part of the title the reader remembers, and it need
        # not be the part the title starts with.
        ("Project Hail Mary", 2),
        ("Mary Hail", 3),
    ],
)
def test_title_match_rank_places_a_query_inside_a_longer_title(candidate_title, expected_rank):
    rank = lookup_module._title_match_rank(
        {"title": candidate_title, "authors": ["Andy Weir"]},
        "Hail Mary",
        "",
    )

    assert rank[0] == expected_rank


def test_search_books_keeps_a_title_that_contains_the_query(monkeypatch):
    """Searching "Hail Mary" must not report nothing because of "Project"."""
    monkeypatch.setattr(
        lookup_module,
        "_open_library_title_search",
        lambda *args, **kwargs: [_candidate("9780593135204", title="Project Hail Mary")],
    )
    monkeypatch.setattr(lookup_module, "_google_books_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(lookup_module, "lookup_books_by_author", lambda *args, **kwargs: [])

    results = lookup_module.search_books("Hail Mary")

    assert [candidate["title"] for candidate in results] == ["Project Hail Mary"]


def test_search_books_keeps_the_providers_that_answer(monkeypatch):
    """One failing provider leaves the others to answer."""

    def down(*args, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(lookup_module, "_open_library_title_search", down)
    monkeypatch.setattr(lookup_module, "_google_books_title_search", lambda *args, **kwargs: [_candidate("111")])
    monkeypatch.setattr(lookup_module, "lookup_books_by_author", down)

    assert [candidate["isbn13"] for candidate in lookup_module.search_books("Dune")] == ["111"]


def test_search_books_keeps_an_author_answer_that_does_not_match_the_title(monkeypatch):
    """A query naming an author is answered by that author's Books."""
    monkeypatch.setattr(lookup_module, "_open_library_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(lookup_module, "_google_books_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        lookup_module,
        "lookup_books_by_author",
        lambda *args, **kwargs: [_candidate("555", title="The Left Hand of Darkness")],
    )

    results = lookup_module.search_books("Ursula K. Le Guin")

    assert [candidate["isbn13"] for candidate in results] == ["555"]
