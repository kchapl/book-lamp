import logging
from datetime import datetime, timezone
from typing import Any, List, Optional

from book_lamp.services.stats_calculator import resolve_physical_format
from book_lamp.utils.authors import display, parse
from book_lamp.utils.books import (
    Category,
    cover_is_blank,
    full_title,
    normalise_title_pair,
    resolve_category,
)
from book_lamp.utils.reading_status import READING_STATUSES
from book_lamp.utils.readings import RATED_STATUS, iso_date_string, require_end_date, require_rating

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
        self.readings: list[dict[str, Any]] = []
        self.reading_list: list[dict[str, Any]] = []
        self.recommendations: list[dict[str, Any]] = []
        self.settings: dict[str, str] = {}
        self.next_book_id = 1
        self.next_reading_id = 1
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

    def get_books_missing_covers(
        self,
        book_ids: Optional[list[int]] = None,
        placeholder_hosts: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Books with no cover, optionally narrowed to the given ids.

        A cover hosted where placeholders are served is included too: storage
        cannot read bytes, so the run fingerprints it and decides.
        """
        wanted = set(book_ids or [])

        def no_cover(value: Any) -> bool:
            return value is None or (isinstance(value, str) and not value.strip())

        def on_placeholder_host(book: dict[str, Any]) -> bool:
            covers = [book.get("thumbnail_url"), book.get("cover_url")]
            return any(isinstance(url, str) and host in url for url in covers for host in (placeholder_hosts or []))

        return [
            book
            for book in self.books
            if (not wanted or book["id"] in wanted)
            and ((no_cover(book.get("thumbnail_url")) and no_cover(book.get("cover_url"))) or on_placeholder_host(book))
        ]

    def set_book_cover(
        self,
        book_id: int,
        isbn13: str,
        thumbnail_url: Optional[str] = None,
        cover_url: Optional[str] = None,
        replace_urls: Optional[list[str]] = None,
    ) -> bool:
        """Write a Book's cover fields while it still has the ISBN it had.

        A corrected ISBN means the cover the lookup found belongs to a different
        edition, so the write is refused rather than attached to the wrong Book.
        A stored cover may be replaced only when it is one of ``replace_urls``,
        the placeholder URLs the run fingerprinted.
        """
        book = self.get_book_by_id(book_id)
        if book is None or book.get("isbn13") != isbn13:
            return False

        # A cover the reader added while the run was looking is kept: the run
        # only ever fills a gap it saw at the start, or replaces a placeholder
        # it has just fingerprinted. Each field being written is checked on its
        # own, so a placeholder left in the other field cannot authorise
        # overwriting a real cover the reader has saved since.
        replaceable = {url for url in (replace_urls or []) if url}

        def writable(field: str) -> bool:
            value = book.get(field)
            return cover_is_blank(value) or (isinstance(value, str) and value.strip() in replaceable)

        if thumbnail_url and not writable("thumbnail_url"):
            return False
        if cover_url and not writable("cover_url"):
            return False
        if thumbnail_url:
            book["thumbnail_url"] = thumbnail_url
        if cover_url:
            book["cover_url"] = cover_url
        return True

    def get_readings(self, book_id: Optional[int] = None) -> list[dict[str, Any]]:
        records = []
        if book_id is None:
            records = list(self.readings)
        else:
            records = [r for r in self.readings if r["book_id"] == book_id]
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
        authors: List[str],
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
        subtitle: Optional[str] = None,
    ) -> dict[str, Any]:
        from book_lamp.utils.books import normalize_isbn

        # One list and one display string, the string derived from the list, so
        # this adapter and Postgres present a Book's authors the same way.
        authors = [str(name).strip() for name in authors if str(name).strip()]
        # A binding is stored as one of the four labels; a media type or a
        # language code arriving in the field names no binding and is dropped.
        physical_format = resolve_physical_format(physical_format)
        book = {
            "id": self.next_book_id,
            "isbn13": normalize_isbn(isbn13),
            "title": title,
            "subtitle": subtitle,
            "author": display(authors),
            "authors": authors,
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
        }
        self.books.append(book)
        self.next_book_id += 1
        return book

    def update_book(
        self,
        book_id: int,
        isbn13: str,
        title: str,
        authors: List[str],
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
        subtitle: Optional[str] = None,
        physical_format_provided: bool = False,
    ) -> dict[str, Any]:
        for book in self.books:
            if book["id"] == book_id:
                authors = [str(name).strip() for name in authors if str(name).strip()]
                # The triple resolves through the one rule, shared with the
                # Postgres adapter and the import paths (see ADR-0002).
                resolved = resolve_category(
                    Category.from_fields(bisac_category, bisac_main_category, bisac_sub_category),
                    Category.from_mapping(book),
                )

                book.update(
                    {
                        "isbn13": isbn13,
                        "title": title,
                        "subtitle": subtitle,
                        "author": display(authors),
                        "authors": authors,
                        "publication_year": publication_year,
                        "thumbnail_url": thumbnail_url or book.get("thumbnail_url"),
                        "publisher": publisher or book.get("publisher"),
                        "description": description or book.get("description"),
                        "series": series or book.get("series"),
                        "bisac_category": resolved.category,
                        "bisac_main_category": resolved.main,
                        "bisac_sub_category": resolved.sub,
                        "language": language or book.get("language"),
                        "page_count": page_count or book.get("page_count"),
                        # A blank that arrives from the edit form is an explicit
                        # clear, so it is told apart from a field the caller never
                        # mentioned rather than read as "keep the old value".
                        "physical_format": resolve_physical_format(
                            physical_format,
                            book.get("physical_format"),
                            provided=physical_format_provided,
                        ),
                        "edition": edition or book.get("edition"),
                        "cover_url": cover_url or book.get("cover_url"),
                    }
                )
                return book
        logger.error(f"Book with ID {book_id} not found")
        raise Exception(f"Book with ID {book_id} not found")

    def upsert_book(
        self,
        isbn13: str,
        title: str,
        authors: List[str],
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
        subtitle: Optional[str] = None,
    ) -> dict[str, Any]:
        existing = self.get_book_by_isbn(isbn13)
        if existing:
            return self.update_book(
                book_id=existing["id"],
                isbn13=isbn13,
                title=title,
                # Postgres keeps the stored subtitle when an upsert supplies
                # none, so the mock must too: re-adding a Book without one does
                # not erase the subtitle it already had.
                subtitle=subtitle if subtitle is not None else existing.get("subtitle"),
                authors=authors,
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
            )
        else:
            return self.add_book(
                isbn13=isbn13,
                title=title,
                subtitle=subtitle,
                authors=authors,
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
            )

    def add_reading(
        self,
        book_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
        require_end_date(status, end_date)
        require_rating(status, rating)
        record = {
            "id": self.next_reading_id,
            "book_id": book_id,
            "status": status,
            "start_date": start_date,
            "end_date": end_date,
            "rating": rating,
            "created_at": "2024-01-01T00:00:00",
        }
        self.readings.append(record)
        self.next_reading_id += 1
        logger.info(f"READING_RECORD_ADDED: book_id={book_id}, status='{status}', id={record['id']}")
        return record

    def update_reading(
        self,
        reading_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
        require_end_date(status, end_date)
        require_rating(status, rating)
        for record in self.readings:
            if record["id"] == reading_id:
                old_status = record.get("status")
                record.update(
                    {
                        "status": status,
                        "start_date": start_date,
                        "end_date": end_date,
                        "rating": rating,
                    }
                )
                logger.info(f"READING_UPDATED: id={reading_id}, status_change='{old_status}'->'{status}'")
                return record
        logger.error(f"Reading record with ID {reading_id} not found")
        raise Exception(f"Reading record with ID {reading_id} not found")

    def delete_reading(self, reading_id: int) -> bool:
        for i, record in enumerate(self.readings):
            if record["id"] == reading_id:
                self.readings.pop(i)
                return True
        return False

    def delete_book(self, book_id: int) -> bool:
        for i, book in enumerate(self.books):
            if book["id"] == book_id:
                self.books.pop(i)
                return True
        return False

    def get_reading_list(self) -> list[dict[str, Any]]:
        result = []
        book_map = {b["id"]: b for b in self.books}
        for item in sorted(self.reading_list, key=lambda x: x["position"]):
            book = book_map.get(item["book_id"])
            if book:
                enriched = item.copy()
                enriched["title"] = book.get("title", "")
                enriched["subtitle"] = book.get("subtitle")
                enriched["author"] = book.get("author", "")
                enriched["thumbnail_url"] = book.get("thumbnail_url")
                result.append(enriched)
        return result

    def add_to_reading_list(self, book_id: int) -> None:
        if any(item["book_id"] == book_id for item in self.reading_list):
            logger.info(f"Book {book_id} is already in the reading list (MockStorage)")
            return
        pos = max((item["position"] for item in self.reading_list), default=0) + 1
        self.reading_list.append({"book_id": book_id, "position": pos, "created_at": "2024-01-01T00:00:00"})
        logger.info(f"Successfully added book {book_id} to reading list (MockStorage)")

    def remove_from_reading_list(self, book_id: int) -> None:
        for i, item in enumerate(self.reading_list):
            if item["book_id"] == book_id:
                self.reading_list.pop(i)
                logger.info(f"Successfully removed book {book_id} from reading list (MockStorage)")
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

    def bulk_import(
        self,
        items: list[dict[str, Any]],
        infer_subtitles: bool = False,
        write_names: bool = True,
    ) -> int:
        """Write imported rows, keeping a stored Book's title and subtitle apart.

        Only ``infer_subtitles`` reads a combined title as provider text; the
        metadata backfill resends every stored Book, and a reader may have kept
        ``Foo Bar: Baz`` whole by clearing its subtitle. That backfill also
        passes ``write_names=False``, because its snapshot predates the lookups
        and a title split may have landed since.
        """
        import_count = 0
        for item in items:
            book_data = item["book"]
            record_data = item["record"]

            imported_authors = book_data.get("authors") or parse(str(book_data.get("author") or ""))
            if write_names:
                title, subtitle = normalise_title_pair(
                    book_data["title"],
                    book_data.get("subtitle"),
                    infer_subtitle=infer_subtitles,
                )
            else:
                existing = self.get_book_by_isbn(book_data["isbn13"])
                title = existing["title"] if existing else book_data["title"]
                subtitle = existing.get("subtitle") if existing else book_data.get("subtitle")
            book = self.upsert_book(
                isbn13=book_data["isbn13"],
                title=title,
                subtitle=subtitle,
                authors=imported_authors,
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
            )

            if record_data:
                is_duplicate = False
                matched_record = None

                r_status = record_data["status"]
                r_start = record_data["start_date"]
                r_end = record_data.get("end_date")
                require_end_date(r_status, r_end)
                require_rating(r_status, record_data.get("rating") or 0)

                for r in self.readings:
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
                            if ek_status == r_status and ek_start == r_start and ek_end == r_end:
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
                            "rating": (
                                (record_data.get("rating") or matched_record.get("rating", 0))
                                if r_status == RATED_STATUS
                                else 0
                            ),
                        }
                    )
                    logger.info(
                        f"READING_UPDATED (Mock bulk): id={matched_record['id']}, "
                        f"status_change='{old_status}'->'{r_status}'"
                    )
                else:
                    self.add_reading(
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

        self.add_reading(book_id=book_id, status="In Progress", start_date=date.today().isoformat())

    def get_reading_history(self) -> list[dict[str, Any]]:
        """Retrieve all readings joined with book metadata."""
        history = []
        book_map = {b["id"]: b for b in self.books}
        # Use get_readings to ensure consistency with GoogleSheetsStorage
        records = self.get_readings()
        for record in records:
            # The reading log view should not show books that are in 'Plan to read' status.
            # The books in the reading log should be either in progress, completed or abandoned.
            if record.get("status") not in READING_STATUSES:
                continue

            book = book_map.get(record["book_id"])
            if book:
                # Create a copy of the record and enrich it
                enriched_record = record.copy()
                enriched_record["book_title_main"] = book["title"]
                enriched_record["book_subtitle"] = book.get("subtitle")
                enriched_record["book_title"] = full_title(book["title"], book.get("subtitle"))
                enriched_record["book_author"] = book["author"]
                enriched_record["book_authors"] = book.get("authors", [])
                enriched_record["book_thumbnail_url"] = book.get("thumbnail_url")
                enriched_record["book_cover_url"] = book.get("cover_url")
                enriched_record["book_publication_year"] = book.get("publication_year")
                for field in ("start_date", "end_date", "created_at"):
                    enriched_record[field] = iso_date_string(enriched_record.get(field))
                history.append(enriched_record)

        return history

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search across all book data fields.

        Args:
            query: Search query (free text).

        Returns:
            List of matching books with readings attached, sorted by relevance.
        """
        from book_lamp.services.search import search_books

        return search_books(self.books, self.readings, query)

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
