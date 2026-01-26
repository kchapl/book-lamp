import csv
import html
import io
import re
from typing import Any, Dict, List, Optional


def clean_isbn(isbn: str) -> str:
    """Remove hyphens and other non-digit characters from ISBN."""
    if not isbn:
        return ""
    return re.sub(r"\D", "", str(isbn))


def normalize_date(date_str: str) -> str:
    """Convert common date formats to YYYY-MM-DD."""
    if not date_str:
        return ""

    # Already YYYY-MM-DD
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        return date_str

    # Handle MM/DD/YYYY
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", date_str)
    if match:
        m, d, y = match.groups()
        return f"{y}-{int(m):02d}-{int(d):02d}"

    # Handle MM/DD/YY (assume 20xx for now as Libib is modern)
    match = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", date_str)
    if match:
        m, d, y = match.groups()
        return f"20{y}-{int(m):02d}-{int(d):02d}"

    return date_str


def parse_libib_csv(csv_content: str) -> List[Dict[str, Any]]:
    """Parse Libib CSV content into a list of book and reading record data.

    Expected columns:
    Title, Author, ISBN, UPC, LCCN, Item Type, Publish Date, Publisher,
    Rating, Review, Tags, Notes, Date Added, Date Completed, Price
    """
    stream = io.StringIO(csv_content)
    # Some Libib exports might have a BOM
    if csv_content.startswith("\ufeff"):
        stream.seek(1)

    reader = csv.DictReader(stream)
    results = []

    for row in reader:
        # Map headers (case-insensitive and handling potential spaces)
        def get_val(keys: List[str]) -> str:
            for k in row.keys():
                clean_k = k.strip().lower().replace("_", " ")
                if clean_k in [key.lower().replace("_", " ") for key in keys]:
                    return html.unescape(row[k].strip())
            return ""

        title = get_val(["Title"])
        author = get_val(["Author", "Creators"])
        isbn = clean_isbn(
            get_val(["ISBN", "ISBN 13", "ISBN 10", "ean_isbn13", "upc_isbn10"])
        )
        publish_date = get_val(["Publish Date"])
        rating_str = get_val(["Rating"])
        date_added = normalize_date(get_val(["Date Added", "added"]))
        date_completed = normalize_date(get_val(["Date Completed", "completed"]))
        date_began = normalize_date(get_val(["began"]))
        libib_status = get_val(["Reading Status", "Status"])
        publisher = get_val(["Publisher"])
        description = get_val(["Description", "Notes"])
        series = get_val(["Series"])
        dewey_decimal = get_val(["DDC"])
        language = get_val(["Language"])
        page_count_str = get_val(["Page Count", "Pages"])
        physical_format = get_val(["Physical Format", "Item Type"])
        edition = get_val(["Edition"])

        page_count = None
        if page_count_str:
            try:
                page_count = int(re.sub(r"\D", "", page_count_str))
            except (ValueError, TypeError):
                page_count = None

        if not title or not isbn:
            continue

        # Basic year extraction from publish_date
        year = None
        if publish_date:
            year_match = re.search(r"\d{4}", publish_date)
            if year_match:
                year = int(year_match.group())

        # Rating conversion
        rating = 0
        if rating_str:
            try:
                rating = int(float(rating_str))
            except (ValueError, TypeError):
                rating = 0

        # Reading Record Logic
        # If we have a completed date, it's definitely Completed.
        # If we only have an added date, we'll assume it's Completed on that day for the sake of history,
        # unless it's very recent? Actually, let's just use what's there.
        # Status mapping
        # Libib: Abandoned, Not begun, In progress, Completed
        # Book Lamp: Abandoned, In Progress, Completed
        status: Optional[str] = "Completed"
        if libib_status:
            ls = libib_status.lower()
            if "abandon" in ls:
                status = "Abandoned"
            elif "progress" in ls:
                status = "In Progress"
            elif "begun" in ls or "not" in ls:
                status = "Not begun"  # We'll allow this or map to In Progress?
                # Let's stick to Book Lamp's 3 states. If not begun, we might just not add a record?
                # Actually let's just use "In Progress" or skip.
                # User said "Each entry will create a new reading history record".
                # If "Not begun", it's just on the shelf. Maybe we skip the record but add the book.
                pass
            else:
                status = "Completed"
        elif date_completed:
            status = "Completed"
        elif date_added:
            status = "In Progress"

        if libib_status and "not begun" in libib_status.lower():
            # If not begun, don't create a reading record, just the book.
            status = None

        # Prefer 'began' date, then 'added' date, then 'completed' date
        start_date = (
            date_began if date_began else (date_added if date_added else date_completed)
        )
        end_date = (
            date_completed if date_completed else None
        )  # Don't fill end_date if not completed

        if status == "Completed" and not end_date:
            end_date = start_date

        # Sanity check: Start date shouldn't be after end date
        if start_date and end_date and start_date > end_date:
            # If they conflict, assume the record was completed on the end_date
            # and we just don't have a reliable start date.
            start_date = end_date

        # If no dates at all, use today
        if not start_date and status:
            from datetime import date

            start_date = date.today().isoformat()

        results.append(
            {
                "book": {
                    "isbn13": isbn,
                    "title": title,
                    "author": author,
                    "publication_year": year,
                    "publisher": publisher,
                    "description": description,
                    "series": series,
                    "dewey_decimal": dewey_decimal,
                    "language": language,
                    "page_count": page_count,
                    "physical_format": physical_format,
                    "edition": edition,
                },
                "record": (
                    {
                        "status": status,
                        "start_date": start_date,
                        "end_date": end_date,
                        "rating": rating,
                    }
                    if status
                    else None
                ),
            }
        )

    return results
