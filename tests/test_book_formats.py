"""A Book's binding is recorded by the reader, kept across lookups, and backfilled."""

from book_lamp.app import get_storage
from book_lamp.services.format_backfill import (
    ITUNES,
    OPEN_LIBRARY,
    BindingAnswer,
    backfill_missing_formats,
    look_up_binding,
    report_formats,
)


def _edit(client, book, **payload):
    body = {"title": book["title"], "authors": book["authors"], "isbn13": book["isbn13"], **payload}
    return client.post(f"/api/books/{book['id']}/edit", json=body)


def test_the_reader_can_record_and_clear_a_format(authenticated_client):
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780000002013",
        title="A Book",
        authors=["An Author"],
    )

    response = _edit(authenticated_client, book, physical_format="Paperback")
    assert response.status_code == 200
    assert storage.get_book_by_id(book["id"])["physical_format"] == "Paperback"

    # Choosing "Not recorded" is a clear, not an omitted field.
    response = _edit(authenticated_client, book, physical_format="")
    assert response.status_code == 200
    assert storage.get_book_by_id(book["id"])["physical_format"] is None

    response = _edit(authenticated_client, book, physical_format="Hardback")
    assert response.status_code == 200

    # An edit that says nothing about the format leaves the recorded one alone.
    response = _edit(authenticated_client, book, publisher="A Publisher")
    assert response.status_code == 200
    assert storage.get_book_by_id(book["id"])["physical_format"] == "Hardback"


def test_a_later_lookup_without_a_binding_does_not_erase_the_choice():
    storage = get_storage()
    storage.add_book(
        isbn13="9780000002020",
        title="A Book",
        authors=["An Author"],
        physical_format="Paperback",
    )

    storage.upsert_book(
        isbn13="9780000002020",
        title="A Book",
        authors=["An Author"],
    )

    assert storage.get_book_by_isbn("9780000002020")["physical_format"] == "Paperback"


def test_the_backfill_fills_only_a_gap():
    books = [
        {"id": 1, "isbn13": "9780000002037", "physical_format": "Paperback"},
        {"id": 2, "isbn13": "9780000002044", "physical_format": None},
        {"id": 3, "isbn13": "9780000002051", "physical_format": "en"},
        {"id": 4, "isbn13": "", "physical_format": None},
    ]
    writes = []

    def lookup(isbn):
        return {
            "9780000002037": BindingAnswer("Hardback", OPEN_LIBRARY),
            "9780000002044": BindingAnswer("Perfect Paperback", OPEN_LIBRARY),
            "9780000002051": BindingAnswer("BOOK", OPEN_LIBRARY),
        }.get(isbn)

    counts = backfill_missing_formats(
        books,
        lookup=lookup,
        write=lambda book, isbn, binding: writes.append((book["id"], isbn, binding)) or True,
    )

    assert counts == {"updated": 1, "skipped": 3, "failed": 0}
    # A stored binding is never replaced, and a media type is not a binding.
    assert writes == [(2, "9780000002044", "Perfect Paperback")]


def test_the_backfill_treats_a_failed_provider_as_no_answer():
    books = [{"id": 1, "isbn13": "9780000002068", "physical_format": None}]

    def lookup(isbn):
        raise RuntimeError("provider is down")

    counts = backfill_missing_formats(books, lookup=lookup, write=lambda *args: True)

    assert counts == {"updated": 0, "skipped": 0, "failed": 1}


def test_the_report_counts_what_a_run_would_gain_and_where_it_came_from():
    books = [
        {"id": 1, "isbn13": "9780000002075", "physical_format": "Paperback"},
        {"id": 2, "isbn13": "9780000002082", "physical_format": None},
        {"id": 3, "isbn13": "9780000002099", "physical_format": "BOOK"},
        {"id": 4, "isbn13": "9780000002105", "physical_format": None},
    ]

    counts = report_formats(
        books,
        lookup=lambda isbn: {
            "9780000002082": BindingAnswer("Hardback", OPEN_LIBRARY),
            "9780000002099": BindingAnswer("Ebook", ITUNES),
        }.get(isbn),
    )

    assert counts == {
        "with_binding": 1,
        "gained": 2,
        "left_empty": 1,
        "failed": 0,
        OPEN_LIBRARY: 1,
        ITUNES: 1,
    }


def test_open_library_is_asked_first_and_a_media_type_is_not_an_answer(monkeypatch):
    from book_lamp.services import book_lookup

    monkeypatch.setattr(book_lookup, "_lookup_open_library", lambda isbn: {"physical_format": "BOOK"})
    monkeypatch.setattr(book_lookup, "_lookup_itunes", lambda isbn: {"physical_format": "Ebook"})

    assert look_up_binding("9780000002112") == BindingAnswer("Ebook", ITUNES)

    monkeypatch.setattr(book_lookup, "_lookup_itunes", lambda isbn: {"physical_format": "en"})
    assert look_up_binding("9780000002112") is None
