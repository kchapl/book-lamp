#!/usr/bin/env python
"""Split stored Book titles once, and fill in missing subtitles (#384).

Migration 0011 adds the column but leaves the titles already stored alone,
because it lands while the previous instance is still serving and writes
combined titles. The rewrite is this script's one-off step, run after the
release has switched over:

    uv run python scripts/backfill_subtitles.py --split-titles

That run divides the stored titles the shared rule can divide, then fills the
subtitles no title carried from Open Library and Google Books. Later runs fill
subtitles only, and are safe to repeat:

    uv run python scripts/backfill_subtitles.py
    uv run python scripts/backfill_subtitles.py --report
    uv run python scripts/backfill_subtitles.py --dry-run

``--split-titles`` must not be repeated: clearing a subtitle is how a reader
keeps a whole title such as ``Foo Bar: Baz`` after undoing a split, and another
run would divide it again. ``--report`` makes no changes and only counts what
the subtitle fill would find. Lookups are sequential and use the app's shared
HTTP session, which keeps the providers' rate limits in view.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from book_lamp.services.subtitle_backfill import (  # noqa: E402
    backfill_missing_subtitles,
    report_subtitles,
    split_stored_titles,
)


def _pool():
    from book_lamp.services.pg_storage import get_pool

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set")
    return get_pool()


def _books_without_subtitle(pool) -> List[Dict[str, Any]]:
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT id, isbn13, title, subtitle
            FROM books
            WHERE subtitle IS NULL
            ORDER BY id
            """).fetchall()
    return [dict(row) for row in rows]


def _books_missing_subtitle(pool) -> List[Dict[str, Any]]:
    with pool.connection() as conn:
        rows = conn.execute("""
            SELECT id, isbn13, title, subtitle
            FROM books
            WHERE subtitle IS NULL AND btrim(isbn13) <> ''
            ORDER BY id
            """).fetchall()
    return [dict(row) for row in rows]


def _all_books(pool) -> List[Dict[str, Any]]:
    """Every Book, before or after migration 0011 has added the column.

    ``--report`` answers a question about the state the backfill starts from,
    which may be the release before the migration. Reading the column only when
    it exists lets the same command run on either side of the deploy.
    """
    with pool.connection() as conn:
        has_subtitle = conn.execute(
            "SELECT 1 FROM information_schema.columns " "WHERE table_name = 'books' AND column_name = 'subtitle'"
        ).fetchone()
        column = "subtitle" if has_subtitle else "NULL::text AS subtitle"
        rows = conn.execute(
            f"SELECT id, isbn13, title, {column} FROM books WHERE btrim(isbn13) <> '' ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def _write_split(pool, book: Dict[str, Any], title: str, subtitle: str) -> bool:
    """Store the parts only while the row still holds the title the run read."""
    with pool.connection() as conn:
        row = conn.execute(
            """
            UPDATE books SET title = %s, subtitle = %s
            WHERE id = %s AND title = %s AND subtitle IS NULL
            RETURNING id
            """,
            [title, subtitle, book["id"], book["title"]],
        ).fetchone()
    return row is not None


def _write_subtitle(pool, book_id: int, isbn13: str, subtitle: str) -> bool:
    """Fill a subtitle only while the row is still the one the run read."""
    with pool.connection() as conn:
        row = conn.execute(
            """
            UPDATE books SET subtitle = %s
            WHERE id = %s AND isbn13 = %s AND subtitle IS NULL
            RETURNING id
            """,
            [subtitle, book_id, isbn13],
        ).fetchone()
    return row is not None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split-titles",
        action="store_true",
        help="one-off: divide the stored titles migration 0011 left whole",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="count what the backfill would do, without writing anything",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="look every ISBN up but do not write the subtitles",
    )
    args = parser.parse_args()

    pool = _pool()

    if args.report:
        counts = report_subtitles(_all_books(pool))
        print(
            "Stored titles that split: {split}. "
            "Of those, a provider has a subtitle: {split_with_provider}. "
            "Rows where only a provider has a subtitle: {provider_only}.".format(**counts)
        )
        return

    def progress(done: int, total: int) -> None:
        if done == total or done % 25 == 0:
            print(f"  {done}/{total}", file=sys.stderr)

    if args.split_titles:
        counts = split_stored_titles(
            _books_without_subtitle(pool),
            write=None if args.dry_run else lambda book, title, subtitle: _write_split(pool, book, title, subtitle),
            on_progress=progress,
        )
        print("Stored titles split: updated {updated}, skipped {skipped}, failed {failed}.".format(**counts))

    counts = backfill_missing_subtitles(
        _books_missing_subtitle(pool),
        write=None if args.dry_run else lambda book_id, isbn, subtitle: _write_subtitle(pool, book_id, isbn, subtitle),
        on_progress=progress,
    )
    print("Subtitle backfill: updated {updated}, skipped {skipped}, failed {failed}.".format(**counts))


if __name__ == "__main__":
    main()
