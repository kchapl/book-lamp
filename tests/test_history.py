"""Tests for reading history and reading record management."""

from book_lamp.app import get_storage


def test_get_reading_history_empty(authenticated_client):
    """Test reading history when no records exist."""
    response = authenticated_client.get("/history", follow_redirects=True)
    assert response.status_code == 200
    assert b"Reading History" in response.data
    assert b"No history found" in response.data


def test_get_reading_history_populated(authenticated_client):
    """Test reading history with records; reading list items are excluded."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="1", title="Pride and Prejudice", author="Jane Austen"
    )
    storage.add_reading_record(
        book_id=book["id"],
        status="Completed",
        start_date="2023-01-01",
        end_date="2023-01-15",
        rating=5,
    )
    # also add the book to the reading list; it should not appear in history
    storage.add_to_reading_list(book["id"])

    response = authenticated_client.get("/history", follow_redirects=True)
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "Pride and Prejudice" in html
    assert "Completed: 2023-01-15" in html
    assert "Plan to Read" not in html


def test_reading_history_filtering(authenticated_client):
    """Test filtering by status and rating."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="1", title="Book 1", author="A1")
    b2 = storage.add_book(isbn13="2", title="Book 2", author="A2")

    storage.add_reading_record(
        b1["id"], "Completed", "2023-01-01", "2023-01-02", rating=5
    )
    storage.add_reading_record(b2["id"], "Reading", "2023-02-01")

    # Filter by status
    response = authenticated_client.get("/history?status=Completed")
    assert b"Book 1" in response.data
    assert b"Book 2" not in response.data


def test_reading_history_sorting(authenticated_client):
    """Test sorting results."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="1", title="Z Book", author="A1")
    b2 = storage.add_book(isbn13="2", title="A Book", author="A2")

    storage.add_reading_record(b1["id"], "Completed", "2023-01-01", "2023-01-10")
    storage.add_reading_record(b2["id"], "Completed", "2023-01-01", "2023-01-20")

    # Sort by title
    response = authenticated_client.get("/history?sort=title")
    content = response.data.decode()
    assert content.find("A Book") < content.find("Z Book")


def test_stats_top_authors_only_completed(authenticated_client):
    """Stats page should count authors based on completed books only."""
    storage = get_storage()
    # Author1 has two books but only one completed
    b1 = storage.add_book(isbn13="1", title="A", author="Author1")
    b2 = storage.add_book(isbn13="2", title="B", author="Author1")
    b3 = storage.add_book(isbn13="3", title="C", author="Author2")
    storage.add_reading_record(b1["id"], "Completed", "2023-01-01", "2023-01-10")
    storage.add_reading_record(b2["id"], "Reading", "2023-02-01")
    storage.add_reading_record(b3["id"], "Completed", "2023-03-01", "2023-03-10")
    # make sure reading list items also don't affect author counts
    storage.add_to_reading_list(b1["id"])
    storage.add_to_reading_list(b2["id"])

    resp = authenticated_client.get("/stats")
    html = resp.data.decode("utf-8")
    # Author1 should be listed with 1 books, not 2
    assert "Author1" in html
    assert "1 books" in html
    # Author2 also appears with 1
    assert "Author2" in html
    assert html.count("books") >= 2


# --- Reading Record Management ---


def test_update_reading_record(authenticated_client):
    """Test updating an existing reading record."""
    storage = get_storage()
    book = storage.add_book(isbn13="1", title="Test Book", author="Author")
    record = storage.add_reading_record(
        book_id=book["id"], status="In Progress", start_date="2024-01-01"
    )

    response = authenticated_client.post(
        f"/reading-records/{record['id']}/edit",
        data={
            "status": "Completed",
            "start_date": "2024-01-01",
            "end_date": "2024-01-05",
            "rating": 5,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    updated_record = storage.get_reading_records(book_id=book["id"])[0]
    assert updated_record["status"] == "Completed"
    assert updated_record["rating"] == 5


def test_delete_reading_record(authenticated_client):
    """Test deleting a reading record."""
    storage = get_storage()
    book = storage.add_book(isbn13="1", title="Test Book", author="Author")
    record = storage.add_reading_record(
        book_id=book["id"], status="In Progress", start_date="2024-01-01"
    )

    assert len(storage.get_reading_records()) == 1
    response = authenticated_client.post(
        f"/reading-records/{record['id']}/delete", follow_redirects=True
    )
    assert response.status_code == 200
    assert len(storage.get_reading_records()) == 0
