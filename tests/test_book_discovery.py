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
    # Open Library's title search, then Google Books, then the author search.
    session = _Session(
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


def test_open_library_title_search_asks_one_free_text_search(monkeypatch):
    """One Open Library request, wide enough to hold every edition it describes.

    The free-text search already finds the edition that drops a leading article
    or carries a subtitle. Asking the exact title field as well spent a second
    request on editions the first answer had described, so the page is asked for
    wider instead.
    """
    answer = {
        "docs": [
            {
                "title": "A History of England in 100 Places",
                "author_name": ["John Julius Norwich"],
                "isbn": ["9781848546066"],
                "first_publish_year": 2011,
            },
            {
                "title": "A History of England in 100 Places: From Stonehenge to the Gherkin",
                "author_name": ["John Julius Norwich"],
                "isbn": ["9781848546073"],
                "first_publish_year": 2011,
            },
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

    calls = []

    class _SingleSearch:
        def get(self, url, params=None, **kwargs):
            params = params or {}
            calls.append((url, params))
            if url == lookup_module.OPEN_LIBRARY_SEARCH_API and "q" in params:
                return _Response(answer)
            return _Response({"docs": []})  # Google Books and the author search

    monkeypatch.setattr(lookup_module, "_get_session", lambda: _SingleSearch())

    results = lookup_module.search_books("A history of England in 100 places")

    isbns = [candidate["isbn13"] for candidate in results]
    assert "9781848546066" in isbns
    assert "9781848546073" in isbns
    assert "9781848025097" in isbns
    # A loose search returns near-misses; they are not answers to this question.
    assert "9780140430097" not in isbns
    # The exact title first, then the article-dropped and subtitled forms.
    assert isbns[0] == "9781848546066"

    # Open Library answers with one free-text request: no call scopes the title
    # field, and the page is wide enough to keep the editions ranked below it.
    assert all("title" not in params for _, params in calls)
    title_queries = [params for url, params in calls if url == lookup_module.OPEN_LIBRARY_SEARCH_API and "q" in params]
    assert len(title_queries) == 1
    assert title_queries[0]["limit"] == "20"


@pytest.mark.parametrize(
    "candidate_title, expected_rank",
    [
        ("A history of England in 100 places", 0),
        ("A HISTORY OF ENGLAND IN 100 PLACES", 0),
        ("History of England in 100 Places", 1),
        ("A History of England in 100 Places From Stonehenge To The Gherkin", 1),
        ("The History of Tom Jones", 4),
        ("The Picture of Dorian Gray", 4),
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
        # The same words, reordered: still the title the reader means.
        ("Mary Hail", 3),
        ("Dune", 4),
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


@pytest.mark.parametrize("query", ["Earthsea", "Earthsea Wizard", "A Wizard of Earthsea"])
def test_search_books_keeps_a_partial_title_query(monkeypatch, query):
    """A reader who remembers part of a title, in any order, finds the Book.

    The discovery box is labelled title-or-author, and a reader who types a word
    from the middle of a title is asking a question the search must answer.
    """
    monkeypatch.setattr(
        lookup_module,
        "_open_library_title_search",
        lambda *args, **kwargs: [_candidate("9780547773742", title="A Wizard of Earthsea")],
    )
    monkeypatch.setattr(lookup_module, "_google_books_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(lookup_module, "lookup_books_by_author", lambda *args, **kwargs: [])

    results = lookup_module.search_books(query)

    assert [candidate["isbn13"] for candidate in results] == ["9780547773742"]


@pytest.mark.parametrize("candidate_title", ["Ender's Game", "Ender’s Game"])
def test_search_books_folds_an_apostrophe_the_query_leaves_out(monkeypatch, candidate_title):
    """A reader who types "Enders Game" is asking for "Ender's Game".

    An apostrophe inside a word is punctuation, not a word break: folding one
    title to "ender s game" and the other to "enders game" would rank the answer
    as a near-miss and drop it before the route ever sees the ISBN.
    """
    monkeypatch.setattr(
        lookup_module,
        "_open_library_title_search",
        lambda *args, **kwargs: [_candidate("9780812550702", title=candidate_title)],
    )
    monkeypatch.setattr(lookup_module, "_google_books_title_search", lambda *args, **kwargs: [])
    monkeypatch.setattr(lookup_module, "lookup_books_by_author", lambda *args, **kwargs: [])

    results = lookup_module.search_books("Enders Game")

    assert [candidate["isbn13"] for candidate in results] == ["9780812550702"]


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
