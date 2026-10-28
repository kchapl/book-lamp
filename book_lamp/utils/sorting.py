"""Sorting utilities for books following librarian best practices.

This module provides sorting functions that follow library science principles
for organising books.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast

from book_lamp.utils.authors import sort_key as author_sort_key
from book_lamp.utils.reading_status import latest_reading_by_book


def _normalise_title_for_sort(title: str) -> str:
    """Normalise title for sorting by removing leading articles.

    Removes "The", "A", and "An" from the beginning of titles for sorting
    purposes, while preserving original capitalisation in display.

    Args:
        title: The book title to normalise.

    Returns:
        Title with leading articles removed, lowercased for comparison.
    """
    if not title:
        return ""
    # Remove leading articles (case-insensitive)
    title_lower = title.lower().strip()
    for article in ["the ", "a ", "an "]:
        if title_lower.startswith(article):
            return title_lower[len(article) :]
    return title_lower


def sort_by_author(books: List[Dict[str, Any]], reverse: bool = False) -> List[Dict[str, Any]]:
    """Sort books alphabetically by author (last name, then first name).

    Handles multiple authors by using the first author for primary sort.
    Secondary sort: by title when authors are the same.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort in reverse order.

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> Tuple[str, str, str]:
        authors = book.get("authors", [])
        if authors:
            author = authors[0]
        else:
            author = book.get("author", "") or ""
        last_name, first_name = author_sort_key(author)
        title = _normalise_title_for_sort(book.get("title", "") or "")
        return (last_name, first_name, title)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_title(books: List[Dict[str, Any]], reverse: bool = False) -> List[Dict[str, Any]]:
    """Sort books alphabetically by title.

    Ignores leading articles ("The", "A", "An") for sorting.
    Secondary sort: by author when titles are identical.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort in reverse order.

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> Tuple[str, str, str]:
        title = _normalise_title_for_sort(book.get("title", "") or "")
        author = book.get("author", "") or ""
        last_name, first_name = author_sort_key(author)
        return (title, last_name, first_name)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_year(books: List[Dict[str, Any]], reverse: bool = False) -> List[Dict[str, Any]]:
    """Sort books chronologically by publication year.

    Secondary sort: by title when publication years match.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort newest first (reverse chronological).

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> Tuple[int, str]:
        year = book.get("publication_year")
        if year:
            try:
                year_int = int(year)
            except (ValueError, TypeError):
                year_int = 0
        else:
            year_int = 0
        title = _normalise_title_for_sort(book.get("title", "") or "")
        return (year_int, title)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_category(books: List[Dict[str, Any]], reverse: bool = False) -> List[Dict[str, Any]]:
    """Sort books by BISAC Category.

    Groups books by genre. Secondary sort: by title within same category.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort in reverse order.

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> Tuple[str, str]:
        bisac = book.get("bisac_category") or ""
        title = _normalise_title_for_sort(book.get("title", "") or "")
        return (bisac.lower(), title)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_date_added(books: List[Dict[str, Any]], reverse: bool = True) -> List[Dict[str, Any]]:
    """Sort books by date added (created_at timestamp).

    Defaults to reverse=True to show most recently added first.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort most recent first.

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> str:
        return book.get("created_at", "") or ""

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_reading_date(
    books: List[Dict[str, Any]],
    readings: List[Dict[str, Any]],
    reverse: bool = True,
) -> List[Dict[str, Any]]:
    """Sort books by most recent reading date.

    Uses the start_date of the most recent reading. If never read,
    falls back to created_at. Defaults to reverse=True to show most recently
    read first.

    Args:
        books: List of book dictionaries.
        readings: List of reading dictionaries.
        reverse: If True, sort most recent first.

    Returns:
        Sorted list of books.
    """
    # The same rule the catalogue and the dashboard use, so sort order cannot
    # disagree with the Reading Status a Book is shown with.
    records_by_book = latest_reading_by_book(readings)

    def sort_key(book: Dict[str, Any]) -> str:
        book_id = book.get("id")
        if book_id and book_id in records_by_book:
            start_date = records_by_book[book_id].get("start_date", "")
            # Only use start_date if it's non-empty, otherwise fall back to created_at
            if start_date:
                return str(start_date)
        created_at = book.get("created_at", "")
        return str(created_at) if created_at else ""

    return sorted(books, key=sort_key, reverse=reverse)


# Type alias for sort functions
SortFunction = Union[
    Callable[[List[Dict[str, Any]], bool], List[Dict[str, Any]]],
    Callable[[List[Dict[str, Any]], List[Dict[str, Any]], bool], List[Dict[str, Any]]],
]

SORT_OPTIONS: Dict[str, Tuple[str, SortFunction]] = {
    "reading_date": ("Most recently read", sort_by_reading_date),
    "date_added": ("Date added", sort_by_date_added),
    "author": ("Author (A-Z)", sort_by_author),
    "title": ("Title (A-Z)", sort_by_title),
    "year": ("Publication year", sort_by_year),
    "category": ("Category (A-Z)", sort_by_category),
}


def sort_books(
    books: List[Dict[str, Any]],
    sort_by: str = "reading_date",
    readings: Optional[List[Dict[str, Any]]] = None,
    reverse: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Sort books using the specified method.

    Args:
        books: List of book dictionaries to sort.
        sort_by: Sort method key (one of: reading_date, date_added, author, title, year, category).
        readings: Optional list of readings (required for reading_date sort).
        reverse: Whether to reverse sort order. If None, uses method default.

    Returns:
        Sorted list of books.
    """
    if sort_by not in SORT_OPTIONS:
        sort_by = "reading_date"  # Default fallback

    sort_name, sort_func = SORT_OPTIONS[sort_by]

    # Determine reverse flag
    if reverse is None:
        # Use defaults: reverse=True for date-based sorts, False for alphabetical
        reverse = sort_by in ("reading_date", "date_added", "year")

    # Special handling for reading_date which needs readings
    if sort_by == "reading_date":
        if readings is None:
            readings = []
        # Type narrowing: we know this is sort_by_reading_date which takes 3 args
        reading_date_func = cast(
            Callable[[List[Dict[str, Any]], List[Dict[str, Any]], bool], List[Dict[str, Any]]],
            sort_func,
        )
        return reading_date_func(books, readings, reverse)  # type: ignore[call-arg]

    # Type narrowing: we know other sort functions take 2 args (books, reverse)
    standard_func = cast(
        Callable[[List[Dict[str, Any]], bool], List[Dict[str, Any]]],
        sort_func,
    )
    return standard_func(books, reverse)  # type: ignore[call-arg]
