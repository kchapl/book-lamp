import datetime
import logging
import os
from functools import wraps
from typing import Any

import click  # noqa: E402
from authlib.integrations.flask_client import OAuth  # type: ignore  # noqa: E402
from dotenv import load_dotenv
from flask import (  # noqa: E402
    Flask,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from book_lamp.services import sheets_storage as from_sheets_storage
from book_lamp.services.mock_storage import MockStorage
from book_lamp.services.sheets_storage import GoogleSheetsStorage
from book_lamp.utils import is_valid_isbn13, parse_publication_year
from book_lamp.utils.libib_import import parse_libib_csv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)
logging.getLogger("book_lamp").setLevel(logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

app = Flask(__name__)

# Test mode configuration
TEST_MODE = os.environ.get("TEST_MODE", "0") == "1"
TEST_ISBN = "9780000000000"

# Initialize Google Sheets storage
storage: Any
if TEST_MODE:
    # In test mode, use a mock storage
    storage = MockStorage()
else:
    # Use different sheet names for production and development
    # FLASK_DEBUG=True or lack of FLASK_ENV=production indicates development
    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"
    storage = GoogleSheetsStorage(sheet_name=sheet_name)


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


@app.route("/")
def home():
    is_authorized = storage.is_authorized()
    return render_template("home.html", is_authorized=is_authorized)


@app.route("/about")
def about():
    return render_template("about.html", version=APP_VERSION)


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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not storage.is_authorized():
            flash("Please authorize Google Sheets access first.", "info")
            return redirect(url_for("home"))
        return f(*args, **kwargs)

    return decorated_function


@app.route("/login")
def login():
    if TEST_MODE:
        return redirect(url_for("test_login"))

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
        return oauth.google.authorize_redirect(redirect_uri)
    except Exception:
        app.logger.exception("OAuth login failed")
        return (
            "<h1>Login Error</h1>"
            "<p>Failed to initiate Google OAuth login.</p>"
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

            storage.save_credentials(creds_data)

        flash("Successfully authorized Google Sheets access!", "success")
        return redirect(url_for("home"))
    except Exception:
        app.logger.exception("Failed to authorize access token")
        return (
            "<h1>Authorization Error</h1><p>Failed to complete Google OAuth authorization.</p><a href='/'>Go back</a>"
        ), 401


@app.cli.command("init-sheets")
def init_sheets_command():
    """Initialize Google Sheets with required tabs and headers."""
    if TEST_MODE:
        click.echo("Not available in test mode.")
        return
    storage.initialize_sheets()
    click.echo("Google Sheets initialized successfully.")


# -----------------------------
# Books feature
# -----------------------------


@app.route("/books/new", methods=["GET"])
@login_required
def new_book_form():
    return render_template("add_book.html")


@app.route("/books", methods=["GET"])
@login_required
def list_books():
    books = storage.get_all_books()
    all_records = storage.get_reading_records()

    # Attach records to books
    for book in books:
        book["reading_records"] = [r for r in all_records if r["book_id"] == book["id"]]
        # Sort records by start_date descending (most recent first)
        book["reading_records"].sort(
            key=lambda r: r.get("start_date", ""), reverse=True
        )

    # Sort books by the start date of their most recent reading record (reverse chronological)
    # If never read, fall back to created_at
    def get_sort_key(book):
        if book["reading_records"]:
            # records are now sorted descending, so first one is most recent
            return book["reading_records"][0].get("start_date", "")
        return book.get("created_at", "")

    books.sort(key=get_sort_key, reverse=True)
    today = datetime.date.today().isoformat()
    return render_template("books.html", books=books, today=today)


@app.route("/books/search", methods=["GET"])
@login_required
def search_books():
    query = request.args.get("q", "").strip()

    if not query:
        flash("Please enter a search query.", "info")
        return redirect(url_for("list_books"))

    try:
        books = storage.search(query)
        today = datetime.date.today().isoformat()
        return render_template(
            "books.html",
            books=books,
            today=today,
            search_query=query,
        )
    except Exception as e:
        app.logger.error(f"Search failed: {str(e)}")
        flash(f"Search error: {str(e)}", "error")
        return redirect(url_for("list_books"))


@app.route("/books/<int:book_id>/reading-records", methods=["POST"])
@login_required
def create_reading_record(book_id: int):
    status = request.form.get("status")
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    rating = int(request.form.get("rating", 0))

    if not status or not start_date:
        flash("Status and start date are required.", "error")
        return redirect(url_for("list_books"))

    storage.add_reading_record(
        book_id=book_id,
        status=status,
        start_date=start_date,
        end_date=end_date,
        rating=rating,
    )
    flash("Reading record added.", "success")
    return redirect(url_for("list_books"))


@app.route("/books", methods=["POST"])
@login_required
def create_book():
    isbn = (request.form.get("isbn", "") or "").strip().replace("-", "")

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
            "thumbnail_url": None,
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
    )
    flash("Book added successfully.", "success")
    return redirect(url_for("list_books"))


@app.route("/books/import", methods=["GET"])
@login_required
def import_books_form():
    return render_template("import_books.html")


@app.route("/books/import", methods=["POST"])
@login_required
def import_books():
    if "file" not in request.files:
        flash("No file part", "error")
        return redirect(url_for("import_books_form"))

    file = request.files["file"]
    if file.filename == "":
        flash("No selected file", "error")
        return redirect(url_for("import_books_form"))

    if file and file.filename.endswith(".csv"):
        try:
            content = file.read().decode("utf-8")
            items = parse_libib_csv(content)

            import_count = storage.bulk_import(items)
            flash(f"Successfully imported {import_count} entries", "success")
            return redirect(url_for("list_books"))
        except Exception as e:
            app.logger.error(f"Failed to import Libib CSV: {str(e)}")
            flash(f"Error importing file: {str(e)}", "error")
            return redirect(url_for("import_books_form"))

    flash("Please upload a valid CSV file.", "error")
    return redirect(url_for("import_books_form"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
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
        try:
            storage.books = []
            storage.reading_records = []
            storage.next_book_id = 1
            storage.next_record_id = 1
            return {"status": "ok"}
        except Exception as e:
            app.logger.exception("Failed to reset test storage: %s", e)
            return {
                "status": "error",
                "message": "Internal error during test reset",
            }, 500


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
