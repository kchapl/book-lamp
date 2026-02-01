"""Google Sheets storage adapter for book data."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.oauth2.credentials import Credentials  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

# If modifying these scopes, delete the token.json file.
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


class GoogleSheetsStorage:
    """Adapter for storing book data in Google Sheets.

    Expected sheet structure:
    - 'Books' tab: id, isbn13, title, author, publication_year, thumbnail_url, created_at, publisher, description, series, dewey_decimal
    - 'ReadingRecords' tab: id, book_id, status, start_date, end_date, rating, created_at
    - 'Authors' tab: id, name
    - 'BookAuthors' tab: book_id, author_id
    """

    def __init__(
        self, sheet_name: str, credentials_dict: Optional[Dict[str, Any]] = None
    ):
        """Initialise the storage adapter.

        Args:
            sheet_name: Name of the Google Sheet to use.
            credentials_dict: Dictionary containing OAuth2 credentials.
        """
        self.sheet_name = sheet_name
        self.spreadsheet_id: Optional[str] = None
        self.credentials_dict = credentials_dict
        self.service = None
        self.drive_service = None
        if self.credentials_dict:
            self._connect()

    def _connect(self) -> None:
        """Establish connection to Google Sheets and Drive APIs."""
        creds = self.load_credentials()
        if creds and creds.valid:
            self.service = build("sheets", "v4", credentials=creds)
            self.drive_service = build("drive", "v3", credentials=creds)

    def load_credentials(self) -> Optional[Credentials]:
        """Load credentials from the internal dictionary.

        Client ID and secret are injected from environment variables if not present.
        """
        if not self.credentials_dict:
            return None

        try:
            # Create a copy to avoid mutating the original
            token_data = self.credentials_dict.copy()

            # Inject client credentials from environment variables if missing
            if not token_data.get("client_id"):
                token_data["client_id"] = os.environ.get("GOOGLE_CLIENT_ID")
            if not token_data.get("client_secret"):
                token_data["client_secret"] = os.environ.get("GOOGLE_CLIENT_SECRET")

            creds = Credentials.from_authorized_user_info(token_data, SCOPES)

            # If expired, we let google-auth handle the refresh automatically
            # when requests are made, provided we have a refresh token.
            # We don't manually refresh here because we don't have an easy way
            # to propagate changes back to the session yet.
            # Ideally, we would update the session if the token updates.

            return creds if creds and creds.valid else None
        except (ValueError, KeyError):
            return None

    def is_authorised(self) -> bool:
        """Check if we have valid credentials."""
        creds = self.load_credentials()
        return creds is not None and creds.valid

    def _get_or_create_folder_path(self, path: str) -> str:
        """Get or create a folder hierarchy in Google Drive.

        Args:
            path: Forward-slash separated path, e.g. 'AppData/BookLamp'.

        Returns:
            The ID of the final folder in the path.
        """
        assert self.drive_service is not None
        parts = path.split("/")
        parent_id = "root"

        for part in parts:
            query = f"name = '{part}' and '{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
            results = (
                self.drive_service.files()
                .list(q=query, spaces="drive", fields="files(id, name)")
                .execute()
            )
            files = results.get("files", [])

            if files:
                parent_id = files[0]["id"]
            else:
                # Create the folder
                file_metadata = {
                    "name": part,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [parent_id],
                }
                file = (
                    self.drive_service.files()
                    .create(body=file_metadata, fields="id")
                    .execute()
                )
                parent_id = file.get("id")

        return parent_id

    def _ensure_spreadsheet_id(self) -> str:
        """Ensure we have the spreadsheet ID, discovering or creating it if necessary.

        Returns:
            The ID of the spreadsheet.
        """
        if self.spreadsheet_id:
            return self.spreadsheet_id

        if not self.drive_service or not self.service:
            raise Exception("Not authorised. Please log in via the web interface.")

        # Find or create AppData/BookLamp folder
        folder_id = self._get_or_create_folder_path("AppData/BookLamp")

        # Find the sheet in that folder
        query = (
            f"name = '{self.sheet_name}' and '{folder_id}' in parents and "
            f"mimeType = 'application/vnd.google-apps.spreadsheet' and trashed = false"
        )
        results = (
            self.drive_service.files()
            .list(q=query, spaces="drive", fields="files(id, name)")
            .execute()
        )
        files = results.get("files", [])

        if files:
            self.spreadsheet_id = files[0]["id"]
        else:
            # Create the sheet
            file_metadata = {
                "name": self.sheet_name,
                "mimeType": "application/vnd.google-apps.spreadsheet",
                "parents": [folder_id],
            }
            file = (
                self.drive_service.files()
                .create(body=file_metadata, fields="id")
                .execute()
            )
            self.spreadsheet_id = file.get("id")

            # Initialise it with headers
            self.initialize_sheets()

        return self.spreadsheet_id

    def _get_next_id(self, tab_name: str) -> int:
        """Get the next available ID for a tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range=f"{tab_name}!A:A")
                .execute()
            )
            values = result.get("values", [])
            if len(values) <= 1:  # Only header or empty
                return 1
            # Find max ID (skip header)
            ids = []
            for row in values[1:]:
                if not row or not row[0]:
                    continue
                try:
                    # Handle "1" or "1.0"
                    val = float(row[0])
                    ids.append(int(val))
                except (ValueError, TypeError):
                    continue
            return max(ids) + 1 if ids else 1
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
            return 1

    def get_authors(self) -> List[Dict[str, Any]]:
        """Retrieve all authors from the Authors tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Authors!A:B")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            authors = []
            for row in values[1:]:
                if not row or not row[0].isdigit():
                    continue
                authors.append(
                    {"id": int(row[0]), "name": row[1] if len(row) > 1 else ""}
                )
            return authors
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                return []
            raise Exception(f"Failed to fetch authors: {error}") from error

    def get_book_authors(self) -> List[Dict[str, Any]]:
        """Retrieve all book-author relationships."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="BookAuthors!A:B")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            links = []
            for row in values[1:]:
                if not row or len(row) < 2:
                    continue
                try:
                    bid = int(row[0]) if str(row[0]).isdigit() else None
                    aid = int(row[1]) if str(row[1]).isdigit() else None
                    if bid is not None and aid is not None:
                        links.append({"book_id": bid, "author_id": aid})
                except (ValueError, TypeError):
                    continue
            return links
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                return []
            raise Exception(f"Failed to fetch book authors: {error}") from error

    def _sync_book_authors(self, sid: str, book_id: int, author_str: str) -> None:
        """Sync Authors and BookAuthors tabs based on an author string."""
        assert self.service is not None
        from book_lamp.utils.authors import split_authors

        names = split_authors(author_str)
        if not names:
            return

        # 1. Fetch existing authors
        all_authors = self.get_authors()
        name_to_id = {a["name"]: a["id"] for a in all_authors}
        max_aid = max([a["id"] for a in all_authors] + [0])

        # 2. Identify new authors
        new_authors = []
        author_ids = []
        for name in names:
            if name in name_to_id:
                author_ids.append(name_to_id[name])
            else:
                max_aid += 1
                new_authors.append([max_aid, name])
                author_ids.append(max_aid)
                name_to_id[name] = max_aid

        if new_authors:
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="Authors!A1",
                    valueInputOption="RAW",
                    body={"values": new_authors},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="Authors!A1",
                        valueInputOption="RAW",
                        body={"values": new_authors},
                    ).execute()
                else:
                    raise

        # 3. Update BookAuthors links
        all_links = self.get_book_authors()
        existing_aids = {
            link["author_id"] for link in all_links if link["book_id"] == book_id
        }
        links_to_add = [
            [book_id, aid] for aid in author_ids if aid not in existing_aids
        ]

        if links_to_add:
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="BookAuthors!A1",
                    valueInputOption="RAW",
                    body={"values": links_to_add},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="BookAuthors!A1",
                        valueInputOption="RAW",
                        body={"values": links_to_add},
                    ).execute()
                else:
                    raise

    def get_all_books(self) -> List[Dict[str, Any]]:
        """Retrieve all books from the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:P")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            headers = values[0]
            books_raw = []
            for row in values[1:]:
                if not row or len(row) < 3 or not row[0] or not row[2]:
                    # Skip empty rows or rows without ID or Title
                    continue
                # Pad row to match header length (now 16 columns)
                row = row + [""] * (len(headers) - len(row))
                try:
                    # Handle potential float IDs like "1.0"
                    book_id = int(float(row[0]))
                    pub_year = (
                        int(float(row[4]))
                        if row[4] and str(row[4]).replace(".", "").isdigit()
                        else None
                    )
                    page_count = (
                        int(float(row[12]))
                        if len(row) > 12
                        and row[12]
                        and str(row[12]).replace(".", "").isdigit()
                        else None
                    )
                except (ValueError, TypeError):
                    continue

                book = {
                    "id": book_id,
                    "isbn13": row[1],
                    "title": row[2],
                    "author": row[3],
                    "publication_year": pub_year,
                    "thumbnail_url": row[5] if row[5] else None,
                    "created_at": row[6] if row[6] else None,
                    "publisher": row[7] if len(row) > 7 else None,
                    "description": row[8] if len(row) > 8 else None,
                    "series": row[9] if len(row) > 9 else None,
                    "dewey_decimal": row[10] if len(row) > 10 else None,
                    "language": row[11] if len(row) > 11 else None,
                    "page_count": page_count,
                    "physical_format": row[13] if len(row) > 13 else None,
                    "edition": row[14] if len(row) > 14 else None,
                    "cover_url": row[15] if len(row) > 15 and row[15] else None,
                }
                books_raw.append(book)

            # Fetch authors and links to join
            authors_list = self.get_authors()
            author_map = {a["id"]: a["name"] for a in authors_list}
            links = self.get_book_authors()

            # Map book_id to list of author names
            book_authors_map = {}
            for link in links:
                bid = link["book_id"]
                aid = link["author_id"]
                if aid in author_map:
                    if bid not in book_authors_map:
                        book_authors_map[bid] = []
                    book_authors_map[bid].append(author_map[aid])

            from book_lamp.utils.authors import split_authors

            final_books = []
            for b in books_raw:
                # If we have individual authors in BookAuthors, use them.
                # Otherwise, split the legacy 'author' string.
                if b["id"] in book_authors_map:
                    b["authors"] = book_authors_map[b["id"]]
                else:
                    b["authors"] = split_authors(b["author"])
                final_books.append(b)

            return final_books
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                return []
            raise Exception(f"Failed to fetch books: {error}") from error

    def get_reading_records(
        self, book_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve reading records, optionally filtered by book ID."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="ReadingRecords!A:G")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            headers = values[0]
            records = []
            for row in values[1:]:
                if not row or len(row) < 3 or not row[0] or not row[1]:
                    # Skip empty rows or rows without ID or Book ID
                    continue
                # Pad row to match header length
                row = row + [""] * (len(headers) - len(row))
                try:
                    record_id = int(float(row[0]))
                    book_id_val = int(float(row[1]))
                    rating = (
                        int(float(row[5]))
                        if row[5] and str(row[5]).replace(".", "").isdigit()
                        else 0
                    )
                except (ValueError, TypeError):
                    continue

                record = {
                    "id": record_id,
                    "book_id": book_id_val,
                    "status": row[2],
                    "start_date": row[3],
                    "end_date": row[4] if row[4] else None,
                    "rating": rating,
                    "created_at": row[6] if row[6] else None,
                }
                if book_id is None or record["book_id"] == book_id:
                    records.append(record)
            return records
        except HttpError as error:
            # If the tab doesn't exist yet, try initializing and return empty list
            if error.resp.status == 400:
                self.initialize_sheets()
                return []
            raise Exception(f"Failed to fetch reading records: {error}") from error

    def get_book_by_id(self, book_id: int) -> Optional[Dict[str, Any]]:
        """Get a single book by ID."""
        books = self.get_all_books()
        for book in books:
            if book["id"] == book_id:
                return book
        return None

    def get_book_by_isbn(self, isbn13: str) -> Optional[Dict[str, Any]]:
        """Get a single book by ISBN-13."""
        books = self.get_all_books()
        for book in books:
            if book["isbn13"] == isbn13:
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
        dewey_decimal: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a new book to the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        book_id = self._get_next_id("Books")
        created_at = datetime.now(timezone.utc).isoformat()

        row = [
            book_id,
            isbn13,
            title,
            author,
            publication_year if publication_year else "",
            thumbnail_url if thumbnail_url else "",
            created_at,
            publisher if publisher else "",
            description if description else "",
            series if series else "",
            dewey_decimal if dewey_decimal else "",
            language if language else "",
            page_count if page_count else "",
            physical_format if physical_format else "",
            edition if edition else "",
            cover_url if cover_url else "",
        ]
        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Books!A:P",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            # Sync authors
            self._sync_book_authors(sid, book_id, author)
            from book_lamp.utils.authors import split_authors

            return {
                "id": book_id,
                "isbn13": isbn13,
                "title": title,
                "author": author,
                "authors": split_authors(author),
                "publication_year": publication_year,
                "thumbnail_url": thumbnail_url,
                "created_at": created_at,
                "publisher": publisher,
                "description": description,
                "series": series,
                "dewey_decimal": dewey_decimal,
                "language": language,
                "page_count": page_count,
                "physical_format": physical_format,
                "edition": edition,
                "cover_url": cover_url,
            }
        except HttpError as error:
            if error.resp.status == 400:
                # Tab might not exist, try initializing and appending again
                self.initialize_sheets()
                try:
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="Books!A:P",
                        valueInputOption="RAW",
                        body={"values": [row]},
                    ).execute()
                    # Sync authors
                    self._sync_book_authors(sid, book_id, author)
                    from book_lamp.utils.authors import split_authors

                    return {
                        "id": book_id,
                        "isbn13": isbn13,
                        "title": title,
                        "author": author,
                        "authors": split_authors(author),
                        "publication_year": publication_year,
                        "thumbnail_url": thumbnail_url,
                        "created_at": created_at,
                        "publisher": publisher,
                        "description": description,
                        "series": series,
                        "dewey_decimal": dewey_decimal,
                        "language": language,
                        "page_count": page_count,
                        "physical_format": physical_format,
                        "edition": edition,
                        "cover_url": cover_url,
                    }
                except HttpError as retry_error:
                    raise Exception(
                        f"Failed to add book after initialization: {retry_error}"
                    ) from retry_error
            raise Exception(f"Failed to add book: {error}") from error

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
        dewey_decimal: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing book in the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # Get all data to find the row index
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:P")
                .execute()
            )
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                raise Exception(f"Book with ID {book_id} not found")
            raise
        values = result.get("values", [])
        if len(values) <= 1:
            raise Exception(f"Book with ID {book_id} not found")

        # Find the row index (add 1 for header, add 1 for 1-based indexing)
        row_index = None
        created_at = None
        existing_thumbnail = None
        existing_publisher = None
        existing_description = None
        existing_series = None
        existing_dewey = None
        existing_cover_url = None
        existing_language = None
        existing_page_count = None
        existing_physical_format = None
        existing_edition = None

        for idx, row in enumerate(values[1:], start=2):
            if row and row[0] and int(row[0]) == book_id:
                row_index = idx
                existing_thumbnail = row[5] if len(row) > 5 else None
                created_at = row[6] if len(row) > 6 else None
                existing_publisher = row[7] if len(row) > 7 else None
                existing_description = row[8] if len(row) > 8 else None
                existing_series = row[9] if len(row) > 9 else None
                existing_dewey = row[10] if len(row) > 10 else None
                existing_language = row[11] if len(row) > 11 else None
                existing_page_count = row[12] if len(row) > 12 else None
                existing_physical_format = row[13] if len(row) > 13 else None
                existing_edition = row[14] if len(row) > 14 else None
                existing_cover_url = row[15] if len(row) > 15 else None
                break

        if row_index is None:
            raise Exception(f"Book with ID {book_id} not found")

        if not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        if not thumbnail_url and existing_thumbnail:
            thumbnail_url = existing_thumbnail
        if not publisher and existing_publisher:
            publisher = existing_publisher
        if not description and existing_description:
            description = existing_description
        if not series and existing_series:
            series = existing_series
        if not dewey_decimal and existing_dewey:
            dewey_decimal = existing_dewey
        if not language and existing_language:
            language = existing_language
        if not page_count and existing_page_count:
            page_count = existing_page_count
        if not physical_format and existing_physical_format:
            physical_format = existing_physical_format
        if not edition and existing_edition:
            edition = existing_edition
        if not cover_url and existing_cover_url:
            cover_url = existing_cover_url

        row = [
            book_id,
            isbn13,
            title,
            author,
            publication_year if publication_year else "",
            thumbnail_url if thumbnail_url else "",
            created_at,
            publisher if publisher else "",
            description if description else "",
            series if series else "",
            dewey_decimal if dewey_decimal else "",
            language if language else "",
            page_count if page_count else "",
            physical_format if physical_format else "",
            edition if edition else "",
            cover_url if cover_url else "",
        ]

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"Books!A{row_index}:P{row_index}",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            # Sync authors
            self._sync_book_authors(sid, book_id, author)
            from book_lamp.utils.authors import split_authors

            return {
                "id": book_id,
                "isbn13": isbn13,
                "title": title,
                "author": author,
                "authors": split_authors(author),
                "publication_year": publication_year,
                "thumbnail_url": thumbnail_url,
                "created_at": created_at,
                "publisher": publisher,
                "description": description,
                "series": series,
                "dewey_decimal": dewey_decimal,
                "language": language,
                "page_count": page_count,
                "physical_format": physical_format,
                "edition": edition,
                "cover_url": cover_url,
            }
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                raise Exception("Failed to update book: tab was missing") from error
            raise Exception(f"Failed to update book: {error}") from error

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
        dewey_decimal: Optional[str] = None,
        language: Optional[str] = None,
        page_count: Optional[int] = None,
        physical_format: Optional[str] = None,
        edition: Optional[str] = None,
        cover_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Add a new book or update an existing one if ISBN matches."""
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
                author=author,
                publication_year=publication_year,
                thumbnail_url=thumbnail_url,
                publisher=publisher,
                description=description,
                series=series,
                dewey_decimal=dewey_decimal,
                language=language,
                page_count=page_count,
                physical_format=physical_format,
                edition=edition,
                cover_url=cover_url,
            )

    def bulk_import(self, items: List[Dict[str, Any]]) -> int:
        """Optimized bulk import to avoid Google Sheets API rate limits."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # 1. Fetch all existing data once
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Starting bulk import of {len(items)} items")
        try:
            books_result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:P")
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 400:
                self.initialize_sheets()
                books_result = {"values": []}
            else:
                raise

        try:
            records_result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="ReadingRecords!A:G")
                .execute()
            )
        except HttpError as e:
            if e.resp.status == 400:
                self.initialize_sheets()
                records_result = {"values": []}
            else:
                raise

        book_values = books_result.get("values", [])
        existing_books = {}  # normalized_isbn -> (row_data, row_index)
        next_book_id = 1
        from book_lamp.utils.libib_import import clean_isbn

        for idx, row in enumerate(book_values[1:], start=2):
            if row and len(row) > 1:
                # Normalize ISBN for lookup
                norm_isbn = clean_isbn(row[1])
                if norm_isbn:
                    existing_books[norm_isbn] = (row, idx)
                try:
                    if row[0]:
                        next_book_id = max(next_book_id, int(float(row[0])) + 1)
                except (ValueError, TypeError):
                    pass

        record_values = records_result.get("values", [])
        existing_record_keys = set()
        next_record_id = 1
        for row in record_values[1:]:
            if row and len(row) > 4:
                # Key: (book_id, status, start_date, end_date)
                try:
                    if row[0]:
                        next_record_id = max(next_record_id, int(float(row[0])) + 1)
                    if row[1]:
                        bid = int(float(row[1]))
                        key = (bid, row[2], row[3], row[4] if row[4] else None)
                        existing_record_keys.add(key)
                except (ValueError, IndexError, TypeError):
                    pass

        # 1.5 Fetch and process authors
        all_authors = self.get_authors()
        name_to_id = {a["name"]: a["id"] for a in all_authors}
        next_author_id = max([a["id"] for a in all_authors] + [0]) + 1

        all_links = self.get_book_authors()
        # book_id -> set of author_ids
        existing_links = {}
        for link in all_links:
            bid = link["book_id"]
            aid = link["author_id"]
            if bid not in existing_links:
                existing_links[bid] = set()
            existing_links[bid].add(aid)

        # 2. Process items
        books_to_update = []  # list of {"range": ..., "values": [[...]]}
        books_to_append = []
        records_to_append = []
        authors_to_append = []
        links_to_append = []
        import_count = 0

        from book_lamp.utils.authors import split_authors

        for item in items:
            b = item["book"]
            r = item["record"]
            isbn = b["isbn13"]

            created_at = datetime.now(timezone.utc).isoformat()
            book_id = None

            if isbn in existing_books:
                # Update existing
                row_data, row_idx = existing_books[isbn]
                book_id = int(row_data[0])

                # Preserve existing fields if missing in new data
                thumb = b.get("thumbnail_url") or (
                    row_data[5] if len(row_data) > 5 else ""
                )
                cat = row_data[6] if len(row_data) > 6 else created_at
                pub = b.get("publisher") or (row_data[7] if len(row_data) > 7 else "")
                desc = b.get("description") or (
                    row_data[8] if len(row_data) > 8 else ""
                )
                ser = b.get("series") or (row_data[9] if len(row_data) > 9 else "")
                ddc = b.get("dewey_decimal") or (
                    row_data[10] if len(row_data) > 10 else ""
                )
                lang = b.get("language") or (row_data[11] if len(row_data) > 11 else "")
                pc = b.get("page_count") or (row_data[12] if len(row_data) > 12 else "")
                pf = b.get("physical_format") or (
                    row_data[13] if len(row_data) > 13 else ""
                )
                ed = b.get("edition") or (row_data[14] if len(row_data) > 14 else "")
                cu = b.get("cover_url") or (row_data[15] if len(row_data) > 15 else "")

                new_row = [
                    book_id,
                    isbn,
                    b["title"],
                    b["author"],
                    b["publication_year"] if b["publication_year"] else "",
                    thumb,
                    cat,
                    pub,
                    desc,
                    ser,
                    ddc,
                    lang,
                    pc,
                    pf,
                    ed,
                    cu,
                ]
                books_to_update.append(
                    {"range": f"Books!A{row_idx}:P{row_idx}", "values": [new_row]}
                )
            else:
                # Append new
                book_id = next_book_id
                next_book_id += 1
                new_row = [
                    book_id,
                    isbn,
                    b["title"],
                    b["author"],
                    b["publication_year"] if b["publication_year"] else "",
                    b.get("thumbnail_url") or "",
                    created_at,
                    b.get("publisher") or "",
                    b.get("description") or "",
                    b.get("series") or "",
                    b.get("dewey_decimal") or "",
                    b.get("language") or "",
                    b.get("page_count") or "",
                    b.get("physical_format") or "",
                    b.get("edition") or "",
                    b.get("cover_url") or "",
                ]
                books_to_append.append(new_row)

            # Process authors for this book
            names = split_authors(b["author"])
            current_book_aids = existing_links.get(book_id, set())

            for name in names:
                if name not in name_to_id:
                    aid = next_author_id
                    next_author_id += 1
                    name_to_id[name] = aid
                    authors_to_append.append([aid, name])

                aid = name_to_id[name]
                if aid not in current_book_aids:
                    links_to_append.append([book_id, aid])
                    # Add to existing to prevent internal duplicates
                    current_book_aids.add(aid)
                    if book_id not in existing_links:
                        existing_links[book_id] = set()
                    existing_links[book_id].add(aid)

            if r:
                # Robust deduplication:
                # If Completed, match on (book_id, status, end_date) - ignoring start_date
                # because start_date can shift between 'added' and 'began' in different imports.
                # If NOT Completed, match on (book_id, status, start_date).
                is_duplicate = False
                r_status = r["status"]
                r_start = r["start_date"]
                r_end = r.get("end_date")

                for ek in existing_record_keys:
                    # ek = (bid, status, start_date, end_date)
                    if ek[0] == book_id and ek[1] == r_status:
                        if r_status == "Completed":
                            if ek[3] == r_end:
                                is_duplicate = True
                                break
                        elif r_status == "In Progress":
                            # For In Progress, any existing In Progress record for this book is a duplicate.
                            # This handles start dates shifting between 'added' and 'began'.
                            is_duplicate = True
                            break
                        else:
                            if ek[2] == r_start:
                                is_duplicate = True
                                break

                if not is_duplicate:
                    new_rec_row = [
                        next_record_id,
                        book_id,
                        r_status,
                        r_start,
                        r_end or "",
                        r.get("rating") or 0,
                        created_at,
                    ]
                    records_to_append.append(new_rec_row)
                    next_record_id += 1
                    # Add to existing to prevent internal duplicates
                    existing_record_keys.add((book_id, r_status, r_start, r_end))

            import_count += 1

        # 3. Execute batch operations
        if books_to_update:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=sid,
                body={"valueInputOption": "RAW", "data": books_to_update},
            ).execute()

        if books_to_append:
            # Batch append new books
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="Books",
                    valueInputOption="RAW",
                    body={"values": books_to_append},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="Books",
                        valueInputOption="RAW",
                        body={"values": books_to_append},
                    ).execute()
                else:
                    raise

        if records_to_append:
            # Batch append new records
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="ReadingRecords",
                    valueInputOption="RAW",
                    body={"values": records_to_append},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="ReadingRecords",
                        valueInputOption="RAW",
                        body={"values": records_to_append},
                    ).execute()
                else:
                    raise

        if authors_to_append:
            # Batch append new authors
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="Authors",
                    valueInputOption="RAW",
                    body={"values": authors_to_append},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="Authors",
                        valueInputOption="RAW",
                        body={"values": authors_to_append},
                    ).execute()
                else:
                    raise

        if links_to_append:
            # Batch append new links
            try:
                self.service.spreadsheets().values().append(
                    spreadsheetId=sid,
                    range="BookAuthors",
                    valueInputOption="RAW",
                    body={"values": links_to_append},
                ).execute()
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="BookAuthors",
                        valueInputOption="RAW",
                        body={"values": links_to_append},
                    ).execute()
                else:
                    raise

        logger.info(
            f"Executed batch operations: {len(books_to_update)} updates, {len(books_to_append)} appends, {len(records_to_append)} records"
        )
        return import_count

    def update_reading_record(
        self,
        record_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> Dict[str, Any]:
        """Update an existing reading record in the ReadingRecords tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # Get all data to find the row index
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="ReadingRecords!A:G")
                .execute()
            )
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                raise Exception(f"Reading record with ID {record_id} not found")
            raise

        values = result.get("values", [])
        if len(values) <= 1:
            raise Exception(f"Reading record with ID {record_id} not found")

        # Find the row index (add 1 for header, add 1 for 1-based indexing)
        row_index = None
        book_id = None
        created_at = None
        for idx, row in enumerate(values[1:], start=2):
            if row and row[0] and int(row[0]) == record_id:
                row_index = idx
                book_id = int(row[1])
                created_at = row[6] if len(row) > 6 else None
                break

        if row_index is None:
            raise Exception(f"Reading record with ID {record_id} not found")

        if not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        row = [
            record_id,
            book_id,
            status,
            start_date,
            end_date if end_date else "",
            rating,
            created_at,
        ]

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"ReadingRecords!A{row_index}:G{row_index}",
                valueInputOption="RAW",
                body={"values": [row]},
            ).execute()

            return {
                "id": record_id,
                "book_id": book_id,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
                "rating": rating,
                "created_at": created_at,
            }
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                # If we're here, the row_index we had is likely invalid now anyway
                raise Exception(
                    "Failed to update reading record: tab was missing"
                ) from error
            raise Exception(f"Failed to update reading record: {error}") from error

    def delete_reading_record(self, record_id: int) -> bool:
        """Delete a reading record by ID."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # Get all data to find the row index
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="ReadingRecords!A:A")
                .execute()
            )
        except HttpError as error:
            if error.resp.status == 400:
                self.initialize_sheets()
                return False
            raise

        values = result.get("values", [])
        if len(values) <= 1:
            return False

        # Find the row index
        row_index = None
        for idx, row in enumerate(values[1:], start=2):
            if row and row[0] and int(row[0]) == record_id:
                row_index = idx
                break

        if row_index is None:
            return False

        sheet_id = self._get_sheet_id("ReadingRecords")
        body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,
                            "dimension": "ROWS",
                            "startIndex": row_index - 1,
                            "endIndex": row_index,
                        }
                    }
                }
            ]
        }
        try:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=sid, body=body
            ).execute()
            return True
        except HttpError as error:
            raise Exception(f"Failed to delete reading record: {error}") from error

    def delete_book(self, book_id: int) -> bool:
        """Delete a book by ID."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            # Get all data
            try:
                result = (
                    self.service.spreadsheets()
                    .values()
                    .get(spreadsheetId=sid, range="Books!A:P")
                    .execute()
                )
            except HttpError as error:
                if error.resp.status == 400:
                    self.initialize_sheets()
                    return False
                raise

            values = result.get("values", [])
            if len(values) <= 1:
                return False

            # Find the row index (add 1 for header, add 1 for 1-based indexing)
            row_index = None
            for idx, row in enumerate(values[1:], start=2):
                if row and row[0] and int(row[0]) == book_id:
                    row_index = idx
                    break

            if row_index is None:
                return False

            # Delete the row
            request = {
                "deleteDimension": {
                    "range": {
                        "sheetId": self._get_sheet_id("Books"),
                        "dimension": "ROWS",
                        "startIndex": row_index - 1,
                        "endIndex": row_index,
                    }
                }
            }

            self.service.spreadsheets().batchUpdate(
                spreadsheetId=sid, body={"requests": [request]}
            ).execute()

            return True
        except HttpError as error:
            raise Exception(f"Failed to delete book: {error}") from error

    def _get_sheet_id(self, tab_name: str) -> int:
        """Get the sheet ID for a given tab name."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            sheet_metadata = (
                self.service.spreadsheets().get(spreadsheetId=sid).execute()
            )
            for sheet in sheet_metadata.get("sheets", []):
                if sheet["properties"]["title"] == tab_name:
                    return int(sheet["properties"]["sheetId"])

            # Not found, try initializing
            self.initialize_sheets()
            sheet_metadata = (
                self.service.spreadsheets().get(spreadsheetId=sid).execute()
            )
            for sheet in sheet_metadata.get("sheets", []):
                if sheet["properties"]["title"] == tab_name:
                    return int(sheet["properties"]["sheetId"])

            raise Exception(f"Tab '{tab_name}' not found after initialization")
        except HttpError as error:
            raise Exception(f"Failed to get sheet ID: {error}") from error

    def initialize_sheets(self) -> None:
        """Initialise the spreadsheet with required tabs and headers."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            # Refresh sheet metadata to get current state
            sheet_metadata = (
                self.service.spreadsheets().get(spreadsheetId=sid).execute()
            )
            sheets_in_doc = [
                s["properties"]["title"] for s in sheet_metadata.get("sheets", [])
            ]

            # 1. Create missing tabs in one batch
            required_tabs = ["Books", "ReadingRecords", "Authors", "BookAuthors"]
            add_requests = []
            for tab in required_tabs:
                if tab not in sheets_in_doc:
                    add_requests.append({"addSheet": {"properties": {"title": tab}}})

            if add_requests:
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=sid, body={"requests": add_requests}
                ).execute()

            # 2. Setup headers for each tab
            tab_headers = {
                "Books": [
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
                "ReadingRecords": [
                    "id",
                    "book_id",
                    "status",
                    "start_date",
                    "end_date",
                    "rating",
                    "created_at",
                ],
                "Authors": ["id", "name"],
                "BookAuthors": ["book_id", "author_id"],
            }

            for tab, headers in tab_headers.items():
                try:
                    # Check if headers exist
                    result = (
                        self.service.spreadsheets()
                        .values()
                        .get(spreadsheetId=sid, range=f"{tab}!A1:Z1")
                        .execute()
                    )
                    values = result.get("values", [])
                    if not values or not values[0]:
                        # Write headers
                        self.service.spreadsheets().values().update(
                            spreadsheetId=sid,
                            range=f"{tab}!A1",
                            valueInputOption="RAW",
                            body={"values": [headers]},
                        ).execute()
                except HttpError as e:
                    if e.resp.status == 400:
                        # This should usually not happen if tab was created above,
                        # but if it does, it confirms the tab is missing or range is invalid.
                        continue
                    raise

            # Add headers for Authors if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Authors!A1:B1")
                .execute()
            )
            values = result.get("values", [])

            if not values:
                headers = [["id", "name"]]
                self.service.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range="Authors!A1:B1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

            # Add headers for BookAuthors if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="BookAuthors!A1:B1")
                .execute()
            )
            values = result.get("values", [])

            if not values:
                headers = [["book_id", "author_id"]]
                self.service.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range="BookAuthors!A1:B1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

        except HttpError as error:
            raise Exception(f"Failed to initialize sheets: {error}") from error

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search across all book data fields.

        Args:
            query: Search query (free text).

        Returns:
            List of matching books with reading_records attached, sorted by relevance.
        """
        from book_lamp.services.search import search_books

        all_books = self.get_all_books()
        all_records = self.get_reading_records()
        return search_books(all_books, all_records, query)

    def get_reading_history(self) -> List[Dict[str, Any]]:
        """Retrieve all reading records joined with book metadata."""
        # Fetch both books and records to join in memory
        books = self.get_all_books()
        records = self.get_reading_records()

        book_map = {b["id"]: b for b in books}
        history = []
        for record in records:
            book = book_map.get(record["book_id"])
            if book:
                enriched_record = record.copy()
                enriched_record["book_title"] = book["title"]
                enriched_record["book_author"] = book["author"]
                enriched_record["book_authors"] = book.get("authors", [])
                enriched_record["book_thumbnail_url"] = book.get("thumbnail_url")
                history.append(enriched_record)

        return history
