"""The subtitle backfill splits once, then only fills gaps, and reports what it did."""

import sys

from book_lamp.services.search import search_books
from book_lamp.services.subtitle_backfill import (
    backfill_missing_subtitles,
    report_subtitles,
    split_stored_titles,
)


def _books():
    return [
        {"id": 1, "isbn13": "9780000000001", "title": "The Spy and the Traitor", "subtitle": None},
        {"id": 2, "isbn13": "9780000000002", "title": "Piranesi", "subtitle": "A Novel"},
        {"id": 3, "isbn13": "", "title": "No ISBN", "subtitle": None},
    ]


def test_it_fills_only_a_missing_subtitle():
    writes = []

    counts = backfill_missing_subtitles(
        _books(),
        lookup=lambda isbn: {
            "9780000000001": "The Greatest Espionage Story of the Cold War",
            "9780000000002": "A Different Subtitle",
        }.get(isbn),
        write=lambda book, isbn, subtitle: writes.append((book["id"], isbn, subtitle)) or True,
    )

    assert counts == {"updated": 1, "skipped": 2, "failed": 0}
    assert writes == [(1, "9780000000001", "The Greatest Espionage Story of the Cold War")]


def test_a_second_run_finds_nothing_to_fill():
    books = _books()
    lookup = lambda isbn: "A Subtitle"  # noqa: E731
    write = lambda book, isbn, subtitle: book.update(subtitle=subtitle) or True  # noqa: E731

    backfill_missing_subtitles(books, lookup=lookup, write=write)

    assert backfill_missing_subtitles(books, lookup=lookup, write=write)["updated"] == 0


def test_a_provider_failure_is_counted_and_does_not_stop_the_run():
    def lookup(isbn):
        if isbn == "9780000000001":
            raise RuntimeError("provider is down")
        return "A Subtitle"

    counts = backfill_missing_subtitles(
        _books(),
        lookup=lookup,
        write=lambda book, isbn, subtitle: True,
    )

    assert counts["failed"] == 1
    assert counts["skipped"] == 2


def test_stored_titles_are_split_after_the_old_instance_has_stopped():
    """The deferred rewrite divides what it can and leaves the rest whole."""
    books = [
        {"id": 1, "isbn13": "9780000000001", "title": "Piranesi: A Novel", "subtitle": None},
        {"id": 2, "isbn13": "9780000000002", "title": "Re: Zero", "subtitle": None},
        {"id": 3, "isbn13": "9780000000003", "title": "A Book - A Memoir", "subtitle": "Stored"},
    ]
    writes = []

    counts = split_stored_titles(
        books,
        write=lambda book, title, subtitle: writes.append((book["id"], title, subtitle)) or True,
    )

    assert counts == {"updated": 1, "skipped": 2, "failed": 0}
    assert writes == [(1, "Piranesi", "A Novel")]


def test_a_title_that_still_carries_its_subtitle_is_left_for_the_split():
    """Filling only the subtitle would store the pair twice, so the row waits."""
    counts = backfill_missing_subtitles(
        [{"id": 1, "isbn13": "9780000000001", "title": "Piranesi: A Novel", "subtitle": None}],
        lookup=lambda isbn: "A Novel",
        write=lambda book, isbn, subtitle: True,
    )

    assert counts == {"updated": 0, "skipped": 1, "failed": 0}


def test_the_split_title_still_answers_to_its_old_combined_name():
    """Search never relied on the separator being stored, so the split keeps it.

    Migration 0011 only adds the column and the backfill divides the title, so a
    reader typing ``Piranesi: A Novel`` must find the Book from its two stored
    parts: the title answers for ``Piranesi`` and the subtitle for ``A Novel``.
    """
    books = [
        {"id": 1, "isbn13": "9781635575637", "title": "Piranesi: A Novel", "subtitle": None},
    ]

    split_stored_titles(
        books,
        write=lambda book, title, subtitle: book.update(title=title, subtitle=subtitle) or True,
    )

    assert (books[0]["title"], books[0]["subtitle"]) == ("Piranesi", "A Novel")
    assert [book["title"] for book in search_books(books, [], "Piranesi: A Novel")] == ["Piranesi"]


def test_the_plain_run_does_not_split_a_title_the_reader_kept_whole(monkeypatch):
    """Only ``--split-titles`` rewrites titles: a cleared subtitle stays cleared.

    Clearing the subtitle is how a wrong split is undone, so the routine fill
    that the docs call repeatable must not divide the title again.
    """
    from scripts import backfill_subtitles

    splits = []
    monkeypatch.setattr(backfill_subtitles, "_pool", lambda: object())
    monkeypatch.setattr(backfill_subtitles, "_books_without_subtitle", lambda pool: [])
    monkeypatch.setattr(
        backfill_subtitles,
        "split_stored_titles",
        lambda books, write=None, on_progress=None: splits.append(list(books))
        or {"updated": 0, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(
        backfill_subtitles,
        "backfill_missing_subtitles",
        lambda books, write=None, on_progress=None: {"updated": 0, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(sys, "argv", ["backfill_subtitles.py"])

    backfill_subtitles.main()

    assert splits == []


def test_the_split_flag_runs_the_deferred_rewrite(monkeypatch):
    """The one-off step runs when it is asked for, over the rows it was read."""
    from scripts import backfill_subtitles

    stored = [{"id": 1, "isbn13": "9780000000001", "title": "Piranesi: A Novel", "subtitle": None}]
    calls = []
    monkeypatch.setattr(backfill_subtitles, "_pool", lambda: object())
    monkeypatch.setattr(backfill_subtitles, "_books_without_subtitle", lambda pool: stored)
    monkeypatch.setattr(
        backfill_subtitles,
        "split_stored_titles",
        lambda books, write=None, on_progress=None: calls.append(list(books))
        or {"updated": 0, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(
        backfill_subtitles,
        "backfill_missing_subtitles",
        lambda books, write=None, on_progress=None: {"updated": 0, "skipped": 0, "failed": 0},
    )
    monkeypatch.setattr(sys, "argv", ["backfill_subtitles.py", "--split-titles"])

    backfill_subtitles.main()

    assert calls == [stored]


def test_the_report_counts_the_split_and_the_provider_only_subtitles():
    counts = report_subtitles(
        [
            {"isbn13": "9780000000001", "title": "Piranesi: A Novel", "subtitle": None},
            {"isbn13": "9780000000002", "title": "The Spy and the Traitor", "subtitle": None},
            {"isbn13": "9780000000003", "title": "Dune", "subtitle": None},
        ],
        lookup=lambda isbn: {
            "9780000000001": "A Novel",
            "9780000000002": "The Greatest Espionage Story of the Cold War",
            "9780000000003": "Book One of the Dune Chronicles",
        }.get(isbn),
    )

    # One title splits, and the provider has a subtitle for it; two rows have no
    # separable subtitle but the provider still knows one.
    assert counts == {"split": 1, "split_with_provider": 1, "provider_only": 2}
