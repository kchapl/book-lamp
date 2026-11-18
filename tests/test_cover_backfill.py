"""Filling in covers for Books that have none (#370).

The run must be the narrow operation the issue asked for: it considers only
Books with no cover, writes only their cover fields, and leaves a Book that
already has a cover exactly as it was.
"""

from unittest.mock import patch

from book_lamp.app import get_storage
from book_lamp.services.book_lookup import look_up_missing_covers
from book_lamp.services.job_queue import get_job_queue


def _finished(job_id: str):
    job = get_job_queue().get_job(job_id)
    assert job is not None, f"job {job_id} disappeared"
    assert job.wait_for_completion(timeout=10), "the cover job did not finish"
    return job


def _provider_answer(isbn, **kwargs):
    return {
        "title": "Provider title",
        "author": "Provider author",
        "publisher": "Provider House",
        "thumbnail_url": f"https://example.com/{isbn}-M.jpg",
        "cover_url": f"https://example.com/{isbn}-L.jpg",
    }


def test_look_up_returns_covers_only():
    """The seam hands the job cover fields and nothing else."""
    books = [{"id": 7, "isbn13": "9780000000007", "title": "A Book", "author": "An Author"}]

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=_provider_answer,
    ):
        found = look_up_missing_covers(books)

    assert found == {
        7: {
            "thumbnail_url": "https://example.com/9780000000007-M.jpg",
            "cover_url": "https://example.com/9780000000007-L.jpg",
        }
    }


def test_look_up_keeps_going_when_one_lookup_fails():
    """A provider's bad day leaves its Book missing, and does not fail the run."""

    def answer(isbn, **kwargs):
        if isbn.endswith("8"):
            raise RuntimeError("provider down")
        return {"thumbnail_url": "https://example.com/ok-M.jpg"}

    books = [
        {"id": 1, "isbn13": "9780000000027", "title": "One"},
        {"id": 2, "isbn13": "9780000000028", "title": "Two"},
    ]

    with patch("book_lamp.services.book_lookup.lookup_book_by_isbn13", side_effect=answer):
        found = look_up_missing_covers(books)

    assert found == {1: {"thumbnail_url": "https://example.com/ok-M.jpg"}}


def test_look_up_ignores_a_blank_cover():
    books = [{"id": 1, "isbn13": "9780000000029", "title": "Blank"}]

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        return_value={"thumbnail_url": "   ", "cover_url": None},
    ):
        found = look_up_missing_covers(books)

    assert found == {}


def test_run_fills_only_books_without_a_cover(authenticated_client):
    storage = get_storage()
    covered = storage.add_book(
        isbn13="9780000000031",
        title="Covered",
        authors=["A"],
        thumbnail_url="https://example.com/already.jpg",
        publisher="Kept House",
    )
    missing = storage.add_book(isbn13="9780000000032", title="Missing", authors=["B"])
    blank = storage.add_book(
        isbn13="9780000000033",
        title="Blank",
        authors=["C"],
        thumbnail_url="",
        cover_url="   ",
    )

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=_provider_answer,
    ):
        response = authenticated_client.post("/api/books/fetch-covers", json={"book_ids": []})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert job.status.value == "completed"
    assert "Checked 2 book(s)" in job.result
    assert "filled 2" in job.result
    assert "0 still missing" in job.result

    kept = storage.get_book_by_id(covered["id"])
    assert kept["thumbnail_url"] == "https://example.com/already.jpg"
    assert kept["title"] == "Covered"
    assert kept["publisher"] == "Kept House"

    filled = storage.get_book_by_id(missing["id"])
    assert filled["thumbnail_url"] == "https://example.com/9780000000032-M.jpg"
    assert filled["cover_url"] == "https://example.com/9780000000032-L.jpg"
    # Nothing but the covers was written.
    assert filled["title"] == "Missing"

    filled_blank = storage.get_book_by_id(blank["id"])
    assert filled_blank["thumbnail_url"] == "https://example.com/9780000000033-M.jpg"
    assert filled_blank["cover_url"] == "https://example.com/9780000000033-L.jpg"


def test_run_honours_named_book_ids(authenticated_client):
    storage = get_storage()
    named = storage.add_book(isbn13="9780000000041", title="Named", authors=["A"])
    other = storage.add_book(isbn13="9780000000042", title="Other", authors=["B"])

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=_provider_answer,
    ) as lookup:
        response = authenticated_client.post("/api/books/fetch-covers", json={"book_ids": [named["id"]]})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert "Checked 1 book(s)" in job.result
    assert [call.args[0] for call in lookup.call_args_list] == ["9780000000041"]
    assert storage.get_book_by_id(named["id"])["cover_url"] == "https://example.com/9780000000041-L.jpg"
    assert storage.get_book_by_id(other["id"])["thumbnail_url"] is None


def test_run_leaves_a_book_whose_isbn_changed_mid_run(authenticated_client):
    """A corrected ISBN gets no cover: the lookup answered for the old edition."""
    storage = get_storage()
    book = storage.add_book(isbn13="9780000000061", title="Corrected", authors=["A"])

    def correct_the_isbn(isbn, **kwargs):
        storage.get_book_by_id(book["id"])["isbn13"] = "9780000000062"
        return _provider_answer(isbn)

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=correct_the_isbn,
    ):
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert job.status.value == "completed"
    assert "filled 0" in job.result
    corrected = storage.get_book_by_id(book["id"])
    assert corrected["thumbnail_url"] is None
    assert corrected["cover_url"] is None


def test_run_leaves_a_cover_added_mid_run(authenticated_client):
    """A cover the reader added while the run was looking is kept."""
    storage = get_storage()
    book = storage.add_book(isbn13="9780000000071", title="Late cover", authors=["A"])

    def add_a_cover(isbn, **kwargs):
        storage.get_book_by_id(book["id"])["thumbnail_url"] = "https://example.com/reader.jpg"
        return _provider_answer(isbn)

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=add_a_cover,
    ):
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert job.status.value == "completed"
    assert "filled 0" in job.result
    kept = storage.get_book_by_id(book["id"])
    assert kept["thumbnail_url"] == "https://example.com/reader.jpg"
    assert kept["cover_url"] is None


def test_run_reports_when_nothing_is_missing(authenticated_client):
    storage = get_storage()
    storage.add_book(
        isbn13="9780000000051",
        title="Covered",
        authors=["A"],
        thumbnail_url="https://example.com/x.jpg",
    )

    with patch("book_lamp.services.book_lookup.lookup_book_by_isbn13") as lookup:
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert job.result == "No books are missing a cover."
    lookup.assert_not_called()


def test_run_rejects_a_body_that_is_not_a_list_of_ids(authenticated_client):
    not_a_list = authenticated_client.post("/api/books/fetch-covers", json={"book_ids": "1"})
    not_integers = authenticated_client.post("/api/books/fetch-covers", json={"book_ids": ["one"]})

    assert not_a_list.status_code == 400
    assert not_integers.status_code == 400
