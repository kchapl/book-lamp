class MockStorage:
    def __init__(self):
        self.books = []
        self.reading_records = []
        self.next_book_id = 1
        self.next_record_id = 1

    def is_authorized(self):
        """Always authorized in mock mode."""
        return True

    def get_all_books(self):
        return self.books

    def get_reading_records(self, book_id=None):
        if book_id is None:
            return self.reading_records
        return [r for r in self.reading_records if r["book_id"] == book_id]

    def get_book_by_id(self, book_id):
        for book in self.books:
            if book["id"] == book_id:
                return book
        return None

    def get_book_by_isbn(self, isbn13):
        for book in self.books:
            if book["isbn13"] == isbn13:
                return book
        return None

    def add_book(
        self, isbn13, title, author, publication_year=None, thumbnail_url=None
    ):
        book = {
            "id": self.next_book_id,
            "isbn13": isbn13,
            "title": title,
            "author": author,
            "publication_year": publication_year,
            "thumbnail_url": thumbnail_url,
            "created_at": "2024-01-01T00:00:00",
        }
        self.books.append(book)
        self.next_book_id += 1
        return book

    def add_reading_record(self, book_id, status, start_date, end_date=None, rating=0):
        record = {
            "id": self.next_record_id,
            "book_id": book_id,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "rating": rating,
            "created_at": "2024-01-01T00:00:00",
        }
        self.reading_records.append(record)
        self.next_record_id += 1
        return record

    def delete_book(self, book_id):
        for i, book in enumerate(self.books):
            if book["id"] == book_id:
                self.books.pop(i)
                return True
        return False
