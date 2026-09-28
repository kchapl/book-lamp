"""Tests for the Reading Status rule.

The rule is pure, so these are table-driven tests over the fold itself rather
than tests driven through Flask. ``tests/test_books.py`` covers the catalogue
route's use of it.
"""

from typing import Any

import pytest

from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.stats_calculator import calculate_collection_stats
from book_lamp.utils.reading_status import (
    READING_STATUSES,
    latest_record_by_book,
    with_reading_status,
)
from book_lamp.utils.sorting import sort_by_reading_date


def _record(
    record_id: object,
    book_id: object,
    start_date: str,
    status: str = "Completed",
) -> dict[str, Any]:
    """Build a Reading Record as the storage adapters hand it over."""
    return {
        "id": record_id,
        "book_id": book_id,
        "start_date": start_date,
        "status": status,
    }


def _book(book_id: object, title: str = "A Book") -> dict[str, Any]:
    """Build a Book as the storage adapters hand it over."""
    return {"id": book_id, "title": title}


def _picked(records: list[dict[str, Any]]) -> dict[int, int]:
    """Summarise the fold as Book id -> chosen Reading Record id.

    Only the map's keys and its ordering are normalised to ints; the values stay
    the raw records, so the summary normalises the record id itself.
    """
    return {book_id: int(record["id"]) for book_id, record in latest_record_by_book(records).items()}


FOLD_CASES = [
    pytest.param([], {}, id="no-records"),
    pytest.param([_record(1, 7, "2024-01-01")], {7: 1}, id="single-record"),
    pytest.param(
        [_record(1, 7, "2024-01-01"), _record(2, 7, "2024-05-01")],
        {7: 2},
        id="later-start-date-wins",
    ),
    pytest.param(
        [_record(2, 7, "2024-05-01"), _record(1, 7, "2024-01-01")],
        {7: 2},
        id="later-start-date-wins-when-it-arrives-first",
    ),
    pytest.param(
        [_record(1, 7, "2024-01-01"), _record(2, 7, "2024-01-01")],
        {7: 2},
        id="same-day-tie-goes-to-the-later-record",
    ),
    pytest.param(
        [_record(2, 7, "2024-01-01"), _record(1, 7, "2024-01-01")],
        {7: 2},
        id="same-day-tie-goes-to-the-later-record-when-it-arrives-first",
    ),
    pytest.param(
        [
            _record(1, 7, "2024-01-01"),
            _record(2, 8, "2024-02-01"),
            _record(3, 7, "2024-03-01"),
        ],
        {7: 3, 8: 2},
        id="books-are-folded-independently",
    ),
    pytest.param(
        [_record(1, 7, "2024-01-01"), _record(2, 7, "2024-05-01", "Plan to read")],
        {7: 2},
        id="fold-does-not-filter-by-status",
    ),
    pytest.param(
        [_record(1, "not-a-number", "2024-01-01"), _record(2, 7, "2024-01-01")],
        {7: 2},
        id="unusable-book-id-is-skipped",
    ),
    pytest.param(
        [_record("not-a-number", 7, "2024-01-01"), _record(2, 7, "2024-01-01")],
        {7: 2},
        id="unusable-record-id-is-skipped",
    ),
    pytest.param([_record(1, 0, "2024-01-01")], {}, id="zero-book-id-is-skipped"),
    pytest.param([_record(0, 7, "2024-01-01")], {}, id="zero-record-id-is-skipped"),
    pytest.param([_record("1", "7", "2024-01-01")], {7: 1}, id="string-ids-are-coerced"),
]


@pytest.mark.parametrize("records, expected", FOLD_CASES)
def test_latest_record_by_book_picks_the_current_record(
    records: list[dict[str, Any]], expected: dict[int, int]
) -> None:
    assert _picked(records) == expected


@pytest.mark.parametrize("records, expected", FOLD_CASES)
def test_latest_record_by_book_ignores_iteration_order(records: list[dict[str, Any]], expected: dict[int, int]) -> None:
    """The rule must not depend on the order an adapter returns records in.

    One adapter hands back records newest-first and the other in insertion
    order, so an order-dependent fold gives different answers in tests and in
    production. This is the regression test for that divergence.
    """
    assert _picked(list(reversed(records))) == expected


def test_the_fold_keeps_the_whole_record() -> None:
    record = _record(1, 7, "2024-01-01", "Completed")

    assert latest_record_by_book([record])[7]["status"] == "Completed"


def test_reading_statuses_are_the_three_readings() -> None:
    assert READING_STATUSES == ("In Progress", "Completed", "Abandoned")


def test_with_reading_status_attaches_the_current_status() -> None:
    records = [
        _record(1, 7, "2024-01-01", "In Progress"),
        _record(2, 7, "2024-02-01", "Completed"),
    ]

    assert with_reading_status([_book(7)], records) == [{"id": 7, "title": "A Book", "latest_status": "Completed"}]


def test_with_reading_status_omits_books_without_a_record() -> None:
    assert with_reading_status([_book(7), _book(8)], [_record(1, 7, "2024-01-01")]) == [
        {"id": 7, "title": "A Book", "latest_status": "Completed"}
    ]


def test_with_reading_status_omits_books_whose_current_record_is_not_a_reading() -> None:
    records = [_record(1, 7, "2024-01-01", "Plan to read")]

    assert with_reading_status([_book(7)], records) == []


def test_with_reading_status_omits_books_with_an_unusable_id() -> None:
    assert with_reading_status([_book(None)], [_record(1, 7, "2024-01-01")]) == []


def test_with_reading_status_keeps_the_given_order() -> None:
    records = [_record(1, 8, "2024-01-01"), _record(2, 7, "2024-02-01")]

    result = with_reading_status([_book(8, "First"), _book(7, "Second")], records)

    assert [book["title"] for book in result] == ["First", "Second"]


def test_with_reading_status_returns_copies() -> None:
    books = [_book(7)]

    result = with_reading_status(books, [_record(1, 7, "2024-01-01")])

    assert result[0] is not books[0]
    assert books == [{"id": 7, "title": "A Book"}]


def test_with_reading_status_leaves_an_adapters_own_books_untouched() -> None:
    """MockStorage hands out its live list, so attaching in place would write into it."""
    storage = MockStorage()
    book = storage.add_book(isbn13="9780000000001", title="A Book", author="An Author")
    storage.add_reading_record(book["id"], "Completed", "2024-01-01")

    with_reading_status(storage.get_all_books(), storage.get_reading_records())

    assert "latest_status" not in storage.get_all_books()[0]


def test_status_counts_agree_with_the_reading_status_rule() -> None:
    books = [_book(1), _book(2), _book(3)]
    records = [
        _record(1, 1, "2024-01-01", "Abandoned"),
        _record(2, 2, "2024-02-01", "Completed"),
        _record(3, 3, "2024-03-01", "Plan to read"),
    ]

    stats = calculate_collection_stats(books, records)
    statuses = [book["latest_status"] for book in with_reading_status(books, records)]

    assert statuses == ["Abandoned", "Completed"]
    assert stats["status_counts"] == {"Abandoned": 1, "Completed": 1}


def test_sort_by_reading_date_uses_the_current_record() -> None:
    books = [_book(1), _book(2)]
    records = [
        _record(1, 1, "2024-01-01"),
        _record(2, 1, "2024-05-01"),
        _record(3, 2, "2024-03-01"),
    ]

    ordered = sort_by_reading_date(books, records)

    assert [book["id"] for book in ordered] == [1, 2]
