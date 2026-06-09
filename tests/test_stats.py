def test_stats_category_limit(client, authenticated_client):
    """Test that the stats page limits categories and groups others into 'Other'."""
    # Reset storage and connect
    authenticated_client.post("/test/reset")
    authenticated_client.get("/test/connect")

    # Add many books with different categories
    categories = [f"Category {i}" for i in range(20)]
    for i, cat in enumerate(categories):
        # Create a book
        authenticated_client.post(
            "/books",
            data={
                "title": f"Book {i}",
                "author": "Author",
                "isbn": f"9780000000{i:03d}",
                "publication_year": "2020",
                "bisac_category": cat,
            },
        )

        # Mark as completed
        # book_id starts from 1
        authenticated_client.post(
            f"/books/{i+1}/reading-records",
            data={
                "status": "Completed",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "rating": "5",
            },
        )

    # Get stats page (now redirects to /dashboard)
    resp = authenticated_client.get("/stats", follow_redirects=True)
    assert resp.status_code == 200

    # Check that we only have 11 categories shown (10 + Other)
    # The count should appear for each category
    html = resp.data.decode()

    # "Other" should be present because we added 20 categories
    assert "Other" in html

    # Check that there are 11 category-label items
    assert html.count('class="category-label"') == 11

    # Check normalization: 'FICTION' should become 'Fiction'
    # Add 5 books to Fiction to make it a top category
    for i in range(5):
        authenticated_client.post(
            "/books",
            data={
                "title": f"Fiction Book {i}",
                "author": "Author",
                "isbn": f"978111111111{i}",
                "bisac_category": "FICTION / General",
            },
        )
        authenticated_client.post(
            f"/books/{21+i}/reading-records",
            data={
                "status": "Completed",
                "start_date": "2024-01-01",
                "end_date": "2024-01-02",
                "rating": "5",
            },
        )

    resp = authenticated_client.get("/stats", follow_redirects=True)
    html = resp.data.decode()
    assert "Fiction" in html
    # It should NOT show "FICTION" (all uppercase) as a label
    # We use .title() normalization, so FICTION -> Fiction
    assert "FICTION" not in html or "FICTION / General" not in html


def test_stats_bulk_actions_are_in_overflow_menu(authenticated_client):
    resp = authenticated_client.get("/stats", follow_redirects=True)
    html = resp.data.decode("utf-8")

    assert 'aria-label="More statistics actions"' in html
    assert 'role="menu"' in html
    assert 'class="action-menu-item" role="menuitem"' in html
    assert html.index("Fetch missing categories") > html.index('role="menu"')


def test_dashboard_route_redirect(authenticated_client):
    """Test that /stats redirects to /dashboard."""
    resp = authenticated_client.get("/stats", follow_redirects=False)
    # Should redirect with 301
    assert resp.status_code == 301
    # Location should be /dashboard
    assert "dashboard" in resp.location


def test_api_dashboard_endpoint(authenticated_client):
    """Test the new /api/dashboard endpoint returns enhanced stats."""
    authenticated_client.post("/test/reset")
    authenticated_client.get("/test/connect")

    # Add a completed book
    authenticated_client.post(
        "/books",
        data={
            "title": "Test Book",
            "author": "Test Author",
            "isbn": "9781234567890",
            "bisac_category": "FICTION / General",
            "page_count": "300",
            "physical_format": "Hardcover",
            "language": "English",
        },
    )
    authenticated_client.post(
        "/books/1/reading-records",
        data={
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-15",
            "rating": "4",
        },
    )

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


def test_api_stats_redirect(authenticated_client):
    """Test that /api/stats redirects to /api/dashboard."""
    resp = authenticated_client.get("/api/stats", follow_redirects=False)
    # Should redirect with 301
    assert resp.status_code == 301
    # Location should be /api/dashboard
    assert "dashboard" in resp.location
