"""Google Sheets storage adapter for book data."""

import os
from datetime import datetime
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
    - 'Books' tab: id, isbn13, title, author, publication_year, thumbnail_url, created_at
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
        """Load credentials from token.json or refresh them if expired."""
        token_path = "token.json"
        if not os.path.exists(token_path):
            return None

        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
            except Exception:
                return None
        return creds if creds and creds.valid else None

    def is_authorized(self) -> bool:
        """Check if we have valid credentials."""
        creds = self.load_credentials()
        return creds is not None and creds.valid

    def save_credentials(self, creds_dict: Dict[str, Any]) -> None:
        """Save new credentials to token.json and reconnect."""
        token_path = "token.json"
        with open(token_path, "w") as token:
            import json

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

    def get_all_books(self) -> List[Dict[str, Any]]:
        """Retrieve all books from the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:G")
                .execute()
            )
            values = result.get("values", [])
            if not values or len(values) < 2:
                return []

            headers = values[0]
            books = []
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
                }
                books.append(book)
            return books
        except HttpError as error:
            raise Exception(f"Failed to fetch books: {error}") from error

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
    ) -> Dict[str, Any]:
        """Add a new book to the Books tab."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        book_id = self._get_next_id("Books")
        created_at = datetime.now(datetime.timezone.utc).isoformat()

        row = [
            book_id,
            isbn13,
            title,
            author,
            publication_year if publication_year else "",
            thumbnail_url if thumbnail_url else "",
            created_at,
        ]

        try:
            self.service.spreadsheets().values().append(
                spreadsheetId=sid,
                range="Books!A:G",
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
            }
        except HttpError as error:
            raise Exception(f"Failed to add book: {error}") from error

    def delete_book(self, book_id: int) -> bool:
        """Delete a book by ID."""
        sid = self._ensure_spreadsheet_id()
        assert self.service is not None
        try:
            # Get all data
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A:G")
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

            # Add headers if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=sid, range="Books!A1:G1")
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
                    ]
                ]
                self.service.spreadsheets().values().update(
                    spreadsheetId=sid,
                    range="Books!A1:G1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

        except HttpError as error:
            raise Exception(f"Failed to initialize sheets: {error}") from error
