"""Authorship: the names a Book is credited to.

A Book's Authors are a list, in the order the source credited them. Text enters
that list in one place, :func:`parse`, and leaves it in one place,
:func:`display`; nothing ever parses a display string back. That is the point:
the comma that means "Last, First" in a name never has to be told apart from a
comma separating two names, because a list never arrives as a comma-joined
string.

Two rules keep the list authoritative:

- A source that gives a list (Open Library, Google Books, a CSV column) is taken
  as given. A source that gives one name — iTunes' artist, a person's typed
  text — contributes one Author per name it actually lists, and
  :func:`parse` is what reads that text.
- An Author is identified by name (see ``CONTEXT.md``): two spellings are two
  Authors, each with its own page.

:func:`slug` and :func:`matches` are how an Author gets a page, and
:func:`sort_key` is how a shelf of Books is ordered by surname.
"""

import re
from typing import Iterable, List, Tuple


def _names(text: str) -> List[str]:
    """Split text on the separators that mark a list, keeping order."""
    parts = [part.strip() for part in re.split(r"\s*;\s*", text) if part.strip()]
    return [part for part in parts if part]


def parse(text: str) -> List[str]:
    """Read text that lists several Authors into the names it lists.

    Use this only for text that is a list of names: a payload field, a CSV
    column, or something a person typed. A provider's single value is one
    Author, so it never comes through here.

    Semicolons separate names unambiguously, as do " and " and " & ". A single
    comma is read as "Last, First" — the one genuinely ambiguous mark — and two
    or more commas are read as a list, which is how a bare "A, B, C" is handled.
    """
    if not text or not text.strip():
        return []

    # A semicolon is the unambiguous list separator, so it decides the split
    # outright: it is what "Last, First" entries are joined with.
    if ";" in text:
        return _names(text)

    # " and " / " & " join names too, and cannot appear inside one. Commas are
    # left alone for the moment, because "Last, First" uses one.
    joined = text.replace(" and ", " || ").replace(" & ", " || ")

    names: List[str] = []
    for part in joined.split(" || "):
        part = part.strip()
        if not part:
            continue
        if part.count(",") > 1:
            # More than one comma cannot be a single "Last, First" name, so it
            # is a bare list separated by commas.
            names.extend(name.strip() for name in part.split(",") if name.strip())
        else:
            names.append(part)
    return names


def display(names: Iterable[str]) -> str:
    """The one-line form of a Book's Authors: what a reader sees.

    A projection, never an input: the result is not meant to be parsed back,
    which is why ", " is safe to use for a list of people.
    """
    cleaned = [str(name).strip() for name in names if str(name).strip()]
    return ", ".join(cleaned)


def slug(name: str) -> str:
    """The URL segment that names an Author.

    Frozen: every author link already handed out depends on this shape, so it
    keeps the spaces-to-hyphens and dropped dots it has always had.
    """
    if not name:
        return ""
    return name.lower().replace(" ", "-").replace(".", "")


def matches(name: str, author_slug: str) -> bool:
    """Whether ``name`` is the Author the page at ``author_slug`` is about."""
    if not author_slug:
        return False
    return slug(name) == author_slug.strip().lower()


def sort_key(name: str) -> Tuple[str, str]:
    """Order one Author's name by surname, then given name, both lowercased.

    "Last, First" says which part is the surname outright. Otherwise the last
    word is taken as the surname, which is what "First Last" means.
    """
    if not name or not name.strip():
        return ("", "")

    name = name.strip()
    if "," in name:
        surname, _, given = name.partition(",")
        return (surname.strip().lower(), given.strip().lower())

    parts = name.rsplit(" ", 1)
    if len(parts) == 2:
        return (parts[1].lower(), parts[0].lower())
    return (name.lower(), "")
