import calendar
import datetime
import logging
import os
import re
from collections import Counter
from functools import wraps
from typing import Union, cast
from urllib.parse import urlparse

import click  # noqa: E402
from authlib.integrations.flask_client import OAuth  # type: ignore  # noqa: E402
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

from book_lamp.services import sheets_storage as from_sheets_storage
from book_lamp.services.async_sqlite_storage import AsyncSQLiteStorage
from book_lamp.services.book_lookup import lookup_books_by_author
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.llm_client import LLMClient
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.sheets_storage import GoogleSheetsStorage
from book_lamp.utils import (
    SORT_OPTIONS,
    is_valid_isbn13,
    parse_bisac_category,
    parse_publication_year,
    sort_books,
)
from book_lamp.utils.libib_import import parse_libib_csv
from book_lamp.utils.protobuf_patch import apply_patch

# Apply security patch for CVE-2026-0994
apply_patch()


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


# Global singleton for test mode only
_mock_storage_singleton = MockStorage()
_async_storage_singleton: AsyncSQLiteStorage | None = None


def get_storage():
    """Get the appropriate storage backend for the current request context."""
    global _async_storage_singleton
    if is_test_mode():
        return _mock_storage_singleton
    if os.environ.get("ASYNC_SQLITE_STORAGE", "0") == "1":
        if _async_storage_singleton is None:
            is_prod = os.environ.get("FLASK_ENV") == "production"
            sheet_name = "BookLampData" if is_prod else "DevBookLampData"
            _async_storage_singleton = AsyncSQLiteStorage(sheet_name=sheet_name)
        _async_storage_singleton.configure_remote(
            credentials_dict=session.get("credentials"),
            spreadsheet_id=session.get("spreadsheet_id"),
        )
        return _async_storage_singleton
    if "storage" not in g:
        app.logger.info("Initializing storage for request...")
        # Use different sheet names for production and development
        # FLASK_DEBUG=True or lack of FLASK_ENV=production indicates development
        is_prod = os.environ.get("FLASK_ENV") == "production"
        sheet_name = "BookLampData" if is_prod else "DevBookLampData"

        # Initialize implementation with credentials from session
        credentials = session.get("credentials")
        spreadsheet_id = session.get("spreadsheet_id")
        g.storage = GoogleSheetsStorage(
            sheet_name=sheet_name,
            credentials_dict=credentials,
            spreadsheet_id=spreadsheet_id,
        )
    return g.storage


def get_llm_client() -> LLMClient:
    """Return a per-request LLMClient singleton (cheap to construct)."""
    if "llm_client" not in g:
        g.llm_client = LLMClient()
    return cast(LLMClient, g.llm_client)


def authorisation_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        app.logger.info(f"AUTHORISATION_CHECK for route: {f.__name__}")
        if not get_storage().is_authorised():
            return redirect(url_for("unauthorised"))
        return f(*args, **kwargs)

    return decorated_function


def get_app_version():
    """Get the application version based on environment."""
    if os.environ.get("FLASK_ENV") == "production":
        # Check for common deployment commit hash environment variables
        for env_var in ["RENDER_GIT_COMMIT", "GIT_COMMIT", "HEROKU_SLUG_COMMIT"]:
            val = os.environ.get(env_var)
            if val:
                return val[:7]
        return "prod"
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
    # Use a fast check for the template context to avoid redundant storage creation
    is_auth = False
    if "credentials" in session:
        # In test mode, we might want to still call is_authorised
        if is_test_mode():
            is_auth = get_storage().is_authorised()
        else:
            is_auth = True

    # Fetch user theme preference
    theme = "dark"
    if is_auth:
        try:
            settings = get_storage().get_settings()
            theme = settings.get("theme", "dark")
        except Exception:
            app.logger.warning("Failed to fetch settings for template injection")

    return {
        "is_authorised": is_auth,
        "current_year": datetime.datetime.now().year,
        "app_version": getattr(app, "app_version", APP_VERSION),
        "user_theme": theme,
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


@app.route("/api/sync/diagnostics", methods=["GET"])
@authorisation_required
def sync_diagnostics():
    """Return async sync diagnostics when SQLite async storage is enabled."""
    storage = get_storage()
    if isinstance(storage, AsyncSQLiteStorage) or hasattr(
        storage, "get_sync_diagnostics"
    ):
        return jsonify(storage.get_sync_diagnostics())
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
    is_authorised = get_storage().is_authorised()
    return render_template("home.html", is_authorised=is_authorised)


@app.route("/about")
@authorisation_required
def about():
    return render_template("about.html", version=APP_VERSION)


@app.route("/unauthorised")
def unauthorised():
    return render_template("unauthorised.html"), 401


@app.route("/logout")
def logout():
    if is_test_mode():
        return redirect(url_for("test_disconnect"))
    session.clear()
    flash("Google Sheets disconnected.", "info")
    return redirect(url_for("home"))


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.png")


# Secret key for session management
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# Google OAuth configuration
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET")
app.config["GOOGLE_DISCOVERY_URL"] = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

# Validate OAuth configuration (skip in test mode)
if not is_test_mode():
    if not app.config["GOOGLE_CLIENT_ID"]:
        raise ValueError(
            "GOOGLE_CLIENT_ID environment variable is required. "
            "Please set it in your .env file. "
            "Get credentials from https://console.cloud.google.com/"
        )
    if not app.config["GOOGLE_CLIENT_SECRET"]:
        raise ValueError(
            "GOOGLE_CLIENT_SECRET environment variable is required. "
            "Please set it in your .env file. "
            "Get credentials from https://console.cloud.google.com/"
        )

oauth = OAuth(app)
if not is_test_mode():
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
        client_kwargs={
            "scope": " ".join(from_sheets_storage.SCOPES)
        },  # drive.file only
    )


@app.route("/connect")
def connect():
    if is_test_mode():
        return redirect(url_for("test_connect"))

    try:
        if (
            "CODESPACE_NAME" in os.environ
            and "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN" in os.environ
        ):
            codespace_name = os.environ["CODESPACE_NAME"]
            domain = os.environ["GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"]
            redirect_uri = f"https://{codespace_name}-5000.{domain}/authorize"
        else:
            redirect_uri = url_for("authorize", _external=True)

        app.logger.info(f"Initiating OAuth flow with redirect_uri: {redirect_uri}")
        # Request offline access to get a refresh token
        return oauth.google.authorize_redirect(
            redirect_uri, access_type="offline", prompt="consent"
        )
    except Exception:
        app.logger.exception("OAuth authorisation initiation failed")
        return (
            "<h1>Authorisation Error</h1>"
            "<p>Failed to initiate Google authorisation.</p>"
            "<p>Please check that GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set correctly.</p>"
            "<a href='/'>Go back</a>"
        ), 500


@app.route("/authorize")
def authorize():
    try:
        token = oauth.google.authorize_access_token()
        app.logger.info("OAuth token received successfully")

        # Save the token for GoogleSheetsStorage
        if not is_test_mode():
            # Bridging Authlib token to Google-auth format.
            # Client ID and secret are NOT saved - they're read from env vars for security.
            creds_data = {
                "token": token.get("access_token"),
                "refresh_token": token.get("refresh_token"),
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": from_sheets_storage.SCOPES,  # drive.file only
            }
            if token.get("expires_at"):
                creds_data["expiry"] = (
                    datetime.datetime.fromtimestamp(
                        token["expires_at"], tz=datetime.timezone.utc
                    )
                    .isoformat()
                    .replace("+00:00", "Z")
                )

            # Save credentials to session for this user
            session["credentials"] = creds_data

        flash("Google Sheets access authorised!", "success")
        return redirect(url_for("home"))
    except Exception:
        app.logger.exception("Failed to authorise access token")
        return (
            "<h1>Authorisation Error</h1><p>Failed to complete Google authorisation.</p><a href='/'>Go back</a>"
        ), 401


@app.cli.command("init-sheets")
def init_sheets_command():
    """Initialize Google Sheets with required tabs and headers."""
    if is_test_mode():
        click.echo("Not available in test mode.")
        return

    # Note: This will likely fail in CLI since there is no session
    # A robust CLI would need a way to input a token manually
    get_storage().initialize_sheets()
    click.echo("Google Sheets initialized successfully.")


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


@app.cli.command("backfill-broad-categories")
def backfill_broad_categories_command():
    """Enhance existing books with broad categories."""
    if is_test_mode():
        click.echo("Running in test mode with mock storage.")

    from book_lamp.utils.books import resolve_broad_category

    storage = get_storage()
    books = storage.get_all_books()

    click.echo(f"Starting broad category backfill for {len(books)} books...")
    count = 0
    for book in books:
        # Resolve from existing BISAC or other fields
        # Note: We don't have Dewey or Subjects in the Sheets storage yet for old books
        broad_cat = resolve_broad_category(
            bisac=book.get("bisac_category"),
        )
        if broad_cat:
            storage.update_book(
                book_id=book["id"],
                isbn13=book["isbn13"],
                title=book["title"],
                author=book["author"],
                broad_category=broad_cat,
            )
            count += 1

    click.echo(f"Finished backfill. Updated {count} books.")


# -----------------------------
# Reading History feature
# -----------------------------


@app.route("/history", methods=["GET"])
@authorisation_required
def reading_history():
    """Show detailed reading history as a chronological list of individual events."""
    storage = get_storage()
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

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


# -----------------------------
# Books feature
# -----------------------------


@app.route("/books/new", methods=["GET"])
@authorisation_required
def new_book_form():
    isbn = request.args.get("isbn", "")
    show_manual = request.args.get("manual", "0") == "1"
    return render_template("add_book.html", isbn=isbn, show_manual=show_manual)


@app.route("/reading-list", methods=["GET"])
@authorisation_required
def reading_list():
    storage = get_storage()
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

    rl_items = storage.get_reading_list()
    books = []

    all_books = storage.get_all_books()
    book_map = {b["id"]: b for b in all_books}
    for item in rl_items:
        if item["book_id"] in book_map:
            books.append(book_map[item["book_id"]])

    return render_template("reading_list.html", books=books)


@app.route("/reading-list/reorder", methods=["POST"])
@authorisation_required
def reorder_reading_list():
    storage = get_storage()
    book_ids = request.json.get("book_ids", [])
    storage.update_reading_list_order(book_ids)
    return jsonify({"success": True})


@app.route("/reading-list/remove/<int:book_id>", methods=["POST"])
@authorisation_required
def remove_from_reading_list(book_id: int):
    storage = get_storage()
    storage.remove_from_reading_list(book_id)
    flash("Removed from reading list.", "success")
    return redirect(get_safe_redirect_target("reading_list"))


@app.route("/books/<int:book_id>/start-reading", methods=["POST"])
@authorisation_required
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
def add_existing_to_reading_list(book_id: int):
    storage = get_storage()
    try:
        storage.add_to_reading_list(book_id)
        app.logger.info(f"Successfully added book ID {book_id} to reading list")
        if storage.spreadsheet_id:
            session["spreadsheet_id"] = storage.spreadsheet_id
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
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

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
            broad_cat = b.get("broad_category")
            bisac = b.get("bisac_category")
            if (broad_cat and category_filter.lower() in broad_cat.lower()) or (
                bisac and category_filter.lower() in str(bisac).lower()
            ):
                filtered_books.append(b)
        books = filtered_books

    # Extract all top-level categories for the filter dropdown
    all_categories = set()
    for b in storage.get_all_books():
        broad_cat = b.get("broad_category")
        if broad_cat:
            all_categories.add(broad_cat)
        else:
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
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

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

    # Sort each category by reverse publication date
    def get_pub_year(b: dict) -> int:
        py = b.get("publication_year")
        if not py:
            return 0
        if isinstance(py, int):
            return py
        try:
            return int(str(py))
        except (ValueError, TypeError):
            return 0

    read_books.sort(key=get_pub_year, reverse=True)
    reading_list_books.sort(key=get_pub_year, reverse=True)

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


@app.route("/publisher/<path:publisher_slug>", methods=["GET"])
@authorisation_required
def publisher_page(publisher_slug: str):
    storage = get_storage()
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

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

    # Sort books by reverse publication date
    def get_pub_year(b):
        py = b.get("publication_year")
        if not py:
            return 0
        if isinstance(py, int):
            return py
        try:
            return int(str(py))
        except (ValueError, TypeError):
            return 0

    publisher_books.sort(key=get_pub_year, reverse=True)

    return render_template(
        "publisher.html",
        publisher_name=display_publisher_name,
        books=publisher_books,
    )


@app.route("/stats", methods=["GET"])
@authorisation_required
def collection_stats():
    storage = get_storage()
    storage.prefetch()
    if storage.spreadsheet_id:
        session["spreadsheet_id"] = storage.spreadsheet_id

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
        date_str = r.get("end_date", "")
        if date_str and len(date_str) >= 4:
            year = date_str[:4]
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
        broad_cat = b.get("broad_category")
        if broad_cat:
            category_bins[broad_cat] += 1
        else:
            # Fallback for books without broad_category
            bisac = b.get("bisac_category")
            if bisac:
                from book_lamp.utils.books import parse_bisac_category

                main_cat, _ = parse_bisac_category(bisac)
                if main_cat:
                    # Normalize (e.g., 'Fiction' vs 'FICTION')
                    norm_cat = (
                        main_cat.title() if len(main_cat) > 3 else main_cat.upper()
                    )
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
        return redirect(url_for("new_book_form", isbn=isbn, manual=1))

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
        if storage.spreadsheet_id:
            session["spreadsheet_id"] = storage.spreadsheet_id
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


def _background_fetch_missing_data(job_id: str, credentials_dict, sheet_name: str):
    """Background task: bulk fetch missing data (covers, metadata) for all books."""
    from book_lamp.services.book_lookup import enhance_books_batch

    try:
        # Create storage with passed credentials (outside request context)
        storage: Union[MockStorage, GoogleSheetsStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = GoogleSheetsStorage(
                sheet_name=sheet_name, credentials_dict=credentials_dict
            )

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
def fetch_missing_data():
    """Queue background job to fetch missing data (covers, metadata) for all books."""
    job_queue = get_job_queue()

    # Capture request-context data before submitting to background thread
    credentials_dict = session.get("credentials")
    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"

    job_id = job_queue.submit_job(
        "fetch_missing_data",
        _background_fetch_missing_data,
        credentials_dict,
        sheet_name,
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
    credentials_dict = session.get("credentials")
    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"

    job_id = job_queue.submit_job(
        "backfill_bisac",
        _background_fetch_missing_data,  # Reusing the background fetcher which now includes categories
        credentials_dict,
        sheet_name,
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
    job_id: str, content: str, fetch_metadata: bool, credentials_dict, sheet_name: str
):
    """Background task: import books from Libib CSV."""
    app.logger.info(f"Background job {job_id}: parsing CSV content...")

    try:
        # Create storage with passed credentials (outside request context)
        storage: Union[MockStorage, GoogleSheetsStorage]
        if is_test_mode():
            storage = _mock_storage_singleton
        else:
            storage = GoogleSheetsStorage(
                sheet_name=sheet_name, credentials_dict=credentials_dict
            )

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

    if not file or not file.filename.endswith(".csv"):
        flash("Please upload a valid CSV file.", "error")
        return redirect(url_for("import_books_form"))

    try:
        content = file.read().decode("utf-8")
        fetch_metadata = request.form.get("fetch_metadata") == "on"

        # Capture request-context data before submitting to background thread
        credentials_dict = session.get("credentials")
        is_prod = os.environ.get("FLASK_ENV") == "production"
        sheet_name = "BookLampData" if is_prod else "DevBookLampData"

        # Queue the import job
        job_id = job_queue.submit_job(
            "import_books",
            _background_import_books,
            content,
            fetch_metadata,
            credentials_dict,
            sheet_name,
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
def delete_book(book_id: int):
    storage = get_storage()
    success = storage.delete_book(book_id)
    if not success:
        flash("Book not found.", "error")
    else:
        flash("Book deleted.", "success")
    return redirect(url_for("list_books"))


@app.route("/admin/backfill-categories")
@authorisation_required
def backfill_categories_route():
    """Trigger the broad category backfill from the web UI."""
    from book_lamp.utils.books import resolve_broad_category

    storage = get_storage()
    books = storage.get_all_books()

    app.logger.info(f"Starting broad category backfill for {len(books)} books...")
    updates_to_make = []
    
    for book in books:
        if not book.get("broad_category") or book.get("broad_category") == "Other":
            # Resolve from existing BISAC or other fields
            broad_cat = resolve_broad_category(
                bisac=book.get("bisac_category"),
            )
            if broad_cat and broad_cat != "Other":
                updates_to_make.append({
                    "id": book["id"],
                    "broad_category": broad_cat
                })

    count = 0
    if updates_to_make:
        if hasattr(storage, "batch_update_broad_categories"):
            count = storage.batch_update_broad_categories(updates_to_make)
        else:
            # Fallback for other storage types
            for update in updates_to_make:
                storage.update_book(
                    book_id=update["id"],
                    # We need other fields for update_book, so this fallback is actually tricky
                    # But all our main storages have the batch method now.
                    **{k: v for k, v in [b for b in books if b["id"] == update["id"]][0].items() if k != "broad_category"},
                    broad_category=update["broad_category"]
                )
                count += 1

    app.logger.info(f"Finished backfill. Updated {count} books.")
    return f"Backfill complete! Updated {count} books via batch update."


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
