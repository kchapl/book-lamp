"""Fill a Book's missing binding from a provider.

A Book's ``physical_format`` is a binding — paperback, hardback, ebook or
audiobook — and nothing else. Google Books offers no binding (its ``printType``
is a media type), so its lookups store nothing. Open Library supplies
``physical_format`` per edition and iTunes answers only with ebooks, which are
the two sources this run asks.

The run only fills a gap: a Book that already names a binding is never touched,
and a value that names no binding (``book``, ``BOOK``, ``en``, ``Large Print``)
counts as a gap. Every lookup is sequential, and a write guards on the value the
run read, so a resumed run can repeat without overwriting a reader's choice.
"""

from typing import Any, Callable, Dict, Iterable, NamedTuple, Optional

from book_lamp.services.stats_calculator import normalise_physical_format
from book_lamp.utils.books import normalize_isbn

OPEN_LIBRARY = "open_library"
ITUNES = "itunes"


class BindingAnswer(NamedTuple):
    """What a provider answered, and which provider it was."""

    binding: Optional[str]
    source: str


FormatLookup = Callable[[str], Optional[BindingAnswer]]
FormatWriter = Callable[[Dict[str, Any], str, str], bool]


def _binding_from(value: object) -> Optional[str]:
    """The provider's value when it names a binding, else None."""
    text = str(value or "").strip()
    if not text:
        return None
    # The panel folds provider spellings ("Perfect Paperback", "Kindle
    # Edition") into the four labels; a value the fold does not recognise is
    # not a binding and must not be stored as one.
    return text if normalise_physical_format(text) else None


def look_up_binding(isbn13: str) -> Optional[BindingAnswer]:
    """Ask Open Library, then iTunes, for the binding of this ISBN.

    A provider failure is an absent answer rather than a failed run, so one
    provider's bad day does not stop the backfill.
    """
    from book_lamp.services.book_lookup import _lookup_itunes, _lookup_open_library

    isbn = normalize_isbn(isbn13)
    for source, lookup in ((OPEN_LIBRARY, _lookup_open_library), (ITUNES, _lookup_itunes)):
        try:
            info = lookup(isbn)
        except Exception:
            info = None
        binding = _binding_from((info or {}).get("physical_format"))
        if binding:
            return BindingAnswer(binding, source)
    return None


def _has_binding(book: Dict[str, Any]) -> bool:
    return normalise_physical_format(book.get("physical_format")) is not None


def backfill_missing_formats(
    books: Iterable[Dict[str, Any]],
    lookup: FormatLookup = look_up_binding,
    write: Optional[FormatWriter] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, int]:
    """Fill each Book's empty or invalid format from a provider.

    Returns updated / skipped / failed. A Book that already carries a binding
    is skipped, so a repeat run fills nothing new and a reader's choice is
    never replaced. ``write`` receives the Book as it was read, its ISBN and
    the binding, and must keep the row only while it still holds the value the
    run read.
    """
    candidates = list(books)
    counts = {"updated": 0, "skipped": 0, "failed": 0}

    for done, book in enumerate(candidates, start=1):
        isbn = normalize_isbn(str(book.get("isbn13") or ""))
        if _has_binding(book) or not isbn:
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        try:
            answer = lookup(isbn)
        except Exception:
            counts["failed"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        binding = _binding_from(answer.binding) if answer else None
        if not binding:
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        try:
            wrote = write(book, isbn, binding) if write else False
        except Exception:
            counts["failed"] += 1
        else:
            counts["updated" if wrote else "skipped"] += 1
        if on_progress:
            on_progress(done, len(candidates))

    return counts


def report_formats(
    books: Iterable[Dict[str, Any]],
    lookup: FormatLookup = look_up_binding,
) -> Dict[str, int]:
    """Count what a backfill would do, without writing anything.

    ``gained`` is how many gaps a provider can fill, ``left_empty`` how many it
    leaves, and the per-source counts say where the answers came from. A
    source with no answers is the one that dried up.
    """
    counts = {
        "with_binding": 0,
        "gained": 0,
        "left_empty": 0,
        "failed": 0,
        OPEN_LIBRARY: 0,
        ITUNES: 0,
    }

    for book in books:
        if _has_binding(book):
            counts["with_binding"] += 1
            continue

        isbn = normalize_isbn(str(book.get("isbn13") or ""))
        if not isbn:
            counts["left_empty"] += 1
            continue

        try:
            answer = lookup(isbn)
        except Exception:
            counts["failed"] += 1
            counts["left_empty"] += 1
            continue

        if not answer or not _binding_from(answer.binding):
            counts["left_empty"] += 1
            continue

        counts["gained"] += 1
        counts[answer.source] += 1

    return counts
