import os
from functools import wraps
from typing import Any, Callable, Optional

import click
from authlib.integrations.flask_client import OAuth  # type: ignore
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func

load_dotenv()

app = Flask(__name__)

# Database configuration
# Enable lightweight, file-backed SQLite DB in test mode for Playwright
TEST_MODE = os.environ.get("TEST_MODE", "0") == "1"
if TEST_MODE:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DB_URL", f"sqlite:////{os.path.abspath('e2e_test.db')}"
    )
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DB_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)


class User(db.Model):  # type: ignore
    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=True)
    google_id = db.Column(db.String(120), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    name = db.Column(db.String(120), nullable=True)


class AllowedUser(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)


class Book(db.Model):  # type: ignore
    id = db.Column(db.Integer, primary_key=True)
    isbn13 = db.Column(db.String(13), unique=True, nullable=False, index=True)
    title = db.Column(db.String(300), nullable=False)
    author = db.Column(db.String(200), nullable=False)
    publication_year = db.Column(db.Integer, nullable=True)
    thumbnail_url = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )


def login_required(f: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if "user_id" not in session:
            return redirect(url_for("unauthorized"))

        return f(*args, **kwargs)

    return decorated_function


@app.route("/")
def home():
    if "user_id" in session:
        user = db.session.get(User, session["user_id"])
        return f'<h1>Hello {user.name}!</h1><p>My simple Python web app is running!</p><a href="/logout">Logout</a>'
    return '<h1>Hello World!</h1><p>You are not logged in.</p><a href="/login">Login with Google</a>'


@app.route("/about")
@login_required
def about():
    return "<h1>About</h1><p>This is a simple Flask web application.</p>"


@app.route("/unauthorized")
def unauthorized():
    return render_template("unauthorized.html"), 401


# Secret key for session management
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

# Google OAuth configuration
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID")
app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET")
app.config["GOOGLE_DISCOVERY_URL"] = (
    "https://accounts.google.com/.well-known/openid-configuration"
)

oauth = OAuth(app)
oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url=app.config["GOOGLE_DISCOVERY_URL"],
    client_kwargs={"scope": "openid email profile"},
)


@app.route("/login")
def login():
    if (
        "CODESPACE_NAME" in os.environ
        and "GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN" in os.environ
    ):
        codespace_name = os.environ["CODESPACE_NAME"]
        domain = os.environ["GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN"]
        redirect_uri = f"https://{codespace_name}-5000.{domain}/authorize"
    else:
        redirect_uri = url_for("authorize", _external=True)
    if TEST_MODE:
        # In test mode, skip external OAuth to keep e2e deterministic.
        return redirect(url_for("test_login"))
    return oauth.google.authorize_redirect(redirect_uri)


@app.route("/authorize")
def authorize():
    token = oauth.google.authorize_access_token()
    userinfo = token.get("userinfo")
    if not userinfo or "email" not in userinfo:
        return redirect(url_for("unauthorized"))

    allowed = AllowedUser.query.filter_by(email=userinfo["email"]).first()
    if not allowed:
        return redirect(url_for("unauthorized"))

    user = User.query.filter_by(email=userinfo["email"]).first()
    if not user:
        user = User(
            user_name=userinfo.get("email", ""),
            google_id=userinfo.get("sub", None),
            email=userinfo.get("email", None),
            name=userinfo.get("name", None),
        )
        db.session.add(user)
        db.session.commit()

    session["user_id"] = user.user_id
    return redirect(url_for("home"))


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect("/")


@app.cli.command("init-db")
def init_db_command():
    """Drop all tables and re-initialize the database."""
    db.drop_all()
    db.create_all()
    click.echo("Database re-initialized (all data was deleted).")


@app.cli.command("add-user")
@click.argument("email")
def add_user(email):
    """Add a user to the allow list."""
    if AllowedUser.query.filter_by(email=email).first():
        click.echo("User already allowed.")
        return

    allowed = AllowedUser(email=email)
    db.session.add(allowed)
    db.session.commit()
    click.echo(f"User {email} added to allow list.")


@app.cli.command("list-users")
def list_users():
    """List all users in the allow list."""
    users = AllowedUser.query.all()
    for user in users:
        print(user.email)


# -----------------------------
# Books feature
# -----------------------------


def is_valid_isbn13(isbn: str) -> bool:
    """Validate ISBN-13 using checksum algorithm and format constraints."""
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
    # Extract first 4-digit year anywhere in the string (e.g., '2019-05-02', 'July 2019')
    for token in (
        publish_date.replace("-", " ").replace("/", " ").replace(",", " ").split()
    ):
        if len(token) == 4 and token.isdigit():
            return int(token)
    return None


@app.route("/books/new", methods=["GET"])
def new_book_form():
    return render_template("add_book.html")


@app.route("/books", methods=["GET"])
def list_books():
    books = Book.query.order_by(Book.created_at.desc()).all()
    return render_template("books.html", books=books)


@app.route("/books", methods=["POST"])
def create_book():
    isbn = (request.form.get("isbn", "") or "").strip().replace("-", "")
    if not is_valid_isbn13(isbn):
        flash("Please enter a valid 13-digit ISBN.", "error")
        return redirect(url_for("new_book_form"))

    # Avoid duplicates
    existing = Book.query.filter_by(isbn13=isbn).first()
    if existing:
        flash("This book has already been added.", "info")
        return redirect(url_for("list_books"))

    # Lookup via Open Library Books API (stubbed in TEST_MODE)
    from book_lamp.services.book_lookup import lookup_book_by_isbn13

    # Deterministic stub for E2E tests
    if TEST_MODE and isbn == "9780000000000":
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
            return redirect(url_for("new_book_form"))

    if not data:
        flash("No book data found for that ISBN.", "error")
        return redirect(url_for("new_book_form"))

    title = data.get("title") or ""
    author = data.get("author") or ""
    publish_date = data.get("publish_date")
    year = parse_publication_year(publish_date)
    thumbnail_url = data.get("thumbnail_url")

    if not title or not author:
        flash("The external service did not return required fields.", "error")
        return redirect(url_for("new_book_form"))

    book = Book(
        isbn13=isbn,
        title=title[:300],
        author=author[:200],
        publication_year=year,
        thumbnail_url=(thumbnail_url[:500] if thumbnail_url else None),
    )
    db.session.add(book)
    db.session.commit()
    flash("Book added successfully.", "success")
    return redirect(url_for("list_books"))


@app.route("/books/<int:book_id>/delete", methods=["POST"])
def delete_book(book_id: int):
    book = db.session.get(Book, book_id)
    if not book:
        flash("Book not found.", "error")
        return redirect(url_for("list_books"))

    db.session.delete(book)
    db.session.commit()
    flash("Book deleted.", "success")
    return redirect(url_for("list_books"))


# -----------------------------
# Test utilities (enabled only when TEST_MODE=1)
# -----------------------------

if TEST_MODE:

    @app.route("/test/reset", methods=["POST"])
    def test_reset():
        """Reset database and seed a default allowed and app user.

        Only available when TEST_MODE=1.
        """
        db.drop_all()
        db.create_all()

        # Seed allowed user and a matching application user
        allowed_email = os.environ.get("TEST_ALLOWED_EMAIL", "test.user@example.com")
        allowed = AllowedUser(email=allowed_email)
        db.session.add(allowed)
        user = User(user_name=allowed_email, email=allowed_email, name="Test User")
        db.session.add(user)
        db.session.commit()
        return {"status": "ok"}

    @app.route("/test/login", methods=["GET"])  # simple GET for convenience
    def test_login():
        """Log in as the seeded test user.

        Only available when TEST_MODE=1.
        """
        allowed_email = os.environ.get("TEST_ALLOWED_EMAIL", "test.user@example.com")
        user = User.query.filter_by(email=allowed_email).first()
        if not user:
            # If DB isn't reset yet, create minimal seed on the fly
            allowed = AllowedUser(email=allowed_email)
            db.session.add(allowed)
            user = User(user_name=allowed_email, email=allowed_email, name="Test User")
            db.session.add(user)
            db.session.commit()
        session["user_id"] = user.user_id
        return redirect(url_for("home"))


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    app.run(debug=debug_mode)
