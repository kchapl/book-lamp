#!/usr/bin/env python
"""Fill the bindings of Books that do not record one (#406).

The Formats panel can only count a binding a Book stores, and most of the
library stores a Google media type, a language code or nothing. This run asks
Open Library and iTunes for the binding of each such Book:

    uv run python scripts/backfill_formats.py --report
    uv run python scripts/backfill_formats.py --dry-run
    uv run python scripts/backfill_formats.py

It never overwrites a Book that already names a binding, and it never stores a
value that names none. Lookups are sequential and a real run can be repeated:
a write keeps the row only while it still holds the format the run read, so a
resumed run picks up the Books that are still empty. ``--delay`` slows the
lookups further when a provider asks for it.
"""

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from book_lamp.services.format_backfill import (  # noqa: E402
    backfill_missing_formats,
    report_formats,
)


def _pool():
    from book_lamp.services.pg_storage import get_pool

    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL is not set")
    return get_pool()


def _all_books(pool) -> List[Dict[str, Any]]:
    with pool.connection() as conn:
        rows = conn.execute(
            "SELECT id, isbn13, physical_format FROM books WHERE btrim(isbn13) <> '' ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def _write_binding(pool, book: Dict[str, Any], isbn13: str, binding: str) -> bool:
    """Store a binding only while the row still holds what the run read."""
    with pool.connection() as conn:
        row = conn.execute(
            """
            UPDATE books SET physical_format = %s
            WHERE id = %s AND isbn13 = %s
              AND COALESCE(NULLIF(btrim(physical_format), ''), '') = %s
            RETURNING id
            """,
            [binding, book["id"], isbn13, str(book.get("physical_format") or "").strip()],
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
        help="look every ISBN up but do not write the bindings",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="seconds to wait between lookups, when a provider asks for it",
    )
    args = parser.parse_args()

    pool = _pool()

    def slow_lookup(isbn: str):
        from book_lamp.services.format_backfill import look_up_binding

        answer = look_up_binding(isbn)
        if args.delay:
            time.sleep(args.delay)
        return answer

    if args.report:
        counts = report_formats(_all_books(pool), lookup=slow_lookup)
        print(
            "Books with a binding: {with_binding}. "
            "A provider can fill: {gained}. "
            "Left empty: {left_empty}. "
            "Failed lookups: {failed}. "
            "Answers from Open Library: {open_library}, iTunes: {itunes}.".format(**counts)
        )
        return

    def progress(done: int, total: int) -> None:
        if done == total or done % 25 == 0:
            print(f"  {done}/{total}", file=sys.stderr)

    def write_binding(book: Dict[str, Any], isbn: str, binding: str) -> bool:
        """Store a binding, or count the write a dry run would make."""
        return True if args.dry_run else _write_binding(pool, book, isbn, binding)

    counts = backfill_missing_formats(
        _all_books(pool),
        lookup=slow_lookup,
        write=write_binding,
        on_progress=progress,
    )
    print("Format backfill: updated {updated}, skipped {skipped}, failed {failed}.".format(**counts))


if __name__ == "__main__":
    main()
