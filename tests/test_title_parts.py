"""The one rule that decides where a Book's title ends and its subtitle begins.

A provider's separate subtitle is used as given; only a combined title is
split, and only where the split is safe. These are the cases the issue names.
"""

import pytest

from book_lamp.utils.books import full_title, normalise_title_pair, split_title_parts


@pytest.mark.parametrize(
    ("raw", "title", "subtitle"),
    [
        (
            "A History of England in 100 Places: From Stonehenge to the Gherkin",
            "A History of England in 100 Places",
            "From Stonehenge to the Gherkin",
        ),
        ("The Spy in the Archive — A Novel", "The Spy in the Archive", "A Novel"),
        ("The Spy in the Archive – A Novel", "The Spy in the Archive", "A Novel"),
        ("The Spy in the Archive - A Novel", "The Spy in the Archive", "A Novel"),
        # Whitespace the rule normalises, on both sides of the separator.
        ("  The  Last  King :   A Life ", "The Last King", "A Life"),
        # A title with no separator is never cut: "Dune Messiah" is not a
        # subtitle of "Dune".
        ("Dune Messiah", "Dune Messiah", None),
        ("Piranesi", "Piranesi", None),
        # A colon after a prefix too short to stand as a heading is the title's.
        ("Re: Zero", "Re: Zero", None),
        ("10:04", "10:04", None),
        # A bare hyphen belongs to the word, not between parts.
        ("Spider-Man", "Spider-Man", None),
        # A separator with nothing after it separates nothing.
        ("Colon:", "Colon:", None),
    ],
)
def test_the_shared_rule_splits_only_what_it_can(raw, title, subtitle):
    assert split_title_parts(raw) == (title, subtitle)


def test_a_provider_subtitle_is_used_as_given():
    assert split_title_parts(
        "The Spy and the Traitor",
        "The Greatest Espionage Story of the Cold War",
    ) == ("The Spy and the Traitor", "The Greatest Espionage Story of the Cold War")


def test_a_blank_provider_subtitle_falls_back_to_the_split_rule():
    assert split_title_parts("Piranesi: A Novel", "   ") == ("Piranesi", "A Novel")


def test_a_missing_provider_subtitle_falls_back_to_the_split_rule():
    assert split_title_parts("Piranesi: A Novel", None) == ("Piranesi", "A Novel")


def test_a_subtitle_repeated_inside_the_title_is_held_once():
    """Wherever a provider puts the subtitle, the pair stores it once."""
    assert normalise_title_pair("Piranesi: A Novel", "A Novel") == ("Piranesi", "A Novel")
    assert normalise_title_pair("Piranesi - A Novel", "A Novel") == ("Piranesi", "A Novel")
    # A subtitle that disagrees with the one in the title is not the same name,
    # and an unsplittable title is left exactly as it arrived.
    assert normalise_title_pair("Piranesi: A Novel", "A Memoir") == ("Piranesi: A Novel", "A Memoir")
    assert normalise_title_pair("Re: Zero", "Zero") == ("Re: Zero", "Zero")


def test_the_full_title_recombines_the_parts_for_export_and_the_log():
    assert full_title("Piranesi", "A Novel") == "Piranesi: A Novel"
    assert full_title("Piranesi", None) == "Piranesi"
    assert full_title("", "A Novel") == ""
