"""Search service for book data.

This module provides search functionality across book and reading record fields.
Supports both free text and regex pattern matching.
"""

import re
from typing import Any, Dict, List


def calculate_relevance_score(
    book: Dict[str, Any],
    reading_records: List[Dict[str, Any]],
    query: str,
    is_regex: bool,
) -> float:
    """Calculate relevance score for a book based on search query.

    Args:
        book: Book dictionary with fields to search.
        reading_records: List of reading records for this book.
        query: Search query string.
        is_regex: Whether the query is a regex pattern.

    Returns:
        Relevance score (higher is more relevant).
    """
    score = 0.0

    # Field weights (higher weight = more important match)
    weights = {
        "title": 10.0,
        "author": 8.0,
        "isbn13": 7.0,
        "series": 6.0,
        "publisher": 4.0,
        "description": 2.0,
        "dewey_decimal": 3.0,
        "publication_year": 3.0,
        "id": 10.0,  # strong match if user searches for specific ID
        "created_at": 1.0,
        # Reading record fields
        "status": 5.0,
        "rating": 4.0,
        "dates": 3.0,  # start_date and end_date
    }

    def matches(text: str, pattern: str, is_regex_match: bool) -> bool:
        """Check if text matches the pattern."""
        if not text:
            return False

        text_str = str(text)

        if not is_regex_match:
            try:
                # Escape the pattern so literal characters aren't interpreted as regex
                search_pattern = re.escape(pattern)
                return bool(re.search(search_pattern, text_str, re.IGNORECASE))
            except Exception:
                # Should not happen with re.escape, but safe fallback
                return pattern.lower() in text_str.lower()

        # Regex mode
        try:
            # We do NOT escape the pattern here because the user explicitly requested regex mode.
            # This allows patterns like '.*' or '^Title' to work as expected.
            return bool(re.search(pattern, text_str, re.IGNORECASE))
        except re.error:
            # Invalid regex, fall back to literal match
            return pattern.lower() in text_str.lower()

    # Search book fields
    for field, weight in weights.items():
        if field in ["status", "rating", "dates"]:
            continue  # These are in reading records

        value = book.get(field)
        if value and matches(str(value), query, is_regex):
            score += weight
            # Bonus for exact match
            if str(value).lower() == query.lower():
                score += weight * 0.5

    # Search reading record fields
    for record in reading_records:
        if matches(record.get("status", ""), query, is_regex):
            score += weights["status"]
        if record.get("rating") and matches(str(record["rating"]), query, is_regex):
            score += weights["rating"]
        if matches(record.get("start_date", ""), query, is_regex):
            score += weights["dates"]
        if matches(record.get("end_date", ""), query, is_regex):
            score += weights["dates"]

    return score


def search_books(
    all_books: List[Dict[str, Any]],
    all_records: List[Dict[str, Any]],
    query: str,
    is_regex: bool = False,
) -> List[Dict[str, Any]]:
    """Search across all book data fields.

    Args:
        all_books: List of all books.
        all_records: List of all reading records.
        query: Search query (free text or regex).
        is_regex: Whether to treat query as a regex pattern.

    Returns:
        List of matching books with reading_records attached, sorted by relevance.
    """
    if not query or not query.strip():
        return []

    query = query.strip()

    # Attach reading records to books and calculate scores
    results = []
    for book in all_books:
        book_records = [r for r in all_records if r["book_id"] == book["id"]]
        score = calculate_relevance_score(book, book_records, query, is_regex)

        if score > 0:
            # Create a copy to avoid mutating the original
            book_copy = book.copy()
            book_copy["reading_records"] = book_records
            book_copy["_relevance_score"] = score
            results.append(book_copy)

    # Sort by relevance score (descending)
    results.sort(key=lambda b: b["_relevance_score"], reverse=True)

    return results
