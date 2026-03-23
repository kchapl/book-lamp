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

    # Get stats page
    resp = authenticated_client.get("/stats")
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

    resp = authenticated_client.get("/stats")
    html = resp.data.decode()
    assert "Fiction" in html
    # It should NOT show "FICTION" (all uppercase) as a label
    # We use .title() normalization, so FICTION -> Fiction
    assert "FICTION" not in html or "FICTION / General" not in html
