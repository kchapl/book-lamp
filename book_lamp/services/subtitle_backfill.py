"""Split stored titles and fill in a Book's subtitle from a provider.

The stored title is the main title; the subtitle is a separate fact. Migration
0011 only adds the column: the rewrite of titles already stored happens here,
after the release, so no instance still writing combined titles can undo it.
The split runs first, by the shared rule, and touches only a title it can divide
safely. The provider run then fills a *missing* subtitle (Open Library first,
Google Books second), never overwrites one already stored, and skips a title
that still carries its subtitle so an answer cannot store the pair twice.

``report`` answers the discovery questions the issue asks for before a run:
how many stored titles split under the shared rule, of those how many the
provider can give a subtitle to, and how many rows the provider gives a
subtitle the stored title lacked.
"""

from typing import Any, Callable, Dict, Iterable, Optional

from book_lamp.utils.books import full_title, normalize_isbn, split_title_parts

SubtitleLookup = Callable[[str], Optional[str]]
SubtitleWriter = Callable[[int, str, str], bool]
TitleSplitWriter = Callable[[Dict[str, Any], str, str], bool]


def look_up_subtitle(isbn13: str) -> Optional[str]:
    """A provider's subtitle for this ISBN, or None when none knows one.

    Open Library is asked first and Google Books second, matching the order the
    ISBN lookup already uses. A provider failure is treated as "no answer", so
    one provider's bad day does not fail the whole run.
    """
    from book_lamp.services.book_lookup import _lookup_google_books, _lookup_open_library

    for lookup in (_lookup_open_library, _lookup_google_books):
        try:
            info = lookup(normalize_isbn(isbn13))
        except Exception:
            info = None
        subtitle = str((info or {}).get("subtitle") or "").strip()
        if subtitle:
            return subtitle
    return None


def split_stored_titles(
    books: Iterable[Dict[str, Any]],
    write: Optional[TitleSplitWriter] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, int]:
    """Split stored combined titles into a main title and a subtitle.

    This is the rewrite migration 0011 deliberately leaves out. It runs after
    the release, when no instance that writes combined titles is still serving,
    so a late save cannot put the subtitle back into the title. Only a title the
    shared rule divides is touched, a row that already has a subtitle is not,
    and ``write`` receives the whole book so it can guard on the title it read.

    This is a one-off step, not a routine sweep: clearing a subtitle is how a
    reader keeps a whole title after undoing a split, so a later run must not
    divide that title again. The script therefore gates it behind
    ``--split-titles``.
    """
    candidates = list(books)
    counts = {"updated": 0, "skipped": 0, "failed": 0}
    for done, book in enumerate(candidates, start=1):
        if str(book.get("subtitle") or "").strip():
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        main, subtitle = split_title_parts(book.get("title"))
        if subtitle is None:
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        try:
            wrote = write(book, main, subtitle) if write else False
        except Exception:
            counts["failed"] += 1
        else:
            counts["updated" if wrote else "skipped"] += 1
        if on_progress:
            on_progress(done, len(candidates))
    return counts


def backfill_missing_subtitles(
    books: Iterable[Dict[str, Any]],
    lookup: SubtitleLookup = look_up_subtitle,
    write: Optional[SubtitleWriter] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, int]:
    """Fill each Book's missing subtitle from a provider.

    Returns updated / skipped / failed counts. A Book with no ISBN cannot be
    looked up, and one that already has a subtitle is not asked about, so a
    second run fills nothing new. A cleared subtitle is stored as NULL and reads
    exactly like one never filled, though, so a suggestion the reader removed
    can be filled again: this run cannot tell the two apart. A title that still
    carries its subtitle is skipped too, because filling only the subtitle would
    store the pair twice, and splitting the title is ``split_stored_titles``'s
    job.
    ``write`` is called with (book id, ISBN, subtitle) and must itself keep the
    row only when the subtitle is still null, which is what makes a concurrent
    edit win.
    """
    candidates = list(books)
    counts = {"updated": 0, "skipped": 0, "failed": 0}

    for done, book in enumerate(candidates, start=1):
        isbn = normalize_isbn(str(book.get("isbn13") or ""))
        _, split_subtitle = split_title_parts(book.get("title"))
        if not isbn or str(book.get("subtitle") or "").strip() or split_subtitle:
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        try:
            subtitle = lookup(isbn)
        except Exception:
            counts["failed"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        subtitle = str(subtitle or "").strip()
        if not subtitle:
            counts["skipped"] += 1
            if on_progress:
                on_progress(done, len(candidates))
            continue

        try:
            wrote = write(book["id"], isbn, subtitle) if write else False
        except Exception:
            counts["failed"] += 1
        else:
            counts["updated" if wrote else "skipped"] += 1
        if on_progress:
            on_progress(done, len(candidates))

    return counts


def report_subtitles(
    books: Iterable[Dict[str, Any]],
    lookup: SubtitleLookup = look_up_subtitle,
) -> Dict[str, int]:
    """Count what a provider backfill could do, without writing anything.

    ``split`` counts stored titles the rule can divide; ``split_with_provider``
    counts those where a provider also has a subtitle; ``provider_only`` counts
    rows where the stored title has no separable subtitle but the provider
    still knows one.
    """
    counts = {"split": 0, "split_with_provider": 0, "provider_only": 0}
    for book in books:
        stored_subtitle = str(book.get("subtitle") or "").strip()
        # Reconstruct the whole title first, so this counts the same rows before
        # and after the title split has run.
        _, split_subtitle = split_title_parts(full_title(book.get("title"), stored_subtitle))
        local_subtitle = stored_subtitle or split_subtitle
        if split_subtitle:
            counts["split"] += 1

        isbn = normalize_isbn(str(book.get("isbn13") or ""))
        if not isbn:
            continue
        try:
            provider_subtitle = str(lookup(isbn) or "").strip()
        except Exception:
            provider_subtitle = ""
        if not provider_subtitle:
            continue
        if local_subtitle:
            counts["split_with_provider"] += 1
        else:
            counts["provider_only"] += 1
    return counts
