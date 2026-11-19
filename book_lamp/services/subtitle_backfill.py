"""Fill in a Book's subtitle from a metadata provider, one look at a time.

The stored title is the main title; the subtitle is a separate fact. This run
only ever fills a *missing* subtitle: it reads the provider by ISBN (Open
Library first, Google Books second), refuses to overwrite a subtitle already
stored, and never rewrites the title. A split migration 0011 guessed from a
combined title is therefore left as it is; only a Book whose subtitle is NULL
can be changed by this script.

``report`` answers the discovery questions the issue asks for before a run:
how many stored titles split under the shared rule, of those how many the
provider can give a subtitle to, and how many rows the provider gives a
subtitle the stored title lacked.
"""

from typing import Any, Callable, Dict, Iterable, Optional

from book_lamp.utils.books import full_title, normalize_isbn, split_title_parts

SubtitleLookup = Callable[[str], Optional[str]]
SubtitleWriter = Callable[[int, str, str], bool]


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


def backfill_missing_subtitles(
    books: Iterable[Dict[str, Any]],
    lookup: SubtitleLookup = look_up_subtitle,
    write: Optional[SubtitleWriter] = None,
    on_progress: Optional[Callable[[int, int], None]] = None,
) -> Dict[str, int]:
    """Fill each Book's missing subtitle from a provider.

    Returns updated / skipped / failed counts. A Book with no ISBN cannot be
    looked up, and one that already has a subtitle is not asked about, so the
    run is idempotent: a second run finds nothing to fill. ``write`` is called
    with (book id, ISBN, subtitle) and must itself keep the row only when the
    subtitle is still null, which is what makes a concurrent edit win.
    """
    candidates = list(books)
    counts = {"updated": 0, "skipped": 0, "failed": 0}

    for done, book in enumerate(candidates, start=1):
        isbn = normalize_isbn(str(book.get("isbn13") or ""))
        if not isbn or str(book.get("subtitle") or "").strip():
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
        # and after migration 0011 rewrote the stored title.
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
