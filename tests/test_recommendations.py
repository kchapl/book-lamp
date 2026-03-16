"""Tests for the recommendation service logic."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from book_lamp.services.recommendations import (
    CACHE_TTL_DAYS,
    _is_cache_stale,
    get_liked_books,
    get_or_refresh_recommendations,
    refresh_recommendations,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_storage(books=None, records=None, cached_recs=None):
    storage = MagicMock()
    storage.get_all_books.return_value = books or []
    storage.get_reading_records.return_value = records or []
    storage.get_recommendations.return_value = cached_recs or []
    return storage


def _make_llm(recs=None):
    llm = MagicMock()
    llm.generate_recommendations.return_value = recs or []
    return llm


def _fresh_ts():
    return datetime.now(timezone.utc).isoformat()


def _stale_ts():
    return (datetime.now(timezone.utc) - timedelta(days=CACHE_TTL_DAYS + 1)).isoformat()


# ---------------------------------------------------------------------------
# _is_cache_stale
# ---------------------------------------------------------------------------


def test_stale_when_empty():
    assert _is_cache_stale([]) is True


def test_stale_when_old_timestamp():
    recs = [{"created_at": _stale_ts()}]
    assert _is_cache_stale(recs) is True


def test_fresh_when_recent_timestamp():
    recs = [{"created_at": _fresh_ts()}]
    assert _is_cache_stale(recs) is False


def test_stale_when_created_at_missing():
    assert _is_cache_stale([{"created_at": None}]) is True


# ---------------------------------------------------------------------------
# get_liked_books
# ---------------------------------------------------------------------------


def test_get_liked_books_filters_by_rating():
    books = [{"id": 1, "title": "Dune", "author": "Herbert"}]
    records = [
        {"book_id": 1, "status": "Completed", "rating": 5, "end_date": "2024-01-01"},
        {"book_id": 1, "status": "Completed", "rating": 2, "end_date": "2023-01-01"},
    ]
    storage = _make_storage(books=books, records=records)
    liked = get_liked_books(storage)
    assert len(liked) == 1
    assert liked[0]["title"] == "Dune"


def test_get_liked_books_only_completed():
    books = [{"id": 1, "title": "Dune", "author": "Herbert"}]
    records = [
        {"book_id": 1, "status": "In Progress", "rating": 5, "end_date": ""},
    ]
    storage = _make_storage(books=books, records=records)
    assert get_liked_books(storage) == []


def test_get_liked_books_sorted_by_end_date():
    books = [
        {"id": 1, "title": "Book A", "author": "Author"},
        {"id": 2, "title": "Book B", "author": "Author"},
    ]
    records = [
        {"book_id": 1, "status": "Completed", "rating": 5, "end_date": "2023-01-01"},
        {"book_id": 2, "status": "Completed", "rating": 4, "end_date": "2024-06-01"},
    ]
    storage = _make_storage(books=books, records=records)
    liked = get_liked_books(storage)
    assert liked[0]["title"] == "Book B"  # Most recent first


# ---------------------------------------------------------------------------
# refresh_recommendations
# ---------------------------------------------------------------------------


def test_refresh_returns_none_when_no_liked_books():
    storage = _make_storage()
    llm = _make_llm()
    result = refresh_recommendations(storage, llm)
    assert result is None
    llm.generate_recommendations.assert_not_called()


def test_refresh_returns_none_when_llm_returns_empty():
    books = [{"id": 1, "title": "Dune", "author": "Herbert"}]
    records = [
        {"book_id": 1, "status": "Completed", "rating": 5, "end_date": "2024-01-01"}
    ]
    storage = _make_storage(books=books, records=records)
    llm = _make_llm(recs=[])
    result = refresh_recommendations(storage, llm)
    assert result is None
    storage.save_recommendations.assert_not_called()


def test_refresh_saves_and_returns_recs():
    books = [{"id": 1, "title": "Dune", "author": "Herbert"}]
    records = [
        {"book_id": 1, "status": "Completed", "rating": 5, "end_date": "2024-01-01"}
    ]
    new_recs = [
        {
            "title": "Foundation",
            "author": "Asimov",
            "isbn13": "9780553293357",
            "justification": "Test",
        }
    ]
    storage = _make_storage(books=books, records=records)
    llm = _make_llm(recs=new_recs)
    result = refresh_recommendations(storage, llm)
    assert result == new_recs
    storage.save_recommendations.assert_called_once_with(new_recs)


# ---------------------------------------------------------------------------
# get_or_refresh_recommendations
# ---------------------------------------------------------------------------


def test_returns_cache_when_fresh():
    cached = [{"title": "Foundation", "created_at": _fresh_ts()}]
    storage = _make_storage(cached_recs=cached)
    llm = _make_llm()
    result = get_or_refresh_recommendations(storage, llm)
    assert result == cached
    llm.generate_recommendations.assert_not_called()


def test_refreshes_when_stale():
    old_recs = [{"title": "Old Book", "created_at": _stale_ts()}]
    books = [{"id": 1, "title": "Dune", "author": "Herbert"}]
    records = [
        {"book_id": 1, "status": "Completed", "rating": 5, "end_date": "2024-01-01"}
    ]
    new_recs = [
        {
            "title": "Foundation",
            "author": "Asimov",
            "isbn13": "9780553293357",
            "justification": "Great read",
        }
    ]

    storage = _make_storage(books=books, records=records, cached_recs=old_recs)
    llm = _make_llm(recs=new_recs)
    result = get_or_refresh_recommendations(storage, llm)
    assert result == new_recs


def test_returns_stale_cache_when_refresh_fails():
    """If the LLM fails, we should still return the old cache rather than nothing."""
    old_recs = [{"title": "Old Book", "created_at": _stale_ts()}]
    storage = _make_storage(cached_recs=old_recs)
    llm = _make_llm(recs=[])  # LLM returns nothing
    result = get_or_refresh_recommendations(storage, llm)
    assert result == old_recs
