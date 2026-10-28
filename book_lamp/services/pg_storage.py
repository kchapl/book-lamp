import datetime
import logging
import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional, cast

import psycopg
from psycopg import OperationalError
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from book_lamp.utils.authors import display, parse
from book_lamp.utils.books import Category, normalize_isbn, resolve_category
from book_lamp.utils.readings import require_end_date

logger = logging.getLogger(__name__)

# Neon serverless has strict connection limits (typically 10)
NEON_DEFAULT_POOL_SIZE = 10
LOCAL_DEFAULT_POOL_SIZE = 20
NEON_CONNECTION_TIMEOUT = 10
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1  # seconds

# Global connection pool initialized from environment
_pool: Optional[ConnectionPool] = None


def is_neon_url(db_url: str) -> bool:
    """Detect if the database URL is from Neon (serverless PostgreSQL)."""
    return "neon.tech" in db_url or "neon.database" in db_url


def get_pool_size(db_url: str) -> int:
    """Determine appropriate pool size based on database type."""
    if is_neon_url(db_url):
        return NEON_DEFAULT_POOL_SIZE
    return LOCAL_DEFAULT_POOL_SIZE


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")

        pool_size = get_pool_size(db_url)

        # Use dict_row by default for all connections from this pool
        # Configure for Neon serverless limits with timeout
        _pool = ConnectionPool(
            conninfo=db_url,
            kwargs={"row_factory": dict_row},
            min_size=min(2, pool_size),
            max_size=pool_size,
            timeout=NEON_CONNECTION_TIMEOUT,
            max_idle=60,
        )
        logger.info(f"PostgreSQL connection pool initialized (size={pool_size})")
    return _pool


def with_retry(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for retrying database operations with exponential backoff.

    Handles Neon 'too many connections' errors and transient failures.
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        last_exception: Optional[Exception] = None
        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except OperationalError as e:
                last_exception = e
                error_msg = str(e).lower()
                # Check for retryable errors (SSL, connection closed, timeouts, pool issues)
                is_retryable = (
                    "too many connections" in error_msg
                    or "connection" in error_msg
                    and "timeout" in error_msg
                    or "pool" in error_msg
                    or "ssl" in error_msg
                    or "consuming input failed" in error_msg
                )
                if not is_retryable or attempt == MAX_RETRIES - 1:
                    raise
                wait_time = RETRY_BACKOFF_BASE * (2**attempt)
                logger.warning(
                    f"Database operation failed (attempt {attempt + 1}/{MAX_RETRIES}), "
                    f"retrying in {wait_time}s: {e}"
                )
                time.sleep(wait_time)
            except Exception:
                raise
        raise (last_exception if last_exception else OperationalError("Max retries exceeded"))

    return wrapper


class PostgresStorage:
    def __init__(self, user_id: int) -> None:
        self.user_id = user_id
        self.pool = get_pool()

    def prefetch(self) -> None:
        """No-op for Postgres - we query as needed."""
        pass

    def is_authorised(self) -> bool:
        """Postgres users are considered authorised if we have their user_id."""
        return True

    def health_check(self) -> bool:
        """Verify database connectivity.

        Returns True if the database is reachable, False otherwise.
        """
        try:
            with self.pool.connection() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    @with_retry
    def get_all_books(self, user_id: Optional[int] = None) -> list[dict[str, Any]]:
        """Return all books known to the system for a given user.

        In multi-user model, returns only books the user has interacted with via readings.
        If user_id is provided, uses that; otherwise uses the instance user_id.
        """
        effective_user_id = user_id or self.user_id
        query = """
            SELECT DISTINCT b.*, array_agg(a.name ORDER BY ba.position) as author_names
            FROM books b
            LEFT JOIN readings rr ON b.id = rr.book_id AND rr.user_id = %s
            LEFT JOIN reading_list rl ON b.id = rl.book_id AND rl.user_id = %s
            LEFT JOIN book_authors ba ON b.id = ba.book_id
            LEFT JOIN authors a ON ba.author_id = a.id
            WHERE rr.id IS NOT NULL OR rl.book_id IS NOT NULL
            GROUP BY b.id
        """
        with self.pool.connection() as conn:
            rows = conn.execute(query, [effective_user_id, effective_user_id]).fetchall()
            books = []
            for row_raw in rows:
                book = cast(Dict[str, Any], row_raw)

                # One spelling of the display string, from the links in stored
                # order, so every path that names a Book's authors agrees.
                authors_list = [a for a in (book.get("author_names") or []) if a is not None]
                book["authors"] = authors_list
                book["author"] = display(authors_list)
                books.append(book)
            return books

    def get_readings(self, book_id: Optional[int] = None) -> list[dict[str, Any]]:
        """Return readings for the current user, optionally filtered by book_id."""
        query = "SELECT * FROM readings WHERE user_id = %s"
        params: list[Any] = [self.user_id]

        if book_id is not None:
            query += " AND book_id = %s"
            params.append(book_id)

        query += " ORDER BY created_at DESC"

        with self.pool.connection() as conn:
            rows = conn.execute(query, params).fetchall()
            records = []
            for row in rows:
                record = dict(row)
                # Convert date objects to ISO strings
                for date_field in ("start_date", "end_date", "created_at"):
                    if isinstance(record.get(date_field), datetime.date):
                        record[date_field] = record[date_field].isoformat()
                records.append(record)
            return records

    def get_book_by_id(self, book_id: int) -> Optional[dict[str, Any]]:
        query = """
            SELECT b.*, array_agg(a.name ORDER BY ba.position) as author_names
            FROM books b
            LEFT JOIN book_authors ba ON b.id = ba.book_id
            LEFT JOIN authors a ON ba.author_id = a.id
            WHERE b.id = %s
            GROUP BY b.id
        """
        with self.pool.connection() as conn:
            row_raw = conn.execute(query, [book_id]).fetchone()
            if not row_raw:
                return None
            row = cast(Dict[str, Any], row_raw)
            book = dict(row)

            book["authors"] = [name for name in (row["author_names"] or []) if name is not None]
            book["author"] = display(book["authors"])

            return book

    def get_book_by_isbn(self, isbn13: str) -> Optional[dict[str, Any]]:
        target_isbn = normalize_isbn(isbn13)
        query = """
            SELECT b.*, array_agg(a.name ORDER BY ba.position) as author_names
            FROM books b
            LEFT JOIN book_authors ba ON b.id = ba.book_id
            LEFT JOIN authors a ON ba.author_id = a.id
            WHERE b.isbn13 = %s
            GROUP BY b.id
        """
        with self.pool.connection() as conn:
            row_raw = conn.execute(query, [target_isbn]).fetchone()
            if not row_raw:
                return None
            row = cast(Dict[str, Any], row_raw)
            book = dict(row)

            book["authors"] = [name for name in (row["author_names"] or []) if name is not None]
            book["author"] = display(book["authors"])
            return book

    def get_reading_list(self) -> list[dict[str, Any]]:
        query = """
            SELECT rl.*, b.title, b.thumbnail_url,
                   (SELECT string_agg(a.name, ', ' ORDER BY ba.position)
                    FROM book_authors ba
                    JOIN authors a ON a.id = ba.author_id
                    WHERE ba.book_id = b.id) AS author
            FROM reading_list rl
            JOIN books b ON rl.book_id = b.id
            WHERE rl.user_id = %s
            ORDER BY rl.position ASC
        """
        with self.pool.connection() as conn:
            rows = conn.execute(query, [self.user_id]).fetchall()
            return [dict(row) for row in rows]

    def get_reading_history(self) -> list[dict[str, Any]]:
        """Retrieve all readings joined with book metadata."""
        query = """
            SELECT rr.*, b.title as book_title, b.thumbnail_url as book_thumbnail_url,
                   array_agg(a.name ORDER BY ba.position) FILTER (WHERE a.name IS NOT NULL) AS book_author_names
            FROM readings rr
            JOIN books b ON rr.book_id = b.id
            LEFT JOIN book_authors ba ON ba.book_id = b.id
            LEFT JOIN authors a ON ba.author_id = a.id
            WHERE rr.user_id = %s AND rr.status IN ('In Progress', 'Completed', 'Abandoned')
            GROUP BY rr.id, b.title, b.thumbnail_url
            ORDER BY rr.start_date DESC, rr.created_at DESC
        """
        with self.pool.connection() as conn:
            rows = conn.execute(query, [self.user_id]).fetchall()
            history = []
            for row_raw in rows:
                row = cast(Dict[str, Any], row_raw)
                enriched = dict(row)
                enriched["book_authors"] = [name for name in (row["book_author_names"] or []) if name is not None]
                enriched["book_author"] = ", ".join(enriched["book_authors"])

                history.append(enriched)
            return history

    def search(self, query: str) -> list[dict[str, Any]]:
        """Search across all book data fields."""
        # We delegate to the pure search function for now, same as MockStorage
        all_books = self.get_all_books(self.user_id)
        # MockStorage search also needs readings to attach status
        all_records = self.get_readings()
        from book_lamp.services.search import search_books

        return search_books(all_books, all_records, query)

    def get_recommendations(self) -> list[dict[str, Any]]:
        query = "SELECT * FROM recommendations WHERE user_id = %s ORDER BY created_at DESC"
        with self.pool.connection() as conn:
            rows = conn.execute(query, [self.user_id]).fetchall()
            return [dict(row) for row in rows]

    def get_settings(self) -> dict[str, str]:
        query = "SELECT key, value FROM settings WHERE user_id = %s"
        with self.pool.connection() as conn:
            rows = conn.execute(query, [self.user_id]).fetchall()
            return {cast(Dict[str, Any], row)["key"]: cast(Dict[str, Any], row)["value"] for row in rows}

    # Write operations
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
    ) -> dict[str, Any]:
        target_isbn = normalize_isbn(isbn13)
        with self.pool.connection() as conn:
            with conn.transaction():
                # This statement is also the create path's conflict path, so a
                # stored category outranks an incoming Dewey code here too
                # (see ADR-0002).
                existing_raw = conn.execute(
                    "SELECT bisac_category, bisac_main_category, bisac_sub_category FROM books WHERE isbn13 = %s",
                    [target_isbn],
                ).fetchone()
                stored = Category.from_mapping(cast(Dict[str, Any], existing_raw)) if existing_raw else Category()
                resolved = resolve_category(
                    Category.from_fields(bisac_category, bisac_main_category, bisac_sub_category),
                    stored,
                )

                # First try atomic upsert
                query = """
                    INSERT INTO books (
                        isbn13, title, publication_year, thumbnail_url,
                        publisher, description, series, bisac_category,
                        bisac_main_category, bisac_sub_category, language,
                        page_count, physical_format, edition, cover_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (isbn13) DO UPDATE SET
                        title = EXCLUDED.title,
                        publication_year = EXCLUDED.publication_year,
                        thumbnail_url = EXCLUDED.thumbnail_url,
                        publisher = EXCLUDED.publisher,
                        description = EXCLUDED.description,
                        series = EXCLUDED.series,
                        bisac_category = EXCLUDED.bisac_category,
                        bisac_main_category = EXCLUDED.bisac_main_category,
                        bisac_sub_category = EXCLUDED.bisac_sub_category,
                        language = EXCLUDED.language,
                        page_count = EXCLUDED.page_count,
                        physical_format = EXCLUDED.physical_format,
                        edition = EXCLUDED.edition,
                        cover_url = EXCLUDED.cover_url
                    RETURNING id
                """
                row_raw = cast(
                    Dict[str, Any],
                    conn.execute(
                        query,
                        [
                            target_isbn,
                            title,
                            publication_year,
                            thumbnail_url,
                            publisher,
                            description,
                            series,
                            resolved.category,
                            resolved.main,
                            resolved.sub,
                            language,
                            page_count,
                            physical_format,
                            edition,
                            cover_url,
                        ],
                    ).fetchone(),
                )
                if not row_raw or not row_raw["id"]:
                    # If for some reason ON CONFLICT didn't work, fetch existing
                    existing = cast(
                        Dict[str, Any],
                        conn.execute("SELECT id FROM books WHERE isbn13 = %s", [target_isbn]).fetchone(),
                    )
                    if existing:
                        book_id = existing["id"]
                    else:
                        raise Exception("Failed to insert or find book")
                else:
                    book_id = row_raw["id"]

                # Handle authors
                self._update_book_authors(conn, book_id, author)

        return self.get_book_by_id(book_id)  # type: ignore

    def _update_book_authors(self, conn: psycopg.Connection[Any], book_id: int, author_str: str) -> None:
        """Helper to sync the authors table and the ordered book_authors links."""
        author_names = parse(author_str)
        # Clear existing links
        conn.execute("DELETE FROM book_authors WHERE book_id = %s", [book_id])

        # position is what every read orders by, so the order the names were
        # split in survives the write (see migration 0006).
        for position, name in enumerate(author_names, start=1):
            # Upsert author
            conn.execute(
                "INSERT INTO authors (name) VALUES (%s) ON CONFLICT (name) DO NOTHING",
                [name],
            )
            author_row = conn.execute("SELECT id FROM authors WHERE name = %s", [name]).fetchone()
            if author_row:
                author_id = author_row["id"]
                conn.execute(
                    """
                    INSERT INTO book_authors (book_id, author_id, position) VALUES (%s, %s, %s)
                    ON CONFLICT (book_id, author_id) DO UPDATE SET position = EXCLUDED.position
                    """,
                    [book_id, author_id, position],
                )

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
    ) -> dict[str, Any]:
        with self.pool.connection() as conn:
            with conn.transaction():
                # Mirror BISAC prioritization logic from MockStorage
                existing_raw = conn.execute(
                    "SELECT bisac_category, bisac_main_category, bisac_sub_category, thumbnail_url, publisher, description, series, language, page_count, physical_format, edition, cover_url FROM books WHERE id = %s",
                    [book_id],
                ).fetchone()
                if not existing_raw:
                    raise Exception(f"Book with ID {book_id} not found")
                existing = cast(Dict[str, Any], existing_raw)

                # The triple resolves through the one rule, shared with the
                # in-memory adapter and the import paths (see ADR-0002).
                resolved = resolve_category(
                    Category.from_fields(bisac_category, bisac_main_category, bisac_sub_category),
                    Category.from_mapping(existing),
                )

                query = """
                    UPDATE books SET
                        isbn13 = %s, title = %s, publication_year = %s,
                        thumbnail_url = %s, publisher = %s, description = %s, series = %s,
                        bisac_category = %s, bisac_main_category = %s, bisac_sub_category = %s,
                        language = %s, page_count = %s, physical_format = %s, edition = %s, cover_url = %s
                    WHERE id = %s
                """
                conn.execute(
                    query,
                    [
                        normalize_isbn(isbn13),
                        title,
                        publication_year,
                        thumbnail_url or existing["thumbnail_url"],
                        publisher or existing["publisher"],
                        description or existing["description"],
                        series or existing["series"],
                        resolved.category,
                        resolved.main,
                        resolved.sub,
                        language or existing["language"],
                        page_count or existing["page_count"],
                        physical_format or existing["physical_format"],
                        edition or existing["edition"],
                        cover_url or existing["cover_url"],
                        book_id,
                    ],
                )
                self._update_book_authors(conn, book_id, author)

        return self.get_book_by_id(book_id)  # type: ignore

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
    ) -> dict[str, Any]:
        # add_book now handles duplicates atomically with ON CONFLICT DO UPDATE
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
        )

    def delete_book(self, book_id: int) -> bool:
        with self.pool.connection() as conn:
            res = conn.execute("DELETE FROM books WHERE id = %s", [book_id])
            return res.rowcount > 0

    def add_reading(
        self,
        book_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
        require_end_date(status, end_date)
        # A Reading is one attempt at a Book, so the same status and start date
        # as an earlier Reading makes a second Reading rather than a duplicate of
        # it: the row is always inserted. Returning the earlier row instead
        # discarded what the reader had typed, and CONTEXT.md expects two
        # Readings to be able to start on the same date.
        query = """
            INSERT INTO readings (user_id, book_id, status, start_date, end_date, rating)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
        """
        with self.pool.connection() as conn:
            row_raw = conn.execute(query, [self.user_id, book_id, status, start_date, end_date, rating]).fetchone()
            if not row_raw:
                raise Exception("Failed to add reading")
            row = cast(Dict[str, Any], row_raw)

        logger.info(f"READING_RECORD_ADDED: book_id={book_id}, status='{status}', id={row['id']}")
        return dict(row)

    def update_reading(
        self,
        reading_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> dict[str, Any]:
        require_end_date(status, end_date)
        query = """
            UPDATE readings
            SET status = %s, start_date = %s, end_date = %s, rating = %s
            WHERE id = %s AND user_id = %s
            RETURNING *
        """
        with self.pool.connection() as conn:
            row_raw = conn.execute(query, [status, start_date, end_date, rating, reading_id, self.user_id]).fetchone()
            if not row_raw:
                raise Exception(f"Reading record with ID {reading_id} not found")
            row = cast(Dict[str, Any], row_raw)

            logger.info(f"READING_UPDATED: id={reading_id}, status='{status}'")
            return dict(row)

    def delete_reading(self, reading_id: int) -> bool:
        with self.pool.connection() as conn:
            res = conn.execute(
                "DELETE FROM readings WHERE id = %s AND user_id = %s",
                [reading_id, self.user_id],
            )
            return res.rowcount > 0

    def add_to_reading_list(self, book_id: int) -> None:
        with self.pool.connection() as conn:
            # Check if already in list
            existing = conn.execute(
                "SELECT 1 FROM reading_list WHERE user_id = %s AND book_id = %s",
                [self.user_id, book_id],
            ).fetchone()
            if existing:
                return

            # Get max position
            row_raw = conn.execute(
                "SELECT COALESCE(MAX(position), 0) as max_pos FROM reading_list WHERE user_id = %s",
                [self.user_id],
            ).fetchone()
            row = cast(Dict[str, Any], row_raw)
            new_pos = (row["max_pos"] if row else 0) + 1

            conn.execute(
                "INSERT INTO reading_list (user_id, book_id, position) VALUES (%s, %s, %s)",
                [self.user_id, book_id, new_pos],
            )
            logger.info(f"Successfully added book {book_id} to reading list (Postgres)")

    def remove_from_reading_list(self, book_id: int) -> None:
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute(
                    "DELETE FROM reading_list WHERE user_id = %s AND book_id = %s",
                    [self.user_id, book_id],
                )
                # Re-order positions
                rows = conn.execute(
                    "SELECT book_id FROM reading_list WHERE user_id = %s ORDER BY position ASC",
                    [self.user_id],
                ).fetchall()
                for i, row_raw in enumerate(rows):
                    row = cast(Dict[str, Any], row_raw)
                    conn.execute(
                        "UPDATE reading_list SET position = %s WHERE user_id = %s AND book_id = %s",
                        [i + 1, self.user_id, row["book_id"]],
                    )

            logger.info(f"Successfully removed book {book_id} from reading list (Postgres)")

    def update_reading_list_order(self, book_ids: list[int]) -> None:
        with self.pool.connection() as conn:
            with conn.transaction():
                for i, bid in enumerate(book_ids):
                    conn.execute(
                        "UPDATE reading_list SET position = %s WHERE user_id = %s AND book_id = %s",
                        [i + 1, self.user_id, bid],
                    )

    def bulk_import(self, items: list[dict[str, Any]]) -> int:
        import_count = 0
        with self.pool.connection() as conn:
            with conn.transaction():
                for item in items:
                    book_data = item["book"]
                    record_data = item["record"]

                    # Reuse upsert_book logic but with the current transaction
                    isbn13 = normalize_isbn(book_data["isbn13"])
                    row_raw = conn.execute(
                        "SELECT id, bisac_category, bisac_main_category, bisac_sub_category FROM books WHERE isbn13 = %s",
                        [isbn13],
                    ).fetchone()
                    if row_raw:
                        row = cast(Dict[str, Any], row_raw)
                        book_id = row["id"]

                        # An imported Dewey code must not undo a category this
                        # Book already has (see ADR-0002).
                        resolved = resolve_category(
                            Category.from_mapping(book_data),
                            Category.from_mapping(row),
                        )

                        # Update book (simplified for bulk)
                        query = """
                            UPDATE books SET
                                title = %s, publication_year = %s,
                                publisher = %s, description = %s, series = %s,
                                bisac_category = %s, bisac_main_category = %s, bisac_sub_category = %s,
                                language = %s, page_count = %s, physical_format = %s, edition = %s,
                                thumbnail_url = COALESCE(%s, thumbnail_url),
                                cover_url = COALESCE(%s, cover_url)
                            WHERE id = %s
                        """
                        conn.execute(
                            query,
                            [
                                book_data["title"],
                                book_data["publication_year"],
                                book_data.get("publisher"),
                                book_data.get("description"),
                                book_data.get("series"),
                                resolved.category,
                                resolved.main,
                                resolved.sub,
                                book_data.get("language"),
                                book_data.get("page_count"),
                                book_data.get("physical_format"),
                                book_data.get("edition"),
                                book_data.get("thumbnail_url"),
                                book_data.get("cover_url"),
                                book_id,
                            ],
                        )
                    else:
                        query = """
                            INSERT INTO books (
                                isbn13, title, publication_year, thumbnail_url,
                                publisher, description, series, bisac_category,
                                bisac_main_category, bisac_sub_category, language,
                                page_count, physical_format, edition, cover_url
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (isbn13) DO UPDATE SET
                                title = EXCLUDED.title,
                                publication_year = EXCLUDED.publication_year,
                                thumbnail_url = EXCLUDED.thumbnail_url
                            RETURNING id
                        """
                        row_raw = conn.execute(
                            query,
                            [
                                isbn13,
                                book_data["title"],
                                book_data["publication_year"],
                                book_data.get("thumbnail_url"),
                                book_data.get("publisher"),
                                book_data.get("description"),
                                book_data.get("series"),
                                book_data.get("bisac_category"),
                                book_data.get("bisac_main_category"),
                                book_data.get("bisac_sub_category"),
                                book_data.get("language"),
                                book_data.get("page_count"),
                                book_data.get("physical_format"),
                                book_data.get("edition"),
                                book_data.get("cover_url"),
                            ],
                        ).fetchone()
                        if not row_raw:
                            continue
                        row = cast(Dict[str, Any], row_raw)
                        book_id = row["id"]

                    self._update_book_authors(conn, book_id, book_data["author"])

                    if record_data:
                        # Find existing record to avoid duplicates
                        r_status = record_data["status"]
                        r_start = record_data["start_date"]
                        r_end = record_data.get("end_date")
                        require_end_date(r_status, r_end)

                        existing_record = conn.execute(
                            "SELECT * FROM readings WHERE user_id = %s AND book_id = %s",
                            [self.user_id, book_id],
                        ).fetchall()

                        is_duplicate = False
                        matched_reading_id = None

                        for r_raw in existing_record:
                            r = cast(Dict[str, Any], r_raw)
                            ek_status = r["status"]

                            ek_start = r["start_date"]
                            ek_end = r["end_date"]

                            is_same_attempt = False
                            if ek_start and r_start and ek_start.isoformat() == str(r_start):
                                is_same_attempt = True
                            elif (
                                r_status == "Completed"
                                and ek_status == "Completed"
                                and ek_end
                                and r_end
                                and ek_end.isoformat() == str(r_end)
                            ):
                                is_same_attempt = True
                            elif ek_status == "In Progress":
                                is_same_attempt = True

                            if is_same_attempt:
                                if (
                                    ek_status == r_status
                                    and (
                                        (not ek_start and not r_start)
                                        or (ek_start and r_start and ek_start.isoformat() == str(r_start))
                                    )
                                    and (
                                        (not ek_end and not r_end)
                                        or (ek_end and r_end and ek_end.isoformat() == str(r_end))
                                    )
                                ):
                                    is_duplicate = True
                                else:
                                    # r was already cast above
                                    matched_reading_id = r["id"]
                                break

                        if not is_duplicate:
                            if matched_reading_id:
                                conn.execute(
                                    "UPDATE readings SET status = %s, start_date = %s, end_date = %s, rating = %s WHERE id = %s",
                                    [
                                        r_status,
                                        r_start,
                                        r_end,
                                        record_data.get("rating") or 0,
                                        matched_reading_id,
                                    ],
                                )
                            else:
                                conn.execute(
                                    "INSERT INTO readings (user_id, book_id, status, start_date, end_date, rating) VALUES (%s, %s, %s, %s, %s, %s)",
                                    [
                                        self.user_id,
                                        book_id,
                                        r_status,
                                        r_start,
                                        r_end,
                                        record_data.get("rating") or 0,
                                    ],
                                )

                    import_count += 1
        return import_count

    def start_reading(self, book_id: int) -> None:
        with self.pool.connection() as conn:
            with conn.transaction():
                # 1. Remove from reading list
                conn.execute(
                    "DELETE FROM reading_list WHERE user_id = %s AND book_id = %s",
                    [self.user_id, book_id],
                )
                # 2. Add In Progress record
                from datetime import date

                conn.execute(
                    "INSERT INTO readings (user_id, book_id, status, start_date) VALUES (%s, %s, %s, %s)",
                    [self.user_id, book_id, "In Progress", date.today().isoformat()],
                )

    def save_recommendations(self, recommendations: list[dict[str, Any]]) -> None:
        with self.pool.connection() as conn:
            with conn.transaction():
                conn.execute("DELETE FROM recommendations WHERE user_id = %s", [self.user_id])
                for rec in recommendations:
                    conn.execute(
                        "INSERT INTO recommendations (user_id, title, author, isbn13, justification) VALUES (%s, %s, %s, %s, %s)",
                        [
                            self.user_id,
                            rec.get("title", ""),
                            rec.get("author", ""),
                            rec.get("isbn13", ""),
                            rec.get("justification", ""),
                        ],
                    )

    def update_setting(self, key: str, value: str) -> None:
        query = """
            INSERT INTO settings (user_id, key, value)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id, key) DO UPDATE
            SET value = EXCLUDED.value
        """
        with self.pool.connection() as conn:
            conn.execute(query, [self.user_id, key, value])

    @classmethod
    def find_user_id_by_email(cls, email: str) -> Optional[int]:
        """Return the id of the user with this email, or None when unknown.

        Read-only, and deliberately so: the MCP service reads as one configured
        reader and refuses to serve anybody else, so an email it has never seen
        is a refusal rather than a new account.
        """
        query = "SELECT id FROM users WHERE email = %s"
        with get_pool().connection() as conn:
            row_raw = conn.execute(query, [email]).fetchone()
        if not row_raw:
            return None
        row = cast(Dict[str, Any], row_raw)
        return int(row["id"])

    @classmethod
    def upsert_user(cls, email: str, name: str) -> int:
        """Upsert a user by email and return their ID. Used by auth flow."""
        query = """
            INSERT INTO users (email, name)
            VALUES (%s, %s)
            ON CONFLICT (email) DO UPDATE
            SET name = EXCLUDED.name
            RETURNING id
        """
        with get_pool().connection() as conn:
            row_raw = conn.execute(query, [email, name]).fetchone()
            if not row_raw:
                raise Exception("Failed to upsert user")
            row = cast(Dict[str, Any], row_raw)
            return int(row["id"])
