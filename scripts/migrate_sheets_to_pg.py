#!/usr/bin/env python3
"""Migration script to transfer data from Google Sheets to PostgreSQL."""

import argparse
import json
import os
import sys
from typing import Any, List, cast

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Add the parent directory to the path so we can import book_lamp modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from book_lamp.services.pg_storage import PostgresStorage


def get_google_service(service_name: str, service_version: str) -> Any:
    """Create a Google API service using service account authentication."""
    credentials_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_KEY")
    if not credentials_json:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_KEY environment variable is required")

    try:
        credentials_info = json.loads(credentials_json)
        credentials = service_account.Credentials.from_service_account_info(
            credentials_info,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        return build(service_name, service_version, credentials=credentials)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in GOOGLE_SERVICE_ACCOUNT_KEY: {e}")


def get_sheet_data(
    service: Any, spreadsheet_id: str, range_name: str
) -> List[List[str]]:
    """Get data from a Google Sheets range."""
    try:
        result = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=range_name)
            .execute()
        )
        values = result.get("values", [])
        # Ensure all values are strings and return proper type
        return [[str(cell) for cell in row] for row in values]
    except HttpError as e:
        print(f"Error accessing sheet {range_name}: {e}")
        return []


def parse_date(date_str: str) -> str | None:
    """Parse a date string from Sheets format to ISO format."""
    if not date_str or date_str.strip() == "":
        return None
    # Sheets dates are often in various formats, return as-is for now
    # The database will handle parsing
    return date_str.strip()


def migrate_books(
    storage: PostgresStorage, rows: List[List[str]], dry_run: bool
) -> int:
    """Migrate books from Sheets data."""
    if len(rows) < 2:  # No data rows
        return 0

    books_added = 0

    # Expected headers: id, isbn13, title, author, publication_year, thumbnail_url, created_at
    for row in rows[1:]:
        if len(row) < 6 or not row[2]:  # Skip rows without title
            continue

        book_data = {
            "isbn13": row[1] if len(row) > 1 and row[1] else None,
            "title": row[2],
            "author": row[3] if len(row) > 3 and row[3] else None,
            "publication_year": (
                int(row[4]) if len(row) > 4 and row[4].isdigit() else None
            ),
            "thumbnail_url": row[5] if len(row) > 5 and row[5] else None,
        }

        if dry_run:
            print(f"DRY RUN: Would add book: {book_data['title']}")
        else:
            storage.add_book(
                isbn13=str(book_data["isbn13"]) if book_data["isbn13"] else "",
                title=str(book_data["title"]),
                author=str(book_data["author"]) if book_data["author"] else "",
                publication_year=(
                    cast(int, book_data["publication_year"])
                    if book_data["publication_year"]
                    else None
                ),
                thumbnail_url=(
                    cast(str, book_data["thumbnail_url"])
                    if book_data["thumbnail_url"]
                    else None
                ),
            )

        books_added += 1

    return books_added


def migrate_reading_records(
    storage: PostgresStorage, rows: List[List[str]], dry_run: bool
) -> int:
    """Migrate reading records from Sheets data."""
    if len(rows) < 2:  # No data rows
        return 0

    records_added = 0

    # Expected headers: id, book_id, status, start_date, end_date, rating, created_at
    for row in rows[1:]:
        if len(row) < 3 or not row[2]:  # Skip rows without status
            continue

        record_data = {
            "book_id": int(row[1]) if len(row) > 1 and row[1].isdigit() else None,
            "status": row[2],
            "start_date": parse_date(row[3]) if len(row) > 3 else None,
            "end_date": parse_date(row[4]) if len(row) > 4 else None,
            "rating": int(row[5]) if len(row) > 5 and row[5].isdigit() else None,
        }

        if dry_run:
            print(f"DRY RUN: Would add reading record: {record_data['status']}")
        else:
            storage.add_reading_record(
                book_id=cast(int, record_data["book_id"]) or 0,
                status=str(record_data["status"]),
                start_date=(
                    str(record_data["start_date"]) if record_data["start_date"] else ""
                ),
                end_date=(
                    cast(str, record_data["end_date"])
                    if record_data["end_date"]
                    else None
                ),
                rating=cast(int, record_data["rating"]) or 0,
            )

        records_added += 1

    return records_added


def migrate_reading_list(
    storage: PostgresStorage, rows: List[List[str]], user_id: int, dry_run: bool
) -> int:
    """Migrate reading list from Sheets data."""
    if len(rows) < 2:  # No data rows
        return 0

    list_added = 0

    # Expected headers: id, user_id, book_id, created_at
    for row in rows[1:]:
        if len(row) < 3 or not row[2]:  # Skip rows without book_id
            continue

        if dry_run:
            print(f"DRY RUN: Would add book {row[2]} to reading list")
        else:
            storage.add_to_reading_list(int(row[2]))

        list_added += 1

    return list_added


def migrate_settings(
    storage: PostgresStorage, rows: List[List[str]], user_id: int, dry_run: bool
) -> int:
    """Migrate settings from Sheets data."""
    if len(rows) < 2:  # No data rows
        return 0

    settings_added = 0

    # Expected headers: id, user_id, key, value, created_at
    for row in rows[1:]:
        if len(row) < 4 or not row[2]:  # Skip rows without key
            continue

        if dry_run:
            print(f"DRY RUN: Would set setting {row[2]} = {row[3]}")
        else:
            storage.update_setting(row[2], row[3])

        settings_added += 1

    return settings_added


def migrate_recommendations(
    storage: PostgresStorage, rows: List[List[str]], user_id: int, dry_run: bool
) -> int:
    """Migrate recommendations from Sheets data."""
    if len(rows) < 2:  # No data rows
        return 0

    recommendations_added = 0

    # Expected headers: id, user_id, book_id, reason, created_at
    for row in rows[1:]:
        if len(row) < 4 or not row[2]:  # Skip rows without book_id
            continue

        if dry_run:
            print(f"DRY RUN: Would add recommendation for book {row[2]}")
        else:
            # Create recommendation dict for save_recommendations
            recommendation = {
                "title": "",  # Not available in this format
                "author": "",  # Not available in this format
                "isbn13": "",  # Not available in this format
                "justification": row[3] if len(row) > 3 else None,
            }
            storage.save_recommendations([recommendation])

        recommendations_added += 1

    return recommendations_added


def main() -> None:
    """Main migration function."""
    parser = argparse.ArgumentParser(
        description="Migrate data from Google Sheets to PostgreSQL"
    )
    parser.add_argument(
        "--spreadsheet-id", required=True, help="Google Sheets spreadsheet ID"
    )
    parser.add_argument(
        "--user-email", required=True, help="User email for the migration"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing to database",
    )

    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        print("Error: DATABASE_URL environment variable is required")
        sys.exit(1)

    try:
        # Initialize storage
        user_id = None
        if not args.dry_run:
            user_id = PostgresStorage.upsert_user(args.user_email, args.user_email)
            print(f"User ID: {user_id}")
        else:
            print("DRY RUN: Would create/get user")

        storage = PostgresStorage(user_id or 0)

        # Get Google Sheets service
        sheets_service = get_google_service("sheets", "v4")

        print(
            f"{'DRY RUN: ' if args.dry_run else ''}Starting migration from spreadsheet {args.spreadsheet_id}"
        )
        print(f"User email: {args.user_email}")

        # Get data from each tab
        tabs = {
            "Books": ("Books!A:G", migrate_books),
            "ReadingRecords": ("ReadingRecords!A:G", migrate_reading_records),
            "ReadingList": (
                "ReadingList!A:D",
                lambda s, r, d: migrate_reading_list(s, r, user_id or 0, d),
            ),
            "Settings": (
                "Settings!A:E",
                lambda s, r, d: migrate_settings(s, r, user_id or 0, d),
            ),
            "Recommendations": (
                "Recommendations!A:E",
                lambda s, r, d: migrate_recommendations(s, r, user_id or 0, d),
            ),
        }

        total_migrated = 0

        for tab_name, (range_name, migrate_func) in tabs.items():
            print(f"\nProcessing {tab_name}...")
            data = get_sheet_data(sheets_service, args.spreadsheet_id, range_name)

            if not data:
                print(f"  No data found in {tab_name}")
                continue

            count = migrate_func(storage, data, args.dry_run)
            print(
                f"  {tab_name}: {count} records {'would be ' if args.dry_run else ''}migrated"
            )
            total_migrated += count

        print(f"\n{'DRY RUN: ' if args.dry_run else ''}Migration complete!")
        print(f"Total records migrated: {total_migrated}")

        if args.dry_run:
            print("This was a dry run. No data was actually modified.")
        else:
            print("Data has been successfully migrated to PostgreSQL.")

    except Exception as e:
        print(f"Error during migration: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
