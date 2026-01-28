import pytest

from book_lamp.app import app, get_storage


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_get_reading_history_empty(client):
    """Test reading history when no records exist."""
    storage = get_storage()
    # Reset storage
    storage.books = []
    storage.reading_records = []

    response = client.get("/history", follow_redirects=True)
    assert response.status_code == 200
    assert b"Reading History" in response.data
    assert b"No history found" in response.data


def test_get_reading_history_populated(client):
    """Test reading history with records."""
    storage = get_storage()
    # Setup mock data
    storage.books = []
    storage.reading_records = []

    book = storage.add_book(
        isbn13="9780141439518", title="Pride and Prejudice", author="Austen, Jane"
    )

    storage.add_reading_record(
        book_id=book["id"],
        status="Completed",
        start_date="2023-01-01",
        end_date="2023-01-15",
        rating=5,
    )

    response = client.get("/history", follow_redirects=True)
    assert response.status_code == 200
    assert b"Pride and Prejudice" in response.data
    assert b"Completed: 2023-01-15" in response.data
    assert b"Completed" in response.data


def test_reading_history_filtering(client):
    """Test filtering by status and rating."""
    storage = get_storage()
    storage.books = []
    storage.reading_records = []

    b1 = storage.add_book(isbn13="1", title="Book 1", author="A1")
    b2 = storage.add_book(isbn13="2", title="Book 2", author="A2")

    storage.add_reading_record(
        b1["id"], "Completed", "2023-01-01", "2023-01-02", rating=5
    )
    storage.add_reading_record(b2["id"], "Reading", "2023-02-01")

    # Filter by status
    response = client.get("/history?status=Completed")
    assert b"Book 1" in response.data
    assert b"Book 2" not in response.data

    # Filter by rating
    response = client.get("/history?min_rating=5")
    assert b"Book 1" in response.data
    assert b"Book 2" not in response.data


def test_reading_history_sorting(client):
    """Test sorting by title and date."""
    storage = get_storage()
    storage.books = []
    storage.reading_records = []

    b1 = storage.add_book(isbn13="1", title="Z Book", author="A1")
    b2 = storage.add_book(isbn13="2", title="A Book", author="A2")

    storage.add_reading_record(b1["id"], "Completed", "2023-01-01", "2023-01-10")
    storage.add_reading_record(b2["id"], "Completed", "2023-01-01", "2023-01-20")

    # Sort by title
    response = client.get("/history?sort=title")
    content = response.data.decode()
    assert content.find("A Book") < content.find("Z Book")

    # Sort by date desc (default)
    response = client.get("/history?sort=date_desc")
    content = response.data.decode()
    assert content.find("2023-01-20") < content.find("2023-01-10")
