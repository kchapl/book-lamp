"""Filling in covers for Books that have none (#370).

The run must be the narrow operation the issue asked for: it considers only
Books with no cover, writes only their cover fields, and leaves a Book that
already has a cover exactly as it was.
"""

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from book_lamp.app import get_storage
from book_lamp.services.book_lookup import look_up_missing_covers
from book_lamp.services.cover_placeholders import (
    PLACEHOLDER_DIGESTS,
    CoverFingerprints,
)
from book_lamp.services.job_queue import get_job_queue

PLACEHOLDER_HOST = "images.penguinrandomhouse.com"
PLACEHOLDER_URL = f"https://{PLACEHOLDER_HOST}/cover/9780000000099"
ANOTHER_PLACEHOLDER_URL = f"https://{PLACEHOLDER_HOST}/cover/9780000000098"
PLACEHOLDER_FIXTURE = (
    Path(__file__).parent / "fixtures" / "cover_placeholders" / "images.penguinrandomhouse.com-cover-coming-soon.jpg"
)


class _ImageResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.status_code = status
        self.content = content
        self.headers = {"Content-Type": "image/jpeg"}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _ImageSession:
    """A provider that serves one image, counting every fetch."""

    def __init__(self, content: bytes, status: int = 200):
        self._content = content
        self._status = status
        self.calls: list[str] = []

    def get(self, url: str, **kwargs: object) -> _ImageResponse:
        self.calls.append(url)
        return _ImageResponse(self._content, self._status)


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
    assert "replaced 0 placeholders" in job.result
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


def test_each_placeholder_fixture_still_matches_a_registry_digest():
    """The registry and the image it describes cannot drift apart."""
    digest = hashlib.sha256(PLACEHOLDER_FIXTURE.read_bytes()).hexdigest()

    assert digest in PLACEHOLDER_DIGESTS[PLACEHOLDER_HOST]


def test_a_host_outside_the_registry_is_never_fetched():
    """Only a host that serves a known placeholder costs a download."""

    def refuse():
        pytest.fail("a host outside the registry must not be fetched")

    fingerprints = CoverFingerprints(session_factory=refuse)

    assert fingerprints.is_placeholder("https://example.com/cover.jpg") is False


def test_a_url_needed_twice_in_a_run_is_fetched_once():
    session = _ImageSession(PLACEHOLDER_FIXTURE.read_bytes())
    fingerprints = CoverFingerprints(session_factory=lambda: session)

    assert fingerprints.is_placeholder(PLACEHOLDER_URL) is True
    assert fingerprints.is_placeholder(PLACEHOLDER_URL) is True

    assert session.calls == [PLACEHOLDER_URL]


def test_a_failed_fingerprint_is_not_a_placeholder():
    class _Down(_ImageSession):
        def get(self, url, **kwargs):
            self.calls.append(url)
            raise RuntimeError("host down")

    session = _Down(b"")
    fingerprints = CoverFingerprints(session_factory=lambda: session)

    assert fingerprints.is_placeholder(PLACEHOLDER_URL) is False


def test_the_cover_lookup_refuses_a_placeholder_and_keeps_looking(monkeypatch):
    """A placeholder from one provider is not an answer; the chain continues."""
    import book_lamp.services.book_lookup as lookup_module

    monkeypatch.setattr(
        lookup_module,
        "_get_session",
        lambda: _ImageSession(PLACEHOLDER_FIXTURE.read_bytes()),
    )
    monkeypatch.setattr(lookup_module, "_lookup_open_library", lambda *args, **kwargs: None)
    monkeypatch.setattr(lookup_module, "_lookup_google_books", lambda *args, **kwargs: None)
    monkeypatch.setattr(lookup_module, "_lookup_open_library_cover_direct", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        lookup_module,
        "_lookup_amazon_cover",
        lambda isbn: "https://example.com/amazon-real.jpg",
    )

    found = lookup_module.lookup_book_by_isbn13("9780000000099")

    assert found["thumbnail_url"] == "https://example.com/amazon-real.jpg"
    assert found["cover_url"] == "https://example.com/amazon-real.jpg"


def test_the_cover_lookup_returns_a_real_penguin_cover(monkeypatch):
    import book_lamp.services.book_lookup as lookup_module

    monkeypatch.setattr(lookup_module, "_get_session", lambda: _ImageSession(b"real cover" * 500))

    found = lookup_module._lookup_penguin_cover("9780000000099")

    assert found == "https://images.penguinrandomhouse.com/cover/9780000000099"


def _fingerprints_knowing(monkeypatch, placeholders):
    """Treat exactly these URLs as fingerprinted placeholders, in both seams."""
    import book_lamp.routes.books as books_route
    import book_lamp.services.book_lookup as lookup_module

    class _FakeFingerprints:
        def is_placeholder(self, url):
            return url in placeholders

    monkeypatch.setattr(books_route, "CoverFingerprints", lambda: _FakeFingerprints())
    monkeypatch.setattr(lookup_module, "CoverFingerprints", lambda: _FakeFingerprints())


def test_run_replaces_a_stored_placeholder(authenticated_client, monkeypatch):
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780000000099",
        title="Placeholder cover",
        authors=["A"],
        thumbnail_url=PLACEHOLDER_URL,
        cover_url=PLACEHOLDER_URL,
    )
    _fingerprints_knowing(monkeypatch, {PLACEHOLDER_URL})

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=_provider_answer,
    ):
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        assert response.status_code == 200
        job = _finished(response.get_json()["job_id"])

    assert "Checked 1 book(s) without a cover" in job.result
    assert "filled 0" in job.result
    assert "replaced 1 placeholders" in job.result
    assert "0 still missing" in job.result

    replaced_book = storage.get_book_by_id(book["id"])
    assert replaced_book["thumbnail_url"] == "https://example.com/9780000000099-M.jpg"
    assert replaced_book["cover_url"] == "https://example.com/9780000000099-L.jpg"
    assert PLACEHOLDER_URL not in (replaced_book["thumbnail_url"], replaced_book["cover_url"])


def test_run_counts_a_book_still_covered_by_a_placeholder_as_missing(authenticated_client, monkeypatch):
    """A lookup that finds only another placeholder leaves the Book as it was."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780000000099",
        title="Still a placeholder",
        authors=["A"],
        thumbnail_url=PLACEHOLDER_URL,
        cover_url=PLACEHOLDER_URL,
    )
    _fingerprints_knowing(monkeypatch, {PLACEHOLDER_URL, ANOTHER_PLACEHOLDER_URL})

    def another_placeholder(isbn, **kwargs):
        return {
            "thumbnail_url": ANOTHER_PLACEHOLDER_URL,
            "cover_url": ANOTHER_PLACEHOLDER_URL,
        }

    with patch(
        "book_lamp.services.book_lookup.lookup_book_by_isbn13",
        side_effect=another_placeholder,
    ):
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        job = _finished(response.get_json()["job_id"])

    assert "replaced 0 placeholders" in job.result
    assert "1 still missing" in job.result
    kept = storage.get_book_by_id(book["id"])
    assert kept["thumbnail_url"] == PLACEHOLDER_URL


def test_run_ignores_a_real_cover_on_a_placeholder_host(authenticated_client, monkeypatch):
    """The host alone is not evidence; the bytes decide."""
    storage = get_storage()
    storage.add_book(
        isbn13="9780000000097",
        title="Real cover",
        authors=["A"],
        thumbnail_url=f"https://{PLACEHOLDER_HOST}/cover/real.jpg",
    )
    _fingerprints_knowing(monkeypatch, set())

    with patch("book_lamp.services.book_lookup.lookup_book_by_isbn13") as lookup:
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        job = _finished(response.get_json()["job_id"])

    assert job.result == "No books are missing a cover."
    lookup.assert_not_called()


def test_the_report_names_every_outcome(authenticated_client, monkeypatch):
    storage = get_storage()
    missing = storage.add_book(isbn13="9780000000081", title="Missing", authors=["A"])
    placeholder = storage.add_book(
        isbn13="9780000000082",
        title="Placeholder",
        authors=["B"],
        thumbnail_url=PLACEHOLDER_URL,
    )
    uncovered = storage.add_book(isbn13="9780000000083", title="No lookup", authors=["C"])
    _fingerprints_knowing(monkeypatch, {PLACEHOLDER_URL})

    def answer(isbn, **kwargs):
        if isbn.endswith("83"):
            return None
        return _provider_answer(isbn)

    with patch("book_lamp.services.book_lookup.lookup_book_by_isbn13", side_effect=answer):
        response = authenticated_client.post("/api/books/fetch-covers", json={})
        job = _finished(response.get_json()["job_id"])

    assert job.result == ("Checked 3 book(s) without a cover: filled 1, replaced 1 placeholders, 1 still missing.")
    assert storage.get_book_by_id(missing["id"])["cover_url"] is not None
    assert storage.get_book_by_id(placeholder["id"])["cover_url"] == "https://example.com/9780000000082-L.jpg"
    assert storage.get_book_by_id(uncovered["id"])["thumbnail_url"] is None


def test_the_in_memory_storage_widens_missing_to_placeholder_hosts(authenticated_client):
    """The in-memory adapter offers the same candidate set as Postgres."""
    storage = get_storage()
    book = storage.add_book(
        isbn13="9780000000096",
        title="Held placeholder",
        authors=["A"],
        thumbnail_url=PLACEHOLDER_URL,
    )

    assert book["id"] not in {b["id"] for b in storage.get_books_missing_covers()}
    widened = storage.get_books_missing_covers(placeholder_hosts=[PLACEHOLDER_HOST])
    assert book["id"] in {b["id"] for b in widened}
