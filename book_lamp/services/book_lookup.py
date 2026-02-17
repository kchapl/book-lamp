import html
import logging
from typing import Any, Dict, List, Optional, Union, cast

import requests

from book_lamp.services.cache import get_cache
from book_lamp.utils.books import (
    isbn13_to_isbn10,
    normalize_isbn,
)

logger = logging.getLogger("book_lamp")

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"
OPEN_LIBRARY_SEARCH_API = "https://openlibrary.org/search.json"

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
    params = {
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
    """Helper to check Open Library covers API directly if not in metadata."""
    session = _get_session()
    url = f"https://covers.openlibrary.org/b/isbn/{isbn13}-M.jpg?default=false"
    try:
        # We only need to check if the image exists
        response = session.head(url, timeout=5, allow_redirects=True)
        if response.status_code == 200 and "image" in response.headers.get(
            "Content-Type", ""
        ):
            return url
    except Exception:
        pass
    return None


def _lookup_open_library_search(
    title: str, author: Optional[str] = None
) -> Optional[Dict[str, Optional[Any]]]:
    """Search Open Library by title (and optionally author) to find a cover.

    This is the key fallback for ISBN editions that lack cover images.
    Many books have covers on Open Library under a different edition
    (ISBN) of the same work. The search API lets us find those editions.

    Only used when ISBN-based lookups have failed to locate a cover.
    """
    session = _get_session()
    params: Dict[str, Union[str, int]] = {
        "title": title,
        "limit": 5,
        "fields": "key,title,author_name,cover_i,first_publish_year,publisher,isbn",
    }
    if author:
        params["author"] = author

    try:
        response = session.get(OPEN_LIBRARY_SEARCH_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        logger.debug(f"Open Library search failed for '{title}': {e}")
        return None

    docs = data.get("docs") or []
    if not docs:
        logger.debug(f"Open Library search returned no results for '{title}'")
        return None

    # Find the first result that has a cover_i (cover ID)
    for doc in docs:
        cover_id = doc.get("cover_i")
        if not cover_id:
            continue

        thumbnail_url = f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg"

        authors = doc.get("author_name") or []
        author_name = ", ".join(authors) if authors else None
        publish_year = doc.get("first_publish_year")
        publishers = doc.get("publisher") or []

        result: Dict[str, Optional[Any]] = {
            "title": doc.get("title"),
            "author": author_name,
            "publish_date": str(publish_year) if publish_year else None,
            "thumbnail_url": thumbnail_url,
            "cover_url": cover_url,
            "publisher": publishers[0] if publishers else None,
            "description": None,
            "dewey_decimal": None,
            "page_count": None,
            "language": None,
            "physical_format": None,
            "edition": None,
        }
        logger.debug(
            f"Open Library search found cover for '{title}' via cover_id={cover_id}"
        )
        return result

    logger.debug(
        f"Open Library search: results found for '{title}' but none had covers"
    )
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

        params = {
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


def _lookup_google_books(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via Google Books API."""
    session = _get_session()
    url = "https://www.googleapis.com/books/v1/volumes"
    params = {"q": f"isbn:{isbn13}"}
    try:
        response = session.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "items" not in data or not data["items"]:
            logger.debug(f"Google Books has no results for {isbn13}")
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

        result = {
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
        logger.debug(
            f"Google Books returned data for {isbn13}: has_cover={bool(thumbnail_url)}"
        )
        return result
    except Exception as e:
        logger.debug(f"Google Books lookup failed for {isbn13}: {e}")
        return None


def _lookup_itunes(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Helper to lookup book details via iTunes Search API."""
    session = _get_session()
    url = "https://itunes.apple.com/search"
    params = {"term": isbn13, "media": "ebook", "limit": "1"}
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
    base: Optional[Dict[str, Optional[Any]]],
    overlay: Dict[str, Optional[Any]],
) -> Dict[str, Optional[Any]]:
    """Merge two metadata dicts, filling in missing fields from overlay.

    The base dict takes priority for non-empty fields. Overlay fills gaps.
    """
    if base is None:
        return dict(overlay)

    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if existing is None or (isinstance(existing, str) and not existing.strip()):
            if value is not None and (not isinstance(value, str) or value.strip()):
                merged[key] = value
    return merged


def lookup_book_by_isbn13(isbn13: str) -> Optional[Dict[str, Optional[Any]]]:
    """Lookup a book by ISBN-13 using cached data or fallback APIs.

    Optimised lookup chain:
      1. Cache
      2. Open Library (ISBN)
      3. Google Books (ISBN)
      4. Open Library direct cover
      5. Penguin Random House cover
      6. Amazon cover (HEAD check, no full download)
      7. Open Library search by title+author (finds covers from other editions)
      8. iTunes (ISBN search)

    Metadata from all sources is merged — the first source to provide a
    value for a field wins. Cover-only sources augment existing metadata.

    Returns a dict with keys: title, author, publish_date, thumbnail_url,
    cover_url, etc., or None if absolutely nothing was found.
    """
    clean_isbn = normalize_isbn(isbn13)
    logger.debug(f"Deep lookup for ISBN {clean_isbn}")

    # 0. Check Cache
    cache = get_cache()
    cached_data = cache.get(f"isbn:{clean_isbn}")
    if cached_data is not None:
        logger.debug(f"  Cache hit for {clean_isbn}")
        return cast(Dict[str, Optional[Any]], cached_data)

    best: Optional[Dict[str, Optional[Any]]] = None

    # 1. Open Library (ISBN) — primary metadata source
    logger.debug("  Trying Open Library...")
    ol_result = _lookup_open_library(clean_isbn)
    if ol_result:
        best = _merge_metadata(best, ol_result)
        if best.get("thumbnail_url"):
            logger.debug("  Found cover in Open Library")
            cache.set(f"isbn:{clean_isbn}", best)
            return best

    # 2. Google Books — often has covers when OL doesn't
    logger.debug("  Trying Google Books...")
    gb_result = _lookup_google_books(clean_isbn)
    if gb_result:
        best = _merge_metadata(best, gb_result)
        if best.get("thumbnail_url"):
            logger.debug("  Found cover in Google Books")
            cache.set(f"isbn:{clean_isbn}", best)
            return best

    # 3. Open Library direct cover check
    logger.debug("  Trying Open Library direct cover...")
    ol_cover = _lookup_open_library_cover_direct(clean_isbn)
    if ol_cover:
        logger.debug("  Found cover in Open Library direct")
        if best is None:
            best = _empty_result()
        best["thumbnail_url"] = ol_cover
        best["cover_url"] = ol_cover.replace("-M.jpg", "-L.jpg")
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    # 4. Penguin Random House cover
    logger.debug("  Trying Penguin Random House cover...")
    prh_cover = _lookup_penguin_cover(clean_isbn)
    if prh_cover:
        logger.debug("  Found cover in Penguin Random House")
        if best is None:
            best = _empty_result()
        best["thumbnail_url"] = prh_cover
        best["cover_url"] = prh_cover
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    # 5. Amazon cover (uses HEAD to avoid downloading the full image)
    logger.debug("  Trying Amazon cover lookup...")
    amazon_cover = _lookup_amazon_cover(clean_isbn)
    if amazon_cover:
        logger.debug("  Found cover on Amazon")
        if best is None:
            best = _empty_result()
        best["thumbnail_url"] = amazon_cover
        best["cover_url"] = amazon_cover
        cache.set(f"isbn:{clean_isbn}", best)
        return best

    # 6. Open Library search by title+author — finds covers from OTHER editions
    #    This is the most important fallback. Many books exist on OL under a
    #    different ISBN edition that has a cover image attached. A search by
    #    title (and author when available) often succeeds where ISBN lookup fails.
    title = best.get("title") if best else None
    author = best.get("author") if best else None
    if title:
        logger.debug(f"  Trying Open Library search for '{title}' by '{author}'...")
        search_result = _lookup_open_library_search(title, author)
        if search_result and search_result.get("thumbnail_url"):
            logger.debug("  Found cover via Open Library search")
            best = _merge_metadata(best, search_result)
            cache.set(f"isbn:{clean_isbn}", best)
            return best

    # 7. iTunes Store — least likely to have covers but worth trying
    logger.debug("  Trying iTunes...")
    itunes_result = _lookup_itunes(clean_isbn)
    if itunes_result:
        best = _merge_metadata(best, itunes_result)
        if best and best.get("thumbnail_url"):
            logger.debug("  Found cover in iTunes")
            cache.set(f"isbn:{clean_isbn}", best)
            return best

    # If we have any metadata at all (even without a cover), cache it
    if best:
        cache.set(f"isbn:{clean_isbn}", best)
        logger.debug(f"  Cached metadata without cover for {clean_isbn}")
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
                deep_info = lookup_book_by_isbn13(isbn)
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
