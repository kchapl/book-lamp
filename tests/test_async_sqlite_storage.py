from book_lamp.services.async_sqlite_storage import AsyncSQLiteStorage


def test_async_sqlite_storage_local_write_and_read():
    storage = AsyncSQLiteStorage(sheet_name="TestSheet")
    storage.set_authorised(True)

    book = storage.add_book(
        isbn13="9780000000001",
        title="Local First",
        author="Test Author",
    )
    storage.add_to_reading_list(book["id"])

    books = storage.get_all_books()
    reading_list = storage.get_reading_list()

    assert len(books) == 1
    assert books[0]["title"] == "Local First"
    assert len(reading_list) == 1
    assert reading_list[0]["book_id"] == book["id"]


def test_async_sqlite_storage_settings_roundtrip():
    storage = AsyncSQLiteStorage(sheet_name="TestSheet")
    storage.set_authorised(True)
    storage.update_setting("theme", "light")
    assert storage.get_settings().get("theme") == "light"


def test_async_sqlite_storage_records_failed_sync():
    class FailingRemote:
        def add_book(self, **kwargs):  # noqa: ANN003
            raise RuntimeError("sync failed")

    storage = AsyncSQLiteStorage(sheet_name="TestSheet")
    storage._new_remote = lambda: FailingRemote()  # type: ignore[method-assign]
    storage._max_attempts = 1
    storage.configure_remote(credentials_dict={"token": "dummy"})

    storage.add_book(
        isbn13="9780000000002",
        title="Will Fail Sync",
        author="Test Author",
    )
    storage.wait_for_idle(timeout_seconds=1.0)

    diag = storage.get_sync_diagnostics()
    assert diag["outbox"]["failed"] >= 1
    assert diag["metrics"]["failed"] >= 1
