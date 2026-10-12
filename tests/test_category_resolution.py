"""The category precedence rule, on its own.

The rule used to exist twice over, inside the two storage adapters, and the
"Dewey code" test it consulted had four spellings. ADR-0002 gives it one home,
so it can be tested directly here instead of through whichever adapter a test
happened to reach for.
"""

import pytest

from book_lamp.utils.books import Category, is_dewey_category, resolve_category


@pytest.mark.parametrize(
    "value, expected",
    [
        ("823.914", True),
        ("823", True),
        (" 823.914 ", True),
        ("FICTION / General", False),
        ("FICTION", False),
        ("en", False),
        ("416", True),
        ("...", False),
        ("   ", False),
        ("", False),
        (None, False),
    ],
)
def test_is_dewey_category(value, expected):
    assert is_dewey_category(value) is expected


def test_a_real_category_replaces_whatever_is_stored():
    stored = Category("823.914", "823.914", None)
    incoming = Category.from_fields("FICTION / General", "FICTION", "General")

    assert resolve_category(incoming, stored) == incoming


def test_a_dewey_code_does_not_replace_a_real_category():
    stored = Category("FICTION / General", "FICTION", "General")
    incoming = Category.from_fields("823.914", "823.914", None)

    assert resolve_category(incoming, stored) == stored


def test_a_real_category_replaces_a_dewey_code():
    stored = Category("823.914", "823.914", None)
    incoming = Category.from_fields("FICTION / General", "FICTION", "General")

    assert resolve_category(incoming, stored) == incoming


def test_a_dewey_code_does_not_replace_another_dewey_code():
    stored = Category("823.914", "823.914", None)
    incoming = Category.from_fields("999.9", "999.9", None)

    assert resolve_category(incoming, stored) == stored


def test_a_dewey_code_fills_the_gap_when_nothing_is_stored():
    incoming = Category.from_fields("823.914", "823.914", None)

    assert resolve_category(incoming, Category()) == incoming


def test_an_absent_category_leaves_the_stored_one_standing():
    stored = Category("FICTION / General", "FICTION", "General")

    assert resolve_category(Category(), stored) == stored


def test_an_absent_category_still_answers_with_what_is_stored():
    stored = Category("FICTION", "FICTION", None)
    # A payload with no category at all must not erase the stored triple.
    assert resolve_category(Category.from_fields(None, None, None), stored) == stored


def test_a_whitespace_only_category_counts_as_absent():
    stored = Category("FICTION", "FICTION", None)

    assert resolve_category(Category.from_fields("   "), stored) == stored


def test_the_pair_is_derived_when_only_the_category_is_given():
    # The edit form sends the full category and nothing else, so the major and
    # sub must come from it rather than from the category being replaced.
    stored = Category("HISTORY / Ancient / General", "HISTORY", "Ancient / General")
    incoming = Category.from_fields("FICTION / Literary")

    resolved = resolve_category(incoming, stored)

    assert resolved == Category("FICTION / Literary", "FICTION", "Literary")


def test_a_supplied_pair_wins_over_the_derived_one():
    stored = Category("823.914", "823.914", None)
    incoming = Category.from_fields("FICTION / General", "FICTION", "General")

    assert resolve_category(incoming, stored) == Category("FICTION / General", "FICTION", "General")


def test_the_winning_value_is_never_rewritten_by_the_derivation():
    # Deriving the pair must not normalise the value the caller sent.
    incoming = Category.from_fields("History / Europe")

    assert resolve_category(incoming, Category()).category == "History / Europe"
