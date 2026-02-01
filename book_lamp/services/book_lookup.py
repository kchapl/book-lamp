import html
from typing import Any, Dict, List, Optional

import requests

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"


def _parse_open_library_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper to parse a single book's data from Open Library."""
    title = data.get("title")
    authors = data.get("authors") or []
    author_name = None
    if authors and isinstance(authors, list):
        names = [a.get("name") for a in authors if a and a.get("name")]
        if names:
            author_name = ", ".join(names)

    publish_date = data.get("publish_date")
    publisher_list = data.get("publishers") or []
    publisher_name = None
    if publisher_list and isinstance(publisher_list, list):
        first_pub = publisher_list[0] or {}
        publisher_name = first_pub.get("name")

    description = data.get("notes")
    classifications = data.get("classifications") or {}
    dewey_list = classifications.get("dewey_decimal_class") or []
    dewey = dewey_list[0] if dewey_list and isinstance(dewey_list, list) else None

    # Edition info
    page_count = data.get("number_of_pages")
    physical_format = data.get("physical_format")
    edition_name = data.get("edition_name")

    languages = data.get("languages") or []
    language = None
    if languages and isinstance(languages, list):
        language = languages[0].get("name")

    thumbnail_url = None
    cover_url = None
    cover = data.get("cover") or {}
    if isinstance(cover, dict):
        thumbnail_url = cover.get("medium") or cover.get("small")
        cover_url = cover.get("large") or cover.get("medium")

    return {
        "title": html.unescape(title) if title else title,
        "author": html.unescape(author_name) if author_name else author_name,
        "publish_date": publish_date,
        "thumbnail_url": thumbnail_url,
        "cover_url": cover_url,
        "publisher": (
            html.unescape(publisher_name) if publisher_name else publisher_name
        ),
        "description": html.unescape(description) if description else description,
        "dewey_decimal": dewey,
        "page_count": page_count,
        "language": language,
        "physical_format": physical_format,
        "edition": edition_name,
    }


def _lookup_open_library(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via Open Library."""
    params = {
        "bibkeys": f"ISBN:{isbn13}",
        "format": "json",
        "jscmd": "data",
    }
    try:
        response = requests.get(OPEN_LIBRARY_API, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None

    key = f"ISBN:{isbn13}"
    if key not in payload:
        return None

    return _parse_open_library_data(payload[key])


def lookup_books_batch(isbn13_list: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Lookup metadata for multiple books via Open Library in batches.

    Args:
        isbn13_list: List of ISBN-13 strings.

    Returns:
        Dict mapping ISBN13 -> metadata dict (or None if not found).
    """
    results: Dict[str, Optional[Dict[str, Any]]] = {}
    if not isbn13_list:
        return results

    # Deduplicate
    unique_isbns = list(set(isbn13_list))

    # Process in chunks of 50
    chunk_size = 50
    for i in range(0, len(unique_isbns), chunk_size):
        chunk = unique_isbns[i : i + chunk_size]
        bibkeys = ",".join([f"ISBN:{isbn}" for isbn in chunk])

        params = {
            "bibkeys": bibkeys,
            "format": "json",
            "jscmd": "data",
        }

        try:
            response = requests.get(OPEN_LIBRARY_API, params=params, timeout=20)
            if response.status_code != 200:
                continue

            payload = response.json()

            for isbn in chunk:
                key = f"ISBN:{isbn}"
                if key in payload:
                    results[isbn] = _parse_open_library_data(payload[key])
                else:
                    results[isbn] = None

        except Exception:
            # If a batch fails, we just skip it (or could define retry logic)
            for isbn in chunk:
                results[isbn] = None

    return results


def _lookup_google_books(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via Google Books API."""
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{isbn13}"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "items" not in data or not data["items"]:
            return None

        item = data["items"][0]
        info = item.get("volumeInfo", {})

        title = info.get("title")
        authors = info.get("authors", [])
        author_name = ", ".join(authors) if authors else None
        publish_date = info.get("publishedDate")
        description = info.get("description")
        publisher = info.get("publisher")

        # Edition info
        page_count = info.get("pageCount")
        language = info.get("language")
        # Map ISO language codes to names if needed, but for now just the code
        physical_format = info.get("printType")

        image_links = info.get("imageLinks", {})
        thumbnail_url = image_links.get("thumbnail") or image_links.get(
            "smallThumbnail"
        )
        # Try to get larger images
        cover_url = (
            image_links.get("extraLarge")
            or image_links.get("large")
            or image_links.get("medium")
            or thumbnail_url
        )

        # Ensure HTTPS
        if thumbnail_url and thumbnail_url.startswith("http://"):
            thumbnail_url = thumbnail_url.replace("http://", "https://", 1)
        if cover_url and cover_url.startswith("http://"):
            cover_url = cover_url.replace("http://", "https://", 1)

        return {
            "title": html.unescape(title) if title else title,
            "author": html.unescape(author_name) if author_name else author_name,
            "publish_date": publish_date,
            "thumbnail_url": thumbnail_url,
            "cover_url": cover_url,
            "publisher": (html.unescape(publisher) if publisher else publisher),
            "description": html.unescape(description) if description else description,
            "dewey_decimal": None,
            "page_count": page_count,
            "language": language,
            "physical_format": physical_format,
            "edition": None,
        }
    except Exception:
        return None


def _lookup_itunes(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via iTunes Search API."""
    url = "https://itunes.apple.com/search"
    params = {"term": isbn13, "media": "ebook", "limit": "1"}
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "results" not in data or not data["results"]:
            return None

        item = data["results"][0]

        title = item.get("trackName")
        author_name = item.get("artistName")
        publish_date = item.get("releaseDate")
        if publish_date:
            publish_date = publish_date.split("T")[0]  # Extract date part
        description = item.get("description")

        # iTunes gives different sized artwork, "artworkUrl100" is usually available
        base_url = item.get("artworkUrl100") or item.get("artworkUrl60")
        thumbnail_url = base_url
        cover_url = None

        # Get high-res artwork if possible by replacing dimension in URL
        if base_url:
            thumbnail_url = base_url.replace("100x100bb", "200x200bb")
            cover_url = base_url.replace("100x100bb", "600x600bb")

        return {
            "title": html.unescape(title) if title else title,
            "author": html.unescape(author_name) if author_name else author_name,
            "publish_date": publish_date,
            "thumbnail_url": thumbnail_url,
            "cover_url": cover_url,
            "publisher": None,
            "description": html.unescape(description) if description else description,
            "dewey_decimal": None,
            "page_count": None,
            "language": None,
            "physical_format": "Ebook",
            "edition": None,
        }
    except Exception:
        return None


def _isbn13_to_isbn10(isbn13: str) -> Optional[str]:
    """Convert ISBN-13 to ISBN-10 if possible."""
    if not isbn13.startswith("978") or len(isbn13) != 13:
        return None

    # Use first 9 digits of the ISBN-13 (excluding 978 prefix)
    core = isbn13[3:12]

    # Calculate checksum
    total = 0
    for i, digit in enumerate(core):
        total += int(digit) * (10 - i)

    remainder = total % 11
    check_digit = 11 - remainder
    if check_digit == 10:
        check_char = "X"
    elif check_digit == 11:
        check_char = "0"
    else:
        check_char = str(check_digit)

    return core + check_char


def _lookup_amazon_cover(isbn13: str) -> Optional[str]:
    """Helper to lookup cover via Amazon image system.

    Amazon often has covers even if others don't, accessible via ISBN-10.
    Returns: URL string or None.
    """
    isbn10 = _isbn13_to_isbn10(isbn13)
    if not isbn10:
        return None

    # URL pattern for Amazon images
    url = f"https://images-na.ssl-images-amazon.com/images/P/{isbn10}.01.LZZZZZZZ.jpg"

    try:
        response = requests.get(url, timeout=5)
        # Amazon returns 200 OK even for missing images (usually a 1x1 pixel gif)
        # A real cover should be at least a few hundred bytes.
        # We'll use a conservative threshold of 100 bytes.
        if response.status_code == 200 and len(response.content) > 100:
            return url
    except Exception:
        pass

    return None


def lookup_book_by_isbn13(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Lookup a book by ISBN-13 using Open Library, Google Books, then iTunes.

    If metadata is found but no cover, attempts to fetch cover from Amazon.

    Returns a dict with keys: title, author, publish_date, thumbnail_url, cover_url, or None if not found.
    """
    # 1. Open Library
    ol_result = _lookup_open_library(isbn13)
    if ol_result and ol_result.get("thumbnail_url"):
        return ol_result

    # 2. Google Books
    gb_result = _lookup_google_books(isbn13)
    if gb_result and gb_result.get("thumbnail_url"):
        return gb_result

    # 3. iTunes Store
    itunes_result = _lookup_itunes(isbn13)
    if itunes_result and itunes_result.get("thumbnail_url"):
        return itunes_result

    # If we reached here, we have no result with a cover.
    # Pick the best available metadata to augment.
    best_result = ol_result or gb_result or itunes_result

    if best_result:
        # 4. Amazon (Cover only)
        # If we have valid metadata types but missing cover, try Amazon
        amazon_cover = _lookup_amazon_cover(isbn13)
        if amazon_cover:
            best_result["thumbnail_url"] = amazon_cover
            best_result["cover_url"] = amazon_cover

        return best_result

    return None


def enhance_books_batch(books: List[Dict[str, Any]], max_workers: int = 5) -> int:
    """Enhance a list of books with missing metadata/covers in parallel.

    Updates the books list in-place.
    Returns the number of books successfully updated.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def is_empty(value):
        return value is None or (isinstance(value, str) and not value.strip())

    candidates = []
    for b in books:
        if not b.get("isbn13"):
            continue
        # Check if missing any key field
        if any(
            is_empty(b.get(f))
            for f in [
                "thumbnail_url",
                "title",
                "author",
                "publication_year",
                "publisher",
                "description",
                "cover_url",
            ]
        ):
            candidates.append(b)

    if not candidates:
        return 0

    # 1. Batch lookup via Open Library
    all_isbns = [b["isbn13"] for b in candidates]
    batch_results = lookup_books_batch(all_isbns)

    updated_count = 0

    def process_book(book_item):
        isbn = book_item["isbn13"]
        try:
            # Try batch first
            info = batch_results.get(isbn)
            # Fallback to deep lookup
            if not info:
                info = lookup_book_by_isbn13(isbn)

            if not info:
                return False

            has_updates = False
            # Map fields safely
            field_map = {
                "thumbnail_url": "thumbnail_url",
                "cover_url": "cover_url",
                "title": "title",
                "author": "author",
                "publisher": "publisher",
                "description": "description",
                "dewey_decimal": "dewey_decimal",
                "language": "language",
                "page_count": "page_count",
                "physical_format": "physical_format",
                "edition": "edition",
            }

            for target, source in field_map.items():
                if is_empty(book_item.get(target)) and info.get(source):
                    val = info[source]
                    # Specific handling for strings/lengths
                    if target == "title" and len(val) > 300:
                        val = val[:300]
                    if target == "author" and len(val) > 200:
                        val = val[:200]
                    book_item[target] = val
                    has_updates = True

            # Special handling for publication_year
            if is_empty(book_item.get("publication_year")) and info.get("publish_date"):
                from book_lamp.utils.books import parse_publication_year

                year = parse_publication_year(info["publish_date"])
                if year:
                    book_item["publication_year"] = year
                    has_updates = True

            return has_updates
        except Exception:
            return False

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_book, b): b for b in candidates}
        for future in as_completed(futures):
            if future.result():
                updated_count += 1

    return updated_count
