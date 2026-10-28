from unittest.mock import patch

from book_lamp.app import get_storage, is_valid_isbn13, parse_publication_year


def test_isbn13_validation():
    assert is_valid_isbn13("9780306406157") is True  # known valid
    assert is_valid_isbn13("9780306406158") is False  # wrong checksum
    assert is_valid_isbn13("123") is False


def test_parse_publication_year():
    assert parse_publication_year("2001") == 2001
    assert parse_publication_year("July 2019") == 2019
    assert parse_publication_year(None) is None


@patch("book_lamp.services.book_lookup._lookup_google_books")
@patch("book_lamp.services.book_lookup._lookup_open_library")
def test_lookup_upgrades_isbn10_to_isbn13(mock_open_library, mock_google_books):
    """A 10-digit ISBN is upgraded to ISBN-13 before hitting the metadata APIs."""
    from book_lamp.services.book_lookup import lookup_book_by_isbn13

    mock_open_library.return_value = {
        "title": "Upgraded Book",
        "author": "Someone",
        "thumbnail_url": "https://covers.openlibrary.org/b/id/1-M.jpg",
    }
    mock_google_books.return_value = None

    result = lookup_book_by_isbn13("0143127741")

    assert mock_open_library.call_args[0][0] == "9780143127741"
    assert mock_google_books.call_args[0][0] == "9780143127741"
    assert result["isbn13"] == "9780143127741"
    assert result["title"] == "Upgraded Book"


@patch("book_lamp.services.book_lookup._get_session")
def test_add_book_success(mock_session_factory, authenticated_client):
    storage = get_storage()

    class MockResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "ISBN:9780306406157": {
                    "title": "Example Book",
                    "authors": [{"name": "Jane Doe"}],
                    "publish_date": "2001",
                    "cover": {"medium": "https://covers.openlibrary.org/b/id/12345-M.jpg"},
                }
            }

    mock_session = mock_session_factory.return_value
    mock_session.get.return_value = MockResp()
    mock_session.head.return_value = MockResp()

    resp = authenticated_client.post("/api/books", json={"isbn": "9780306406157"})
    assert resp.status_code == 201
    assert resp.get_json()["title"] == "Example Book"

    book = storage.get_book_by_isbn("9780306406157")
    assert book["title"] == "Example Book"


def test_delete_book_success(authenticated_client):
    storage = get_storage()
    book = storage.add_book(isbn13="9780306406157", title="Test Book", authors=["Test Author"])
    book_id = book["id"]

    resp = authenticated_client.post(f"/api/books/{book_id}/delete")
    assert resp.status_code == 200
    assert storage.get_book_by_id(book_id) is None


def test_edit_book_success(authenticated_client):
    storage = get_storage()
    book = storage.add_book(isbn13="9780306406157", title="Original Title", authors=["Original Author"])

    updated_data = {
        "isbn13": "9780306406157",
        "title": "Updated Title",
        "author": "Updated Author",
        "publication_year": "2022",
    }
    resp = authenticated_client.post(f"/api/books/{book['id']}/edit", json=updated_data)
    assert resp.status_code == 200

    updated_book = storage.get_book_by_id(book["id"])
    assert updated_book["title"] == "Updated Title"


def _titles(payload):
    return {b["title"] for b in payload["books"]}


def _two_books_out_of_title_order(authenticated_client):
    """Two Books whose title order and reading-date order disagree.

    "Apple" was started first, "Zebra" most recently, so a title sort and the
    default reading-date sort give opposite answers. A Book needs a Reading
    Status to be listed at all.
    """
    storage = get_storage()
    apple = storage.add_book(isbn13="301", title="Apple", authors=["A1"])
    zebra = storage.add_book(isbn13="302", title="Zebra", authors=["A2"])
    storage.add_reading(apple["id"], "Completed", "2024-01-01", "2024-01-10")
    storage.add_reading(zebra["id"], "Completed", "2024-02-01", "2024-02-10")


def test_books_sort_by_title(authenticated_client):
    """The `sort` parameter reorders the catalogue (see SORT_OPTIONS).

    The collection page keeps its sort in the URL and sends it here; nothing
    pinned that the request carried it, so a page that dropped it looked fine.
    """
    _two_books_out_of_title_order(authenticated_client)

    resp = authenticated_client.get("/api/books?sort=title")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert [b["title"] for b in payload["books"]] == ["Apple", "Zebra"]
    assert payload["sort"] == "title"


def test_books_unknown_sort_falls_back_to_reading_date(authenticated_client):
    """A sort the server does not implement silently becomes the default.

    This is why the collection page offers only the server's sorts: a `rating`
    option was offered and quietly returned the default order.
    """
    _two_books_out_of_title_order(authenticated_client)

    resp = authenticated_client.get("/api/books?sort=rating")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["sort"] == "reading_date"
    # Most recently read first, which is not the order a title sort gives.
    assert [b["title"] for b in payload["books"]] == ["Zebra", "Apple"]


def test_books_year_filter(authenticated_client):
    """Test filtering the books API by year completed."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="101", title="2024 Book", authors=["A1"])
    b2 = storage.add_book(isbn13="102", title="2023 Book", authors=["A2"])

    # b1 completed in 2024
    storage.add_reading(b1["id"], "Completed", "2024-01-01", "2024-01-15", rating=5)
    # b2 completed in 2023
    storage.add_reading(b2["id"], "Completed", "2023-12-01", "2023-12-31", rating=4)

    # Filter by year 2024
    resp = authenticated_client.get("/api/books?year=2024")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert _titles(payload) == {"2024 Book"}
    assert payload["filters"]["year"] == "2024"

    # An 'In Progress' book started in 2024 must be excluded
    b3 = storage.add_book(isbn13="103", title="2024 In Progress", authors=["A3"])
    storage.add_reading(b3["id"], "In Progress", "2024-01-01")
    resp = authenticated_client.get("/api/books?year=2024")
    assert "2024 In Progress" not in _titles(resp.get_json())

    # Filter by year 2023
    resp = authenticated_client.get("/api/books?year=2023")
    assert _titles(resp.get_json()) == {"2023 Book"}


def test_books_month_filter(authenticated_client):
    """Test filtering the books API by month completed."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="201", title="January Book", authors=["A1"])
    b2 = storage.add_book(isbn13="202", title="February Book", authors=["A2"])

    # b1 completed in January (any year)
    storage.add_reading(b1["id"], "Completed", "2024-01-01", "2024-01-15", rating=5)
    # b2 completed in February (any year)
    storage.add_reading(b2["id"], "Completed", "2023-02-01", "2023-02-28", rating=4)

    # Filter by month 1 (January)
    resp = authenticated_client.get("/api/books?month=1")
    assert resp.status_code == 200
    assert _titles(resp.get_json()) == {"January Book"}

    # An 'In Progress' book started in January must be excluded
    b3 = storage.add_book(isbn13="203", title="January In Progress", authors=["A3"])
    storage.add_reading(b3["id"], "In Progress", "2024-01-05")
    resp = authenticated_client.get("/api/books?month=1")
    assert "January In Progress" not in _titles(resp.get_json())

    # Filter by month 2 (February)
    resp = authenticated_client.get("/api/books?month=2")
    assert _titles(resp.get_json()) == {"February Book"}


def test_books_category_filter(authenticated_client):
    """Test filtering the books API by BISAC category."""
    storage = get_storage()
    # Science category
    b1 = storage.add_book(isbn13="301", title="Science Book", authors=["A1"], bisac_category="Science")
    # Fiction category
    b2 = storage.add_book(isbn13="302", title="Literature Book", authors=["A2"], bisac_category="Fiction")

    # Give them statuses so they show up in the library
    storage.add_reading(b1["id"], "Completed", "2024-01-01", "2024-01-15")
    storage.add_reading(b2["id"], "Completed", "2024-01-01", "2024-01-15")

    # Filter by Science
    resp = authenticated_client.get("/api/books?category=Science")
    assert resp.status_code == 200
    payload = resp.get_json()
    assert _titles(payload) == {"Science Book"}
    assert "Science" in payload["categories"]

    # Filter by Fiction
    resp = authenticated_client.get("/api/books?category=Fiction")
    assert _titles(resp.get_json()) == {"Literature Book"}


def test_books_rating_filter(authenticated_client):
    """Test filtering the books API by rating."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="401", title="5 Star Book", authors=["A1"])
    b2 = storage.add_book(isbn13="402", title="4 Star Book", authors=["A2"])

    # b1 rated 5
    storage.add_reading(b1["id"], "Completed", "2024-01-01", "2024-01-15", rating=5)
    # b2 rated 4
    storage.add_reading(b2["id"], "Completed", "2024-01-01", "2024-01-15", rating=4)

    # Filter by rating 5
    resp = authenticated_client.get("/api/books?rating=5")
    assert resp.status_code == 200
    assert _titles(resp.get_json()) == {"5 Star Book"}

    # Filter by rating 4
    resp = authenticated_client.get("/api/books?rating=4")
    assert _titles(resp.get_json()) == {"4 Star Book"}


def test_books_status_filter(authenticated_client):
    """Test filtering the books API by status."""
    storage = get_storage()
    b1 = storage.add_book(isbn13="501", title="In Progress Book", authors=["A1"])
    b2 = storage.add_book(isbn13="502", title="Completed Book", authors=["A2"])

    # b1 in progress
    storage.add_reading(b1["id"], "In Progress", "2024-01-01")
    # b2 completed
    storage.add_reading(b2["id"], "Completed", "2024-01-01", "2024-01-15", rating=5)

    # Filter by status "In Progress"
    resp = authenticated_client.get("/api/books?status=In+Progress")
    assert resp.status_code == 200
    assert _titles(resp.get_json()) == {"In Progress Book"}

    # Filter by status "Completed"
    resp = authenticated_client.get("/api/books?status=Completed")
    assert _titles(resp.get_json()) == {"Completed Book"}


def test_books_filters_echoed_in_response(authenticated_client):
    """The API echoes the active filters so the SPA can render them."""
    resp = authenticated_client.get("/api/books?status=Completed&year=2024&month=1&rating=5&category=Fiction")
    assert resp.status_code == 200
    assert resp.get_json()["filters"] == {
        "status": "Completed",
        "year": "2024",
        "month": "1",
        "rating": "5",
        "category": "Fiction",
    }
