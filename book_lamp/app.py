import datetime
import logging
import os
from functools import wraps
from typing import Any, Optional

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
from book_lamp.services.sheets_storage import GoogleSheetsStorage

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
    storage = None
else:
    # Use different sheet names for production and development
    # FLASK_DEBUG=True or lack of FLASK_ENV=production indicates development
    is_prod = os.environ.get("FLASK_ENV") == "production"
    sheet_name = "BookLampData" if is_prod else "DevBookLampData"
    storage = GoogleSheetsStorage(sheet_name=sheet_name)


@app.route("/")
def home():
    is_authorized = TEST_MODE or storage.is_authorized()
    return render_template("home.html", is_authorized=is_authorized)


@app.route("/about")
def about():
    return "<h1>About</h1><p>This is a simple Flask web application that stores your book list in Google Sheets.</p>"


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
        if not TEST_MODE and not storage.is_authorized():
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
    except Exception as e:
        app.logger.error(f"OAuth login failed: {str(e)}")
        return (
            f"<h1>Login Error</h1>"
            f"<p>Failed to initiate Google OAuth login.</p>"
            f"<p>Error: {str(e)}</p>"
            f"<p>Please check that GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set correctly.</p>"
            f"<a href='/'>Go back</a>"
        ), 500


@app.route("/authorize")
def authorize():
    try:
        token = oauth.google.authorize_access_token()
        app.logger.info("OAuth token received successfully")

        # Save the token for GoogleSheetsStorage
        if not TEST_MODE:
            # Bridging Authlib token to Google-auth format
            creds_data = {
                "token": token.get("access_token"),
                "refresh_token": token.get("refresh_token"),
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": app.config["GOOGLE_CLIENT_ID"],
                "client_secret": app.config["GOOGLE_CLIENT_SECRET"],
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
    except Exception as e:
        app.logger.error(f"Failed to authorize access token: {str(e)}")
        return (
            f"<h1>Authorization Error</h1>"
            f"<p>Failed to complete Google OAuth authorization.</p>"
            f"<p>Error: {str(e)}</p>"
            f"<a href='/'>Go back</a>"
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


def is_valid_isbn13(isbn: str) -> bool:
    """Validate ISBN-13 using checksum algorithm and format constraints."""
    if TEST_MODE and isbn == TEST_ISBN:
        return True

    if len(isbn) != 13 or not isbn.isdigit():
        return False
    checksum = 0
    for index, char in enumerate(isbn[:12]):
        digit = ord(char) - 48
        weight = 1 if index % 2 == 0 else 3
        checksum += digit * weight
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit == (ord(isbn[12]) - 48)


def parse_publication_year(publish_date: Optional[str]) -> Optional[int]:
    if not publish_date:
        return None
    for token in (
        publish_date.replace("-", " ").replace("/", " ").replace(",", " ").split()
    ):
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


@app.route("/books/new", methods=["GET"])
@login_required
def new_book_form():
    return render_template("add_book.html")


@app.route("/books", methods=["GET"])
@login_required
def list_books():
    books = storage.get_all_books()
    # Sort by created_at descending
    books.sort(key=lambda b: b.get("created_at", ""), reverse=True)
    return render_template("books.html", books=books)


@app.route("/books", methods=["POST"])
@login_required
def create_book():
    isbn = (request.form.get("isbn", "") or "").strip().replace("-", "")
    if not is_valid_isbn13(isbn):
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
    )
    flash("Book added successfully.", "success")
    return redirect(url_for("list_books"))


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
    # Mock storage for tests
    class MockStorage:
        def __init__(self):
            self.books = []
            self.next_id = 1

        def get_all_books(self):
            return self.books

        def get_book_by_id(self, book_id):
            for book in self.books:
                if book["id"] == book_id:
                    return book
            return None

        def get_book_by_isbn(self, isbn13):
            for book in self.books:
                if book["isbn13"] == isbn13:
                    return book
            return None

        def add_book(
            self, isbn13, title, author, publication_year=None, thumbnail_url=None
        ):
            book = {
                "id": self.next_id,
                "isbn13": isbn13,
                "title": title,
                "author": author,
                "publication_year": publication_year,
                "thumbnail_url": thumbnail_url,
                "created_at": "2024-01-01T00:00:00",
            }
            self.books.append(book)
            self.next_id += 1
            return book

        def delete_book(self, book_id):
            for i, book in enumerate(self.books):
                if book["id"] == book_id:
                    self.books.pop(i)
                    return True
            return False

    storage = MockStorage()

    @app.route("/test/reset", methods=["POST"])
    def test_reset():
        """Reset test storage."""
        try:
            storage.books = []
            storage.next_id = 1
            return {"status": "ok"}
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
