"""The titles metadata providers give are tidied where they are parsed.

The repair is mechanical: whitespace, escaped entities, a full stop that only
ends the title, and casing when the provider supplied none of its own. No word
is ever added, and a title the reader typed is not touched.
"""

import pytest

import book_lamp.services.book_lookup as lookup_module
from book_lamp.utils.books import normalise_provider_title


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return self._payload


class _Session:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def get(self, *args: object, **kwargs: object) -> _Response:
        return _Response(self._payload)


def _session_returning(payload: dict) -> _Session:
    return _Session(payload)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Runs of whitespace, and the ends of the string.
        ("  The  last english king. ", "The Last English King"),
        # All caps, with a trailing full stop that only terminates the title.
        ("SCHEME FOR FULL EMPLOYMENT.", "Scheme for Full Employment"),
        # Lower case; small words stay lower, no leading article is invented.
        ("king and the christmas tree", "King and the Christmas Tree"),
        # Already cased mixed: the provider's choice is kept.
        ("The Lord of the Rings", "The Lord of the Rings"),
        # Tokens that look acronym-like keep their capitals.
        ("U.S.A.", "U.S.A."),
        ("iPhone", "iPhone"),
        ("1984", "1984"),
        ("Spider-Man", "Spider-Man"),
        # Escaped entities are decoded.
        ("A History of England &amp; Wales.", "A History of England & Wales"),
        # A subtitle after a break is part of the same title, and is cased too.
        ("dune: the sequel", "Dune: The Sequel"),
        ("the spy — a novel", "The Spy — A Novel"),
        # A part a bracket or a quote opens is a part of its own, so the word
        # inside it is capitalised even when it is a small word.
        ("the spy (a novel)", "The Spy (A Novel)"),
        ("THE MAN (OF THE YEAR)", "The Man (Of the Year)"),
        ('the spy "a novel"', 'The Spy "A Novel"'),
        # Terminal punctuation other than a full stop stands.
        ("The Last King!", "The Last King!"),
        # An ellipsis is not a full stop that only terminates; title case still
        # capitalises the last word.
        ("Wait for it...", "Wait for It..."),
        # Initials in a shouted title survive as initials.
        ("A GUIDE FOR THE BBC", "A Guide for the BBC"),
        # A shouted title is read as words: two-letter pronouns and particles
        # are not initials, so they are title-cased like everything else.
        ("AN UNEXPECTED JOURNEY", "An Unexpected Journey"),
        ("IT ENDS WITH US", "It Ends with Us"),
        ("WHERE WE ARE GOING", "Where We Are Going"),
        # Initials and numerals a title carries stay as the provider wrote them.
        ("THE CIA FILES", "The CIA Files"),
        ("WORLD WAR III", "World War III"),
        # A full stop that belongs to an abbreviation is part of the word.
        ("Martin Luther King Jr.", "Martin Luther King Jr."),
        ("Acme Inc.", "Acme Inc."),
        ("Collected Poems Vol.", "Collected Poems Vol."),
        # A title that is only a dotted abbreviation keeps its dot: "U.S." is
        # not a sentence that happens to end in a full stop.
        ("U.S.", "U.S."),
        ("U.K.", "U.K."),
        ("A History of the U.S.", "A History of the U.S."),
    ],
)
def test_a_provider_title_is_tidied_without_changing_what_it_names(raw, expected):
    assert normalise_provider_title(raw) == expected


def test_a_missing_title_stays_missing():
    assert normalise_provider_title(None) is None
    assert normalise_provider_title("   ") == ""


def test_the_open_library_isbn_parser_keeps_a_separate_subtitle():
    parsed = lookup_module._parse_open_library_data(
        {
            "title": "The Spy and the Traitor",
            "subtitle": "The Greatest Espionage Story of the Cold War",
            "authors": [{"name": "Ben Macintyre"}],
        }
    )

    assert parsed["title"] == "The Spy and the Traitor"
    assert parsed["subtitle"] == "The Greatest Espionage Story of the Cold War"


def test_the_google_books_parser_keeps_a_separate_subtitle():
    parsed = lookup_module._parse_google_books_item(
        {
            "volumeInfo": {
                "title": "The Spy and the Traitor",
                "subtitle": "The Greatest Espionage Story of the Cold War",
                "authors": ["Ben Macintyre"],
            }
        }
    )

    assert parsed["title"] == "The Spy and the Traitor"
    assert parsed["subtitle"] == "The Greatest Espionage Story of the Cold War"


def test_the_open_library_title_search_carries_its_subtitle(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {
                "docs": [
                    {
                        "title": "The Spy and the Traitor",
                        "subtitle": "The Greatest Espionage Story of the Cold War",
                        "isbn": ["9780241181346"],
                        "author_name": ["Ben Macintyre"],
                    }
                ]
            }
        ),
    )

    found = lookup_module._open_library_title_search("The Spy and the Traitor", None)

    assert found[0]["subtitle"] == "The Greatest Espionage Story of the Cold War"


def test_the_author_search_carries_its_subtitle(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {
                "docs": [
                    {
                        "title": "The Spy and the Traitor",
                        "subtitle": "The Greatest Espionage Story of the Cold War",
                        "author_name": ["Ben Macintyre"],
                        "isbn": [],
                    }
                ]
            }
        ),
    )

    found = lookup_module.lookup_books_by_author("Ben Macintyre")

    assert found[0]["subtitle"] == "The Greatest Espionage Story of the Cold War"


def test_the_open_library_isbn_parser_normalises_its_title():
    parsed = lookup_module._parse_open_library_data(
        {"title": "SCHEME FOR FULL EMPLOYMENT.", "authors": [{"name": "A. Author"}]}
    )

    assert parsed["title"] == "Scheme for Full Employment"


def test_the_open_library_cover_search_normalises_its_title(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {
                "docs": [
                    {
                        "title": "  the  last english king. ",
                        "cover_i": 42,
                        "author_name": ["A. Author"],
                    }
                ]
            }
        ),
    )

    found = lookup_module._lookup_open_library_search("the last english king")

    assert found["title"] == "The Last English King"


def test_the_open_library_title_search_normalises_its_title(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {
                "docs": [
                    {
                        "title": "king and the christmas tree",
                        "isbn": ["9780306406157"],
                        "author_name": ["A. Author"],
                    }
                ]
            }
        ),
    )

    found = lookup_module._open_library_title_search("king and the christmas tree", None)

    assert found[0]["title"] == "King and the Christmas Tree"


def test_the_author_search_normalises_each_title(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {"docs": [{"title": "THE SPY IN THE ARCHIVE.", "author_name": ["A. Author"], "isbn": []}]}
        ),
    )

    found = lookup_module.lookup_books_by_author("A. Author")

    assert [book["title"] for book in found] == ["The Spy in the Archive"]


def test_the_google_books_parser_normalises_its_title():
    parsed = lookup_module._parse_google_books_item(
        {"volumeInfo": {"title": "  the  last english king. ", "authors": ["A. Author"]}}
    )

    assert parsed["title"] == "The Last English King"


def test_the_itunes_cover_search_normalises_its_title(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning(
            {
                "results": [
                    {
                        "trackName": "SCHEME FOR FULL EMPLOYMENT.",
                        "artistName": "A. Author",
                        "artworkUrl100": "http://example.com/100x100bb.jpg",
                    }
                ]
            }
        ),
    )

    found = lookup_module._lookup_itunes_search("scheme for full employment")

    assert found["title"] == "Scheme for Full Employment"


def test_the_itunes_isbn_parser_normalises_its_title(monkeypatch):
    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _session_returning({"results": [{"trackName": "THE SPY IN THE ARCHIVE.", "artistName": "A. Author"}]}),
    )

    parsed = lookup_module._lookup_itunes("9780306406157")

    assert parsed["title"] == "The Spy in the Archive"


def test_a_title_the_reader_typed_is_stored_as_they_typed_it(authenticated_client):
    """Normalisation belongs to provider parsing, not to storage."""
    response = authenticated_client.post(
        "/api/books",
        json={
            "isbn": "9780306406157",
            "title": "the last english king.",
            "author": "A. Author",
        },
    )

    assert response.status_code == 201
    assert response.get_json()["title"] == "the last english king."
