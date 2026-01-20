import html
from typing import Dict, Optional

import requests

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"


def _lookup_open_library(isbn13: str) -> Optional[Dict[str, Optional[str]]]:
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

    data = payload[key]
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

    thumbnail_url = None
    cover = data.get("cover") or {}
    if isinstance(cover, dict):
        thumbnail_url = cover.get("medium") or cover.get("small") or cover.get("large")

    return {
        "title": html.unescape(title) if title else title,
        "author": html.unescape(author_name) if author_name else author_name,
        "publish_date": publish_date,
        "thumbnail_url": thumbnail_url,
        "publisher": (
            html.unescape(publisher_name) if publisher_name else publisher_name
        ),
        "description": html.unescape(description) if description else description,
    }


def _lookup_google_books(isbn13: str) -> Optional[Dict[str, Optional[str]]]:
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

        image_links = info.get("imageLinks", {})
        thumbnail_url = image_links.get("thumbnail") or image_links.get(
            "smallThumbnail"
        )

        # Ensure HTTPS
        if thumbnail_url and thumbnail_url.startswith("http://"):
            thumbnail_url = thumbnail_url.replace("http://", "https://", 1)

        return {
            "title": html.unescape(title) if title else title,
            "author": html.unescape(author_name) if author_name else author_name,
            "publish_date": publish_date,
            "thumbnail_url": thumbnail_url,
            "publisher": (html.unescape(publisher) if publisher else publisher),
            "description": html.unescape(description) if description else description,
        }
    except Exception:
        return None


def _lookup_itunes(isbn13: str) -> Optional[Dict[str, Optional[str]]]:
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
        thumbnail_url = item.get("artworkUrl100") or item.get("artworkUrl60")

        # Get high-res artwork if possible by replacing dimension in URL
        if thumbnail_url:
            thumbnail_url = thumbnail_url.replace("100x100bb", "600x600bb")

        return {
            "title": html.unescape(title) if title else title,
            "author": html.unescape(author_name) if author_name else author_name,
            "publish_date": publish_date,
            "thumbnail_url": thumbnail_url,
            "publisher": None,  # iTunes often doesn't give publisher easily in this endpoint
            "description": html.unescape(description) if description else description,
        }
    except Exception:
        return None


def lookup_book_by_isbn13(isbn13: str) -> Optional[Dict[str, Optional[str]]]:
    """Lookup a book by ISBN-13 using Open Library, then Google Books, then iTunes as fallback.

    Returns a dict with keys: title, author, publish_date, thumbnail_url, or None if not found.
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

    # If all failed (or had no covers), return the first non-None result in order of preference
    # to at least give metadata if possible.
    return ol_result or gb_result or itunes_result
