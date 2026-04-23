import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class MockStorage:
    def __init__(
        self,
        sheet_name: str = "MockData",
        credentials_dict: Optional[dict] = None,
        spreadsheet_id: Optional[str] = None,
    ) -> None:
        self.sheet_name = sheet_name
        self.spreadsheet_id = spreadsheet_id
        self.books: list[dict[str, Any]] = []
        self.reading_records: list[dict[str, Any]] = []
        self.reading_list: list[dict[str, Any]] = []
        self.recommendations: list[dict[str, Any]] = []
        self.settings: dict[str, str] = {}
        self.next_book_id = 1
        self.next_record_id = 1
        self._authorised = False  # Default to False for security and testing

    def prefetch(self) -> None:
        """Mock implementation of prefetch - does nothing as data is already in memory."""
        pass

    def is_authorised(self) -> bool:
        """Authorisation state can be toggled in mock mode for testing."""
        return self._authorised

    def set_authorised(self, status: bool) -> None:
        """Manually set authorisation status (used for E2E tests)."""
        self._authorised = status

    def get_all_books(self) -> list[dict[str, Any]]:
        return self.books

    def get_reading_records(
        self, book_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        records = []
        if book_id is None:
            records = list(self.reading_records)
        else:
            records = [r for r in self.reading_records if r["book_id"] == book_id]
        return records

    def get_book_by_id(self, book_id: int) -> Optional[dict[str, Any]]:
        for book in self.books:
            if book["id"] == book_id:
                return book
        return None

    def get_book_by_isbn(self, isbn13: str) -> Optional[dict[str, Any]]:
        from book_lamp.utils.books import normalize_isbn

        target_isbn = normalize_isbn(isbn13)
        for book in self.books:
            if normalize_isbn(book["isbn13"]) == target_isbn:
                return book
        return None

    def add_book(
        self,
        isbn13: str,
        title: str,
        author: str,
        publication_year: Optional[int] = None,
        thumbnail_url: Optional[str] = None,
        publisher: Optional[str] = None,
        description: Optional[str] = None,
        series: Optional[str] = None,
        bisac_category: Optional[str] = None,
        bisac_main_category: Optional[str] = None,
        bisac_sub_category: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
        broad_category: Optional[str] = None,
    ) -> dict[str, Any]:
        from book_lamp.utils.authors import split_authors
        from book_lamp.utils.books import normalize_isbn

        book = {
            "id": self.next_book_id,
            "isbn13": normalize_isbn(isbn13),
            "title": title,
            "author": author,
            "authors": split_authors(author),
            "publication_year": publication_year,
            "thumbnail_url": thumbnail_url,
            "created_at": "2024-01-01T00:00:00",
            "publisher": publisher,
            "description": description,
            "series": series,
            "bisac_category": bisac_category,
            "bisac_main_category": bisac_main_category,
            "bisac_sub_category": bisac_sub_category,
            "language": language,
            "page_count": page_count,
            "physical_format": physical_format,
            "edition": edition,
            "cover_url": cover_url,
            "broad_category": broad_category,
        }
        self.books.append(book)
        self.next_book_id += 1
        return book

    def update_book(
        self,
        book_id: int,
        isbn13: str,
        title: str,
        author: str,
        publication_year: Optional[int] = None,
        thumbnail_url: Optional[str] = None,
        publisher: Optional[str] = None,
        description: Optional[str] = None,
        series: Optional[str] = None,
        bisac_category: Optional[str] = None,
        bisac_main_category: Optional[str] = None,
        bisac_sub_category: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
        broad_category: Optional[str] = None,
    ) -> dict[str, Any]:
        from book_lamp.utils.authors import split_authors

        for book in self.books:
            if book["id"] == book_id:
                # Mirror BISAC prioritization logic
                new_bisac = bisac_category
                existing_bisac = book.get("bisac_category")

                def is_dewey(val):
                    if not val:
                        return False
                    return all(c.isdigit() or c in ". " for c in str(val))

                if new_bisac and not is_dewey(new_bisac):
                    final_bisac: Optional[str] = new_bisac
                    final_bisac_main: Optional[str] = bisac_main_category or book.get(
                        "bisac_main_category"
                    )
                    final_bisac_sub: Optional[str] = bisac_sub_category or book.get(
                        "bisac_sub_category"
                    )
                else:
                    final_bisac = existing_bisac or new_bisac
                    final_bisac_main = (
                        book.get("bisac_main_category") or bisac_main_category
                    )
                    final_bisac_sub = (
                        book.get("bisac_sub_category") or bisac_sub_category
                    )

                book.update(
                    {
                        "isbn13": isbn13,
                        "title": title,
                        "author": author,
                        "authors": split_authors(author),
                        "publication_year": publication_year,
                        "thumbnail_url": thumbnail_url or book.get("thumbnail_url"),
                        "publisher": publisher or book.get("publisher"),
                        "description": description or book.get("description"),
                        "series": series or book.get("series"),
                        "bisac_category": final_bisac,
                        "bisac_main_category": final_bisac_main,
                        "bisac_sub_category": final_bisac_sub,
                        "language": language or book.get("language"),
                        "page_count": page_count or book.get("page_count"),
                        "physical_format": physical_format
                        or book.get("physical_format"),
                        "edition": edition or book.get("edition"),
                        "cover_url": cover_url or book.get("cover_url"),
                        "broad_category": broad_category or book.get("broad_category"),
                    }
                )
                return book
        logger.error(f"Book with ID {book_id} not found")
        raise Exception(f"Book with ID {book_id} not found")

    def batch_update_broad_categories(self, updates: list[dict[str, Any]]) -> int:
        """Batch update broad categories for multiple books."""
        count = 0
        for update in updates:
            bid = update["id"]
            cat = update["broad_category"]
            for book in self.books:
                if book["id"] == bid:
                    book["broad_category"] = cat
                    count += 1
                    break
        return count

    def upsert_book(
        self,
        isbn13: str,
        title: str,
        author: str,
        publication_year: Optional[int] = None,
        thumbnail_url: Optional[str] = None,
        publisher: Optional[str] = None,
        description: Optional[str] = None,
        series: Optional[str] = None,
        bisac_category: Optional[str] = None,
        bisac_main_category: Optional[str] = None,
        bisac_sub_category: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
        broad_category: Optional[str] = None,
    ) -> dict[str, Any]:
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
                bisac_category=bisac_category,
                bisac_main_category=bisac_main_category,
                bisac_sub_category=bisac_sub_category,
                language=language,
                page_count=page_count,
                physical_format=physical_format,
                edition=edition,
                cover_url=cover_url,
                broad_category=broad_category,
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
                bisac_category=bisac_category,
                bisac_main_category=bisac_main_category,
                bisac_sub_category=bisac_sub_category,
                language=language,
                page_count=page_count,
                physical_format=physical_format,
                edition=edition,
                cover_url=cover_url,
                broad_category=broad_category,
            )

    def add_reading_record(
        self,
        book_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
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
        logger.info(
            f"READING_RECORD_ADDED: book_id={book_id}, status='{status}', id={record['id']}"
        )
        return record

    def update_reading_record(
        self,
        record_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
        for record in self.reading_records:
            if record["id"] == record_id:
                old_status = record.get("status")
                record.update(
                    {
                        "status": status,
                        "start_date": start_date,
                        "end_date": end_date,
                        "rating": rating,
                    }
                )
                logger.info(
                    f"READING_RECORD_UPDATED: id={record_id}, status_change='{old_status}'->'{status}'"
                )
                return record
        logger.error(f"Reading record with ID {record_id} not found")
        raise Exception(f"Reading record with ID {record_id} not found")

    def delete_reading_record(self, record_id: int) -> bool:
        for i, record in enumerate(self.reading_records):
            if record["id"] == record_id:
                self.reading_records.pop(i)
                return True
        return False

    def delete_book(self, book_id: int) -> bool:
        for i, book in enumerate(self.books):
            if book["id"] == book_id:
                self.books.pop(i)
                return True
        return False

    def get_reading_list(self) -> list[dict[str, Any]]:
        return sorted(self.reading_list, key=lambda x: x["position"])

    def add_to_reading_list(self, book_id: int) -> None:
        if any(item["book_id"] == book_id for item in self.reading_list):
            logger.info(f"Book {book_id} is already in the reading list (MockStorage)")
            return
        pos = max((item["position"] for item in self.reading_list), default=0) + 1
        self.reading_list.append(
            {"book_id": book_id, "position": pos, "created_at": "2024-01-01T00:00:00"}
        )
        logger.info(f"Successfully added book {book_id} to reading list (MockStorage)")

    def remove_from_reading_list(self, book_id: int) -> None:
        for i, item in enumerate(self.reading_list):
            if item["book_id"] == book_id:
                self.reading_list.pop(i)
                logger.info(
                    f"Successfully removed book {book_id} from reading list (MockStorage)"
                )
                break
        # Reassign positions
        for idx, item in enumerate(self.reading_list):
            item["position"] = idx + 1

    def update_reading_list_order(self, book_ids: list[int]) -> None:
        item_map = {item["book_id"]: item for item in self.reading_list}
        new_list = []
        pos = 1
        for bid in book_ids:
            if bid in item_map:
                item = item_map[bid]
                item["position"] = pos
                new_list.append(item)
                pos += 1
        self.reading_list = new_list

    def bulk_import(self, items: list[dict[str, Any]]) -> int:
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
                bisac_category=book_data.get("bisac_category"),
                bisac_main_category=book_data.get("bisac_main_category"),
                bisac_sub_category=book_data.get("bisac_sub_category"),
                language=book_data.get("language"),
                page_count=book_data.get("page_count"),
                physical_format=book_data.get("physical_format"),
                edition=book_data.get("edition"),
                thumbnail_url=book_data.get("thumbnail_url"),
                cover_url=book_data.get("cover_url"),
                broad_category=book_data.get("broad_category"),
            )

            if record_data:
                is_duplicate = False
                matched_record = None

                r_status = record_data["status"]
                r_start = record_data["start_date"]
                r_end = record_data.get("end_date")

                for r in self.reading_records:
                    if r["book_id"] == book["id"]:
                        ek_status = r["status"]
                        ek_start = r["start_date"]
                        ek_end = r.get("end_date")

                        is_same_attempt = False
                        if ek_start and r_start and ek_start == r_start:
                            is_same_attempt = True
                        elif (
                            r_status == "Completed"
                            and ek_status == "Completed"
                            and ek_end
                            and r_end
                            and ek_end == r_end
                        ):
                            is_same_attempt = True
                        elif ek_status == "In Progress":
                            is_same_attempt = True

                        if is_same_attempt:
                            if (
                                ek_status == r_status
                                and ek_start == r_start
                                and ek_end == r_end
                            ):
                                is_duplicate = True
                            else:
                                matched_record = r
                            break

                if is_duplicate:
                    pass
                elif matched_record:
                    old_status = matched_record.get("status")
                    matched_record.update(
                        {
                            "status": r_status,
                            "start_date": r_start,
                            "end_date": r_end,
                            "rating": record_data.get("rating")
                            or matched_record.get("rating", 0),
                        }
                    )
                    logger.info(
                        f"READING_RECORD_UPDATED (Mock bulk): id={matched_record['id']}, "
                        f"status_change='{old_status}'->'{r_status}'"
                    )
                else:
                    self.add_reading_record(
                        book_id=book["id"],
                        status=r_status,
                        start_date=r_start,
                        end_date=r_end,
                        rating=record_data.get("rating") or 0,
                    )
            import_count += 1
        return import_count

    def start_reading(self, book_id: int) -> None:
        """Atomic operation: remove from reading list and add 'In Progress' record."""
        # 1. Remove from reading list
        self.remove_from_reading_list(book_id)

        # 2. Add 'In Progress' record
        from datetime import date

        self.add_reading_record(
            book_id=book_id, status="In Progress", start_date=date.today().isoformat()
        )

    def get_reading_history(self) -> list[dict[str, Any]]:
        """Retrieve all reading records joined with book metadata."""
        history = []
        book_map = {b["id"]: b for b in self.books}
        # Use get_reading_records to ensure consistency with GoogleSheetsStorage
        records = self.get_reading_records()
        valid_statuses = ["In Progress", "Completed", "Abandoned"]
        for record in records:
            # The reading log view should not show books that are in 'Plan to read' status.
            # The books in the reading log should be either in progress, completed or abandoned.
            if record.get("status") not in valid_statuses:
                continue

            book = book_map.get(record["book_id"])
            if book:
                # Create a copy of the record and enrich it
                enriched_record = record.copy()
                enriched_record["book_title"] = book["title"]
                enriched_record["book_author"] = book["author"]
                enriched_record["book_authors"] = book.get("authors", [])
                enriched_record["book_thumbnail_url"] = book.get("thumbnail_url")
                history.append(enriched_record)
        return history

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search across all book data fields.

        Args:
            query: Search query (free text).

        Returns:
            List of matching books with reading_records attached, sorted by relevance.
        """
        from book_lamp.services.search import search_books

        return search_books(self.books, self.reading_records, query)

    def get_recommendations(self) -> list[dict[str, Any]]:
        """Return cached recommendations."""
        return list(self.recommendations)

    def save_recommendations(self, recommendations: list[dict[str, Any]]) -> None:
        """Persist recommendations, replacing any existing ones."""
        now = datetime.now(timezone.utc).isoformat()
        self.recommendations = [
            {
                "id": i + 1,
                "title": rec.get("title", ""),
                "author": rec.get("author", ""),
                "isbn13": rec.get("isbn13", ""),
                "justification": rec.get("justification", ""),
                "created_at": now,
            }
            for i, rec in enumerate(recommendations)
        ]

    def get_settings(self) -> dict[str, str]:
        """Return a copy of the mock settings."""
        return dict(self.settings)

    def update_setting(self, key: str, value: str) -> None:
        """Update a mock setting."""
        self.settings[key] = value
