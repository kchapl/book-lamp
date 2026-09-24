"""Books catalog management routes."""

import logging
from typing import Union

from flask import Blueprint, current_app, jsonify, request, session

from book_lamp.middleware.auth import authorisation_required
from book_lamp.middleware.csrf import csrf_protect
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.services.storage_factory import TEST_ISBN, _mock_storage_singleton, get_storage, is_test_mode
from book_lamp.utils import SORT_OPTIONS, is_valid_isbn13, parse_publication_year, sort_books
from book_lamp.utils.books import normalize_isbn

logger = logging.getLogger("book_lamp")
books_bp = Blueprint("books", __name__)


def _background_fetch_missing_data(job_id: str, user_id: int):
    """Background task: bulk fetch missing data (covers, metadata) for all books."""
    from book_lamp.services.book_lookup import enhance_books_batch

    try:
        storage: Union[MockStorage, PostgresStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = PostgresStorage(user_id=user_id)

        books = storage.get_all_books()
        logger.info(
            f"Background job {job_id}: checking {len(books)} books for missing data..."
        )

        updated_count = enhance_books_batch(books, force_refresh=True)

        items_to_update = [{"book": b, "record": None} for b in books]
        storage.bulk_import(items_to_update)

        result_msg = (
            f"Found and updated missing data for {updated_count} book(s)."
            if updated_count > 0
            else "No missing data found to update."
        )
        logger.info(f"Background job {job_id}: completed - {result_msg}")
        return result_msg
    except Exception:
        logger.exception(f"Background job {job_id} failed")
        raise


@books_bp.route("/api/books", methods=["GET"])
@authorisation_required
def api_list_books():
    """API endpoint for books list."""
    storage = get_storage()

    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    sort_by = request.args.get("sort", "reading_date")
    if sort_by not in SORT_OPTIONS:
        sort_by = "reading_date"

    books = sort_books(books, sort_by=sort_by, reading_records=all_records)

    latest_records: dict = {}
    for r in all_records:
        bid = r.get("book_id")
        if bid:
            if bid not in latest_records or r.get("start_date", "") >= latest_records[
                bid
            ].get("start_date", ""):
                latest_records[bid] = r

    for book in books:
        record = latest_records.get(book.get("id"))
        if record:
            book["latest_status"] = record.get("status")

    books = [
        b
        for b in books
        if b.get("latest_status") in ["In Progress", "Completed", "Abandoned"]
    ]

    status_filter = request.args.get("status")
    if status_filter:
        books = [b for b in books if b.get("latest_status") == status_filter]

    year_filter = request.args.get("year")
    if year_filter and year_filter.isdigit():
        filtered_books = []
        for b in books:
            record = latest_records.get(b.get("id"))
            if record and record.get("status") == "Completed":
                end_date = record.get("end_date")
                if end_date and end_date[:4] == year_filter:
                    filtered_books.append(b)
        books = filtered_books

    month_filter = request.args.get("month")
    if month_filter and month_filter.isdigit():
        month_idx = f"{int(month_filter):02d}"
        filtered_books = []
        for b in books:
            record = latest_records.get(b.get("id"))
            if record and record.get("status") == "Completed":
                end_date = record.get("end_date")
                if end_date and end_date[5:7] == month_idx:
                    filtered_books.append(b)
        books = filtered_books

    rating_filter = request.args.get("rating")
    if rating_filter and rating_filter.isdigit():
        filtered_books = []
        for b in books:
            record = latest_records.get(b.get("id"))
            if record and record.get("status") == "Completed":
                if str(record.get("rating")) == rating_filter:
                    filtered_books.append(b)
        books = filtered_books

    category_filter = request.args.get("category")
    if category_filter:
        filtered_books = []
        for b in books:
            bisac = b.get("bisac_category")
            if bisac and category_filter.lower() in str(bisac).lower():
                filtered_books.append(b)
        books = filtered_books

    all_categories = set()
    for b in storage.get_all_books():
        bisac = b.get("bisac_category")
        if bisac:
            top_level = str(bisac).split("/")[0].strip()
            all_categories.add(top_level)
    sorted_categories = sorted(list(all_categories))

    return jsonify(
        {
            "books": books,
            "sort": sort_by,
            "sort_options": {
                key: label for key, (label, _) in SORT_OPTIONS.items()
            },
            "filters": {
                "status": status_filter,
                "year": year_filter,
                "month": month_filter,
                "rating": rating_filter,
                "category": category_filter,
            },
            "categories": sorted_categories,
        }
    )


@books_bp.route("/api/books", methods=["POST"])
@csrf_protect
@authorisation_required
def api_create_book():
    """Create a new book from a JSON payload and add it to the reading list."""
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    isbn = normalize_isbn(str(data.get("isbn", "") or ""))
    title = str(data.get("title", "") or "").strip()
    author = str(data.get("author", "") or "").strip()

    if isbn:
        existing = storage.get_book_by_isbn(isbn)
        if existing:
            try:
                storage.add_to_reading_list(existing["id"])
            except Exception as exc:
                current_app.logger.warning(
                    f"api_create_book: reading-list add failed for existing book {existing['id']}: {exc}"
                )
            return jsonify(existing), 200

    if title and author:
        book_data = {
            "title": title,
            "author": author,
            "publisher": data.get("publisher"),
            "publish_date": data.get("publication_year"),
            "thumbnail_url": data.get("thumbnail_url"),
            "cover_url": data.get("cover_url"),
            "description": data.get("description"),
            "bisac_category": data.get("bisac_category"),
        }
    else:
        if not isbn:
            return jsonify({"error": "isbn is required"}), 400

        from book_lamp.services.book_lookup import lookup_book_by_isbn13

        if is_test_mode() and isbn == TEST_ISBN:
            book_data = {
                "title": "Test Book",
                "author": "Test Author",
                "publish_date": "2019-05-02",
                "thumbnail_url": "http://example.com/thumb.jpg",
            }
        else:
            try:
                book_data = lookup_book_by_isbn13(isbn)
            except Exception:
                current_app.logger.exception(f"api_create_book: ISBN lookup failed for {isbn}")
                return jsonify({"error": "ISBN lookup failed"}), 502

        if not book_data:
            return jsonify({"error": f"No book data found for ISBN {isbn}"}), 404

    title = str(book_data.get("title") or "")
    author = str(book_data.get("author") or "")

    if not title or not author:
        return (
            jsonify({"error": "Could not determine title or author for this ISBN"}),
            422,
        )

    publish_date = book_data.get("publish_date")
    year = parse_publication_year(str(publish_date) if publish_date else None)
    thumbnail_url = book_data.get("thumbnail_url")

    try:
        created = storage.add_book(
            isbn13=isbn,
            title=title[:300],
            author=author[:200],
            publication_year=year,
            thumbnail_url=(thumbnail_url[:500] if thumbnail_url else None),
            publisher=book_data.get("publisher"),
            description=book_data.get("description"),
            bisac_category=book_data.get("bisac_category"),
            language=book_data.get("language"),
            page_count=book_data.get("page_count"),
            physical_format=book_data.get("physical_format"),
            edition=book_data.get("edition"),
            cover_url=book_data.get("cover_url"),
        )
        current_app.logger.info(
            f"BOOK_CREATED (API): id={created['id']}, isbn={isbn}, title='{title}'"
        )
    except Exception as exc:
        current_app.logger.error(
            f"api_create_book: storage.add_book failed: {exc}", exc_info=True
        )
        return jsonify({"error": "Failed to create book"}), 500

    try:
        storage.add_to_reading_list(created["id"])
    except Exception as exc:
        current_app.logger.warning(
            f"api_create_book: add_to_reading_list failed for book {created['id']}: {exc}"
        )

    return jsonify(created), 201


@books_bp.route("/api/books/<int:book_id>", methods=["GET"])
@authorisation_required
def api_book_detail(book_id: int):
    """API endpoint for book detail."""
    storage = get_storage()
    book = storage.get_book_by_id(book_id)
    if not book:
        return jsonify({"error": "Book not found"}), 404

    all_records = storage.get_reading_records()
    book["reading_records"] = [r for r in all_records if r["book_id"] == book_id]
    book["reading_records"].sort(key=lambda r: r.get("start_date", ""), reverse=True)

    rl_items = storage.get_reading_list()
    is_planned = any(item["book_id"] == book_id for item in rl_items)
    book["is_planned"] = is_planned

    return jsonify(book)


@books_bp.route("/api/books/<int:book_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def api_update_book(book_id: int):
    """Update an existing book's details from a JSON payload."""
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    title = str(data.get("title", "") or "").strip()
    author = str(data.get("author", "") or "").strip()

    if not title or not author:
        return jsonify({"error": "title and author are required"}), 400

    isbn13 = str(data.get("isbn13", "") or "").strip().replace("-", "")
    if (
        isbn13
        and not is_valid_isbn13(isbn13)
        and not (is_test_mode() and isbn13 == TEST_ISBN)
    ):
        return jsonify({"error": "Invalid ISBN-13"}), 400

    publication_year = None
    year_str = str(data.get("publication_year", "") or "").strip()
    if year_str:
        try:
            publication_year = int(year_str)
        except ValueError:
            pass

    try:
        storage.update_book(
            book_id=book_id,
            isbn13=isbn13,
            title=title[:300],
            author=author[:200],
            publication_year=publication_year,
            thumbnail_url=(str(data.get("thumbnail_url", "") or "").strip() or None),
            publisher=(str(data.get("publisher", "") or "").strip() or None),
            description=(str(data.get("description", "") or "").strip() or None),
            series=(str(data.get("series", "") or "").strip() or None),
            bisac_category=(str(data.get("bisac_category", "") or "").strip() or None),
            cover_url=(str(data.get("cover_url", "") or "").strip() or None),
        )
        current_app.logger.info(f"BOOK_UPDATED (API): book_id={book_id}")
        return jsonify({"success": True})
    except Exception as exc:
        current_app.logger.error(f"api_update_book: failed for book_id={book_id}: {exc}")
        return jsonify({"error": "Failed to update book"}), 500


@books_bp.route("/api/books/<int:book_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def api_delete_book(book_id: int):
    """Delete a book by ID."""
    storage = get_storage()
    success = storage.delete_book(book_id)
    if not success:
        return jsonify({"error": "Book not found"}), 404
    current_app.logger.info(f"BOOK_DELETED (API): book_id={book_id}")
    return jsonify({"success": True})


@books_bp.route("/api/books/search", methods=["GET"])
@authorisation_required
def api_search_books():
    """Search books and return JSON results."""
    storage = get_storage()
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"books": [], "search_query": ""})

    try:
        books = storage.search(query)
        all_records = storage.get_reading_records()
        latest_records: dict = {}
        for r in all_records:
            bid = r.get("book_id")
            if bid:
                if bid not in latest_records or r.get(
                    "start_date", ""
                ) >= latest_records[bid].get("start_date", ""):
                    latest_records[bid] = r
        for book in books:
            record = latest_records.get(book.get("id"))
            if record:
                book["latest_status"] = record.get("status")
        books = [
            b
            for b in books
            if b.get("latest_status") in ["In Progress", "Completed", "Abandoned"]
        ]
        return jsonify({"books": books, "search_query": query})
    except Exception as exc:
        current_app.logger.error(f"api_search_books: search failed: {exc}")
        return jsonify({"error": "Search failed"}), 500


@books_bp.route("/api/books/lookup", methods=["GET"])
@authorisation_required
def api_lookup_isbn():
    """Look up a book by ISBN without storing it."""
    isbn = request.args.get("isbn", "").strip()
    if not isbn:
        return jsonify({"error": "isbn query parameter is required"}), 400

    if is_test_mode() and isbn == TEST_ISBN:
        return jsonify(
            {
                "title": "Test Book",
                "author": "Test Author",
                "isbn13": TEST_ISBN,
            }
        )

    from book_lamp.services.book_lookup import lookup_book_by_isbn13

    try:
        data = lookup_book_by_isbn13(isbn)
        return jsonify(data)
    except Exception as exc:
        current_app.logger.error(f"api_lookup_isbn: lookup failed for {isbn}: {exc}")
        return jsonify({"error": "Lookup failed"}), 502


@books_bp.route("/api/books/fetch-covers", methods=["POST"])
@authorisation_required
@csrf_protect
def api_fetch_missing_data():
    """Queue a background job to fetch missing covers and metadata."""
    job_queue = get_job_queue()
    job_id = job_queue.submit_job(
        "fetch_missing_data",
        _background_fetch_missing_data,
        session["user_id"],
    )
    return jsonify({"job_id": job_id})
