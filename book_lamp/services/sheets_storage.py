"""Google Sheets storage adapter for book data."""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request  # type: ignore
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

    def __init__(self, sheet_name: str, credentials_path: str = "credentials.json"):
        """Initialise the storage adapter.

        Args:
            sheet_name: Name of the Google Sheet to use.
            credentials_path: Path to the Google Cloud credentials file.
        """
        self.sheet_name = sheet_name
        self.spreadsheet_id: Optional[str] = None
        self.credentials_path = credentials_path
        self.service = None
        self.drive_service = None
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Google Sheets and Drive APIs."""
        creds = self.load_credentials()
        if creds and creds.valid:
            self.service = build("sheets", "v4", credentials=creds)
            self.drive_service = build("drive", "v3", credentials=creds)

    def load_credentials(self) -> Optional[Credentials]:
        """Load credentials from token.json or refresh them if expired.

        Client ID and secret are read from environment variables for security.
        """
        token_path = "token.json"
        if not os.path.exists(token_path):
            return None

        try:
            import json

            # Read token data and inject client_id/client_secret from env vars
            with open(token_path, "r") as token_file:
                token_data = json.load(token_file)

            # Inject client credentials from environment variables
            token_data["client_id"] = os.environ.get("GOOGLE_CLIENT_ID")
            token_data["client_secret"] = os.environ.get("GOOGLE_CLIENT_SECRET")

            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed token (without client credentials)
                    self._save_token_data(creds)
                except Exception:
                    return None
            return creds if creds and creds.valid else None
        except (ValueError, KeyError, json.JSONDecodeError):
            # Token file is in old format, invalid, or missing required fields
            return None

    def is_authorized(self) -> bool:
        """Check if we have valid credentials."""
        creds = self.load_credentials()
        return creds is not None and creds.valid

    def _save_token_data(self, creds: Credentials) -> None:
        """Save token data to token.json (without client credentials)."""
        import json

        token_path = "token.json"
        # Extract only the token data, not client credentials
        token_data = json.loads(creds.to_json())
        # Remove client credentials from saved file
        token_data.pop("client_id", None)
        token_data.pop("client_secret", None)

        with open(token_path, "w") as token_file:
            json.dump(token_data, token_file)

    def save_credentials(self, creds_dict: Dict[str, Any]) -> None:
        """Save new credentials to token.json and reconnect.

        Client ID and secret are NOT saved to the file - they come from env vars.
        """
        import json

        token_path = "token.json"
        # Remove client credentials before saving
        creds_dict.pop("client_id", None)
        creds_dict.pop("client_secret", None)

        with open(token_path, "w") as token:
            token.write(json.dumps(creds_dict))
        self.spreadsheet_id = None  # Reset ID to trigger rediscovery
        self._connect()

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
            ids = [int(row[0]) for row in values[1:] if row and row[0].isdigit()]
            return max(ids) + 1 if ids else 1
        except HttpError:
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
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Authors!A:B",
                valueInputOption="RAW",
                body={"values": new_authors},
            ).execute()

        # 3. Update BookAuthors links
        all_links = self.get_book_authors()
        existing_aids = {
            link["author_id"] for link in all_links if link["book_id"] == book_id
        }
        links_to_add = [
            [book_id, aid] for aid in author_ids if aid not in existing_aids
        ]

        if links_to_add:
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="BookAuthors!A:B",
                valueInputOption="RAW",
                body={"values": links_to_add},
            ).execute()

    def get_all_books(self) -> List[Dict[str, Any]]:
        """Retrieve all books from the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:K")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            headers = values[0]
            books_raw = []
            for row in values[1:]:
                if not row:
                    continue
                # Pad row to match header length
                row = row + [""] * (len(headers) - len(row))
                book = {
                    "id": int(row[0]) if row[0] else 0,
                    "isbn13": row[1],
                    "title": row[2],
                    "author": row[3],
                    "publication_year": (
                        int(row[4]) if row[4] and row[4].isdigit() else None
                    ),
                    "thumbnail_url": row[5] if row[5] else None,
                    "created_at": row[6] if row[6] else None,
                    "publisher": row[7] if len(row) > 7 else None,
                    "description": row[8] if len(row) > 8 else None,
                    "series": row[9] if len(row) > 9 else None,
                    "dewey_decimal": row[10] if len(row) > 10 else None,
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
                if not row:
                    continue
                # Pad row to match header length
                row = row + [""] * (len(headers) - len(row))
                record = {
                    "id": int(row[0]) if row[0] else 0,
                    "book_id": int(row[1]) if row[1] else 0,
                    "status": row[2],
                    "start_date": row[3],
                    "end_date": row[4] if row[4] else None,
                    "rating": int(row[5]) if row[5] and row[5].isdigit() else 0,
                    "created_at": row[6] if row[6] else None,
                }
                if book_id is None or record["book_id"] == book_id:
                    records.append(record)
            return records
        except HttpError as error:
            # If the tab doesn't exist yet, return empty list
            if error.resp.status == 400:
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
        ]

        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Books!A:K",
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
            }
        except HttpError as error:
            if error.resp.status == 400:
                # Tab might not exist, try initializing and appending again
                self.initialize_sheets()
                try:
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="Books!A:K",
                        valueInputOption="RAW",
                        body={"values": [row]},
                    ).execute()
                    return {
                        "id": book_id,
                        "isbn13": isbn13,
                        "title": title,
                        "author": author,
                        "publication_year": publication_year,
                        "thumbnail_url": thumbnail_url,
                        "created_at": created_at,
                        "publisher": publisher,
                        "description": description,
                        "series": series,
                        "dewey_decimal": dewey_decimal,
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
    ) -> Dict[str, Any]:
        """Update an existing book in the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # Get all data to find the row index
        result = (
            self.service.spreadsheets()
            .values()
            .get(spreadsheetId=sid, range="Books!A:K")
            .execute()
        )
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
        for idx, row in enumerate(values[1:], start=2):
            if row and row[0] and int(row[0]) == book_id:
                row_index = idx
                existing_thumbnail = row[5] if len(row) > 5 else None
                created_at = row[6] if len(row) > 6 else None
                existing_publisher = row[7] if len(row) > 7 else None
                existing_description = row[8] if len(row) > 8 else None
                existing_series = row[9] if len(row) > 9 else None
                existing_dewey = row[10] if len(row) > 10 else None
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
        ]

        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=sid,
                range=f"Books!A{row_index}:K{row_index}",
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
            }
        except HttpError as error:
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

    def bulk_import(self, items: List[Dict[str, Any]]) -> int:
        """Optimized bulk import to avoid Google Sheets API rate limits."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None

        # 1. Fetch all existing data once
        try:
            books_result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:K")
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
        existing_books = {}  # isbn -> (row_data, row_index)
        next_book_id = 1
        for idx, row in enumerate(book_values[1:], start=2):
            if row and len(row) > 1:
                existing_books[row[1]] = (row, idx)
                if row[0].isdigit():
                    next_book_id = max(next_book_id, int(row[0]) + 1)

        record_values = records_result.get("values", [])
        existing_record_keys = set()
        next_record_id = 1
        for row in record_values[1:]:
            if row and len(row) > 4:
                # Key: (book_id, status, start_date, end_date)
                try:
                    bid = int(row[1]) if row[1].isdigit() else 0
                    key = (bid, row[2], row[3], row[4] if row[4] else None)
                    existing_record_keys.add(key)
                except (ValueError, IndexError):
                    pass
                if row[0].isdigit():
                    next_record_id = max(next_record_id, int(row[0]) + 1)

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

                # Preserve existing thumbnail and created_at if missing
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
                ]
                books_to_update.append(
                    {"range": f"Books!A{row_idx}:K{row_idx}", "values": [new_row]}
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
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Books!A:K",
                valueInputOption="RAW",
                body={"values": books_to_append},
            ).execute()

        if records_to_append:
            # Batch append new records
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="ReadingRecords!A:G",
                valueInputOption="RAW",
                body={"values": records_to_append},
            ).execute()

        if authors_to_append:
            # Batch append new authors
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Authors!A:B",
                valueInputOption="RAW",
                body={"values": authors_to_append},
            ).execute()

        if links_to_append:
            # Batch append new links
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="BookAuthors!A:B",
                valueInputOption="RAW",
                body={"values": links_to_append},
            ).execute()

        return import_count

    def add_reading_record(
        self,
        book_id: int,
        status: str,
        start_date: str,
        end_date: Optional[str] = None,
        rating: int = 0,
    ) -> Dict[str, Any]:
        """Add a new reading record to the ReadingRecords tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        record_id = self._get_next_id("ReadingRecords")
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
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="ReadingRecords!A:G",
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
                # Tab might not exist, try initializing and appending again
                self.initialize_sheets()
                try:
                    self.service.spreadsheets().values().append(
                        spreadsheetId=sid,
                        range="ReadingRecords!A:G",
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
                except HttpError as retry_error:
                    raise Exception(
                        f"Failed to add reading record after initialization: {retry_error}"
                    ) from retry_error
            raise Exception(f"Failed to add reading record: {error}") from error

    def delete_book(self, book_id: int) -> bool:
        """Delete a book by ID."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            # Get all data
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:K")
                .execute()
            )
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
            raise Exception(f"Tab '{tab_name}' not found")
        except HttpError as error:
            raise Exception(f"Failed to get sheet ID: {error}") from error

    def initialize_sheets(self) -> None:
        """Initialise the spreadsheet with required tabs and headers."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            # Check if Books tab exists
            sheet_metadata = (
                self.service.spreadsheets().get(spreadsheetId=sid).execute()
            )
            sheets = sheet_metadata.get("sheets", [])
            books_exists = any(
                sheet["properties"]["title"] == "Books" for sheet in sheets
            )

            if not books_exists:
                # Create Books tab
                request = {"addSheet": {"properties": {"title": "Books"}}}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=sid, body={"requests": [request]}
                ).execute()

            # Check if ReadingRecords tab exists
            reading_records_exists = any(
                sheet["properties"]["title"] == "ReadingRecords" for sheet in sheets
            )

            if not reading_records_exists:
                # Create ReadingRecords tab
                request = {"addSheet": {"properties": {"title": "ReadingRecords"}}}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=sid, body={"requests": [request]}
                ).execute()

            # Check if Authors tab exists
            authors_exists = any(
                sheet["properties"]["title"] == "Authors" for sheet in sheets
            )

            if not authors_exists:
                # Create Authors tab
                request = {"addSheet": {"properties": {"title": "Authors"}}}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=sid, body={"requests": [request]}
                ).execute()

            # Check if BookAuthors tab exists
            book_authors_exists = any(
                sheet["properties"]["title"] == "BookAuthors" for sheet in sheets
            )

            if not book_authors_exists:
                # Create BookAuthors tab
                request = {"addSheet": {"properties": {"title": "BookAuthors"}}}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=sid, body={"requests": [request]}
                ).execute()

            # Add headers for Books if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A1:K1")
                .execute()
            )
            values = result.get("values", [])

            if not values:
                headers = [
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
                    ]
                ]
                self.service.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range="Books!A1:K1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

            # Add headers for ReadingRecords if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="ReadingRecords!A1:G1")
                .execute()
            )
            values = result.get("values", [])

            if not values:
                headers = [
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
                self.service.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range="ReadingRecords!A1:G1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

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
