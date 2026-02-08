import calendar
import datetime
import logging
import os
import re
from collections import Counter
from functools import wraps
from typing import Union

import click  # noqa: E402
from authlib.integrations.flask_client import OAuth  # type: ignore  # noqa: E402
from dotenv import load_dotenv
from flask import (  # noqa: E402
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from book_lamp.services import sheets_storage as from_sheets_storage
from book_lamp.services.job_queue import get_job_queue
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.sheets_storage import GoogleSheetsStorage
from book_lamp.utils import (
    SORT_OPTIONS,
    is_valid_isbn13,
    parse_publication_year,
    sort_books,
)
from book_lamp.utils.libib_import import parse_libib_csv
from book_lamp.utils.protobuf_patch import apply_patch

# Apply security patch for CVE-2026-0994
apply_patch()

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
TEST_MODE = os.environ.get("TEST_MODE", "0") == "1"
TEST_ISBN = "9780000000000"

# Global singleton for test mode only
_mock_storage_singleton = MockStorage()


def get_storage():
    """Get the appropriate storage backend for the current request context."""
    if os.environ.get("TEST_MODE", "0") == "1":
        return _mock_storage_singleton

    # Use different sheet names for production and development
    # FLASK_DEBUG=True or lack of FLASK_ENV=production indicates development
    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"

    # Initialize implementation with credentials from session
    credentials = session.get("credentials")
    return GoogleSheetsStorage(sheet_name=sheet_name, credentials_dict=credentials)


def authorisation_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
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


@app.context_processor
def inject_global_vars():
    return {
        "is_authorised": get_storage().is_authorised(),
        "version": APP_VERSION,
        "current_year": datetime.date.today().year,
    }


@app.route("/api/jobs/<job_id>", methods=["GET"])
def get_job_status(job_id: str):
    """Get the status of a background job."""
    job_queue = get_job_queue()
    job = job_queue.get_job(job_id)

    if not job:
        return jsonify({"error": "Job not found"}), 404

    return jsonify(job.to_dict())


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
    if TEST_MODE:
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
if not TEST_MODE:
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
if not TEST_MODE:
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
        client_kwargs={"scope": " ".join(from_sheets_storage.SCOPES)},
    )


@app.route("/connect")
def connect():
    if TEST_MODE:
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
        if not TEST_MODE:
            # Bridging Authlib token to Google-auth format.
            # Client ID and secret are NOT saved - they're read from env vars for security.
            creds_data = {
                "token": token.get("access_token"),
                "refresh_token": token.get("refresh_token"),
                "token_uri": "https://oauth2.googleapis.com/token",
                "scopes": from_sheets_storage.SCOPES,
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
    if TEST_MODE:
        click.echo("Not available in test mode.")
        return

    # Note: This will likely fail in CLI since there is no session
    # A robust CLI would need a way to input a token manually
    get_storage().initialize_sheets()
    click.echo("Google Sheets initialized successfully.")


# -----------------------------
# Reading History feature
# -----------------------------


@app.route("/history", methods=["GET"])
@authorisation_required
def reading_history():
    """Show detailed reading history as a chronological list of individual events."""
    storage = get_storage()
    history = storage.get_reading_history()

    # Filtering
    status_filter = request.args.get("status")
    if status_filter:
        history = [r for r in history if r.get("status") == status_filter]

    min_rating = request.args.get("min_rating")
    if min_rating and min_rating.isdigit():
        min_rating = int(min_rating)
        history = [r for r in history if r.get("rating", 0) >= min_rating]

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

    # Get status list for filter dropdown (from all records)
    all_statuses = sorted(
        list(set(r.get("status") for r in history if r.get("status")))
    )

    return render_template(
        "history.html",
        history=history,
        statuses=all_statuses,
        current_status=status_filter,
        current_rating=min_rating,
        current_sort=sort_by,
    )


# -----------------------------
# Books feature
# -----------------------------


@app.route("/books/new", methods=["GET"])
@authorisation_required
def new_book_form():
    return render_template("add_book.html")


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

    return render_template(
        "books.html", books=books, sort_by=sort_by, sort_options=SORT_OPTIONS
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


@app.route("/stats", methods=["GET"])
@authorisation_required
def collection_stats():
    storage = get_storage()
    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    total_books = len(books)
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

    # Status counts - include a 'Not begun' category for books without records
    statuses = []
    for b in books:
        bid = b.get("id")
        if bid in latest_records:
            statuses.append(latest_records[bid].get("status", "Unknown"))
        else:
            statuses.append("Not begun")
    status_counts = Counter(statuses)

    # Top authors
    all_authors = []
    for b in books:
        if b.get("authors"):
            all_authors.extend(b["authors"])
        elif b.get("author"):
            all_authors.append(b["author"])

    total_authors = len(set(all_authors))
    top_authors = Counter(all_authors).most_common(5)

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

    # Map to month names
    ordered_months = []
    for i in range(1, 13):
        idx = f"{i:02d}"
        name = calendar.month_name[i][:3]
        ordered_months.append((name, monthly_counts[idx]))

    max_month_count = max(monthly_counts.values()) if monthly_counts else 1
    avg_month_count = sum(monthly_counts.values()) / 12

    # Dewey Distribution
    DEWEY_LABELS = {
        "0": "000 General",
        "1": "100 Philo",
        "2": "200 Rel",
        "3": "300 Soc Sci",
        "4": "400 Lang",
        "5": "500 Sci",
        "6": "600 Tech",
        "7": "700 Arts",
        "8": "800 Lit",
        "9": "900 Hist",
    }

    dewey_bins = Counter()
    for b in books:
        ddc = b.get("dewey_decimal")
        if ddc:
            # Match first digit of a numeric DDC
            match = re.search(r"\b(\d)", str(ddc))
            if match:
                digit = match.group(1)
                dewey_bins[DEWEY_LABELS.get(digit, "Other")] += 1

    # Ensure all labels present for chart
    dewey_distribution = {label: dewey_bins[label] for label in DEWEY_LABELS.values()}
    max_dewey_count = (
        max(dewey_distribution.values()) if dewey_distribution.values() else 1
    )

    return render_template(
        "stats.html",
        total_books=total_books,
        total_authors=total_authors,
        total_records=total_records,
        avg_rating=avg_rating,
        status_counts=status_counts,
        top_authors=top_authors,
        dewey_distribution=dewey_distribution,
        max_dewey_count=max_dewey_count,
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

    today = datetime.date.today().isoformat()
    return render_template("book_detail.html", book=book, today=today)


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

    storage.add_reading_record(
        book_id=book_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        rating=rating,
    )
    flash("Reading record added.", "success")
    return redirect(url_for("book_detail", book_id=book_id))


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
        return redirect(request.referrer or url_for("reading_history"))

    try:
        storage.update_reading_record(
            record_id=record_id,
            status=status,
            start_date=start_date,
            end_date=end_date,
            rating=rating,
        )
        flash("Reading record updated.", "success")
    except Exception as e:
        app.logger.error(f"Failed to update reading record: {str(e)}")
        flash(f"Error updating record: {str(e)}", "error")

    return redirect(request.referrer or url_for("reading_history"))


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

    return redirect(request.referrer or url_for("reading_history"))


@app.route("/books", methods=["POST"])
@authorisation_required
def create_book():
    storage = get_storage()
    from book_lamp.utils.books import normalize_isbn

    isbn = normalize_isbn(request.form.get("isbn", "") or "")

    # Check if valid (allow special test ISBN in test mode)
    is_valid = (TEST_MODE and isbn == TEST_ISBN) or is_valid_isbn13(isbn)

    if not is_valid:
        flash("Please enter a valid 13-digit ISBN.", "error")
        return redirect(url_for("new_book_form"))

    # Avoid duplicates
    existing = storage.get_book_by_isbn(isbn)
    if existing:
        flash("This book has already been added.", "info")
        return redirect(url_for("list_books"))

    # Lookup via Open Library Books API
    from book_lamp.services.book_lookup import lookup_book_by_isbn13

    if TEST_MODE and isbn == TEST_ISBN:
        data = {
            "title": "Test Driven Development",
            "author": "Test Author",
            "publish_date": "2019-05-02",
            "thumbnail_url": "http://example.com/thumb.jpg",
        }
    else:
        try:
            data = lookup_book_by_isbn13(isbn)
        except Exception as exc:  # noqa: BLE001
            flash(f"Failed to fetch book details: {exc}", "error")
            return redirect(url_for("list_books"))

    if not data:
        flash("No book data found for that ISBN.", "error")
        return redirect(url_for("list_books"))

    title = data.get("title") or ""
    author = data.get("author") or ""
    publish_date = data.get("publish_date")
    year = parse_publication_year(publish_date)
    thumbnail_url = data.get("thumbnail_url")

    if not title or not author:
        flash("The external service did not return required fields.", "error")
        return redirect(url_for("list_books"))

    storage.add_book(
        isbn13=isbn,
        title=title[:300],
        author=author[:200],
        publication_year=year,
        thumbnail_url=(thumbnail_url[:500] if thumbnail_url else None),
        publisher=data.get("publisher"),
        description=data.get("description"),
        dewey_decimal=data.get("dewey_decimal"),
        language=data.get("language"),
        page_count=data.get("page_count"),
        physical_format=data.get("physical_format"),
        edition=data.get("edition"),
        cover_url=data.get("cover_url"),
    )
    flash("Book added successfully.", "success")
    return redirect(url_for("list_books"))


def _background_fetch_missing_data(job_id: str, credentials_dict, sheet_name: str):
    """Background task: bulk fetch missing data (covers, metadata) for all books."""
    from book_lamp.services.book_lookup import enhance_books_batch

    try:
        # Create storage with passed credentials (outside request context)
        storage: Union[MockStorage, GoogleSheetsStorage]
        if os.environ.get("TEST_MODE", "0") == "1":
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
        updated_count = enhance_books_batch(books)

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
        "Data retrieval started in the background. You can continue using the app.",
        "info",
    )
    return redirect(url_for("list_books", job_id=job_id))


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
        if os.environ.get("TEST_MODE", "0") == "1":
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
            "Import started in the background. You can continue using the app while we process your file.",
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
    dewey_decimal = request.form.get("dewey_decimal", "").strip()

    # Basic validation
    if not title or not author:
        flash("Title and author are required.", "error")
        return redirect(url_for("book_detail", book_id=book_id))

    if (
        isbn13
        and not is_valid_isbn13(isbn13)
        and not (TEST_MODE and isbn13 == TEST_ISBN)
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
            dewey_decimal=(dewey_decimal if dewey_decimal else None),
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


# -----------------------------
# Test utilities (enabled only when TEST_MODE=1)
# -----------------------------

if TEST_MODE:
    # storage is already initialized above in the global scope if TEST_MODE is True

    @app.route("/test/reset", methods=["POST"])
    def test_reset():
        """Reset test storage."""
        storage = get_storage()
        try:
            storage.books = []
            storage.reading_records = []
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
        if not TEST_MODE:
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
        if not TEST_MODE:
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
