#!/usr/bin/env python
"""Fill in missing Book subtitles from the metadata providers (#384).

Run this once after migration 0011, and again only if a provider record has
been corrected. It fills only rows whose subtitle is NULL, never rewrites a
title, and reports how many rows it updated, skipped or failed.

    uv run python scripts/backfill_subtitles.py
    uv run python scripts/backfill_subtitles.py --report
    uv run python scripts/backfill_subtitles.py --dry-run

``--report`` makes no changes and only counts what the run would find. Lookups
are sequential and use the app's shared HTTP session, which keeps the
providers' rate limits in view.
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
)


def _pool():
    from book_lamp.services.pg_storage import get_pool

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set")
    return get_pool()


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

    counts = backfill_missing_subtitles(
        _books_missing_subtitle(pool),
        write=None if args.dry_run else lambda book_id, isbn, subtitle: _write_subtitle(pool, book_id, isbn, subtitle),
        on_progress=progress,
    )
    print("Subtitle backfill: updated {updated}, skipped {skipped}, failed {failed}.".format(**counts))


if __name__ == "__main__":
    main()
