"""Google Sheets storage adapter for book data."""

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from google.auth.transport.requests import Request  # type: ignore
from google.oauth2.credentials import Credentials  # type: ignore
from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
from googleapiclient.discovery import build  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

# If modifying these scopes, delete the token.json file.
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


class GoogleSheetsStorage:
    """Adapter for storing book data in Google Sheets.

    Expected sheet structure:
    - 'Books' tab: id, isbn13, title, author, publication_year, thumbnail_url, created_at
    """

    def __init__(self, spreadsheet_id: str, credentials_path: str = "credentials.json"):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_path = credentials_path
        self.service = None
        self._connect()

    def _connect(self) -> None:
        """Establish connection to Google Sheets API."""
        creds = None
        token_path = "token.json"

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception:
                    # Token is invalid or revoked, force re-authentication
                    creds = None

            if not creds:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=8080)

            with open(token_path, "w") as token:
                token.write(creds.to_json())

        self.service = build("sheets", "v4", credentials=creds)

    def _get_next_id(self, tab_name: str) -> int:
        """Get the next available ID for a tab."""
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range=f"{tab_name}!A:A")
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
        assert self.service is not None
        try:
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range="Books!A:G")
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
        assert self.service is not None
        book_id = self._get_next_id("Books")
        created_at = datetime.utcnow().isoformat()

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
                spreadsheetId=self.spreadsheet_id,
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
        assert self.service is not None
        try:
            # Get all data
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range="Books!A:G")
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
                spreadsheetId=self.spreadsheet_id, body={"requests": [request]}
            ).execute()

            return True
        except HttpError as error:
            raise Exception(f"Failed to delete book: {error}") from error

    def _get_sheet_id(self, tab_name: str) -> int:
        """Get the sheet ID for a given tab name."""
        assert self.service is not None
        try:
            sheet_metadata = (
                self.service.spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id)
                .execute()
            )
            for sheet in sheet_metadata.get("sheets", []):
                if sheet["properties"]["title"] == tab_name:
                    return int(sheet["properties"]["sheetId"])
            raise Exception(f"Tab '{tab_name}' not found")
        except HttpError as error:
            raise Exception(f"Failed to get sheet ID: {error}") from error

    def initialize_sheets(self) -> None:
        """Initialize the spreadsheet with required tabs and headers."""
        assert self.service is not None
        try:
            # Check if Books tab exists
            sheet_metadata = (
                self.service.spreadsheets()
                .get(spreadsheetId=self.spreadsheet_id)
                .execute()
            )
            sheets = sheet_metadata.get("sheets", [])
            books_exists = any(
                sheet["properties"]["title"] == "Books" for sheet in sheets
            )

            if not books_exists:
                # Create Books tab
                request = {"addSheet": {"properties": {"title": "Books"}}}
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id, body={"requests": [request]}
                ).execute()

            # Add headers if not present
            result = (
                self.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.spreadsheet_id, range="Books!A1:G1")
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
                    spreadsheetId=self.spreadsheet_id,
                    range="Books!A1:G1",
                    valueInputOption="RAW",
                    body={"values": headers},
                ).execute()

        except HttpError as error:
            raise Exception(f"Failed to initialize sheets: {error}") from error
