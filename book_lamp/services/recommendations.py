"""Pure logic for generating AI book recommendations.

This module is the orchestration layer: it reads the user's reading history,
decides whether fresh recommendations are needed, calls the LLM adapter, and
persists the results to the storage backend.

Following the book-lamp architecture philosophy this module is kept *pure*:
it receives all its dependencies (storage, llm_client) as arguments rather than
importing them directly, making it trivially testable without real API calls.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# How many days before the cached recommendations are considered stale.
CACHE_TTL_DAYS = 7

# Minimum rating a book must have to be used as an input.
MIN_RATING = 4

# Number of recent liked books to feed into the prompt.
MAX_LIKED_BOOKS = 5


def _is_cache_stale(recommendations: List[Dict[str, Any]]) -> bool:
    """Return True if the recommendations are missing or older than CACHE_TTL_DAYS."""
    if not recommendations:
        return True

    # All rows share the same created_at from save_recommendations, so check the first.
    created_at_str = recommendations[0].get("created_at")
    if not created_at_str:
        return True

    try:
        created_at = datetime.fromisoformat(created_at_str)
        age_days = (datetime.now(timezone.utc) - created_at).days
        return age_days >= CACHE_TTL_DAYS
    except (ValueError, TypeError):
        return True


def get_liked_books(storage: Any) -> List[Dict[str, Any]]:
    """Return books with high ratings from completed reading records (pure)."""
    all_books = storage.get_all_books()
    all_records = storage.get_reading_records()

    book_map = {b["id"]: b for b in all_books}

    liked: List[Dict[str, Any]] = []
    for record in all_records:
        if record.get("status") != "Completed":
            continue
        rating = record.get("rating", 0)
        if isinstance(rating, str):
            try:
                rating = int(float(rating))
            except (ValueError, TypeError):
                rating = 0
        if rating < MIN_RATING:
            continue

        book = book_map.get(record["book_id"])
        if book:
            liked.append(
                {
                    "title": book["title"],
                    "author": book.get("author", ""),
                    "end_date": record.get("end_date") or "",
                }
            )

    # Sort by end_date descending to get the most recent reads first.
    liked.sort(key=lambda x: x["end_date"], reverse=True)
    return liked[:MAX_LIKED_BOOKS]


def get_all_known_titles(storage: Any) -> List[str]:
    """Return titles of every book the user has already read or intends to read (pure)."""
    return list(b["title"] for b in storage.get_all_books())


def refresh_recommendations(
    storage: Any, llm_client: Any
) -> Optional[List[Dict[str, Any]]]:
    """Regenerate and cache AI recommendations, returning the new list.

    Returns None if there are not enough liked books to generate useful
    recommendations, or if the LLM call fails.
    """
    liked_books = get_liked_books(storage)
    if not liked_books:
        logger.info("No highly-rated books found; skipping recommendation generation.")
        return None

    existing_titles = get_all_known_titles(storage)
    recs = llm_client.generate_recommendations(liked_books, existing_titles)

    if not recs:
        logger.warning("LLM returned empty recommendations.")
        return None

    storage.save_recommendations(recs)
    logger.info(f"Saved {len(recs)} fresh recommendation(s).")
    return list(recs)


def get_or_refresh_recommendations(
    storage: Any, llm_client: Any
) -> List[Dict[str, Any]]:
    """Return cached recommendations, regenerating them if stale.

    This is the primary entry point for the Flask route.
    """
    cached: List[Dict[str, Any]] = list(storage.get_recommendations())
    if not _is_cache_stale(cached):
        logger.debug("Returning fresh cached recommendations.")
        return cached

    logger.info("Recommendations are stale or missing — refreshing.")
    fresh = refresh_recommendations(storage, llm_client)
    return fresh if fresh is not None else cached
