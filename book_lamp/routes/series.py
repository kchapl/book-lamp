"""Series pages: the Books that share a series name, in reading order.

A series is not a record in storage. The name is free text on each Book, so a
series page is derived from the Books carrying the same normalised name — the
way the author page is derived from author links, and for the same reason: the
Books are the source, and a second copy would drift.

The name is matched after flattening case and runs of whitespace, so a Book
entered as "The  Expanse" belongs to the same series as one entered as "The
Expanse". Publication year orders the page, because that is the order a reader
reads them in; a Book with no year sorts last rather than first, since an
unknown year is not evidence of being the earliest.
"""

from typing import Any, Dict, List

from flask import Blueprint, jsonify

from book_lamp.middleware.auth import authorisation_required
from book_lamp.services.storage_factory import get_storage
from book_lamp.utils.reading_status import READING_STATUSES, latest_reading_by_book

series_bp = Blueprint("series", __name__)


def normalise_series_name(name: str) -> str:
    """The key a series is identified by: case and whitespace flattened."""
    return " ".join(name.split()).casefold()


def _publication_order(book: Dict[str, Any]) -> tuple[bool, int, str]:
    """Order Books by publication year, with an unknown year after a known one."""
    raw_year = book.get("publication_year")
    try:
        year = int(raw_year) if raw_year else None
    except (TypeError, ValueError):
        year = None
    return (year is None, year or 0, str(book.get("title") or "").casefold())


@series_bp.route("/api/series/<path:series_slug>", methods=["GET"])
@authorisation_required
def api_series_page(series_slug: str):
    """Every Book in the reader's books carrying this series name, in reading order."""
    storage = get_storage()
    wanted = normalise_series_name(series_slug)

    in_series = [
        book
        for book in storage.get_all_books()
        if book.get("series") and normalise_series_name(str(book["series"])) == wanted
    ]
    if not in_series:
        return jsonify({"error": "Series not found"}), 404

    # Every Book in the series belongs on the page, including ones with no
    # Reading: with_reading_status drops those, which is right for the Reading
    # Log and wrong here, where an unread volume is the next thing to pick up.
    latest = latest_reading_by_book(storage.get_readings())
    reading_list_ids = {item["book_id"] for item in storage.get_reading_list()}

    books: List[Dict[str, Any]] = []
    for book in sorted(in_series, key=_publication_order):
        record = latest.get(book["id"])
        status = record.get("status") if record else None
        books.append(
            {
                **book,
                "latest_status": status if status in READING_STATUSES else None,
                "in_reading_list": book["id"] in reading_list_ids,
            }
        )

    # Spellings can differ in a reading log by case alone; naming the page after
    # the alphabetically first one keeps the answer the same on every request.
    series_name = sorted({" ".join(str(book["series"]).split()) for book in in_series})[0]

    return jsonify({"series_name": series_name, "books": books})
