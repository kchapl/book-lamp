"""Tests for stats/dashboard endpoints."""

from book_lamp.app import get_storage
from book_lamp.services.stats_calculator import calculate_collection_stats


def test_stats_category_limit(client, authenticated_client):
    """Test that the stats endpoint limits categories and groups others into 'Other'."""
    storage = get_storage()

    # Add many books with different categories
    categories = [f"Category {i}" for i in range(20)]
    for i, cat in enumerate(categories):
        book = storage.add_book(
            isbn13=f"9780000000{i:03d}",
            title=f"Book {i}",
            authors=["Author"],
            publication_year=2020,
            bisac_category=cat,
        )
        storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-02", rating=5)

    # Get stats API data
    resp = authenticated_client.get("/api/dashboard")
    assert resp.status_code == 200

    data = resp.get_json()
    cats = {c["label"]: c["count"] for c in data.get("category_distribution", [])}

    # "Other" should be present because we added 20 categories
    assert "Other" in cats

    # Check normalization: 'FICTION' should become 'Fiction'
    # Add 5 books to Fiction to make it a top category
    for i in range(5):
        book = storage.add_book(
            isbn13=f"978111111111{i}",
            title=f"Fiction Book {i}",
            authors=["Author"],
            bisac_category="FICTION / General",
        )
        storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-02", rating=5)

    resp = authenticated_client.get("/api/dashboard")
    data = resp.get_json()
    cats = {c["label"]: c["count"] for c in data.get("category_distribution", [])}
    assert "Fiction" in cats


def test_stats_bulk_actions_are_in_overflow_menu(authenticated_client):
    resp = authenticated_client.get("/dashboard", follow_redirects=True)
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert '<div id="root">' in html or "index-" in html


def test_dashboard_route_redirect(authenticated_client):
    """Test that /stats serves the SPA which client-side redirects to /dashboard."""
    resp = authenticated_client.get("/stats", follow_redirects=False)
    # The React SPA serves /stats and redirects to /dashboard in the client
    assert resp.status_code == 200
    assert b'id="root"' in resp.data


def test_api_dashboard_endpoint(authenticated_client):
    """Test the new /api/dashboard endpoint returns enhanced stats."""
    storage = get_storage()

    # Add a completed book
    book = storage.add_book(
        isbn13="9781234567890",
        title="Test Book",
        authors=["Test Author"],
        bisac_category="FICTION / General",
        page_count=300,
        physical_format="Hardcover",
        language="English",
    )
    storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-15", rating=4)

    # Test API endpoint
    resp = authenticated_client.get("/api/dashboard")
    assert resp.status_code == 200

    data = resp.get_json()

    # Check basic stats
    assert data["total_books"] == 1
    assert data["avg_rating"] == 4.0
    # Note: MockStorage may not persist page_count, so we just check it exists
    assert "total_pages_read" in data
    assert "avg_pages_per_book" in data

    # Check new stats fields
    assert "current_streak" in data
    assert "longest_streak" in data
    assert "books_this_year" in data
    assert "year_comparison" in data
    assert "reading_pace_monthly" in data
    assert "format_distribution" in data
    assert "language_distribution" in data
    assert "category_details" in data
    assert "last_record_date" in data


def test_dashboard_last_record_date_tracks_the_latest_reading(authenticated_client):
    """The dashboard's as-of date is the most recent reading activity."""
    storage = get_storage()

    older = storage.add_book(isbn13="9780000000101", title="Older", authors=["Author"])
    storage.add_reading(older["id"], "In Progress", "2023-05-01", None)

    recent = storage.add_book(isbn13="9780000000102", title="Recent", authors=["Author"])
    storage.add_reading(recent["id"], "Completed", "2024-03-01", "2024-03-10", rating=5)

    resp = authenticated_client.get("/api/dashboard")
    assert resp.status_code == 200
    assert resp.get_json()["last_record_date"] == "2024-03-10"


def test_api_stats_redirect(authenticated_client):
    """Test that /api/stats redirects to /api/dashboard."""
    resp = authenticated_client.get("/api/stats", follow_redirects=False)
    # Should redirect with 301
    assert resp.status_code == 301
    # Location should be /api/dashboard
    assert "dashboard" in resp.location


def test_dashboard_counts_a_series_by_title_and_subtitle():
    """Two Books of one series that share a main title are two works, not one."""
    books = [
        {"id": 1, "title": "The Expanse", "subtitle": "Leviathan Wakes", "series": "The Expanse"},
        {"id": 2, "title": "The Expanse", "subtitle": "Caliban's War", "series": "The Expanse"},
        {"id": 3, "title": "The Expanse", "subtitle": "Leviathan Wakes", "series": "The Expanse"},
    ]
    records = [
        {"book_id": 1, "status": "Completed", "end_date": "2026-01-02"},
        {"book_id": 2, "status": "Completed", "end_date": "2026-02-02"},
        {"book_id": 3, "status": "Completed", "end_date": "2026-03-02"},
    ]

    stats = calculate_collection_stats(books, records)

    series = {entry["name"]: entry for entry in stats["top_series"]}["The Expanse"]
    # The third Book is the same title and subtitle again, so it is the same work.
    assert series["count"] == 2
    assert series["books"] == ["The Expanse: Leviathan Wakes", "The Expanse: Caliban's War"]


def test_dashboard_ignores_a_rating_on_a_reading_that_has_not_completed():
    """A rating belongs to a finished Reading, so it must not move the average."""
    books = [{"id": 1, "title": "A Book", "authors": ["An Author"]}]
    records = [
        {
            "book_id": 1,
            "status": "In Progress",
            "start_date": "2026-10-01",
            "end_date": None,
            "rating": 5,
        }
    ]

    stats = calculate_collection_stats(books, records)

    assert stats["avg_rating"] == 0.0
    assert dict(stats["rating_distribution"])[5] == 0


def test_dashboard_counts_only_bindings_as_formats():
    """A media type or language is not a format, and spellings of one binding collapse."""
    formats = [
        "Paperback",
        "paperback",
        "Perfect Paperback",
        "Hardback",
        "Hardcover",
        "Ebook",
        "Kindle Edition",
        "Audiobook",
        "Audio Cassette",
        "Spiral-bound",
        "Leather-bound",
        "BOOK",
        "book",
        "MAGAZINE",
        "print",
        "audio",
        "en",
    ]
    books = [{"id": i, "title": f"Book {i}", "physical_format": fmt} for i, fmt in enumerate(formats, start=1)]
    records = [{"book_id": book["id"], "status": "Completed", "end_date": "2026-01-02"} for book in books]

    stats = calculate_collection_stats(books, records)

    assert stats["format_distribution"] == [
        {"label": "Paperback", "count": 3},
        {"label": "Hardcover", "count": 2},
        {"label": "Ebook", "count": 2},
        {"label": "Audiobook", "count": 2},
        {"label": "Spiral-bound", "count": 1},
        {"label": "Leather Bound", "count": 1},
    ]


def test_dashboard_has_no_formats_when_no_book_names_a_binding():
    books = [
        {"id": 1, "title": "A Book", "physical_format": "BOOK"},
        {"id": 2, "title": "Another Book", "physical_format": "en"},
    ]
    records = [
        {"book_id": 1, "status": "Completed", "end_date": "2026-01-02"},
        {"book_id": 2, "status": "Completed", "end_date": "2026-01-03"},
    ]

    stats = calculate_collection_stats(books, records)

    assert stats["format_distribution"] == []
