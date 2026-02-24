import html
import logging
import re
from typing import Any, Dict, List, Optional, cast

import requests

from book_lamp.services.cache import get_cache
from book_lamp.utils.books import (
    isbn13_to_isbn10,
    normalize_isbn,
)

logger = logging.getLogger("book_lamp")

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"
OPEN_LIBRARY_SEARCH_API = "https://openlibrary.org/search.json"
GOOGLE_BOOKS_API = "https://www.googleapis.com/books/v1/volumes"
ITUNES_API = "https://itunes.apple.com/search"

# Shared session for connection pooling and consistent headers.
_session: Optional[requests.Session] = None


def _get_session() -> requests.Session:
    """Get or create a shared requests session with a proper User-Agent.

    Open Library triples its rate limit (100 → 300 req/5 min) when a
    User-Agent header is provided. A session also reuses TCP connections
    for better performance when making many sequential requests.
    """
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(
            {
                "User-Agent": "BookLamp/1.0 (personal reading tracker; https://github.com/book-lamp)",
            }
        )
    return _session


def _clean_title_for_search(title: str) -> str:
    """Clean a book title for better search results.

    Removes subtitles, series info in brackets, and common fluff that can
    trip up API search algorithms.
    """
    if not title:
        return ""

    # 1. Strip HTML entities just in case
    clean = html.unescape(title)

    # 2. Remove anything in brackets or parentheses (often series/edition info)
    clean = re.sub(r"[\(\[\{].*?[\)\]\}]", "", clean)

    # 3. Take the main title before a colon or dash if it's substantial
    for separator in [":", " - "]:
        if separator in clean:
            parts = clean.split(separator)
            # If the part before the separator is long enough to be a title
            if len(parts[0].strip()) > 3:
                clean = parts[0]
                break

    # 4. Final trim and remove trailing punctuation
    return clean.strip().rstrip(".,;:-")


def _upgrade_google_books_image(url: Optional[str]) -> Optional[str]:
    """Upgrade Google Books thumbnail URL to higher resolution and HTTPS."""
    if not url:
        return None

    # Use HTTPS
    url = url.replace("http://", "https://")

    # Remove edge curl and set zoom to a higher value if present
    # zoom=1 is often tiny; zoom=0 or omitting it often gives a larger image
    url = url.replace("&edge=curl", "")
    if "zoom=1" in url:
        url = url.replace("zoom=1", "zoom=0")

    return url


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
    session = _get_session()
    params: Dict[str, str] = {
        "bibkeys": f"ISBN:{isbn13}",
        "format": "json",
        "jscmd": "data",
    }
    try:
        response = session.get(OPEN_LIBRARY_API, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        logger.debug(f"Open Library lookup failed for {isbn13}: {e}")
        return None

    key = f"ISBN:{isbn13}"
    if key not in payload:
        logger.debug(f"Open Library has no data for {isbn13}")
        return None

    result = _parse_open_library_data(payload[key])
    logger.debug(
        f"Open Library returned data for {isbn13}: has_cover={bool(result.get('thumbnail_url'))}"
    )
    return result


def _lookup_open_library_cover_direct(isbn13: str) -> Optional[str]:
    """Helper to check Open Library covers API directly."""
    session = _get_session()
    url = f"https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg?default=false"
    try:
        response = session.head(url, timeout=5, allow_redirects=True)
        if (
            response.status_code == 200
            and "image" in response.headers.get("Content-Type", "").lower()
        ):
            return url
    except Exception:
        pass
    return None


def _lookup_open_library_search(
    title: str, author: Optional[str] = None
) -> Optional[Dict[str, Optional[Any]]]:
    """Search Open Library by title and author to find a cover from a related edition."""
    session = _get_session()
    clean_title = _clean_title_for_search(title)

    # Try structured search first
    params: Dict[str, str] = {
        "title": clean_title,
        "limit": "10",
        "fields": "key,title,author_name,cover_i,first_publish_year,publisher",
    }
    if author:
        params["author"] = author

    try:
        response = session.get(OPEN_LIBRARY_SEARCH_API, params=params, timeout=10)
        data = response.json()
        docs = data.get("docs") or []

        # Fallback to general query if no structured results
        if not docs:
            q = f"{clean_title} {author}" if author else clean_title
            params = {
                "q": q,
                "limit": "10",
                "fields": "key,title,author_name,cover_i,first_publish_year,publisher",
            }
            response = session.get(OPEN_LIBRARY_SEARCH_API, params=params, timeout=10)
            docs = response.json().get("docs") or []

        for doc in docs:
            cover_id = doc.get("cover_i")
            if cover_id:
                authors = doc.get("author_name") or []
                publishers = doc.get("publisher") or []
                return {
                    "title": doc.get("title"),
                    "author": ", ".join(authors) if authors else None,
                    "thumbnail_url": f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg",
                    "cover_url": f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg",
                    "publish_date": (
                        str(doc.get("first_publish_year"))
                        if doc.get("first_publish_year")
                        else None
                    ),
                    "publisher": publishers[0] if publishers else None,
                }
    except Exception as e:
        logger.debug(f"Open Library search failed: {e}")
    return None


def lookup_books_batch(isbn13_list: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
    """Lookup metadata for multiple books via cache or Open Library in batches.

    Args:
        isbn13_list: List of ISBN-13 strings.

    Returns:
        Dict mapping ISBN13 -> metadata dict (or None if not found).
    """
    session = _get_session()
    results: Dict[str, Optional[Dict[str, Any]]] = {}
    if not isbn13_list:
        return results

    # Deduplicate and normalize
    unique_isbns = list(set(normalize_isbn(isbn) for isbn in isbn13_list))
    cache = get_cache()

    # 1. Check cache first
    remaining_isbns = []
    for isbn in unique_isbns:
        cached = cache.get(f"isbn:{isbn}")
        if cached:
            results[isbn] = cached
        else:
            remaining_isbns.append(isbn)

    if not remaining_isbns:
        logger.debug(f"All {len(unique_isbns)} ISBNs found in cache")
        return results

    logger.debug(
        f"Batch lookup for {len(unique_isbns)} unique ISBNs ({len(remaining_isbns)} not in cache)"
    )

    # 2. Process remaining in chunks of 50
    chunk_size = 50
    for i in range(0, len(remaining_isbns), chunk_size):
        chunk = remaining_isbns[i : i + chunk_size]
        bibkeys = ",".join([f"ISBN:{isbn}" for isbn in chunk])

        params: Dict[str, str] = {
            "bibkeys": bibkeys,
            "format": "json",
            "jscmd": "data",
        }

        try:
            logger.debug(f"Making Open Library API request for {len(chunk)} ISBNs")
            response = session.get(OPEN_LIBRARY_API, params=params, timeout=20)
            if response.status_code != 200:
                logger.warning(
                    f"Open Library API returned status {response.status_code}"
                )
                continue

            payload = response.json()
            logger.debug(f"Open Library API returned {len(payload)} results")

            for isbn in chunk:
                key = f"ISBN:{isbn}"
                if key in payload:
                    data = _parse_open_library_data(payload[key])
                    results[isbn] = data
                    cache.set(f"isbn:{isbn}", data)
                    logger.debug(f"  Found and cached data for ISBN {isbn}")
                else:
                    results[isbn] = None
                    logger.debug(f"  No data for ISBN {isbn}")

        except Exception as e:
            logger.warning(f"Batch lookup failed: {e}")
            for isbn in chunk:
                results[isbn] = None

    return results


def lookup_books_by_author(
    author_name: str, max_results: int = 50
) -> List[Dict[str, Any]]:
    """Search Open Library for all books by a given author name.

    Returns deduplicated results with the latest edition per title, sorted
    by reverse publication year. Results are cached to avoid redundant API calls.

    Args:
        author_name: The author's full name (e.g. "Jane Austen").
        max_results: Maximum number of books to return (default 50).

    Returns:
        List of book dicts with keys: title, author, publication_year,
        thumbnail_url, isbn13, publisher, description.
    """
    cache = get_cache()
    cache_key = f"author_books:{author_name.lower().strip()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cast(List[Dict[str, Any]], cached)

    session = _get_session()
    params: Dict[str, str] = {
        "author": author_name,
        "limit": str(min(max_results, 100)),
        "fields": (
            "key,title,author_name,cover_i,first_publish_year,"
            "isbn,publisher,subject,language"
        ),
    }

    books: List[Dict[str, Any]] = []
    try:
        response = session.get(OPEN_LIBRARY_SEARCH_API, params=params, timeout=15)
        response.raise_for_status()
        docs = response.json().get("docs") or []

        # Deduplicate by normalised title, keeping the entry with the latest year.
        # Each doc may have many ISBNs; we prefer an ISBN-13 (13 digits).
        seen_titles: Dict[str, Dict[str, Any]] = {}

        for doc in docs:
            raw_title = doc.get("title")
            if not raw_title:
                continue

            # Normalise title for dedup purposes (lower, strip)
            norm_title = raw_title.strip().lower()

            year_val = doc.get("first_publish_year")
            try:
                year = int(year_val) if year_val else 0
            except (ValueError, TypeError):
                year = 0

            # Choose a preferred ISBN-13
            isbn13 = None
            for isbn_candidate in doc.get("isbn") or []:
                clean = isbn_candidate.replace("-", "").replace(" ", "")
                if len(clean) == 13 and clean.isdigit():
                    isbn13 = clean
                    break

            cover_id = doc.get("cover_i")
            thumbnail_url = (
                f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
                if cover_id
                else None
            )

            doc_authors = doc.get("author_name") or []
            author_str = ", ".join(doc_authors) if doc_authors else author_name

            publishers = doc.get("publisher") or []
            publisher = publishers[0] if publishers else None

            entry: Dict[str, Any] = {
                "title": raw_title.strip(),
                "author": author_str,
                "publication_year": year if year else None,
                "thumbnail_url": thumbnail_url,
                "isbn13": isbn13,
                "publisher": publisher,
                "description": None,  # Not available from search endpoint
            }

            # Keep entry with the latest year for a given title
            existing = seen_titles.get(norm_title)
            if existing is None or year > (existing.get("publication_year") or 0):
                seen_titles[norm_title] = entry

        books = sorted(
            seen_titles.values(),
            key=lambda b: b.get("publication_year") or 0,
            reverse=True,
        )

    except Exception as e:
        logger.debug(f"Author books lookup failed for '{author_name}': {e}")

    # Cache for 24 hours (86400s); author bibliographies rarely change
    cache.set(cache_key, books, ttl=86400)
    return books


def _lookup_google_books(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Lookup book details via Google Books API (ISBN)."""
    session = _get_session()
    params: Dict[str, str] = {"q": f"isbn:{isbn13}"}
    try:
        response = session.get(GOOGLE_BOOKS_API, params=params, timeout=10)
        data = response.json()
        if "items" in data and data["items"]:
            return _parse_google_books_item(data["items"][0])
    except Exception as e:
        logger.debug(f"Google Books lookup failed for {isbn13}: {e}")
    return None


def _lookup_google_books_search(
    title: str, author: Optional[str] = None
) -> Optional[Dict[str, Optional[Any]]]:
    """Search Google Books by title and author for covers."""
    session = _get_session()
    clean_title = _clean_title_for_search(title)
    q = f'intitle:"{clean_title}"'
    if author:
        q += f' inauthor:"{author}"'

    params: Dict[str, str] = {"q": q, "maxResults": "5"}
    try:
        response = session.get(GOOGLE_BOOKS_API, params=params, timeout=10)
        data = response.json()
        if "items" in data and data["items"]:
            # Prioritize result with a cover
            for item in data["items"]:
                if item.get("volumeInfo", {}).get("imageLinks"):
                    return _parse_google_books_item(item)
            return _parse_google_books_item(data["items"][0])
    except Exception as e:
        logger.debug(f"Google Books search failed: {e}")
    return None


def _parse_google_books_item(item: Dict[str, Any]) -> Dict[str, Optional[Any]]:
    """Helper to parse a Google Books API volume item."""
    info = item.get("volumeInfo", {})
    image_links = info.get("imageLinks", {})
    thumbnail = _upgrade_google_books_image(
        image_links.get("thumbnail") or image_links.get("smallThumbnail")
    )

    return {
        "title": html.unescape(info.get("title", "")),
        "author": ", ".join(info.get("authors", [])) if info.get("authors") else None,
        "publish_date": info.get("publishedDate"),
        "thumbnail_url": thumbnail,
        "cover_url": thumbnail,
        "publisher": info.get("publisher"),
        "description": info.get("description"),
        "page_count": info.get("pageCount"),
        "language": info.get("language"),
        "physical_format": info.get("printType"),
    }


def _lookup_itunes_search(
    title: str, author: Optional[str] = None
) -> Optional[Dict[str, Optional[Any]]]:
    """Fallback search via iTunes Store for high-res eBook covers."""
    session = _get_session()
    clean_title = _clean_title_for_search(title)
    term = f"{clean_title} {author}" if author else clean_title
    params: Dict[str, str] = {"term": term, "media": "ebook", "limit": "5"}
    try:
        response = session.get(ITUNES_API, params=params, timeout=10)
        data = response.json()
        if data.get("results"):
            item = data["results"][0]
            base_url = item.get("artworkUrl100")
            if base_url:
                thumbnail = base_url.replace("100x100bb", "200x200bb")
                cover = base_url.replace("100x100bb", "600x600bb")
                return {
                    "title": item.get("trackName"),
                    "author": item.get("artistName"),
                    "thumbnail_url": thumbnail,
                    "cover_url": cover,
                }
    except Exception:
        pass
    return None


def _lookup_itunes(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via iTunes Search API."""
    session = _get_session()
    url = "https://itunes.apple.com/search"
    params: Dict[str, str] = {"term": isbn13, "media": "ebook", "limit": "1"}
    try:
        response = session.get(url, params=params, timeout=10)
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


def _lookup_amazon_cover(isbn13: str) -> Optional[str]:
    """Helper to lookup cover via Amazon image system.

    Amazon often has covers even if others don't, accessible via ISBN-10 or candidate.
    Returns: URL string or None.
    """
    session = _get_session()

    isbn10 = isbn13_to_isbn10(isbn13)
    if not isbn10:
        logger.debug(f"Could not convert {isbn13} to ISBN-10, skipping Amazon lookup")
        return None

    # URL pattern for Amazon images
    url = f"https://images-na.ssl-images-amazon.com/images/P/{isbn10}.01.LZZZZZZZ.jpg"

    try:
        logger.debug(f"Checking Amazon for {isbn13} (ISBN-10: {isbn10}): {url}")
        # Use HEAD to avoid downloading the full image.
        # Amazon returns 200 for missing covers (tiny 1x1 placeholder),
        # so we check Content-Length.
        response = session.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200:
            content_length = int(response.headers.get("Content-Length", 0))
            # A real cover should be at least a few hundred bytes.
            if content_length > 1000:
                logger.debug(f"Found Amazon cover for {isbn13}: {content_length} bytes")
                return url
            elif content_length == 0:
                # Server didn't provide Content-Length; fall back to GET with stream
                get_resp = session.get(url, timeout=5, stream=True)
                # Read just enough to check size
                chunk = get_resp.raw.read(2000)
                get_resp.close()
                if len(chunk) > 1000:
                    logger.debug(
                        f"Found Amazon cover for {isbn13}: confirmed via partial download"
                    )
                    return url
            logger.debug(
                f"No valid cover on Amazon for {isbn13}: size={content_length}"
            )
        else:
            logger.debug(
                f"No valid cover on Amazon for {isbn13}: status={response.status_code}"
            )
    except Exception as e:
        logger.debug(f"Amazon lookup failed for {isbn13}: {e}")

    return None


def _lookup_penguin_cover(isbn13: str) -> Optional[str]:
    """Helper to lookup cover via Penguin Random House image system.

    Works for most Penguin, Vintage, and Random House editions.
    Returns: URL string or None.
    """
    session = _get_session()
    url = f"https://images.penguinrandomhouse.com/cover/{isbn13}"

    try:
        logger.debug(f"Checking Penguin Random House for {isbn13}: {url}")
        # Need to allow redirects as it might redirect to a specific size
        response = session.head(url, timeout=5, allow_redirects=True)
        # Check if it's actually an image and not a 404/placeholder
        if (
            response.status_code == 200
            and "image" in response.headers.get("Content-Type", "").lower()
        ):
            # Basic sanity check on size if available
            size = int(response.headers.get("Content-Length", 0))
            if size > 1000 or size == 0:  # Allow 0 if server doesn't provide length
                return url
    except Exception as e:
        logger.debug(f"Penguin lookup failed for {isbn13}: {e}")

    return None


def _merge_metadata(
    target: Dict[str, Any], source: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Merge non-empty metadata fields from source into target."""
    if not source:
        return target
    for k, v in source.items():
        if v and not (isinstance(v, str) and not v.strip()):
            if not target.get(k):
                target[k] = v
    return target


def lookup_book_by_isbn13(
    isbn13: str, title: Optional[str] = None, author: Optional[str] = None
) -> Optional[Dict[str, Optional[Any]]]:
    """Deep lookup for book details with progressive fallbacks."""
    clean_isbn = normalize_isbn(isbn13)
    cache = get_cache()

    # 0. Check Cache - return if cover found OR if we're not doing a search refinement
    cached = cache.get(f"isbn:{clean_isbn}")
    if cached and (cached.get("thumbnail_url") or not title):
        logger.debug(f"Cache hit for ISBN {clean_isbn}")
        return cast(Dict[str, Any], cached)

    best: Dict[str, Any] = {"isbn13": clean_isbn}
    if title:
        best["title"] = title
    if author:
        best["author"] = author

    # 1. ISBN-based API Lookups
    logger.debug("  Trying ISBN-based lookups...")
    best = _merge_metadata(best, _lookup_open_library(clean_isbn))
    best = _merge_metadata(best, _lookup_google_books(clean_isbn))

    if best.get("thumbnail_url"):
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    # 2. Direct Cover Lookups
    logger.debug("  Trying direct cover lookups...")
    ol_direct = _lookup_open_library_cover_direct(clean_isbn)
    if ol_direct:
        best["thumbnail_url"] = ol_direct
        best["cover_url"] = ol_direct.replace("-M.jpg", "-L.jpg")
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    prh_cover = _lookup_penguin_cover(clean_isbn)
    if prh_cover:
        best["thumbnail_url"] = prh_cover
        best["cover_url"] = prh_cover
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    amazon_cover = _lookup_amazon_cover(clean_isbn)
    if amazon_cover:
        best["thumbnail_url"] = amazon_cover
        best["cover_url"] = amazon_cover
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    # 3. Search Fallbacks (Crucial for missing covers on specific editions)
    search_title = best.get("title")
    search_author = best.get("author")

    if search_title and search_title != "Unknown":
        logger.debug(f"  Initiating search fallback for '{search_title}'")
        # Open Library search often finds related editions with covers
        ol_search = _lookup_open_library_search(search_title, search_author)
        best = _merge_metadata(best, ol_search)
        if best.get("thumbnail_url"):
            cache.set(f"isbn:{clean_isbn}", best)
            return best

        # Google Books search
        gb_search = _lookup_google_books_search(search_title, search_author)
        best = _merge_metadata(best, gb_search)
        if best.get("thumbnail_url"):
            cache.set(f"isbn:{clean_isbn}", best)
            return best

        # iTunes search
        it_search = _lookup_itunes_search(search_title, search_author)
        best = _merge_metadata(best, it_search)
        if best.get("thumbnail_url"):
            cache.set(f"isbn:{clean_isbn}", best)
            return best

    # Cache whatever we found (even if no cover)
    if len(best) > 1:  # More than just the ISBN
        cache.set(f"isbn:{clean_isbn}", best)
        logger.debug(
            f"  Cached metadata for {clean_isbn} (has_cover={bool(best.get('thumbnail_url'))})"
        )
        return best

    logger.debug(f"  No data found for ISBN {clean_isbn}")
    return None


def _empty_result() -> Dict[str, Optional[Any]]:
    """Create an empty metadata template."""
    return {
        "title": None,
        "author": None,
        "publish_date": None,
        "thumbnail_url": None,
        "cover_url": None,
        "publisher": None,
        "description": None,
        "dewey_decimal": None,
        "page_count": None,
        "language": None,
        "physical_format": None,
        "edition": None,
    }


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
            logger.debug(f"Skipping book (no ISBN): {b.get('title', 'Unknown')}")
            continue

        # Consider a book a candidate if it has an ISBN and is missing cover/thumbnail
        # OR if it's missing any other key metadata
        has_cover = b.get("cover_url") or b.get("thumbnail_url")

        missing_fields = [
            f
            for f in [
                "thumbnail_url",
                "title",
                "author",
                "publication_year",
                "publisher",
                "description",
                "cover_url",
            ]
            if is_empty(b.get(f))
        ]

        if missing_fields or not has_cover:
            candidates.append(b)
            if not has_cover:
                logger.debug(f"Candidate book (no cover): {b.get('title', 'Unknown')}")
            else:
                logger.debug(
                    f"Candidate book (missing: {missing_fields}): {b.get('title', 'Unknown')}"
                )
        else:
            logger.debug(f"Skipping book (complete): {b.get('title', 'Unknown')}")

    if not candidates:
        logger.info(f"No candidates found for enhancement out of {len(books)} books")
        return 0

    logger.info(f"Found {len(candidates)} candidate(s) for enhancement")

    # 1. Batch lookup via Open Library
    all_isbns = [b["isbn13"] for b in candidates]
    logger.info(
        f"Performing batch lookup for ISBNs: {all_isbns[:5]}..."
        if len(all_isbns) > 5
        else f"Performing batch lookup for ISBNs: {all_isbns}"
    )
    batch_results = lookup_books_batch(all_isbns)

    found_count = sum(1 for v in batch_results.values() if v is not None)
    logger.info(f"Batch lookup returned data for {found_count}/{len(all_isbns)} books")

    updated_count = 0

    def process_book(book_item):
        from book_lamp.utils.books import normalize_isbn as _normalize_isbn

        isbn = _normalize_isbn(book_item.get("isbn13", ""))
        title = book_item.get("title", "Unknown")
        try:
            # Try batch result first (normalized ISBN lookup)
            info = batch_results.get(isbn)
            source = "batch"

            # Fallback to deep lookup if batch missed or returned no cover
            if not info or not info.get("thumbnail_url"):
                logger.debug(
                    f"Batch lookup {'miss' if not info else 'has no cover'} for {title} "
                    f"(ISBN: {isbn}), trying deep lookup..."
                )
                deep_info = lookup_book_by_isbn13(
                    isbn,
                    title=book_item.get("title"),
                    author=book_item.get("author"),
                )
                if deep_info:
                    # Merge: deep lookup enriches batch data
                    if info:
                        info = _merge_metadata(info, deep_info)
                    else:
                        info = deep_info
                    source = "deep"

            if not info:
                logger.warning(f"No lookup result for {title} (ISBN: {isbn})")
                return False

            logger.debug(f"Found data from {source} for {title}: {info}")

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

            for target, source_field in field_map.items():
                if is_empty(book_item.get(target)) and info.get(source_field):
                    val = info[source_field]
                    # Specific handling for strings/lengths
                    if isinstance(val, str):
                        if target == "title" and len(val) > 300:
                            val = val[:300]
                        if target == "author" and len(val) > 200:
                            val = val[:200]
                    book_item[target] = val
                    has_updates = True
                    logger.debug(f"Updated {target} for {title}: {val}")

            # Special handling for publication_year
            if is_empty(book_item.get("publication_year")) and info.get("publish_date"):
                from book_lamp.utils.books import parse_publication_year

                year = parse_publication_year(info["publish_date"])
                if year:
                    book_item["publication_year"] = year
                    has_updates = True
                    logger.debug(f"Updated publication_year for {title}: {year}")

            if not has_updates:
                logger.debug(
                    f"No updates made for {title} - all fields already present in result"
                )

            return has_updates
        except Exception:
            logger.exception(f"Error processing book {title}")
            return False

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_book, b): b for b in candidates}
        for future in as_completed(futures):
            if future.result():
                updated_count += 1

    logger.info(f"Successfully updated {updated_count} books")
    return updated_count
