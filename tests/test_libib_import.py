import io
import time

from book_lamp.app import get_storage
from book_lamp.services.job_queue import get_job_queue


def _wait_for_latest_job(timeout=30):
    """Wait for the most recent job in the queue to complete."""
    queue = get_job_queue()
    start = time.time()

    # Get the most recent job (by creation time)
    while time.time() - start < timeout:
        jobs = list(queue.jobs.values())
        if jobs:
            latest_job = max(jobs, key=lambda j: j.created_at)
            if latest_job.status.value in ("completed", "failed"):
                return True
        time.sleep(0.1)

    return False


def test_libib_import_success(authenticated_client):
    storage = get_storage()
    csv_content = (
        "Title,Author,ISBN,Publish Date,Date Added,Date Completed,Rating\n"
        "Test Book,Test Author,9780000000001,2020,2023-01-01,2023-01-10,5\n"
        "Another Book,Another Author,9780000000002,2021,2023-02-01,,4\n"
    )

    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")}

    resp = authenticated_client.post(
        "/books/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    # Wait for background job to complete
    _wait_for_latest_job()

    assert resp.status_code == 200

    # Verify books
    book1 = storage.get_book_by_isbn("9780000000001")
    assert book1 is not None
    assert book1["title"] == "Test Book"

    book2 = storage.get_book_by_isbn("9780000000002")
    assert book2 is not None
    assert book2["title"] == "Another Book"

    # Verify reading records
    records1 = storage.get_reading_records(book_id=book1["id"])
    assert len(records1) == 1
    assert records1[0]["status"] == "Completed"
    assert records1[0]["rating"] == 5
    assert records1[0]["start_date"] == "2023-01-01"
    assert records1[0]["end_date"] == "2023-01-10"


def test_libib_import_overwrite_existing(authenticated_client):
    # Pre-add a book
    storage = get_storage()
    storage.add_book(
        isbn13="9780000000001",
        title="Old Title",
        author="Old Author",
        thumbnail_url="http://example.com/cover.jpg",
    )

    csv_content = (
        "Title,Author,ISBN,Publish Date,Date Added,Date Completed,Rating\n"
        "New Title,New Author,9780000000001,2022,2023-03-01,2023-03-15,3\n"
    )

    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")}

    resp = authenticated_client.post(
        "/books/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    # Wait for background job to complete
    _wait_for_latest_job()

    assert resp.status_code == 200

    # Verify book updated
    book = storage.get_book_by_isbn("9780000000001")
    assert book["title"] == "New Title"
    assert book["author"] == "New Author"
    # Verify thumbnail preserved
    assert book["thumbnail_url"] == "http://example.com/cover.jpg"

    # Verify new record added
    records = storage.get_reading_records(book_id=book["id"])
    assert len(records) == 1
    assert records[0].get("rating") == 3


def test_libib_import_complex(authenticated_client):
    storage = get_storage()
    csv_content = (
        "Title,Author,ISBN,Reading Status,Date Added,Date Completed,Rating,Description\n"
        "In Progress Book,Author A,9781111111111,In progress,01/05/2023,,0,Great start\n"
        "Abandoned Book,Author B,9782222222222,Abandoned,2023-01-01,2023-01-05,2,Couldn't finish\n"
        "Not Begun Book,Author C,9783333333333,Not begun,2023-06-01,,0,On wishlist\n"
    )

    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")}

    resp = authenticated_client.post(
        "/books/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    # Wait for background job to complete
    _wait_for_latest_job()

    assert resp.status_code == 200

    # Check In Progress
    book1 = storage.get_book_by_isbn("9781111111111")
    recs1 = storage.get_reading_records(book_id=book1["id"])
    assert len(recs1) == 1
    assert recs1[0]["status"] == "In Progress"
    assert recs1[0]["start_date"] == "2023-01-05"  # Normalized from 01/05/2023
    assert recs1[0]["end_date"] is None
    assert book1["description"] == "Great start"

    # Check Abandoned
    book2 = storage.get_book_by_isbn("9782222222222")
    recs2 = storage.get_reading_records(book_id=book2["id"])
    assert len(recs2) == 1
    assert recs2[0]["status"] == "Abandoned"
    assert recs2[0]["end_date"] == "2023-01-05"

    # Check Not Begun (Book added, but no record)
    book3 = storage.get_book_by_isbn("9783333333333")
    assert book3 is not None
    recs3 = storage.get_reading_records(book_id=book3["id"])
    assert len(recs3) == 0


def test_libib_import_deduplication(authenticated_client):
    storage = get_storage()
    csv_content = (
        "Title,Author,ISBN,Reading Status,Date Added,Date Completed,Rating\n"
        "Duplicate Book,Author D,9784444444444,Completed,2023-01-01,2023-01-02,5\n"
    )

    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")}

    # First import
    authenticated_client.post(
        "/books/import", data=data, content_type="multipart/form-data"
    )
    _wait_for_latest_job()

    # Second import with same file
    data["file"] = (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")
    resp2 = authenticated_client.post(
        "/books/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    _wait_for_latest_job()

    assert resp2.status_code == 200

    book = storage.get_book_by_isbn("9784444444444")
    recs = storage.get_reading_records(book_id=book["id"])

    # Should only have 1 record despite 2 imports
    assert len(recs) == 1


def test_libib_import_with_images(authenticated_client):
    storage = get_storage()
    csv_content = (
        "Title,Author,ISBN,Thumbnail,Large Image\n"
        "Image Book,Image Author,9789999999999,http://example.com/t.jpg,http://example.com/c.jpg\n"
    )

    data = {"file": (io.BytesIO(csv_content.encode("utf-8")), "libib.csv")}

    resp = authenticated_client.post(
        "/books/import",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )

    # Wait for background job to complete
    _wait_for_latest_job()

    assert resp.status_code == 200

    book = storage.get_book_by_isbn("9789999999999")
    assert book is not None
    assert book["thumbnail_url"] == "http://example.com/t.jpg"
    assert book["cover_url"] == "http://example.com/c.jpg"
