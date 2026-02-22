from book_lamp.services.mock_storage import MockStorage


def test_reading_list_mock_storage():
    storage = MockStorage()

    b1 = storage.add_book("1111111111111", "Book 1", "Author 1")
    b2 = storage.add_book("2222222222222", "Book 2", "Author 2")

    assert len(storage.get_reading_list()) == 0

    storage.add_to_reading_list(b1["id"])
    storage.add_to_reading_list(b2["id"])

    rl = storage.get_reading_list()
    assert len(rl) == 2
    assert rl[0]["book_id"] == b1["id"]
    assert rl[0]["position"] == 1
    assert rl[1]["book_id"] == b2["id"]
    assert rl[1]["position"] == 2

    storage.update_reading_list_order([b2["id"], b1["id"]])
    rl = storage.get_reading_list()
    assert rl[0]["book_id"] == b2["id"]
    assert rl[0]["position"] == 1
    assert rl[1]["book_id"] == b1["id"]
    assert rl[1]["position"] == 2

    records = storage.get_reading_records()
    assert len(records) == 2
    assert any(
        r["book_id"] == b1["id"] and r["status"] == "Plan to Read" for r in records
    )
    assert any(
        r["book_id"] == b2["id"] and r["status"] == "Plan to Read" for r in records
    )

    storage.remove_from_reading_list(b2["id"])
    rl = storage.get_reading_list()
    assert len(rl) == 1
    assert rl[0]["book_id"] == b1["id"]
    assert rl[0]["position"] == 1

    records = storage.get_reading_records()
    assert len(records) == 1
