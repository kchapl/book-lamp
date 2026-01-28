import pytest

from book_lamp.app import app, get_storage


@pytest.fixture
def client():
    app.config["TESTING"] = True
    # Ensure TEST_MODE is True for storage to be MockStorage
    from book_lamp import app as app_module

    app_module.TEST_MODE = True

    with app.test_client() as client:
        # Manually reset mock storage
        storage = get_storage()
        storage.books = []
        storage.reading_records = []
        storage.next_book_id = 1
        storage.next_record_id = 1
        yield client


def test_update_reading_record(client):
    """Test updating an existing reading record."""
    storage = get_storage()
    book = storage.add_book(isbn13="1234567890123", title="Test Book", author="Author")
    record = storage.add_reading_record(
        book_id=book["id"], status="In Progress", start_date="2024-01-01"
    )
    record_id = record["id"]

    response = client.post(
        f"/reading-records/{record_id}/edit",
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
    assert updated_record["end_date"] == "2024-01-05"
    assert updated_record["rating"] == 5


def test_delete_reading_record(client):
    """Test deleting a reading record."""
    storage = get_storage()
    book = storage.add_book(isbn13="1234567890123", title="Test Book", author="Author")
    record = storage.add_reading_record(
        book_id=book["id"], status="In Progress", start_date="2024-01-01"
    )
    record_id = record["id"]

    assert len(storage.get_reading_records()) == 1

    response = client.post(
        f"/reading-records/{record_id}/delete", follow_redirects=True
    )

    assert response.status_code == 200
    assert len(storage.get_reading_records()) == 0


def test_delete_book_consistent_behavior(client):
    """Test that deleting a book still works after UI changes."""
    storage = get_storage()
    book = storage.add_book(isbn13="1234567890123", title="Test Book", author="Author")
    book_id = book["id"]

    assert len(storage.get_all_books()) == 1

    response = client.post(f"/books/{book_id}/delete", follow_redirects=True)

    assert response.status_code == 200
    assert len(storage.get_all_books()) == 0
