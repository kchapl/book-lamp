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

    records = storage.get_readings()
    assert len(records) == 0

    storage.remove_from_reading_list(b2["id"])
    rl = storage.get_reading_list()
    assert len(rl) == 1
    assert rl[0]["book_id"] == b1["id"]
    assert rl[0]["position"] == 1

    records = storage.get_readings()
    assert len(records) == 0


def test_an_unqueued_book_is_the_readers_without_being_in_the_queue():
    """A Book saved with the tickbox clear still belongs to its reader.

    The catalogue is shared, so the Reading List row is the only thing that makes
    the Book theirs; the queue is the narrower claim, and it stays empty.
    """
    storage = MockStorage()
    book = storage.add_book("3333333333333", "Book 3", "Author 3")

    storage.add_to_reading_list(book["id"], queued=False)

    assert [item["book_id"] for item in storage.reading_list] == [book["id"]]
    assert storage.get_reading_list() == []

    storage.add_to_reading_list(book["id"])

    assert [item["book_id"] for item in storage.get_reading_list()] == [book["id"]]
    assert storage.get_reading_list()[0]["position"] == 1


def test_queueing_an_unqueued_book_comes_after_the_books_already_queued():
    storage = MockStorage()
    first = storage.add_book("4444444444444", "Book 4", "Author 4")
    second = storage.add_book("5555555555555", "Book 5", "Author 5")

    storage.add_to_reading_list(first["id"])
    storage.add_to_reading_list(second["id"], queued=False)
    storage.add_to_reading_list(second["id"])

    assert [item["book_id"] for item in storage.get_reading_list()] == [first["id"], second["id"]]


def test_reordering_the_queue_keeps_an_unqueued_book():
    storage = MockStorage()
    queued = storage.add_book("6666666666666", "Book 6", "Author 6")
    unqueued = storage.add_book("7777777777777", "Book 7", "Author 7")

    storage.add_to_reading_list(queued["id"])
    storage.add_to_reading_list(unqueued["id"], queued=False)
    storage.update_reading_list_order([queued["id"]])

    assert [item["book_id"] for item in storage.reading_list] == [queued["id"], unqueued["id"]]
    assert storage.get_reading_list()[0]["position"] == 1
