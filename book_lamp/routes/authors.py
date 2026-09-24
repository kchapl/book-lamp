"""Author and publisher detail routes."""

from flask import Blueprint, current_app, jsonify

from book_lamp.middleware.auth import authorisation_required
from book_lamp.services.book_lookup import lookup_books_by_author
from book_lamp.services.storage_factory import get_storage, is_test_mode
from book_lamp.utils.publishers import normalize_publisher

authors_bp = Blueprint("authors", __name__)


@authors_bp.route("/api/author/<path:author_slug>", methods=["GET"])
@authorisation_required
def api_author_page(author_slug: str):
    """API endpoint for author detail and bibliographic catalog."""
    storage = get_storage()

    books = storage.get_all_books()
    rl_items = storage.get_reading_list()
    reading_list_book_ids = {item["book_id"] for item in rl_items}

    def to_slug(name):
        return name.lower().replace(" ", "-").replace(".", "") if name else ""

    search_slug = author_slug.lower()

    author_books = []
    display_author_name = author_slug.replace("-", " ").title()

    for book in books:
        if book.get("authors"):
            for a in book["authors"]:
                if to_slug(a) == search_slug:
                    author_books.append(book)
                    display_author_name = a
                    break
        elif book.get("author"):
            if to_slug(book["author"]) == search_slug:
                author_books.append(book)
                display_author_name = book["author"]

    for book in author_books:
        book["is_owned"] = True
        book["in_reading_list"] = book["id"] in reading_list_book_ids

    read_books = [b for b in author_books if not b["in_reading_list"]]
    reading_list_books = [b for b in author_books if b["in_reading_list"]]

    def sort_key(b):
        py = b.get("publication_year")
        try:
            year = int(py) if py else 0
        except (ValueError, TypeError):
            year = 0
        return (year, (b.get("title") or "").lower())

    read_books.sort(key=sort_key)
    reading_list_books.sort(key=sort_key)

    unread_books: list[dict] = []
    if not is_test_mode():
        try:
            external_books = lookup_books_by_author(display_author_name)
            owned_isbns = {
                b.get("isbn13", "").replace("-", "").replace(" ", "")
                for b in author_books
                if b.get("isbn13")
            }
            owned_norm_titles = {
                b.get("title", "").strip().lower() for b in author_books
            }

            for ext_book in external_books:
                isbn = (ext_book.get("isbn13") or "").replace("-", "").replace(" ", "")
                norm_title = ext_book.get("title", "").strip().lower()
                if isbn and isbn in owned_isbns:
                    continue
                if norm_title in owned_norm_titles:
                    continue
                ext_book["is_owned"] = False
                ext_book["in_reading_list"] = False
                ext_book["id"] = None
                unread_books.append(ext_book)
                owned_norm_titles.add(norm_title)
        except Exception:
            current_app.logger.warning(
                f"Failed to fetch external books for author: {display_author_name}"
            )

    return jsonify(
        {
            "author_name": display_author_name,
            "read_books": read_books,
            "reading_list_books": reading_list_books,
            "unread_books": unread_books,
        }
    )


@authors_bp.route("/api/publisher/<path:publisher_slug>", methods=["GET"])
@authorisation_required
def api_publisher_page(publisher_slug: str):
    """API endpoint for publisher detail page."""
    storage = get_storage()
    books = storage.get_all_books()

    publisher_books = []
    display_publisher_name = publisher_slug.replace("-", " ").title()

    def to_slug(name):
        return name.lower().replace(" ", "-") if name else ""

    search_slug = publisher_slug.lower()

    for book in books:
        if book.get("publisher"):
            norm_pub = normalize_publisher(book["publisher"])
            if norm_pub and to_slug(norm_pub) == search_slug:
                publisher_books.append(book)
                display_publisher_name = norm_pub

    def sort_key(b):
        py = b.get("publication_year")
        try:
            year = int(py) if py else 0
        except (ValueError, TypeError):
            year = 0
        return (year, (b.get("title") or "").lower())

    publisher_books.sort(key=sort_key)

    return jsonify(
        {
            "publisher_name": display_publisher_name,
            "books": publisher_books,
        }
    )
