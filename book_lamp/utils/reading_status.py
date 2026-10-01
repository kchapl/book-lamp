"""Which Reading Record currently represents a Book.

A Book accumulates Reading Records as it is started, abandoned and restarted.
Exactly one record at a time represents the Book. This module owns the rule that
decides which, so every caller reaches the same answer whatever order the
storage adapter happened to return its records in.
"""

import logging
from typing import Any, Dict, Iterable, List, Mapping, Optional

logger = logging.getLogger("book_lamp")

#: The statuses that give a Book a Reading Status. A Book whose current record
#: sits outside this set (a Reading List entry, say) is not in the Reading Log.
READING_STATUSES = ("In Progress", "Completed", "Abandoned")


def _as_identifier(value: Any) -> Optional[int]:
    """Normalise an identifier to a positive int, or None when unusable."""
    try:
        identifier = int(value)
    except (TypeError, ValueError):
        return None
    return identifier if identifier > 0 else None


def _order_key(record: Mapping[str, Any], record_id: int) -> tuple[str, int]:
    """Order records by when they started, then by the order they were added."""
    return (str(record.get("start_date") or ""), record_id)


def latest_record_by_book(
    records: Iterable[Mapping[str, Any]],
) -> Dict[int, Dict[str, Any]]:
    """Map each Book id to the Reading Record that currently represents it.

    The current record is the one that started latest; when two started on the
    same date, the one added last wins. The answer deliberately does not depend
    on the order ``records`` arrives in, so the adapters agree with each other
    even though one returns records newest-first and the other in insertion
    order.

    Records whose ``book_id`` or ``id`` is not a usable identifier are skipped,
    since they cannot be attributed or ordered.

    Returns:
        A dict keyed by Book id, holding the raw Reading Record dicts.
    """
    latest: Dict[int, Dict[str, Any]] = {}
    latest_keys: Dict[int, tuple[str, int]] = {}

    for record in records:
        book_id = _as_identifier(record.get("book_id"))
        record_id = _as_identifier(record.get("id"))
        if book_id is None or record_id is None:
            logger.debug(
                "Skipping Reading Record with unusable identifiers: book_id=%r, id=%r",
                record.get("book_id"),
                record.get("id"),
            )
            continue

        key = _order_key(record, record_id)
        incumbent = latest_keys.get(book_id)
        if incumbent is None or key > incumbent:
            latest[book_id] = dict(record)
            latest_keys[book_id] = key

    return latest


def with_reading_status(
    books: Iterable[Mapping[str, Any]],
    records: Iterable[Mapping[str, Any]],
) -> List[Dict[str, Any]]:
    """Books that have a Reading Status, each carrying ``latest_status``.

    Books with no Reading Record, and books whose current record sits outside
    :data:`READING_STATUSES`, are omitted.

    The given books are left untouched: each result is a copy carrying one extra
    key, so this is safe to call on a storage adapter's own data. Results keep
    the order the books were given in.

    Returns:
        New book dicts.
    """
    latest = latest_record_by_book(records)
    books_with_status: List[Dict[str, Any]] = []

    for book in books:
        book_id = _as_identifier(book.get("id"))
        if book_id is None:
            continue

        record = latest.get(book_id)
        if record is None:
            continue

        status = record.get("status")
        if status not in READING_STATUSES:
            continue

        books_with_status.append({**book, "latest_status": status})

    return books_with_status
