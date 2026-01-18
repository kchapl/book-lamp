import html
from typing import Dict, Optional

import requests

OPEN_LIBRARY_API = "https://openlibrary.org/api/books"


def lookup_book_by_isbn13(isbn13: str) -> Optional[Dict[str, Optional[str]]]:
    """Lookup a book by ISBN-13 using Open Library API.

    Returns a dict with keys: title, author, publish_date, thumbnail_url, or None if not found.
    """
    params = {
        "bibkeys": f"ISBN:{isbn13}",
        "format": "json",
        "jscmd": "data",
    }
    response = requests.get(OPEN_LIBRARY_API, params=params, timeout=10)
    response.raise_for_status()
    payload = response.json()
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
