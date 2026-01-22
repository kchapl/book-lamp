"""Search service for book data.

This module provides search functionality across book and reading record fields.
Supports free text search.
"""

import re
from typing import Any, Dict, List


def calculate_relevance_score(
    book: Dict[str, Any],
    reading_records: List[Dict[str, Any]],
    query: str,
) -> float:
    """Calculate relevance score for a book based on search query.

    Args:
        book: Book dictionary with fields to search.
        reading_records: List of reading records for this book.
        query: Search query string.

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

    def matches(text: str, pattern: str) -> bool:
        """Check if text matches the pattern."""
        if not text:
            return False

        text_str = str(text)

        # Always escape the pattern to treat it as a literal string.
        search_pattern = re.escape(pattern)
        return bool(re.search(search_pattern, text_str, re.IGNORECASE))

    # Search book fields
    for field, weight in weights.items():
        if field in ["status", "rating", "dates"]:
            continue  # These are in reading records

        if field == "author":
            # Search both the legacy field and individual authors
            authors = book.get("authors", [])
            legacy_author = book.get("author")

            matches_found = False
            if legacy_author and matches(str(legacy_author), query):
                score += weight
                matches_found = True

            for author in authors:
                if matches(str(author), query):
                    score += weight
                    matches_found = True

            # Bonus for exact match on any author
            if matches_found:
                if any(str(a).lower() == query.lower() for a in authors) or (
                    legacy_author and str(legacy_author).lower() == query.lower()
                ):
                    score += weight * 0.5
            continue

        value = book.get(field)
        if value and matches(str(value), query):
            score += weight
            # Bonus for exact match
            if str(value).lower() == query.lower():
                score += weight * 0.5

    # Search reading record fields
    for record in reading_records:
        if matches(record.get("status", ""), query):
            score += weights["status"]
        if record.get("rating") and matches(str(record["rating"]), query):
            score += weights["rating"]
        if matches(record.get("start_date", ""), query):
            score += weights["dates"]
        if matches(record.get("end_date", ""), query):
            score += weights["dates"]

    return score


def search_books(
    all_books: List[Dict[str, Any]],
    all_records: List[Dict[str, Any]],
    query: str,
) -> List[Dict[str, Any]]:
    """Search across all book data fields.

    Args:
        all_books: List of all books.
        all_records: List of all reading records.
        query: Search query (free text).

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
        score = calculate_relevance_score(book, book_records, query)

        if score > 0:
            # Create a copy to avoid mutating the original
            book_copy = book.copy()
            book_copy["reading_records"] = book_records
            book_copy["_relevance_score"] = score
            results.append(book_copy)

    # Sort by relevance score (descending)
    results.sort(key=lambda b: b["_relevance_score"], reverse=True)

    return results
