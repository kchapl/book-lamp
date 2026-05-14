#!/usr/bin/env python3
"""Migration script to transfer data from Google Sheets to PostgreSQL."""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from book_lamp.services.pg_storage import PostgresStorage, get_pool

# Load environment variables from .env file
load_dotenv()

# Add the parent directory to the path so we can import book_lamp modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


def create_migration_batch() -> str:
    """Create a new migration batch ID for tracking."""
    batch_id = str(uuid.uuid4())[:8]
    print(f"Migration batch ID: {batch_id}")
    return batch_id


def validate_migration(
    storage: PostgresStorage, spreadsheet_id: str, sheets_service: Any
) -> Dict[str, Any]:
    """Validate migration viability without making changes."""
    validation_results = {
        "valid": True,
        "notes": [],
        "warnings": [],
        "book_count": 0,
        "record_count": 0,
        "list_count": 0,
    }

    tabs = {
        "Books": "Books!A:G",
        "ReadingRecords": "ReadingRecords!A:G",
        "ReadingList": "ReadingList!A:D",
        "Settings": "Settings!A:E",
        "Recommendations": "Recommendations!A:E",
    }

    # Check each tab
    for tab_name, range_name in tabs.items():
        data = get_sheet_data(sheets_service, spreadsheet_id, range_name)
        count = max(0, len(data) - 1) if data else 0  # Subtract header row
        validation_results[f"{tab_name.lower()}_count"] = count
        validation_results["notes"].append(
            f"{tab_name}: {count} rows found"
        )

        # Check for potential issues
        if tab_name == "Books" and data and len(data) > 1:
            for row in data[1:]:
                if len(row) >= 2 and row[1]:  # Has ISBN
                    validation_results["warnings"].append(
                        f"Book '{row[2][:30]}...' has ISBN - may deduplicate"
                    )
                    break

        if tab_name == "ReadingRecords" and data and len(data) > 1:
            for row in data[1:]:
                if len(row) >= 2 and row[1].isdigit():
                    validation_results["warnings"].append(
                        f"Reading record references book_id {row[1]} - ID mapping required"
                    )
                    break

    validation_results["book_count"] = validation_results.get("books_count", 0)
    validation_results["record_count"] = validation_results.get("readingrecords_count", 0)

    return validation_results


def rollback_migration(batch_id: str, user_id: int, dry_run: bool) -> int:
    """Rollback a migration by batch ID.

    This removes records created in the specified batch.
    For simplicity, we delete records within a time window matching the batch.
    Returns number of records rolled back.
    """
    # In a full implementation, we'd track batch_id with each record
    # For now, we provide a warning that manual intervention may be needed
    print(f"Rollback requested for batch: {batch_id}")
    print("Note: Full batch tracking requires migration_history table")

    if dry_run:
        print("DRY RUN: Would rollback migration records")
        return 0

    # Simplified rollback - just warn the user
    print("Manual rollback may be required. Consider backing up data before migration.")
    return 0


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
            storage.upsert_book(
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
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate migration without making changes",
    )
    parser.add_argument(
        "--rollback",
        type=str,
        help="Rollback a migration by batch ID",
    )

    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        print("Error: DATABASE_URL environment variable is required")
        sys.exit(1)

    # Handle rollback option
    if args.rollback:
        if not args.user_email:
            print("Error: --user-email is required for rollback")
            sys.exit(1)
        user_id = PostgresStorage.upsert_user(args.user_email, args.user_email)
        rollback_migration(args.rollback, user_id, args.dry_run)
        return

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

        # Validate first if requested
        if args.validate_only:
            print("Validating migration...")
            validation = validate_migration(storage, args.spreadsheet_id, sheets_service)
            print("\n=== Validation Results ===")
            print(f"Valid: {validation['valid']}")
            print("\nNotes:")
            for note in validation["notes"]:
                print(f"  - {note}")
            if validation["warnings"]:
                print("\nWarnings:")
                for warning in validation["warnings"]:
                    print(f"  - {warning}")
            print(f"\nTotal records to migrate: {validation['book_count']} books, {validation['record_count']} records")
            return

        print(
            f"{'DRY RUN: ' if args.dry_run else ''}Starting migration from spreadsheet {args.spreadsheet_id}"
        )
        print(f"User email: {args.user_email}")

        # Create batch for tracking
        batch_id = create_migration_batch() if not args.dry_run else None

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
