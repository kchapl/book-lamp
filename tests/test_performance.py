"""Unit tests enforcing performance standards for backend operations."""

from unittest.mock import MagicMock

from book_lamp.services.sheets_storage import GoogleSheetsStorage


def test_bulk_import_batch_efficiency():
    """Verify that bulk_import uses batching and doesn't perform N requests for N items."""
    # Mock the Google Sheets service
    mock_service = MagicMock()
    mock_spreadsheets = mock_service.spreadsheets.return_value
    mock_values = mock_spreadsheets.values.return_value

    # Mock sequence for get() calls: Books, ReadingRecords
    # (Discovery/Setup calls like _ensure_spreadsheet_id are mocked separately)
    mock_values.get.return_value.execute.side_effect = [
        {
            "values": [
                [
                    "id",
                    "isbn13",
                    "title",
                    "author",
                    "publication_year",
                    "thumbnail_url",
                    "created_at",
                ]
            ]
        },  # Books
        {
            "values": [
                [
                    "id",
                    "book_id",
                    "status",
                    "start_date",
                    "end_date",
                    "rating",
                    "created_at",
                ]
            ]
        },  # ReadingRecords
    ]

    storage = GoogleSheetsStorage("TestSheet")
    storage.service = mock_service

    # Isolated dependencies to avoid triggering extra API calls during test setup
    storage._ensure_spreadsheet_id = MagicMock(return_value="dummy_id")
    storage.get_authors = MagicMock(return_value=[])
    storage.get_book_authors = MagicMock(return_value=[])

    # 10 items to import
    items = []
    for i in range(10):
        items.append(
            {
                "book": {
                    "isbn13": f"978000000000{i}",
                    "title": f"Title {i}",
                    "author": f"Author {i}",
                    "publication_year": 2020 + i,
                },
                "record": {
                    "status": "Completed",
                    "start_date": "2023-01-01",
                    "end_date": "2023-01-02",
                    "rating": 5,
                },
            }
        )

    storage.bulk_import(items)

    # Assertions:
    # 1. Should fetch Books metadata ONCE
    # 2. Should fetch ReadingRecords ONCE
    # (These are the side_effects we set up)

    # 3. Should perform BATCH append for books (1 call for 10 books)
    # 4. Should perform BATCH append for records (1 call for 10 records)

    # We check the 'execute' calls on the append return value
    append_execute_count = mock_values.append.return_value.execute.call_count

    # We expect 4 append calls: Books, ReadingRecords, Authors, BookAuthors
    # But crucially, NOT 10 or 20.
    assert (
        append_execute_count <= 4
    ), f"Expected batch append (<=4 calls), but got {append_execute_count} calls. N+1 pattern detected!"


def test_get_all_books_efficiency():
    """Verify get_all_books doesn't make redundant calls."""
    mock_service = MagicMock()
    mock_values = mock_service.spreadsheets.return_value.values.return_value

    # Mock data with enough columns to satisfy the indexing in get_all_books
    mock_values.get.return_value.execute.side_effect = [
        {
            "values": [
                [
                    "id",
                    "isbn13",
                    "title",
                    "author",
                    "publication_year",
                    "thumbnail_url",
                    "created_at",
                    "publisher",
                    "description",
                    "series",
                    "dewey_decimal",
                    "language",
                    "page_count",
                    "physical_format",
                    "edition",
                    "cover_url",
                ],
                [
                    "1",
                    "123",
                    "T",
                    "A",
                    "2020",
                    "http://t.jpg",
                    "today",
                    "pub",
                    "desc",
                    "ser",
                    "800",
                    "en",
                    "100",
                    "Hardcover",
                    "1st",
                    "http://c.jpg",
                ],
            ]
        },  # Books
        {"values": [["id", "name"], ["1", "A"]]},  # Authors
        {"values": [["book_id", "author_id"], ["1", "1"]]},  # BookAuthors
    ]

    storage = GoogleSheetsStorage("TestSheet")
    storage.service = mock_service
    storage._ensure_spreadsheet_id = MagicMock(return_value="sid")

    storage.get_all_books()

    # Should only call get() 3 times (Books, Authors, BookAuthors)
    assert mock_values.get.call_count == 3
