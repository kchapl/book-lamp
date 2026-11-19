"""The one-off subtitle backfill only fills a gap, and reports what it did."""

from book_lamp.services.subtitle_backfill import backfill_missing_subtitles, report_subtitles


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
        write=lambda book_id, isbn, subtitle: writes.append((book_id, isbn, subtitle)) or True,
    )

    assert counts == {"updated": 1, "skipped": 2, "failed": 0}
    assert writes == [(1, "9780000000001", "The Greatest Espionage Story of the Cold War")]


def test_a_second_run_finds_nothing_to_fill():
    books = _books()
    lookup = lambda isbn: "A Subtitle"  # noqa: E731
    write = lambda book_id, isbn, subtitle: books[0].update(subtitle=subtitle) or True  # noqa: E731

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
        write=lambda book_id, isbn, subtitle: True,
    )

    assert counts["failed"] == 1
    assert counts["skipped"] == 2


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
