"""Author and publisher detail routes."""

from flask import Blueprint, current_app, jsonify

from book_lamp.middleware.auth import authorisation_required
from book_lamp.services.book_lookup import lookup_books_by_author
from book_lamp.services.storage_factory import get_storage, is_test_mode
from book_lamp.utils.authors import matches
from book_lamp.utils.books import full_title, normalise_provider_title, split_title_parts
from book_lamp.utils.publishers import normalize_publisher, publisher_slug

authors_bp = Blueprint("authors", __name__)


def _title_key(title: object, subtitle: object = None) -> str:
    """A Book's whole title as it reads, for comparing a result with a stored Book.

    The stored title keeps the spelling the reader has; the comparison uses the
    same tidy form the author search returns, so "Dune." and "Dune" are one
    work and an owned Book does not reappear as unread over a full stop. The
    subtitle is part of that name, so two editions of different works under one
    main title do not collapse into one.
    """
    return (normalise_provider_title(full_title(str(title or ""), str(subtitle or ""))) or "").lower()


def _title_parts(title: object, subtitle: object) -> tuple[str, str]:
    """A result's main title and subtitle as storage would hold them.

    Storage keeps a title and its subtitle apart, but author lookup returns a
    provider's title untouched, so a result may still carry ``Foo: Bar`` as its
    title with no subtitle of its own. The split is taken before comparing, or
    the combined key would never equal the stored main title.
    """
    main, second = split_title_parts(str(title or ""), str(subtitle or ""))
    if second:
        # A provider may also leave the subtitle inside the title while giving
        # it separately; the stored pair repeats it once, never twice.
        head, tail = split_title_parts(main)
        if tail and tail.casefold() == second.casefold():
            main = head
    return _title_key(main), _title_key(second)


def _same_work(owned: dict, title: object, subtitle: object) -> bool:
    """Whether a search result names a work the reader already has.

    A title and its subtitle name one work, so two editions of different works
    under one main title stay apart. But a Book stored without a subtitle does
    not say which work it is either, and author lookup supplies whatever
    subtitle an edition carries: an owned ``Dune`` must not reappear as unread
    beside ``Dune`` / ``Book One of the Dune Chronicles``. An empty subtitle is
    therefore unknown, and only two non-empty subtitles that disagree make two
    works.
    """
    main_title, result_subtitle = _title_parts(title, subtitle)
    if not main_title:
        return False
    owned_main, owned_subtitle = _title_parts(owned.get("title"), owned.get("subtitle"))
    if owned_main != main_title:
        return False
    return not owned_subtitle or not result_subtitle or owned_subtitle == result_subtitle


@authors_bp.route("/api/author/<path:author_slug>", methods=["GET"])
@authorisation_required
def api_author_page(author_slug: str):
    """API endpoint for author detail and bibliographic catalog."""
    storage = get_storage()

    books = storage.get_all_books()
    rl_items = storage.get_reading_list()
    reading_list_book_ids = {item["book_id"] for item in rl_items}

    author_books = []
    display_author_name = author_slug.replace("-", " ").title()

    for book in books:
        for name in book.get("authors") or []:
            if matches(name, author_slug):
                author_books.append(book)
                display_author_name = name
                break

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
        return (year, (b.get("title") or "").lower(), (b.get("subtitle") or "").lower())

    read_books.sort(key=sort_key)
    reading_list_books.sort(key=sort_key)

    unread_books: list[dict] = []
    if not is_test_mode():
        try:
            external_books = lookup_books_by_author(display_author_name)
            owned_isbns = {
                b.get("isbn13", "").replace("-", "").replace(" ", "") for b in author_books if b.get("isbn13")
            }
            seen_external_titles: set[str] = set()

            for ext_book in external_books:
                isbn = (ext_book.get("isbn13") or "").replace("-", "").replace(" ", "")
                if isbn and isbn in owned_isbns:
                    continue
                if any(_same_work(book, ext_book.get("title"), ext_book.get("subtitle")) for book in author_books):
                    continue
                norm_title = _title_key(ext_book.get("title"), ext_book.get("subtitle"))
                if norm_title in seen_external_titles:
                    continue
                ext_book["is_owned"] = False
                ext_book["in_reading_list"] = False
                ext_book["id"] = None
                unread_books.append(ext_book)
                seen_external_titles.add(norm_title)
        except Exception:
            current_app.logger.warning(f"Failed to fetch external books for author: {display_author_name}")

    return jsonify(
        {
            "author_name": display_author_name,
            "read_books": read_books,
            "reading_list_books": reading_list_books,
            "unread_books": unread_books,
        }
    )


@authors_bp.route("/api/publisher/<path:publisher_slug_path>", methods=["GET"])
@authorisation_required
def api_publisher_page(publisher_slug_path: str):
    """API endpoint for publisher detail page."""
    storage = get_storage()
    books = storage.get_all_books()

    publisher_books = []
    display_publisher_name = publisher_slug_path.replace("-", " ").title()

    search_slug = publisher_slug_path.lower()

    for book in books:
        if book.get("publisher"):
            norm_pub = normalize_publisher(book["publisher"])
            if norm_pub and publisher_slug(norm_pub) == search_slug:
                publisher_books.append(book)
                display_publisher_name = norm_pub

    def sort_key(b):
        py = b.get("publication_year")
        try:
            year = int(py) if py else 0
        except (ValueError, TypeError):
            year = 0
        return (year, (b.get("title") or "").lower(), (b.get("subtitle") or "").lower())

    publisher_books.sort(key=sort_key)

    return jsonify(
        {
            "publisher_name": display_publisher_name,
            "books": publisher_books,
        }
    )
