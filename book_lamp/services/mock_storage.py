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
        self,
        isbn13,
        title,
        author,
        publication_year=None,
        thumbnail_url=None,
        publisher=None,
        description=None,
        series=None,
        dewey_decimal=None,
    ):
        book = {
            "id": self.next_book_id,
            "isbn13": isbn13,
            "title": title,
            "author": author,
            "publication_year": publication_year,
            "thumbnail_url": thumbnail_url,
            "created_at": "2024-01-01T00:00:00",
            "publisher": publisher,
            "description": description,
            "series": series,
            "dewey_decimal": dewey_decimal,
        }
        self.books.append(book)
        self.next_book_id += 1
        return book

    def update_book(
        self,
        book_id,
        isbn13,
        title,
        author,
        publication_year=None,
        thumbnail_url=None,
        publisher=None,
        description=None,
        series=None,
        dewey_decimal=None,
    ):
        for book in self.books:
            if book["id"] == book_id:
                book.update(
                    {
                        "isbn13": isbn13,
                        "title": title,
                        "author": author,
                        "publication_year": publication_year,
                        "thumbnail_url": thumbnail_url or book.get("thumbnail_url"),
                        "publisher": publisher or book.get("publisher"),
                        "description": description or book.get("description"),
                        "series": series or book.get("series"),
                        "dewey_decimal": dewey_decimal or book.get("dewey_decimal"),
                    }
                )
                return book
        raise Exception(f"Book with ID {book_id} not found")

    def upsert_book(
        self,
        isbn13,
        title,
        author,
        publication_year=None,
        thumbnail_url=None,
        publisher=None,
        description=None,
        series=None,
        dewey_decimal=None,
    ):
        existing = self.get_book_by_isbn(isbn13)
        if existing:
            return self.update_book(
                book_id=existing["id"],
                isbn13=isbn13,
                title=title,
                author=author,
                publication_year=publication_year,
                thumbnail_url=thumbnail_url,
                publisher=publisher,
                description=description,
                series=series,
                dewey_decimal=dewey_decimal,
            )
        else:
            return self.add_book(
                isbn13=isbn13,
                title=title,
                author=author,
                publication_year=publication_year,
                thumbnail_url=thumbnail_url,
                publisher=publisher,
                description=description,
                series=series,
                dewey_decimal=dewey_decimal,
            )

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

    def bulk_import(self, items):
        import_count = 0
        for item in items:
            book_data = item["book"]
            record_data = item["record"]

            book = self.upsert_book(
                isbn13=book_data["isbn13"],
                title=book_data["title"],
                author=book_data["author"],
                publication_year=book_data["publication_year"],
                publisher=book_data.get("publisher"),
                description=book_data.get("description"),
                series=book_data.get("series"),
                dewey_decimal=book_data.get("dewey_decimal"),
            )

            if record_data:
                # Basic dedup check
                is_duplicate = False
                for r in self.reading_records:
                    if (
                        r["book_id"] == book["id"]
                        and r["status"] == record_data["status"]
                    ):
                        if record_data["status"] == "Completed":
                            if r.get("end_date") == record_data.get("end_date"):
                                is_duplicate = True
                                break
                        elif record_data["status"] == "In Progress":
                            is_duplicate = True
                            break
                        else:
                            if r["start_date"] == record_data["start_date"]:
                                is_duplicate = True
                                break

                if not is_duplicate:
                    self.add_reading_record(
                        book_id=book["id"],
                        status=record_data["status"],
                        start_date=record_data["start_date"],
                        end_date=record_data["end_date"],
                        rating=record_data["rating"],
                    )
            import_count += 1
        return import_count

    def search(self, query):
        """Search across all book data fields.

        Args:
            query: Search query (free text).

        Returns:
            List of matching books with reading_records attached, sorted by relevance.
        """
        from book_lamp.services.search import search_books

        return search_books(self.books, self.reading_records, query)
