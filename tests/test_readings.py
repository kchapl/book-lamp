"""Tests for the rule that an ended Reading says when it ended.

The rule is pure, so these are table-driven tests over the pair that decides it.
``tests/test_api_routes.py`` covers the routes turning it into a 400,
``tests/test_libib_import.py`` covers the importer satisfying it, and the last
test here covers the storage seam enforcing it for every writer.
"""

import pytest

from book_lamp.services.mock_storage import MockStorage
from book_lamp.utils.readings import (
    ENDING_STATUSES,
    ReadingEndsWithoutADate,
    end_date_problem,
    require_end_date,
)


@pytest.mark.parametrize("status", ENDING_STATUSES)
def test_an_ended_reading_must_say_when_it_ended(status: str) -> None:
    assert end_date_problem(status, None) is not None

    with pytest.raises(ReadingEndsWithoutADate):
        require_end_date(status, None)


@pytest.mark.parametrize("status", ["In Progress", "Not begun", "", "Plan to Read"])
def test_an_open_reading_needs_no_end_date(status: str) -> None:
    assert end_date_problem(status, None) is None

    require_end_date(status, None)


@pytest.mark.parametrize("status", ENDING_STATUSES)
def test_an_ended_reading_with_a_date_is_writable(status: str) -> None:
    assert end_date_problem(status, "2026-10-12") is None


def test_the_message_names_the_status_that_ended() -> None:
    message = end_date_problem("Abandoned", None)

    assert message is not None
    assert "Abandoned" in message


def test_the_storage_seam_refuses_an_ended_reading_without_a_date() -> None:
    """Enforced where every writer meets, not only in the routes.

    The MCP service reaches the storage seam directly, so a rule that lived in
    the Flask routes alone would not be true for it.
    """
    storage = MockStorage()
    storage.set_authorised(True)
    book = storage.add_book(isbn13="9780000000002", title="A Book", author="An Author")

    with pytest.raises(ReadingEndsWithoutADate):
        storage.add_reading(book["id"], "Completed", "2026-10-12")

    open_reading = storage.add_reading(book["id"], "In Progress", "2026-10-12")

    with pytest.raises(ReadingEndsWithoutADate):
        storage.update_reading(open_reading["id"], "Completed", "2026-10-12")

    ended = storage.update_reading(open_reading["id"], "Completed", "2026-10-12", "2026-10-20")
    assert ended["end_date"] == "2026-10-20"
