"""Sorting utilities for books following librarian best practices.

This module provides sorting functions that follow library science principles
for organising book collections.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union, cast


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


def _parse_author_name(author: str) -> Tuple[str, str]:
    """Parse author name into last name and first name for sorting.

    Handles various formats:
    - "Last, First" (standard library format)
    - "First Last" (common format)
    - Multiple authors (uses first author)

    Args:
        author: Author name string.

    Returns:
        Tuple of (last_name, first_name) for sorting, both lowercased.
    """
    if not author:
        return ("", "")

    # Handle multiple authors - use first author
    # Split on comma first to handle "Last, First" format
    if "," in author:
        # Could be "Last, First" or "Last, First and Other"
        parts = author.split(",", 1)
        first_part = parts[0].strip()
        # Check if there's more after the comma
        if len(parts) > 1:
            second_part = parts[1].strip()
            # Remove "and" or "&" if present (for multiple authors)
            second_part = second_part.split(" and ")[0].split(" & ")[0].strip()
            # If second part exists, it's "Last, First" format
            if second_part:
                return (first_part.lower(), second_part.lower())
        # Just "Last," format
        return (first_part.lower(), "")

    # No comma - assume "First Last" format
    # Remove "and" or "&" for multiple authors
    first_author = author.split(" and ")[0].split(" & ")[0].strip()
    # Split on last space
    parts = first_author.rsplit(" ", 1)
    if len(parts) == 2:
        return (parts[1].lower(), parts[0].lower())
    # Single word - treat as last name
    return (first_author.lower(), "")


def sort_by_author(
    books: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
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
        author = book.get("author", "") or ""
        last_name, first_name = _parse_author_name(author)
        title = _normalise_title_for_sort(book.get("title", "") or "")
        return (last_name, first_name, title)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_title(
    books: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
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
        last_name, first_name = _parse_author_name(author)
        return (title, last_name, first_name)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_year(
    books: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
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


def sort_by_dewey_decimal(
    books: List[Dict[str, Any]], reverse: bool = False
) -> List[Dict[str, Any]]:
    """Sort books by Dewey Decimal Classification.

    Groups books by subject matter. Secondary sort: by title within same classification.

    Args:
        books: List of book dictionaries.
        reverse: If True, sort in reverse order.

    Returns:
        Sorted list of books.
    """

    def sort_key(book: Dict[str, Any]) -> Tuple[float, str]:
        ddc = book.get("dewey_decimal") or ""
        if ddc:
            try:
                # Convert to float for proper numeric sorting
                ddc_float = float(ddc)
            except (ValueError, TypeError):
                ddc_float = 9999.0  # Put unclassified at end
        else:
            ddc_float = 9999.0  # Put unclassified at end
        title = _normalise_title_for_sort(book.get("title", "") or "")
        return (ddc_float, title)

    return sorted(books, key=sort_key, reverse=reverse)


def sort_by_date_added(
    books: List[Dict[str, Any]], reverse: bool = True
) -> List[Dict[str, Any]]:
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
    reading_records: List[Dict[str, Any]],
    reverse: bool = True,
) -> List[Dict[str, Any]]:
    """Sort books by most recent reading date.

    Uses the start_date of the most recent reading record. If never read,
    falls back to created_at. Defaults to reverse=True to show most recently
    read first.

    Args:
        books: List of book dictionaries.
        reading_records: List of reading record dictionaries.
        reverse: If True, sort most recent first.

    Returns:
        Sorted list of books.
    """
    # Create mapping of book_id to most recent reading record
    records_by_book: Dict[int, Dict[str, Any]] = {}
    for record in reading_records:
        book_id = record.get("book_id")
        if not book_id:
            continue
        if book_id not in records_by_book:
            records_by_book[book_id] = record
        else:
            # Keep the most recent (latest start_date)
            existing_date = records_by_book[book_id].get("start_date", "")
            new_date = record.get("start_date", "")
            if new_date > existing_date:
                records_by_book[book_id] = record

    def sort_key(book: Dict[str, Any]) -> str:
        book_id = book.get("id")
        if book_id and book_id in records_by_book:
            return records_by_book[book_id].get("start_date", "") or ""
        return book.get("created_at", "") or ""

    return sorted(books, key=sort_key, reverse=reverse)


# Type alias for sort functions
SortFunction = Union[
    Callable[[List[Dict[str, Any]], bool], List[Dict[str, Any]]],
    Callable[[List[Dict[str, Any]], List[Dict[str, Any]], bool], List[Dict[str, Any]]],
]

SORT_OPTIONS: Dict[str, Tuple[str, SortFunction]] = {
    "reading_date": ("Most Recently Read", sort_by_reading_date),
    "date_added": ("Date Added", sort_by_date_added),
    "author": ("Author (A-Z)", sort_by_author),
    "title": ("Title (A-Z)", sort_by_title),
    "year": ("Publication Year", sort_by_year),
    "dewey": ("Dewey Decimal", sort_by_dewey_decimal),
}


def sort_books(
    books: List[Dict[str, Any]],
    sort_by: str = "reading_date",
    reading_records: Optional[List[Dict[str, Any]]] = None,
    reverse: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    """Sort books using the specified method.

    Args:
        books: List of book dictionaries to sort.
        sort_by: Sort method key (one of: reading_date, date_added, author, title, year, dewey).
        reading_records: Optional list of reading records (required for reading_date sort).
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

    # Special handling for reading_date which needs reading_records
    if sort_by == "reading_date":
        if reading_records is None:
            reading_records = []
        # Type narrowing: we know this is sort_by_reading_date which takes 3 args
        reading_date_func = cast(
            Callable[
                [List[Dict[str, Any]], List[Dict[str, Any]], bool], List[Dict[str, Any]]
            ],
            sort_func,
        )
        return reading_date_func(books, reading_records, reverse)  # type: ignore[call-arg]

    # Type narrowing: we know other sort functions take 2 args (books, reverse)
    standard_func = cast(
        Callable[[List[Dict[str, Any]], bool], List[Dict[str, Any]]],
        sort_func,
    )
    return standard_func(books, reverse)  # type: ignore[call-arg]
