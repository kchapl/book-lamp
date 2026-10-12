"""The rules a Reading must satisfy when it is written.

A Reading has two ends: the date it started and the date it ended. A status that
says the Reading has stopped — Completed or Abandoned — therefore cannot be
written without an end date. This module owns that rule, so the API, the
importers and the MCP tools all reach the same answer.
"""

from typing import Any, Dict, Iterable, List, Mapping, Optional

#: Statuses that end a Reading. A Reading in one of these has stopped.
ENDING_STATUSES = ("Completed", "Abandoned")


class ReadingEndsWithoutADate(ValueError):
    """Raised when a Reading is given an ending status but no end date."""


def end_date_problem(status: str, end_date: Optional[str]) -> Optional[str]:
    """Return why this status may not be written with this end date.

    Returns:
        A sentence naming the problem, or ``None`` when the pair is writable.
    """
    if status in ENDING_STATUSES and not end_date:
        return f"an end date is required when a Reading is {status}"
    return None


def require_end_date(status: str, end_date: Optional[str]) -> None:
    """Raise :class:`ReadingEndsWithoutADate` when the pair breaks the rule."""
    problem = end_date_problem(status, end_date)
    if problem:
        raise ReadingEndsWithoutADate(problem)


#: The orders the Reading Log offers, as the page's `sort` parameter names them.
LOG_SORTS = ("date_desc", "date_asc", "rating_desc", "title")


def filter_reading_log(
    readings: Iterable[Mapping[str, Any]],
    status: Optional[str] = None,
    min_rating: Optional[int] = None,
    year: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """The Reading Log narrowed by the reader's filters.

    The parameters mirror the query string the Reading Log page sends, so the
    page and the MCP tools answer the same question the same way.

    Args:
        readings: Readings as the storage adapters hand them over.
        status: Keep only this Reading Status.
        min_rating: Keep only Readings rated at least this.
        year: Keep Readings that ended in this year, or — when a Reading has no
            end date — those that started in it.

    Returns:
        New dicts, in the order they were given.
    """
    kept: List[Dict[str, Any]] = []
    for reading in readings:
        if status and reading.get("status") != status:
            continue

        if min_rating is not None and int(reading.get("rating") or 0) < min_rating:
            continue

        if year:
            end_date = str(reading.get("end_date") or "")
            start_date = str(reading.get("start_date") or "")
            in_year = (end_date[:4] == year) if end_date else (start_date[:4] == year)
            if not in_year:
                continue

        kept.append(dict(reading))

    return kept


def sort_reading_log(
    readings: Iterable[Mapping[str, Any]],
    sort_by: str = "date_desc",
) -> List[Dict[str, Any]]:
    """Order the Reading Log, keyed the way the page's `sort` parameter is.

    An unknown order is left alone rather than raising: the page falls back to
    its default when the parameter is unrecognised.
    """
    ordered = [dict(reading) for reading in readings]

    if sort_by == "date_desc":
        ordered.sort(key=lambda r: str(r.get("end_date") or r.get("start_date") or ""), reverse=True)
    elif sort_by == "date_asc":
        ordered.sort(key=lambda r: str(r.get("end_date") or r.get("start_date") or ""))
    elif sort_by == "rating_desc":
        ordered.sort(key=lambda r: int(r.get("rating") or 0), reverse=True)
    elif sort_by == "title":
        ordered.sort(key=lambda r: str(r.get("book_title") or "").lower())

    return ordered
