import calendar
import datetime
import logging
import os
import re
import secrets
from collections import Counter
from functools import wraps
from typing import Dict, List, Union, cast
from urllib.parse import urlparse

import click  # noqa: E402
from dotenv import load_dotenv
from flask import (  # noqa: E402
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from book_lamp.services.book_lookup import lookup_books_by_author
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.llm_client import LLMClient
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.utils import (
    SORT_OPTIONS,
    is_valid_isbn13,
    parse_bisac_category,
    parse_publication_year,
    sort_books,
)
from book_lamp.utils.libib_import import parse_libib_csv


def get_safe_redirect_target(fallback_endpoint: str) -> str:
    """
    Return a safe redirect target derived from the request referrer.

    If the referrer is an absolute URL, only accept it if it points to the
    same host as the current request. Otherwise, or if no referrer is set,
    fall back to the URL for the given endpoint.
    """
    referrer = request.referrer
    if referrer:
        # Normalize backslashes, which some browsers treat like forward slashes
        normalized = referrer.replace("\\", "/")
        parsed = urlparse(normalized)
        # Accept relative URLs (no scheme and no netloc)
        if not parsed.scheme and not parsed.netloc:
            return normalized
        # Accept absolute URLs that point to this host using http/https
        if parsed.scheme in ("http", "https") and parsed.netloc == request.host:
            return normalized
    return url_for(fallback_endpoint)


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
logging.getLogger("book_lamp").setLevel(logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.WARNING)
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.WARNING)

app = Flask(__name__)

# Test mode configuration

# The value of TEST_MODE is read from the environment every time we need
# it instead of being cached at import time.  During test collection the
# module is imported before the `app` fixture in `conftest.py` has a
# chance to set `os.environ["TEST_MODE"] = "1"`, which caused several
# tests to behave as if they were running in production.  Using a helper
# function avoids that race entirely.
TEST_ISBN = "9780000000000"


def is_test_mode() -> bool:
    """Return True when the application is running under the test harness.

    The environment variable is used throughout the codebase; previously
    a module‑level constant read it once at import time.  That made tests
    unreliable when the variable was changed after import.
    """
    return os.environ.get("TEST_MODE", "0") == "1"


def generate_csrf_token() -> str:
    """Generate or retrieve a CSRF token for the current session."""
    if "csrf_token" not in session:
        token = secrets.token_hex(32)
        session["csrf_token"] = token
    else:
        token = session["csrf_token"]
    # Store in g for after_request hook
    g.csrf_token = token
    return token


def csrf_protect(f):
    """Decorator to protect routes from CSRF attacks."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Skip CSRF check in test mode or if session doesn't exist yet
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            # Skip CSRF check for test mode (testing infrastructure handles it)
            # Also skip if there's no user_id in session (not authenticated anyway)
            if is_test_mode() or not session.get("user_id"):
                return f(*args, **kwargs)

            # Verify the CSRF token
            submitted_token = request.headers.get("X-CSRF-Token") or request.form.get(
                "csrf_token"
            )
            session_token = session.get("csrf_token")
            if not session_token or submitted_token != session_token:
                app.logger.warning(
                    f"CSRF validation failed for {request.endpoint}: "
                    f"submitted={submitted_token[:8] if submitted_token else 'None'}, "
                    f"session={session_token[:8] if session_token else 'None'}"
                )
                return jsonify({"error": "CSRF token validation failed"}), 403
        return f(*args, **kwargs)

    return decorated_function


# Global singleton for test mode only
_mock_storage_singleton = MockStorage()


def get_storage():
    """Get the appropriate storage backend for the current request context."""
    if is_test_mode():
        # Authorise storage for Lighthouse CI and other automated testing
        _mock_storage_singleton.set_authorised(True)
        return _mock_storage_singleton

    user_id = session.get("user_id")
    if user_id:
        from book_lamp.services.pg_storage import PostgresStorage

        return PostgresStorage(user_id=user_id)

    # Authentication is required - no bypass allowed (except in test mode)
    # Return a storage that will always fail authorization checks
    from book_lamp.services.mock_storage import MockStorage

    unauthed = MockStorage()
    unauthed.set_authorised(False)
    app.logger.warning("Unauthenticated access attempted - no bypass allowed")
    return unauthed


def get_llm_client() -> LLMClient:
    """Return a per-request LLMClient singleton (cheap to construct)."""
    if "llm_client" not in g:
        g.llm_client = LLMClient()
    return cast(LLMClient, g.llm_client)


def authorisation_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app.logger.info(f"AUTHORISATION_CHECK for route: {f.__name__}")

        # Always require valid user_id in session (except in test mode)
        user_id = session.get("user_id")
        if not user_id and not is_test_mode():
            app.logger.warning(
                f"Authorization failed for {f.__name__}: no user_id in session"
            )
            return redirect(url_for("unauthorised"))

        if not get_storage().is_authorised():
            app.logger.warning(
                f"Authorization failed for {f.__name__}: storage not authorised"
            )
            return redirect(url_for("unauthorised"))
        return f(*args, **kwargs)

    return decorated_function


def get_app_version():
    """Get the application version based on environment."""
    # Check for common deployment commit hash environment variables
    for env_var in ["RENDER_GIT_COMMIT", "GIT_COMMIT", "HEROKU_SLUG_COMMIT"]:
        val = os.environ.get(env_var)
        if val:
            return val[:7]

    # Default version
    return "dev"


APP_VERSION = get_app_version()

# Warn early so the operator sees it in the server log without needing to hit a route.
if not os.environ.get("LLM_API_KEY"):
    logging.getLogger(__name__).warning(
        "LLM_API_KEY is not set — AI recommendations will be unavailable. "
        "Add LLM_API_KEY, LLM_BASE_URL, and LLM_MODEL to your .env file to enable this feature."
    )


@app.context_processor
def inject_global_vars():
    """Inject variables into all templates."""
    # Only check storage auth if user_id exists in session
    user_id = session.get("user_id")
    if user_id:
        is_auth = get_storage().is_authorised()
    else:
        is_auth = False
    user_name = session.get("user_name")

    return {
        "is_authorised": is_auth,
        "user_name": user_name,
        "current_year": datetime.datetime.now().year,
        "app_version": getattr(app, "app_version", APP_VERSION),
    }


def _normalize_publisher(name: str) -> str:
    if not name:
        return ""
    # Remove common corporate suffixes
    suffixes = [
        r"\bbooks\b",
        r"\blimited\b",
        r"\bltd\.?\b",
        r"\binc\.?\b",
        r"\bllc\b",
        r"\bpublishers?\b",
        r"\bpublishing\b",
        r"\bpress\b",
        r"\bgroup\b",
        r"\bcompany\b",
        r"\bco\.?\b",
    ]
    pattern = re.compile("|".join(suffixes), flags=re.IGNORECASE)
    cleaned = pattern.sub("", name)
    cleaned = re.sub(r"[,.;:]", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return name.strip()
    return cleaned


@app.template_filter("normalize_pub")
def normalize_pub_filter(s):
    return _normalize_publisher(s)


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Get the status of a background job."""
    job_queue = get_job_queue()
    job = job_queue.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job.to_dict())


@app.route("/api/settings", methods=["POST"])
@authorisation_required
@csrf_protect
def update_settings():
    """Update user settings."""
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    storage = get_storage()
    for key, value in data.items():
        if key == "theme" and value not in ["light", "dark", "system"]:
            continue
        storage.update_setting(key, str(value))

    return jsonify({"success": True})


@app.route("/api/auth/google", methods=["POST"])
def google_one_tap_login():
    """Verify a Google One Tap credential JWT and create a session."""
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token

    # Note: We allow this in test mode so we can test the logic with mocks.
    # The real Google verify will be mocked in tests.

    data = request.get_json(silent=True) or {}
    credential = data.get("credential")
    if not credential:
        return jsonify({"error": "Missing credential"}), 400

    try:
        id_info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            app.config["GOOGLE_CLIENT_ID"],
        )
        email = id_info["email"]
        name = id_info.get("name", "")

        from book_lamp.services.pg_storage import PostgresStorage

        user_id = PostgresStorage.upsert_user(email=email, name=name)

        # Regenerate session to prevent session fixation attacks
        session.clear()
        session["user_id"] = user_id
        session["user_email"] = email
        session["csrf_token"] = secrets.token_hex(32)

        app.logger.info(f"Authentication successful for user: {email}")

        return jsonify({"ok": True})
    except ValueError as e:
        app.logger.exception(f"One Tap credential verification failed: {e}")
        app.logger.warning(f"Authentication failure: {e}")
        return jsonify({"error": "Invalid credential"}), 401


@app.route("/api/sync/diagnostics", methods=["GET"])
@authorisation_required
def sync_diagnostics():
    """Return sync diagnostics (legacy, now disabled)."""
    return jsonify({"enabled": False, "message": "Async SQLite storage is disabled"})


# -----------------------------
# AI Recommendations
# -----------------------------


@app.route("/api/recommendations", methods=["GET"])
@authorisation_required
def api_recommendations():
    """Return (possibly cached) AI book recommendations as JSON.

    The frontend calls this asynchronously after the dashboard has loaded.
    Fresh recommendations are generated from recently highly-rated books;
    results are cached in the Recommendations sheet for up to 7 days.
    """
    from book_lamp.services.recommendations import get_or_refresh_recommendations

    storage = get_storage()
    llm = get_llm_client()

    if not llm.client:
        return (
            jsonify({"recommendations": [], "error": "LLM_API_KEY not configured"}),
            200,
        )

    try:
        recs = get_or_refresh_recommendations(storage, llm)
        return jsonify({"recommendations": recs})
    except Exception:
        app.logger.exception("Failed to generate recommendations")
        return (
            jsonify(
                {"recommendations": [], "error": "Failed to generate recommendations"}
            ),
            200,
        )


@app.route("/")
def home():
    """Home page - public and shows sign-in or dashboard based on authentication."""
    # Only check session for auth state - don't call get_storage() for non-authenticated users
    user_id = session.get("user_id")
    is_authorised = user_id is not None
    return render_template("home.html", is_authorised=is_authorised)


@app.route("/about")
def about():
    """Public about page - no authentication required."""
    return render_template("about.html", version=APP_VERSION)


@app.route("/unauthorised")
def unauthorised():
    return render_template("unauthorised.html"), 401


@app.route("/logout")
def logout():
    # Clear session completely to prevent session reuse
    session.clear()
    # Ensure the session cookie is marked for removal
    session.permanent = False
    flash("Successfully signed out.", "info")
    return redirect(url_for("home"))


@app.route("/connect")
def connect():
    """Redirect to home page which displays the Google sign-in UI."""
    # The home page will show the Google sign-in flow when not authenticated.
    # If already authenticated, redirect to books.
    if session.get("user_id"):
        return redirect(url_for("list_books"))
    return redirect(url_for("home"))


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.png")


# -----------------------------
# JSON API routes for mutating actions (used by the React SPA)
# Each route delegates to the same storage calls as the legacy form-based
# routes but returns JSON instead of redirecting to an HTML template.
# -----------------------------


@app.route("/api/books", methods=["POST"])
@authorisation_required
@csrf_protect
def api_create_book():
    """Create a new book from a JSON payload and add it to the reading list.

    The client must supply at least an ``isbn`` field. If ``title`` and
    ``author`` are also present the book is stored directly (manual entry).
    Otherwise the ISBN is resolved via the Open Library / Google Books APIs.

    Returns:
        JSON representation of the newly created book, with HTTP 201.
    """
    from book_lamp.utils.books import normalize_isbn

    storage = get_storage()
    data = request.get_json(silent=True) or {}

    isbn = normalize_isbn(str(data.get("isbn", "") or ""))
    title = str(data.get("title", "") or "").strip()
    author = str(data.get("author", "") or "").strip()

    # Deduplicate: if book already exists, add it to the reading list.
    if isbn:
        existing = storage.get_book_by_isbn(isbn)
        if existing:
            try:
                storage.add_to_reading_list(existing["id"])
            except Exception as exc:
                app.logger.warning(
                    f"api_create_book: reading-list add failed for existing book {existing['id']}: {exc}"
                )
            return jsonify(existing), 200

    if title and author:
        # Manual entry: store immediately without external lookup.
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
        # Lookup via Open Library / Google Books.
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
                app.logger.exception(
                    f"api_create_book: ISBN lookup failed for {isbn}"
                )
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
        app.logger.info(
            f"BOOK_CREATED (API): id={created['id']}, isbn={isbn}, title='{title}'"
        )
    except Exception as exc:
        app.logger.error(
            f"api_create_book: storage.add_book failed: {exc}", exc_info=True
        )
        return jsonify({"error": "Failed to create book"}), 500

    try:
        storage.add_to_reading_list(created["id"])
    except Exception as exc:
        app.logger.warning(
            f"api_create_book: add_to_reading_list failed for book {created['id']}: {exc}"
        )

    return jsonify(created), 201


@app.route("/api/books/<int:book_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def api_update_book(book_id: int):
    """Update an existing book's details from a JSON payload.

    Returns:
        JSON ``{"success": True}`` on success, or an error object.
    """
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
        app.logger.info(f"BOOK_UPDATED (API): book_id={book_id}")
        return jsonify({"success": True})
    except Exception as exc:
        app.logger.error(f"api_update_book: failed for book_id={book_id}: {exc}")
        return jsonify({"error": "Failed to update book"}), 500


@app.route("/api/books/<int:book_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def api_delete_book(book_id: int):
    """Delete a book by ID.

    Returns:
        JSON ``{"success": True}`` on success, HTTP 404 if not found.
    """
    storage = get_storage()
    success = storage.delete_book(book_id)
    if not success:
        return jsonify({"error": "Book not found"}), 404
    app.logger.info(f"BOOK_DELETED (API): book_id={book_id}")
    return jsonify({"success": True})


@app.route("/api/books/search", methods=["GET"])
@authorisation_required
def api_search_books():
    """Search books and return JSON results.

    Returns:
        JSON with ``books`` list and ``search_query`` string.
    """
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
        app.logger.error(f"api_search_books: search failed: {exc}")
        return jsonify({"error": "Search failed"}), 500


@app.route("/api/books/lookup", methods=["GET"])
@authorisation_required
def api_lookup_isbn():
    """Look up a book by ISBN without storing it.

    Returns:
        JSON book data, or ``null`` if not found.
    """
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
        app.logger.error(f"api_lookup_isbn: lookup failed for {isbn}: {exc}")
        return jsonify({"error": "Lookup failed"}), 502


@app.route("/api/books/<int:book_id>/reading-records", methods=["POST"])
@authorisation_required
@csrf_protect
def api_create_reading_record(book_id: int):
    """Create a reading record for a book from a JSON payload.

    Returns:
        JSON representation of the new reading record, with HTTP 201.
    """
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    status = str(data.get("status", "") or "").strip()
    start_date = str(data.get("start_date", "") or "").strip()
    end_date = str(data.get("end_date", "") or "").strip() or None
    rating_raw = data.get("rating", 0)
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 0

    if not status or not start_date:
        return jsonify({"error": "status and start_date are required"}), 400

    try:
        record = storage.add_reading_record(
            book_id=book_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        app.logger.info(f"RECORD_CREATED (API): book_id={book_id}, status='{status}'")
        return jsonify(record), 201
    except Exception:
        app.logger.exception(
            f"api_create_reading_record: failed for book_id={book_id}"
        )
        return jsonify({"error": "Failed to create reading record"}), 500


@app.route("/api/reading-records/<int:record_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def api_update_reading_record(record_id: int):
    """Update a reading record from a JSON payload.

    Returns:
        JSON ``{"success": True}`` on success.
    """
    storage = get_storage()
    data = request.get_json(silent=True) or {}

    status = str(data.get("status", "") or "").strip()
    start_date = str(data.get("start_date", "") or "").strip()
    end_date = str(data.get("end_date", "") or "").strip() or None
    rating_raw = data.get("rating", 0)
    try:
        rating = int(rating_raw)
    except (TypeError, ValueError):
        rating = 0

    if not status or not start_date:
        return jsonify({"error": "status and start_date are required"}), 400

    try:
        storage.update_reading_record(
            record_id=record_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        app.logger.info(
            f"RECORD_UPDATED (API): record_id={record_id}, status='{status}'"
        )
        return jsonify({"success": True})
    except Exception:
        app.logger.exception(
            f"api_update_reading_record: failed for record_id={record_id}"
        )
        return jsonify({"error": "Failed to update reading record"}), 500


@app.route("/api/reading-records/<int:record_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def api_delete_reading_record(record_id: int):
    """Delete a reading record by ID.

    Returns:
        JSON ``{"success": True}`` on success, HTTP 404 if not found.
    """
    storage = get_storage()
    try:
        success = storage.delete_reading_record(record_id)
        if not success:
            return jsonify({"error": "Reading record not found"}), 404
        app.logger.info(f"RECORD_DELETED (API): record_id={record_id}")
        return jsonify({"success": True})
    except Exception as exc:
        app.logger.error(
            f"api_delete_reading_record: failed for record_id={record_id}: {exc}",
            exc_info=True,
        )
        return jsonify({"error": "Failed to delete reading record"}), 500


@app.route("/api/reading-list/reorder", methods=["POST"])
@authorisation_required
@csrf_protect
def api_reorder_reading_list():
    """Reorder the reading list from a JSON payload.

    Returns:
        JSON ``{"success": True}``.
    """
    storage = get_storage()
    data = request.get_json(silent=True) or {}
    book_ids = data.get("book_ids", [])
    storage.update_reading_list_order(book_ids)
    return jsonify({"success": True})


@app.route("/api/reading-list/remove/<int:book_id>", methods=["POST"])
@authorisation_required
@csrf_protect
def api_remove_from_reading_list(book_id: int):
    """Remove a book from the reading list and return JSON.

    Returns:
        JSON ``{"success": True}``.
    """
    storage = get_storage()
    storage.remove_from_reading_list(book_id)
    return jsonify({"success": True})


@app.route("/api/books/<int:book_id>/start-reading", methods=["POST"])
@authorisation_required
@csrf_protect
def api_start_reading(book_id: int):
    """Move a book from the reading list to the reading log.

    Returns:
        JSON ``{"success": True}`` on success.
    """
    storage = get_storage()
    try:
        storage.start_reading(book_id)
        app.logger.info(
            f"START_READING (API): book_id={book_id}, new_status='In Progress'"
        )
        return jsonify({"success": True})
    except Exception:
        app.logger.exception(
            f"api_start_reading: failed for book_id={book_id}"
        )
        return jsonify({"error": "Failed to start reading."}), 500


@app.route("/api/books/<int:book_id>/add-to-reading-list", methods=["POST"])
@authorisation_required
@csrf_protect
def api_add_to_reading_list(book_id: int):
    """Add an existing book to the reading list and return JSON.

    Returns:
        JSON ``{"success": True}`` on success.
    """
    storage = get_storage()
    try:
        storage.add_to_reading_list(book_id)
        app.logger.info(f"READING_LIST_ADD (API): book_id={book_id}")
        return jsonify({"success": True})
    except Exception:
        app.logger.exception(
            f"api_add_to_reading_list: failed for book_id={book_id}"
        )
        return jsonify({"error": "Failed to add to reading list."}), 500


@app.route("/api/books/fetch-covers", methods=["POST"])
@authorisation_required
@csrf_protect
def api_fetch_missing_data():
    """Queue a background job to fetch missing covers and metadata.

    Returns:
        JSON with ``job_id`` of the queued background job.
    """
    job_queue = get_job_queue()
    job_id = job_queue.submit_job(
        "fetch_missing_data",
        _background_fetch_missing_data,
        session["user_id"],
    )
    return jsonify({"job_id": job_id})


@app.route("/<path:fallback>")
def spa_fallback(fallback):
    """Catch-all for SPA routing - serve index.html for non-API routes."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "Not found"}), 404
    return render_template("index.html")


# Secret key for session management
secret_key = os.environ.get("SECRET_KEY")
if not secret_key and not is_test_mode():
    raise ValueError(
        "SECRET_KEY environment variable is required. "
        "Please set it in your .env file. "
        'Generate a secure key with: python -c "import secrets; print(secrets.token_hex(32))"'
    )
elif not secret_key:
    # Only use for test mode - still warn operators
    secret_key = "test-only-insecure-key-do-not-use-in-production"
    logging.getLogger(__name__).warning(
        "SECRET_KEY not set - using insecure default for TEST MODE ONLY. "
        "This is acceptable for automated testing but NOT for production."
    )

app.config["SECRET_KEY"] = secret_key

# Session cookie security settings
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SECURE"] = not is_test_mode()  # Enable Secure in production
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# Google OAuth configuration (One Tap only needs Client ID)
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")

# Validate OAuth configuration (skip in test mode)
if not is_test_mode():
    if not app.config["GOOGLE_CLIENT_ID"]:
        raise ValueError(
            "GOOGLE_CLIENT_ID environment variable is required. "
            "Please set it in your .env file. "
            "Get credentials from https://console.cloud.google.com/"
        )

    # Authentication is required - Google One Tap is the authentication method
    app.logger.info("Authentication required: Google One Tap authentication is enabled")


@app.after_request
def add_csrf_token_header(response):
    """Add CSRF token to response headers for AJAX requests."""
    if "csrf_token" in g:
        response.headers["X-CSRF-Token"] = g.csrf_token
    return response


@app.context_processor
def inject_csrf_token():
    """Inject CSRF token into all templates."""
    return {"csrf_token": generate_csrf_token()}


@app.cli.command("backfill-bisac")
def backfill_bisac_command():
    """Enhance existing books with BISAC categories."""
    if is_test_mode():
        click.echo("Running in test mode with mock storage.")

    from book_lamp.services.book_lookup import enhance_books_batch

    storage = get_storage()
    books = storage.get_all_books()

    click.echo(f"Starting BISAC backfill for {len(books)} books...")
    updated = enhance_books_batch(books)

    # Persist updates
    for book in books:
        if book.get("bisac_category"):
            storage.update_book(
                book_id=book["id"],
                isbn13=book["isbn13"],
                title=book["title"],
                author=book["author"],
                bisac_category=book["bisac_category"],
            )

    click.echo(f"Finished backfill. Updated {updated} books.")


# -----------------------------
# Reading History feature
# -----------------------------


@app.route("/history", methods=["GET"])
@authorisation_required
def reading_history():
    """Show detailed reading history as a chronological list of individual events."""
    storage = get_storage()

    history = storage.get_reading_history()
    # Get status list for filter dropdown (from all records)
    all_statuses = sorted(
        list(set(r.get("status") for r in history if r.get("status")))
    )

    # Filtering
    status_filter = request.args.get("status")
    if status_filter:
        history = [r for r in history if r.get("status") == status_filter]

    min_rating = request.args.get("min_rating")
    if min_rating and min_rating.isdigit():
        min_rating = int(min_rating)
        history = [r for r in history if r.get("rating", 0) >= min_rating]

    year_filter = request.args.get("year")
    if year_filter and year_filter.isdigit():
        history = [
            r
            for r in history
            if (r.get("end_date") and r.get("end_date")[:4] == year_filter)
            or (
                not r.get("end_date")
                and r.get("start_date")
                and r.get("start_date")[:4] == year_filter
            )
        ]

    # Sorting
    sort_by = request.args.get("sort", "date_desc")

    if sort_by == "date_desc":
        history.sort(
            key=lambda r: r.get("end_date") or r.get("start_date") or "", reverse=True
        )
    elif sort_by == "date_asc":
        history.sort(key=lambda r: r.get("end_date") or r.get("start_date") or "")
    elif sort_by == "rating_desc":
        history.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_by == "title":
        history.sort(key=lambda r: (r.get("book_title") or "").lower())

    return render_template(
        "history.html",
        history=history,
        statuses=all_statuses,
        current_status=status_filter,
        current_rating=min_rating,
        current_year=year_filter,
        current_sort=sort_by,
    )


@app.route("/api/history", methods=["GET"])
@authorisation_required
def api_reading_history():
    """API endpoint for reading history data."""
    storage = get_storage()

    history = storage.get_reading_history()
    all_statuses = sorted(
        list(set(r.get("status") for r in history if r.get("status")))
    )

    status_filter = request.args.get("status")
    if status_filter:
        history = [r for r in history if r.get("status") == status_filter]

    min_rating = request.args.get("min_rating")
    if min_rating and min_rating.isdigit():
        min_rating = int(min_rating)
        history = [r for r in history if r.get("rating", 0) >= min_rating]

    year_filter = request.args.get("year")
    if year_filter and year_filter.isdigit():
        history = [
            r
            for r in history
            if (r.get("end_date") and r.get("end_date")[:4] == year_filter)
            or (
                not r.get("end_date")
                and r.get("start_date")
                and r.get("start_date")[:4] == year_filter
            )
        ]

    sort_by = request.args.get("sort", "date_desc")

    if sort_by == "date_desc":
        history.sort(
            key=lambda r: r.get("end_date") or r.get("start_date") or "", reverse=True
        )
    elif sort_by == "date_asc":
        history.sort(key=lambda r: r.get("end_date") or r.get("start_date") or "")
    elif sort_by == "rating_desc":
        history.sort(key=lambda r: r.get("rating", 0), reverse=True)
    elif sort_by == "title":
        history.sort(key=lambda r: (r.get("book_title") or "").lower())

    return jsonify(
        {
            "history": history,
            "statuses": all_statuses,
            "filters": {
                "status": status_filter,
                "rating": min_rating,
                "year": year_filter,
                "sort": sort_by,
            },
        }
    )


# -----------------------------
# Books feature
# -----------------------------


@app.route("/books/new", methods=["GET"])
@authorisation_required
def new_book_form():
    isbn = request.args.get("isbn", "")
    show_manual = request.args.get("manual", "0") == "1"
    add_to_reading_list = request.args.get("add_to_reading_list", "0") == "1"
    return render_template(
        "add_book.html",
        isbn=isbn,
        show_manual=show_manual,
        add_to_reading_list=add_to_reading_list,
    )


@app.route("/reading-list", methods=["GET"])
@authorisation_required
def reading_list():
    storage = get_storage()

    rl_items = storage.get_reading_list()
    # Extract books directly from reading_list query (already joined with books table)
    books = []
    for item in rl_items:
        book = {
            "id": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "thumbnail_url": item.get("thumbnail_url"),
        }
        books.append(book)

    return render_template("reading_list.html", books=books)


@app.route("/api/reading-list", methods=["GET"])
@authorisation_required
def api_get_reading_list():
    """API endpoint to get reading list."""
    storage = get_storage()
    rl_items = storage.get_reading_list()
    books = []
    for item in rl_items:
        book = {
            "id": item["book_id"],
            "title": item["title"],
            "author": item["author"],
            "thumbnail_url": item.get("thumbnail_url"),
        }
        books.append(book)
    return jsonify({"books": books})


@app.route("/reading-list/reorder", methods=["POST"])
@authorisation_required
@csrf_protect
def reorder_reading_list():
    storage = get_storage()
    book_ids = request.json.get("book_ids", [])
    storage.update_reading_list_order(book_ids)
    return jsonify({"success": True})


@app.route("/reading-list/remove/<int:book_id>", methods=["POST"])
@authorisation_required
@csrf_protect
def remove_from_reading_list(book_id: int):
    storage = get_storage()
    storage.remove_from_reading_list(book_id)
    flash("Removed from reading list.", "success")
    return redirect(get_safe_redirect_target("reading_list"))


@app.route("/books/<int:book_id>/start-reading", methods=["POST"])
@authorisation_required
@csrf_protect
def start_reading(book_id: int):
    """Move book from reading list to reading log and set status to 'In Progress'."""
    app.logger.info(f"START_READING initiation: book_id={book_id}")
    storage = get_storage()
    try:
        storage.start_reading(book_id)
        flash("Started reading! Book moved to reading log.", "success")
        app.logger.info(
            f"START_READING success: book_id={book_id}, new_status='In Progress'"
        )
    except Exception as e:
        app.logger.error(f"START_READING failure: book_id={book_id}, error={str(e)}")
        flash(f"Error starting reading: {str(e)}", "error")
    return redirect(get_safe_redirect_target("reading_list"))


@app.route("/books/<int:book_id>/add-to-reading-list", methods=["POST"])
@authorisation_required
@csrf_protect
def add_existing_to_reading_list(book_id: int):
    storage = get_storage()
    try:
        storage.add_to_reading_list(book_id)
        app.logger.info(f"Successfully added book ID {book_id} to reading list")

        flash("Added to reading list.", "success")
    except Exception as e:
        app.logger.error(
            f"Failed to add book ID {book_id} to reading list: {str(e)}", exc_info=True
        )
        flash(f"Error adding to reading list: {str(e)}", "error")
    return redirect(url_for("reading_list"))


@app.route("/books", methods=["GET"])
@authorisation_required
def list_books():
    storage = get_storage()

    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    # Get sort parameter from query string (default to reading_date)
    sort_by = request.args.get("sort", "reading_date")
    if sort_by not in SORT_OPTIONS:
        sort_by = "reading_date"

    # Sort books using the selected method
    books = sort_books(books, sort_by=sort_by, reading_records=all_records)

    # Attach latest status
    latest_records = {}
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

    # Only show books that have a 'real' status (In Progress, Completed, Abandoned)
    books = [
        b
        for b in books
        if b.get("latest_status") in ["In Progress", "Completed", "Abandoned"]
    ]

    status_filter = request.args.get("status")
    if status_filter:
        books = [b for b in books if b.get("latest_status") == status_filter]

    # Filtering by year
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

    # Filtering by month
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

    month_name = None
    if month_filter and month_filter.isdigit():
        import calendar

        month_name = calendar.month_name[int(month_filter)]

    # Filtering by rating
    rating_filter = request.args.get("rating")
    if rating_filter and rating_filter.isdigit():
        filtered_books = []
        for b in books:
            record = latest_records.get(b.get("id"))
            if record and record.get("status") == "Completed":
                if str(record.get("rating")) == rating_filter:
                    filtered_books.append(b)
        books = filtered_books

    # Filtering by category
    category_filter = request.args.get("category")
    if category_filter:
        filtered_books = []
        for b in books:
            bisac = b.get("bisac_category")
            if bisac and category_filter.lower() in str(bisac).lower():
                filtered_books.append(b)
        books = filtered_books

    # Extract all top-level categories for the filter dropdown
    all_categories = set()
    for b in storage.get_all_books():
        bisac = b.get("bisac_category")
        if bisac:
            # Extract top-level (e.g., "Fiction" from "Fiction / Mystery")
            top_level = str(bisac).split("/")[0].strip()
            all_categories.add(top_level)
    sorted_categories = sorted(list(all_categories))

    return render_template(
        "books.html",
        books=books,
        sort_by=sort_by,
        sort_options=SORT_OPTIONS,
        current_year=year_filter,
        current_month=month_filter,
        current_month_name=month_name,
        current_category=category_filter,
        current_rating=rating_filter,
        current_status=status_filter,
        categories=sorted_categories,
    )


@app.route("/api/books", methods=["GET"])
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

    latest_records = {}
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

    # Apply filters
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
            "sort_options": SORT_OPTIONS,
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


@app.route("/books/search", methods=["GET"])
@authorisation_required
def search_books():
    storage = get_storage()
    query = request.args.get("q", "").strip()

    if not query:
        flash("Please enter a search query.", "info")
        return redirect(url_for("list_books"))

    # Get sort parameter from query string (default to relevance/score)
    sort_by = request.args.get("sort", "relevance")
    if sort_by not in SORT_OPTIONS and sort_by != "relevance":
        sort_by = "relevance"

    try:
        books = storage.search(query)
        all_records = storage.get_reading_records()

        # If not sorting by relevance, apply the selected sort
        if sort_by != "relevance":
            books = sort_books(books, sort_by=sort_by, reading_records=all_records)

        # Attach latest status
        latest_records = {}
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

        # Only show books that have a 'real' status (In Progress, Completed, Abandoned)
        books = [
            b
            for b in books
            if b.get("latest_status") in ["In Progress", "Completed", "Abandoned"]
        ]

        return render_template(
            "books.html",
            books=books,
            search_query=query,
            sort_by=sort_by,
            sort_options=SORT_OPTIONS,
        )
    except Exception as e:
        app.logger.error(f"Search failed: {str(e)}")
        flash(f"Search error: {str(e)}", "error")
        return redirect(url_for("list_books"))


@app.route("/author/<path:author_slug>", methods=["GET"])
@authorisation_required
def author_page(author_slug: str):
    """Display all books by an author, including unread books from Open Library.

    Books the user has read (their reading log) are shown normally. Books they
    plan to read in future are kept in the reading list. Unread titles sourced
    from Open Library are shown semi-transparently with an option to add them
    to the reading list.  Duplicates are suppressed and only the latest edition
    of each title is shown.
    """

    storage = get_storage()

    all_user_books = storage.get_all_books()
    rl_items = storage.get_reading_list()
    reading_list_book_ids = {item["book_id"] for item in rl_items}

    # 1. Identify the user's books for this author
    author_books: list[dict] = []
    display_author_name = author_slug.replace("-", " ").title()  # Fallback

    def to_slug(name: str) -> str:
        return name.lower().replace(" ", "-") if name else ""

    search_slug = author_slug.lower()

    for book in all_user_books:
        matched = False
        if book.get("authors"):
            for a in book["authors"]:
                if to_slug(a) == search_slug:
                    author_books.append(book)
                    display_author_name = a
                    matched = True
                    break

        if not matched and book.get("author"):
            if to_slug(book["author"]) == search_slug:
                author_books.append(book)
                display_author_name = book["author"]

    # Mark owned books and their reading list status
    for book in author_books:
        book["is_owned"] = True
        book["in_reading_list"] = book["id"] in reading_list_book_ids

    # Split into read and reading list books
    read_books = [b for b in author_books if not b["in_reading_list"]]
    reading_list_books = [b for b in author_books if b["in_reading_list"]]

    # Sort each category by publication year (oldest first) then title
    def sort_key(b):
        py = b.get("publication_year")
        try:
            year = int(py) if py else 0
        except (ValueError, TypeError):
            year = 0
        return (year, (b.get("title") or "").lower())

    read_books.sort(key=sort_key)
    reading_list_books.sort(key=sort_key)

    # 2. Fetch the full bibliography from Open Library (skipped in TEST_MODE)
    unread_books: list[dict] = []
    if not is_test_mode():

        try:
            external_books = lookup_books_by_author(display_author_name)
            # Build sets for dedup against already-owned books
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

                # Skip if user already owns a book with that ISBN or title
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
            app.logger.warning(
                f"Failed to fetch external books for author: {display_author_name}",
                exc_info=True,
            )

    return render_template(
        "author.html",
        author_name=display_author_name,
        read_books=read_books,
        reading_list_books=reading_list_books,
        unread_books=unread_books,
    )


@app.route("/api/author/<path:author_slug>", methods=["GET"])
@authorisation_required
def api_author_page(author_slug: str):
    """API endpoint for author page."""
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
            app.logger.warning(
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


@app.route("/api/publisher/<path:publisher_slug>", methods=["GET"])
@authorisation_required
def api_publisher_page(publisher_slug: str):
    """API endpoint for publisher page."""
    storage = get_storage()
    books = storage.get_all_books()

    publisher_books = []
    display_publisher_name = publisher_slug.replace("-", " ").title()

    def to_slug(name):
        return name.lower().replace(" ", "-") if name else ""

    search_slug = publisher_slug.lower()

    for book in books:
        if book.get("publisher"):
            norm_pub = _normalize_publisher(book["publisher"])
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


@app.route("/publisher/<path:publisher_slug>", methods=["GET"])
@authorisation_required
def publisher_page(publisher_slug: str):
    storage = get_storage()

    books = storage.get_all_books()

    publisher_books = []
    display_publisher_name = publisher_slug.replace("-", " ").title()  # Fallback

    def to_slug(name):
        return name.lower().replace(" ", "-") if name else ""

    search_slug = publisher_slug.lower()

    for book in books:
        if book.get("publisher"):
            norm_pub = _normalize_publisher(book["publisher"])
            if norm_pub and to_slug(norm_pub) == search_slug:
                publisher_books.append(book)
                display_publisher_name = norm_pub

    # Sort books by publication year (oldest first) then title
    def sort_key(b):
        py = b.get("publication_year")
        try:
            year = int(py) if py else 0
        except (ValueError, TypeError):
            year = 0
        return (year, (b.get("title") or "").lower())

    publisher_books.sort(key=sort_key)

    return render_template(
        "publisher.html",
        publisher_name=display_publisher_name,
        books=publisher_books,
    )


@app.route("/stats")
@authorisation_required
def stats_redirect():
    """Redirect old /stats route to /dashboard."""
    return redirect(url_for("collection_stats"), code=301)


@app.route("/dashboard", methods=["GET"])
@authorisation_required
def collection_stats():
    storage = get_storage()

    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    # Core metrics only consider completed books
    completed_records = [r for r in all_records if r.get("status") == "Completed"]
    completed_book_ids = {r.get("book_id") for r in completed_records}
    completed_books = [b for b in books if b.get("id") in completed_book_ids]

    total_books = len(completed_books)
    total_records = len(all_records)

    # Average rating - derived from all reading records with a rating > 0
    valid_ratings = []
    for r in all_records:
        rating_val = r.get("rating")
        try:
            if rating_val and int(rating_val) > 0:
                valid_ratings.append(int(rating_val))
        except (ValueError, TypeError):
            continue
    avg_rating = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0.0

    # Map book statuses from latest records
    # Create mapping of book_id to its most recent reading record
    latest_records = {}
    for r in all_records:
        bid = r.get("book_id")
        if bid:
            if bid not in latest_records or r.get("start_date", "") > latest_records[
                bid
            ].get("start_date", ""):
                latest_records[bid] = r

    # Status counts - only include 'In Progress', 'Completed', and 'Abandoned'
    allowed_statuses = {"In Progress", "Completed", "Abandoned"}
    statuses = []
    for b in books:
        bid = b.get("id")
        if bid in latest_records:
            status = latest_records[bid].get("status")
            if status in allowed_statuses:
                statuses.append(status)
    status_counts = Counter(statuses)

    # Rating Distribution (only from completed records)
    rating_counts = Counter()
    for r in all_records:
        if r.get("status") == "Completed":
            try:
                r_val = int(r.get("rating", 0))
                if 1 <= r_val <= 5:
                    rating_counts[r_val] += 1
            except (ValueError, TypeError):
                continue

    rating_distribution = [(stars, rating_counts[stars]) for stars in range(5, 0, -1)]

    # Top authors (only count books that have been completed)
    all_authors = []
    for b in completed_books:
        if b.get("authors"):
            all_authors.extend(b["authors"])
        elif b.get("author"):
            all_authors.append(b["author"])

    total_authors = len(set(all_authors))
    top_authors = sorted(Counter(all_authors).items(), key=lambda x: (-x[1], x[0]))[:5]

    # Top publishers (only count books that have been completed)
    all_publishers = []
    for b in completed_books:
        if b.get("publisher"):
            norm_pub = _normalize_publisher(b["publisher"])
            if norm_pub:
                all_publishers.append(norm_pub)
    top_publishers = sorted(
        Counter(all_publishers).items(), key=lambda x: (-x[1], x[0])
    )[:5]

    # Completed Books by Year and Month
    completed_records = [
        r for r in all_records if r.get("status") == "Completed" and r.get("end_date")
    ]

    # Yearly counts
    yearly_counts = Counter()
    for r in completed_records:
        date_val = r.get("end_date")
        if date_val:
            if isinstance(date_val, datetime.date):
                year = str(date_val.year)
            elif isinstance(date_val, str) and len(date_val) >= 4:
                year = date_val[:4]
            else:
                continue
            if year.isdigit():
                yearly_counts[year] += 1

    # Sort years numerically
    sorted_years = sorted(yearly_counts.items())
    max_year_count = max(yearly_counts.values()) if yearly_counts else 1
    avg_year_count = (
        sum(yearly_counts.values()) / len(yearly_counts) if yearly_counts else 0
    )

    # Monthly counts (seasonal distribution)
    monthly_counts = Counter()
    for r in completed_records:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            month_idx = date_str[5:7]
            if month_idx.isdigit():
                monthly_counts[month_idx] += 1

    # Map to month names and indices for linking
    ordered_months = []
    for i in range(1, 13):
        idx_str = f"{i:02d}"
        name = calendar.month_name[i][:3]
        ordered_months.append((i, name, monthly_counts[idx_str]))

    max_month_count = max(monthly_counts.values()) if monthly_counts else 1
    avg_month_count = sum(monthly_counts.values()) / 12

    # Category Distribution
    category_bins = Counter()
    for b in completed_books:
        bisac = b.get("bisac_category")
        if bisac:
            main_cat, _ = parse_bisac_category(bisac)
            if main_cat:
                # Normalize (e.g., 'Fiction' vs 'FICTION')
                norm_cat = main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                category_bins[norm_cat] += 1

    # Sort categories by count (descending)
    all_categories_sorted = sorted(category_bins.items(), key=lambda x: (-x[1], x[0]))

    # Limit to top 10 most common categories to keep the chart reasonable
    category_distribution = all_categories_sorted[:10]

    # Group others if there are many
    if len(all_categories_sorted) > 10:
        other_total = sum(count for label, count in all_categories_sorted[10:])
        category_distribution.append(("Other", other_total))

    max_category_count = (
        max(count for label, count in category_distribution)
        if category_distribution
        else 1
    )

    return render_template(
        "stats.html",
        total_books=total_books,
        total_authors=total_authors,
        total_records=total_records,
        avg_rating=avg_rating,
        status_counts=status_counts,
        rating_distribution=rating_distribution,
        top_authors=top_authors,
        top_publishers=top_publishers,
        category_distribution=category_distribution,
        max_category_count=max_category_count,
        yearly_counts=sorted_years,
        max_year_count=max_year_count,
        avg_year_count=avg_year_count,
        monthly_counts=ordered_months,
        max_month_count=max_month_count,
        avg_month_count=avg_month_count,
    )


@app.route("/api/stats", methods=["GET"])
@authorisation_required
def api_stats_redirect():
    """Redirect old /api/stats to /api/dashboard."""
    return redirect(url_for("api_collection_stats"), code=301)


@app.route("/api/dashboard", methods=["GET"])
@authorisation_required
def api_collection_stats():
    """API endpoint for collection statistics."""
    storage = get_storage()

    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    completed_records = [r for r in all_records if r.get("status") == "Completed"]
    completed_book_ids = {r.get("book_id") for r in completed_records}
    completed_books = [b for b in books if b.get("id") in completed_book_ids]

    total_books = len(completed_books)
    total_records = len(all_records)

    valid_ratings = []
    for r in all_records:
        rating_val = r.get("rating")
        try:
            if rating_val and int(rating_val) > 0:
                valid_ratings.append(int(rating_val))
        except (ValueError, TypeError):
            continue
    avg_rating = sum(valid_ratings) / len(valid_ratings) if valid_ratings else 0.0

    latest_records = {}
    for r in all_records:
        bid = r.get("book_id")
        if bid:
            if bid not in latest_records or r.get("start_date", "") > latest_records[
                bid
            ].get("start_date", ""):
                latest_records[bid] = r

    allowed_statuses = {"In Progress", "Completed", "Abandoned"}
    statuses = []
    for b in books:
        bid = b.get("id")
        if bid in latest_records:
            status = latest_records[bid].get("status")
            if status in allowed_statuses:
                statuses.append(status)
    status_counts = Counter(statuses)

    rating_counts = Counter()
    for r in all_records:
        if r.get("status") == "Completed":
            try:
                r_val = int(r.get("rating", 0))
                if 1 <= r_val <= 5:
                    rating_counts[r_val] += 1
            except (ValueError, TypeError):
                continue

    rating_distribution = [(stars, rating_counts[stars]) for stars in range(5, 0, -1)]

    all_authors = []
    for b in completed_books:
        if b.get("authors"):
            all_authors.extend(b["authors"])
        elif b.get("author"):
            all_authors.append(b["author"])

    total_authors = len(set(all_authors))
    top_authors = sorted(Counter(all_authors).items(), key=lambda x: (-x[1], x[0]))[:5]

    all_publishers = []
    for b in completed_books:
        if b.get("publisher"):
            norm_pub = _normalize_publisher(b["publisher"])
            if norm_pub:
                all_publishers.append(norm_pub)
    top_publishers = sorted(
        Counter(all_publishers).items(), key=lambda x: (-x[1], x[0])
    )[:5]

    completed_records_for_dates = [
        r for r in all_records if r.get("status") == "Completed" and r.get("end_date")
    ]

    yearly_counts = Counter()
    for r in completed_records_for_dates:
        date_val = r.get("end_date")
        if date_val:
            if isinstance(date_val, datetime.date):
                year = str(date_val.year)
            elif isinstance(date_val, str) and len(date_val) >= 4:
                year = date_val[:4]
            else:
                continue
            if year.isdigit():
                yearly_counts[year] += 1

    sorted_years = sorted(yearly_counts.items())
    max_year_count = max(yearly_counts.values()) if yearly_counts else 1

    monthly_counts = Counter()
    for r in completed_records_for_dates:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            month_idx = date_str[5:7]
            if month_idx.isdigit():
                monthly_counts[month_idx] += 1

    ordered_months = []
    for i in range(1, 13):
        idx_str = f"{i:02d}"
        name = calendar.month_name[i][:3]
        ordered_months.append(
            {"index": i, "name": name, "count": monthly_counts[idx_str]}
        )

    max_month_count = max(monthly_counts.values()) if monthly_counts else 1

    category_bins = Counter()
    for b in completed_books:
        bisac = b.get("bisac_category")
        if bisac:
            main_cat, _ = parse_bisac_category(bisac)
            if main_cat:
                norm_cat = main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                category_bins[norm_cat] += 1

    all_categories_sorted = sorted(category_bins.items(), key=lambda x: (-x[1], x[0]))
    category_distribution = all_categories_sorted[:10]
    if len(all_categories_sorted) > 10:
        other_total = sum(count for label, count in all_categories_sorted[10:])
        category_distribution.append(("Other", other_total))

    max_category_count = (
        max(count for label, count in category_distribution)
        if category_distribution
        else 1
    )

    # NEW: Page count statistics
    total_pages_read = 0
    for b in completed_books:
        page_count = b.get("page_count")
        if page_count:
            try:
                total_pages_read += int(page_count)
            except (ValueError, TypeError):
                pass

    avg_pages_per_book = (
        total_pages_read / total_books if total_books > 0 else 0
    )

    # NEW: Reading duration estimates (based on start/end dates)
    total_reading_days = 0
    for r in completed_records_for_dates:
        start = r.get("start_date")
        end = r.get("end_date")
        if start and end:
            try:
                if isinstance(start, datetime.date):
                    start_dt = start
                elif isinstance(start, str):
                    start_dt = datetime.date.fromisoformat(start[:10])
                else:
                    continue
                if isinstance(end, datetime.date):
                    end_dt = end
                elif isinstance(end, str):
                    end_dt = datetime.date.fromisoformat(end[:10])
                else:
                    continue
                days = (end_dt - start_dt).days
                if days >= 0:
                    total_reading_days += days
            except (ValueError, TypeError):
                pass

    avg_reading_time_days = (
        total_reading_days / len(completed_records_for_dates)
        if completed_records_for_dates
        else 0
    )

    # NEW: Reading streaks
    current_year = datetime.datetime.now().year
    current_streak = 0
    longest_streak = 0

    # Group completions by month
    completions_by_month: Dict[str, int] = {}
    for r in completed_records_for_dates:
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 7:
            year_month = date_str[:7]  # YYYY-MM
            completions_by_month[year_month] = completions_by_month.get(year_month, 0) + 1

    if completions_by_month:
        # Calculate current streak (consecutive months from current month going back)
        check_date = datetime.date(current_year, datetime.datetime.now().month, 1)
        while True:
            key = check_date.strftime("%Y-%m")
            if key in completions_by_month:
                current_streak += 1
                # Move to previous month
                if check_date.month == 1:
                    check_date = datetime.date(check_date.year - 1, 12, 1)
                else:
                    check_date = datetime.date(check_date.year, check_date.month - 1, 1)
            else:
                break

        # Calculate longest streak
        sorted_months = sorted(completions_by_month.keys())
        if sorted_months:
            streak = 1
            for i in range(1, len(sorted_months)):
                prev = datetime.date.fromisoformat(sorted_months[i - 1] + "-01")
                curr = datetime.date.fromisoformat(sorted_months[i] + "-01")
                # Check if consecutive months
                expected = prev.replace(month=prev.month + 1) if prev.month < 12 else datetime.date(prev.year + 1, 1, 1)
                if curr == expected:
                    streak += 1
                else:
                    longest_streak = max(longest_streak, streak)
                    streak = 1
            longest_streak = max(longest_streak, streak)

    # NEW: Year-over-year comparison
    current_year_str = str(current_year)
    previous_year_str = str(current_year - 1)
    books_this_year = yearly_counts.get(current_year_str, 0)
    books_last_year = yearly_counts.get(previous_year_str, 0)

    if books_last_year > 0:
        percentage_change = round(((books_this_year - books_last_year) / books_last_year) * 100, 1)
    else:
        percentage_change = 100.0 if books_this_year > 0 else 0.0

    year_comparison = {
        "current_year": books_this_year,
        "previous_year": books_last_year,
        "percentage_change": percentage_change,
    }

    # NEW: Reading pace (books per month)
    months_with_data = len(completions_by_month) if completions_by_month else 1
    reading_pace_monthly = round(total_books / months_with_data, 2) if months_with_data > 0 else 0
    reading_pace_annualised = round(reading_pace_monthly * 12, 1)

    # NEW: Format distribution
    format_bins = Counter()
    for b in completed_books:
        fmt = b.get("physical_format")
        if fmt:
            format_bins[fmt] += 1
    format_distribution = [
        {"label": label, "count": count}
        for label, count in sorted(format_bins.items(), key=lambda x: -x[1])
    ]

    # NEW: Language distribution
    language_bins = Counter()
    for b in completed_books:
        lang = b.get("language")
        if lang:
            language_bins[lang] += 1
    language_distribution = [
        {"label": label, "count": count}
        for label, count in sorted(language_bins.items(), key=lambda x: -x[1])
    ]

    # NEW: Top series
    series_bins: Dict[str, List[str]] = {}
    for b in completed_books:
        series = b.get("series")
        if series:
            if series not in series_bins:
                series_bins[series] = []
            title = b.get("title", "Unknown")
            if title not in series_bins[series]:
                series_bins[series].append(title)

    top_series = [
        {"name": name, "count": len(books), "books": books[:5]}
        for name, books in sorted(series_bins.items(), key=lambda x: -len(x[1]))[:5]
    ]

    # NEW: Category details with subcategories
    category_details_list = []
    for b in completed_books:
        bisac = b.get("bisac_category")
        if bisac:
            main_cat, sub_cat = parse_bisac_category(bisac)
            if main_cat:
                norm_cat = main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                # Find or create category entry
                existing = next((c for c in category_details_list if c["label"] == norm_cat), None)
                if not existing:
                    existing = {"label": norm_cat, "count": 0, "subcategories": Counter()}
                    category_details_list.append(existing)
                existing["count"] += 1
                if sub_cat:
                    existing["subcategories"][sub_cat] += 1

    category_details_list.sort(key=lambda x: -x["count"])
    category_details = [
        {
            "label": c["label"],
            "count": c["count"],
            "subcategories": [
                {"name": name, "count": count}
                for name, count in c["subcategories"].most_common(5)
            ],
        }
        for c in category_details_list[:10]
    ]

    # NEW: Yearly goal (from settings)
    yearly_goal = None
    try:
        settings = storage.get_settings()
        goal_str = settings.get("yearly_goal")
        if goal_str:
            yearly_goal = int(goal_str)
    except Exception:
        pass

    goal_progress_percent = 0.0
    if yearly_goal and yearly_goal > 0:
        goal_progress_percent = min(round((books_this_year / yearly_goal) * 100, 1), 100.0)

    return jsonify(
        {
            "total_books": total_books,
            "total_authors": total_authors,
            "total_records": total_records,
            "avg_rating": avg_rating,
            "status_counts": dict(status_counts),
            "rating_distribution": rating_distribution,
            "top_authors": [
                {"name": name, "count": count} for name, count in top_authors
            ],
            "top_publishers": [
                {"name": name, "count": count} for name, count in top_publishers
            ],
            "category_distribution": [
                {"label": label, "count": count}
                for label, count in category_distribution
            ],
            "max_category_count": max_category_count,
            "yearly_counts": sorted_years,
            "max_year_count": max_year_count,
            "monthly_counts": ordered_months,
            "max_month_count": max_month_count,
            # New fields
            "total_pages_read": total_pages_read,
            "avg_pages_per_book": round(avg_pages_per_book, 1),
            "avg_reading_time_days": round(avg_reading_time_days, 1),
            "total_reading_days": total_reading_days,
            "current_streak": current_streak,
            "longest_streak": longest_streak,
            "yearly_goal": yearly_goal,
            "books_this_year": books_this_year,
            "goal_progress_percent": goal_progress_percent,
            "format_distribution": format_distribution,
            "language_distribution": language_distribution,
            "top_series": top_series,
            "category_details": category_details,
            "year_comparison": year_comparison,
            "reading_pace_monthly": reading_pace_monthly,
            "reading_pace_annualised": reading_pace_annualised,
        }
    )


@app.route("/api/books/<int:book_id>", methods=["GET"])
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


@app.route("/books/<int:book_id>", methods=["GET"])
@authorisation_required
def book_detail(book_id: int):
    storage = get_storage()
    book = storage.get_book_by_id(book_id)
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("list_books"))

    # Get reading records for this book
    all_records = storage.get_reading_records()
    book["reading_records"] = [r for r in all_records if r["book_id"] == book_id]
    # Sort records by start_date descending (most recent first)
    book["reading_records"].sort(key=lambda r: r.get("start_date", ""), reverse=True)

    rl_items = storage.get_reading_list()
    is_planned = any(item["book_id"] == book_id for item in rl_items)

    today = datetime.date.today().isoformat()
    return render_template(
        "book_detail.html", book=book, today=today, is_planned=is_planned
    )


@app.route("/books/<int:book_id>/reading-records", methods=["POST"])
@authorisation_required
@csrf_protect
def create_reading_record(book_id: int):
    storage = get_storage()
    status = request.form.get("status")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    rating = int(request.form.get("rating", 0))

    if not status or not start_date:
        flash("Status and start date are required.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    try:
        storage.add_reading_record(
            book_id=book_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        app.logger.info(f"RECORD_CREATED: book_id={book_id}, status='{status}'")
        flash("Reading record added.", "success")
    except Exception as e:
        app.logger.error(f"RECORD_CREATE_FAILED: book_id={book_id}, error={str(e)}")
        flash(f"Error adding reading record: {str(e)}", "error")

    return redirect(url_for("book_detail", book_id=book_id))


def _get_safe_redirect_target(target: str | None) -> str | None:
    """
    Return a safe redirect target derived from user-controlled input.

    Only relative URLs (no scheme, no netloc) are allowed. Backslashes are
    stripped to avoid alternative path separators being interpreted by browsers.
    """
    if not target:
        return None
    cleaned = target.replace("\\", "")
    parsed = urlparse(cleaned)
    if parsed.scheme or parsed.netloc:
        return None
    return cleaned


@app.route("/reading-records/<int:record_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def update_reading_record(record_id: int):
    storage = get_storage()
    status = request.form.get("status")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    rating = int(request.form.get("rating", 0))

    if not status or not start_date:
        flash("Status and start date are required.", "error")
        safe_target = _get_safe_redirect_target(request.referrer)
        return redirect(safe_target or url_for("reading_history"))

    try:
        storage.update_reading_record(
            record_id=record_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        app.logger.info(f"RECORD_UPDATED: record_id={record_id}, status='{status}'")
        flash("Reading record updated.", "success")
    except Exception as e:
        app.logger.error(f"RECORD_UPDATE_FAILED: record_id={record_id}, error={str(e)}")
        flash(f"Error updating record: {str(e)}", "error")

    safe_target = _get_safe_redirect_target(request.referrer)
    return redirect(safe_target or url_for("reading_history"))


@app.route("/reading-records/<int:record_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def delete_reading_record(record_id: int):
    storage = get_storage()
    try:
        success = storage.delete_reading_record(record_id)
        if success:
            flash("Reading record deleted.", "success")
        else:
            flash("Reading record not found.", "error")
    except Exception as e:
        app.logger.error(f"Failed to delete reading record: {str(e)}")
        flash(f"Error deleting record: {str(e)}", "error")

    safe_target = _get_safe_redirect_target(request.referrer)
    return redirect(safe_target or url_for("reading_history"))


@app.route("/books", methods=["POST"])
@authorisation_required
@csrf_protect
def create_book():
    storage = get_storage()
    from book_lamp.utils.books import normalize_isbn

    isbn = normalize_isbn(request.form.get("isbn", "") or "")
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()

    # Avoid duplicates if ISBN is present
    if isbn:
        existing = storage.get_book_by_isbn(isbn)
        if existing:
            try:
                storage.add_to_reading_list(existing["id"])
                app.logger.info(
                    f"Successfully added existing book (ID: {existing['id']}, ISBN: {isbn}) to reading list"
                )
                flash("Book moved to your reading list.", "success")
            except Exception as e:
                app.logger.error(
                    f"Failed to add existing book {existing['id']} (ISBN: {isbn}) to reading list: {str(e)}",
                    exc_info=True,
                )
                flash(f"Error adding to reading list: {str(e)}", "error")
            return redirect(url_for("reading_list"))

    # Manual entry or Lookup?
    if title and author:
        # Manual entry path
        # Try to recover cached cover images from a previous lookup attempt
        cached_data = {}
        if isbn and not is_test_mode():
            from book_lamp.services.book_lookup import lookup_book_by_isbn13

            try:
                res = lookup_book_by_isbn13(isbn)
                if res:
                    cached_data = res
            except Exception:
                pass

        data = {
            "title": title,
            "author": author,
            "publisher": request.form.get("publisher"),
            "publish_date": request.form.get("publication_year"),
            "thumbnail_url": cached_data.get("thumbnail_url"),
            "cover_url": cached_data.get("cover_url"),
            "description": request.form.get("description"),
            "bisac_category": request.form.get("bisac_category"),
        }
    else:
        # Lookup via Open Library Books API
        from book_lamp.services.book_lookup import lookup_book_by_isbn13

        if is_test_mode() and isbn == TEST_ISBN:
            data = {
                "title": "Test Book",
                "author": "Test Author",
                "publish_date": "2019-05-02",
                "thumbnail_url": "http://example.com/thumb.jpg",
            }
        else:
            try:
                data = lookup_book_by_isbn13(isbn)
            except Exception as exc:  # noqa: BLE001
                app.logger.error(f"ISBN lookup failed for {isbn}: {exc}")
                flash(
                    f"Lookup failed for ISBN {isbn}. Please enter details manually.",
                    "info",
                )
                return redirect(url_for("new_book_form", isbn=isbn, manual=1))

        if not data:
            flash(
                f"No book data found for ISBN {isbn}. You can enter details manually below.",
                "info",
            )
            return redirect(url_for("new_book_form", isbn=isbn, manual=1))

    title = data.get("title") or ""
    author = data.get("author") or ""
    publish_date = data.get("publish_date")
    year = parse_publication_year(str(publish_date) if publish_date else None)
    thumbnail_url = data.get("thumbnail_url")

    # If it was an external lookup and title/author are still missing
    if not title or not author:
        # We might have received just a cover, but no title/author metadata
        app.logger.info(
            f"ISBN_LOOKUP_FAILED: Missing metadata (title/author) for ISBN {isbn}"
        )
        flash(
            f"No book metadata found for ISBN {isbn}. You can enter details manually below.",
            "info",
        )
        return redirect(
            url_for("new_book_form", isbn=isbn, manual=1, add_to_reading_list=1)
        )

    try:
        created_book = storage.add_book(
            isbn13=isbn,
            title=title[:300],
            author=author[:200],
            publication_year=year,
            thumbnail_url=(thumbnail_url[:500] if thumbnail_url else None),
            publisher=data.get("publisher"),
            description=data.get("description"),
            bisac_category=data.get("bisac_category"),
            language=data.get("language"),
            page_count=data.get("page_count"),
            physical_format=data.get("physical_format"),
            edition=data.get("edition"),
            cover_url=data.get("cover_url"),
        )
        app.logger.info(
            f"BOOK_CREATED: id={created_book['id']}, isbn={isbn}, title='{title}', manual={bool(request.form.get('title'))}"
        )
    except Exception as e:
        app.logger.error(f"Failed to create book: {str(e)}", exc_info=True)
        flash(f"Error creating book: {str(e)}", "error")
        return redirect(url_for("new_book_form", isbn=isbn, manual=1))

    # When a new book is added it should go to the reading list
    try:
        storage.add_to_reading_list(created_book["id"])
        app.logger.info(
            f"BOOK_MOVED_TO_READING_LIST: id={created_book['id']}, status='Plan to Read'"
        )

        flash("Book added to your reading list.", "success")
    except Exception as e:
        app.logger.error(
            f"READING_LIST_ADD_FAILED: id={created_book['id']}, error={str(e)}"
        )
        flash(
            "Book added, but failed to add to reading list.",
            "warning",
        )
    return redirect(url_for("reading_list"))


def _background_fetch_missing_data(job_id: str, user_id: int):
    """Background task: bulk fetch missing data (covers, metadata) for all books."""
    from book_lamp.services.book_lookup import enhance_books_batch

    try:
        # Create storage (outside request context)
        storage: Union[MockStorage, PostgresStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = PostgresStorage(user_id=user_id)

        books = storage.get_all_books()
        app.logger.info(
            f"Background job {job_id}: checking {len(books)} books for missing data..."
        )

        # enhance_books_batch updates in-place and returns count
        # Pass force_refresh=True because we want to update categories for all books
        updated_count = enhance_books_batch(books, force_refresh=True)

        # Always save books back to storage to preserve any existing metadata
        items_to_update = [{"book": b, "record": None} for b in books]
        storage.bulk_import(items_to_update)

        result_msg = (
            f"Found and updated missing data for {updated_count} book(s)."
            if updated_count > 0
            else "No missing data found to update."
        )
        app.logger.info(f"Background job {job_id}: completed - {result_msg}")
        return result_msg
    except Exception:
        app.logger.exception(f"Background job {job_id} failed")
        raise


@app.route("/books/fetch-covers", methods=["POST"])
@authorisation_required
@csrf_protect
def fetch_missing_data():
    """Queue background job to fetch missing data (covers, metadata) for all books."""
    job_queue = get_job_queue()
    job_id = job_queue.submit_job(
        "fetch_missing_data",
        _background_fetch_missing_data,
        session["user_id"],
    )

    flash(
        "Refreshing reading log catalogue: Fetching metadata, covers, and categorisation in the background.",
        "info",
    )
    return redirect(url_for("list_books", job_id=job_id))


@app.route("/stats/backfill-categories")
@authorisation_required
def fetch_missing_categories():
    """Trigger backfill of BISAC categories from the stats page."""
    job_queue = get_job_queue()
    job_id = job_queue.submit_job(
        "backfill_bisac",
        _background_fetch_missing_data,  # Reusing the background fetcher which now includes categories
        session["user_id"],
    )

    flash(
        "Book categorisation started in the background. Your charts will update as data is found.",
        "info",
    )
    return redirect(url_for("collection_stats", job_id=job_id))


@app.route("/books/import", methods=["GET"])
@authorisation_required
def import_books_form():
    return render_template("import_books.html")


def _background_import_books(
    job_id: str, content: str, fetch_metadata: bool, user_id: int
):
    """Background task: import books from Libib CSV."""
    app.logger.info(f"Background job {job_id}: parsing CSV content...")

    try:
        # Create storage (outside request context)
        storage: Union[MockStorage, PostgresStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = PostgresStorage(user_id=user_id)

        items = parse_libib_csv(content)
        app.logger.info(f"Background job {job_id}: parsed {len(items)} items from CSV")

        # Optional data enhancement
        enhanced_count = 0
        if fetch_metadata and items:
            from book_lamp.services.book_lookup import enhance_books_batch

            app.logger.info(
                f"Background job {job_id}: enhancing {len(items)} items with metadata..."
            )
            books = [item["book"] for item in items]
            enhanced_count = enhance_books_batch(books)

        import_count = storage.bulk_import(items)
        msg = f"Successfully imported {import_count} entries"
        if enhanced_count > 0:
            msg += f" and found missing data/covers for {enhanced_count} books"
        app.logger.info(f"Background job {job_id}: completed - {msg}")
        return msg
    except Exception:
        app.logger.exception(f"Background job {job_id} failed")
        raise


@app.route("/books/import", methods=["POST"])
@authorisation_required
@csrf_protect
def import_books():
    """Queue background job to import books from Libib CSV."""
    job_queue = get_job_queue()

    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("import_books_form"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("import_books_form"))

    # pyrefly: ignore [missing-attribute]
    if not file or not file.filename.endswith(".csv"):
        flash("Please upload a valid CSV file.", "error")
        return redirect(url_for("import_books_form"))

    try:
        content = file.read().decode("utf-8")
        fetch_metadata = request.form.get("fetch_metadata") == "on"

        # Queue the import job
        job_queue = get_job_queue()

        job_id = job_queue.submit_job(
            "import_books",
            _background_import_books,
            content,
            fetch_metadata,
            session["user_id"],
        )

        flash(
            "Reading log import in progress: Processing and enriching your reading history.",
            "info",
        )
        return redirect(url_for("list_books", job_id=job_id))
    except Exception as e:
        app.logger.error(f"Failed to queue import job: {str(e)}")
        flash(f"Error starting import: {str(e)}", "error")
        return redirect(url_for("import_books_form"))


@app.route("/books/<int:book_id>/edit", methods=["POST"])
@authorisation_required
@csrf_protect
def edit_book(book_id: int):
    storage = get_storage()
    # Extract data from form
    isbn13 = request.form.get("isbn13", "").strip().replace("-", "")
    title = request.form.get("title", "").strip()
    author = request.form.get("author", "").strip()
    publication_year_str = request.form.get("publication_year", "").strip()
    thumbnail_url = request.form.get("thumbnail_url", "").strip()
    cover_url = request.form.get("cover_url", "").strip()
    publisher = request.form.get("publisher", "").strip()
    description = request.form.get("description", "").strip()
    series = request.form.get("series", "").strip()
    bisac_category = request.form.get("bisac_category", "").strip()

    # Basic validation
    if not title or not author:
        flash("Title and author are required.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    if (
        isbn13
        and not is_valid_isbn13(isbn13)
        and not (is_test_mode() and isbn13 == TEST_ISBN)
    ):
        flash("Please enter a valid 13-digit ISBN.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    publication_year = None
    if publication_year_str:
        try:
            publication_year = int(publication_year_str)
        except ValueError:
            pass

    try:
        storage.update_book(
            book_id=book_id,
            isbn13=isbn13,
            title=title[:300],
            author=author[:200],
            publication_year=publication_year,
            thumbnail_url=(thumbnail_url if thumbnail_url else None),
            publisher=(publisher if publisher else None),
            description=(description if description else None),
            series=(series if series else None),
            bisac_category=(bisac_category if bisac_category else None),
            cover_url=(cover_url if cover_url else None),
        )
        flash("Book updated successfully.", "success")
    except Exception as e:
        app.logger.error(f"Failed to update book: {str(e)}")
        flash(f"Error updating book: {str(e)}", "error")

    return redirect(url_for("book_detail", book_id=book_id))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@authorisation_required
@csrf_protect
def delete_book(book_id: int):
    storage = get_storage()
    success = storage.delete_book(book_id)
    if not success:
        flash("Book not found.", "error")
    else:
        flash("Book deleted.", "success")
    return redirect(url_for("list_books"))


# -----------------------------
# Test utilities (enabled only when TEST_MODE=1)
# -----------------------------

if is_test_mode():
    # storage is already initialized above in the global scope if TEST_MODE is True

    @app.route("/test/reset", methods=["POST"])
    def test_reset():
        """Reset test storage."""
        storage = get_storage()
        try:
            storage.books = []
            storage.reading_records = []
            if hasattr(storage, "reading_list"):
                storage.reading_list = []
            storage.next_book_id = 1
            storage.next_record_id = 1
            # Default to unauthorised for testing the connect flow
            if hasattr(storage, "set_authorised"):
                storage.set_authorised(False)
            return {"status": "ok"}
        except Exception as e:
            app.logger.exception("Failed to reset test storage: %s", e)
            return {
                "status": "error",
                "message": "Internal error during test reset",
            }, 500

    @app.route("/test/connect")
    def test_connect():
        """Authorise as a test user automatically."""
        if not is_test_mode():
            return "Not available", 404

        # Toggle authorised state in MockStorage
        storage = get_storage()
        if hasattr(storage, "set_authorised"):
            storage.set_authorised(True)

        flash("Google Sheets Connected (Test Mode)", "success")
        return redirect(url_for("home"))

    @app.route("/test/disconnect")
    def test_disconnect():
        """Disconnect as a test user automatically."""
        if not is_test_mode():
            return "Not available", 404

        storage = get_storage()
        if hasattr(storage, "set_authorised"):
            storage.set_authorised(False)

        flash("Google Sheets Disconnected (Test Mode)", "info")
        return redirect(url_for("home"))


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
