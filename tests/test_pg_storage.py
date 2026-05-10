import os

import psycopg
import pytest

from alembic import command
from alembic.config import Config
from book_lamp.services.pg_storage import PostgresStorage

# This test requires a running Postgres instance.
# In CI, pytest-docker will provide it.
# Locally, it uses the DATABASE_URL from .env or the default below.


@pytest.fixture(scope="session")
def db_url(docker_ip, docker_services):
    """Get the database URL for tests, waiting for the container to be ready."""
    port = docker_services.port_for("db", 5432)
    url = f"postgresql://book_lamp:book_lamp@{docker_ip}:{port}/book_lamp_test"

    # Wait for postgres to be ready
    def is_responsive(url):
        # Use 'postgres' database for responsiveness check as it always exists
        base_url = url.rsplit("/", 1)[0] + "/postgres"
        try:
            with psycopg.connect(base_url) as _:
                return True
        except Exception:

            return False

    docker_services.wait_until_responsive(
        timeout=30.0, pause=0.5, check=lambda: is_responsive(url)
    )

    # Ensure the test database exists
    base_url = url.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(base_url, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = 'book_lamp_test'"
        ).fetchone()
        if not exists:
            conn.execute("CREATE DATABASE book_lamp_test")

    return url


@pytest.fixture(scope="session")
def setup_database(db_url):
    """Run migrations on the test database."""
    os.environ["DATABASE_URL"] = db_url

    # Create the test database if it doesn't exist (optional, depends on environment)
    # For now, assume it's provided by pytest-docker or manually.

    # Run alembic migrations
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)
    command.upgrade(alembic_cfg, "head")

    yield db_url

    # Cleanup (optional)
    # command.downgrade(alembic_cfg, "base")


@pytest.fixture
def pg_storage(setup_database):
    """Return a PostgresStorage instance for user 1."""
    # Clear tables before each test
    with psycopg.connect(setup_database) as conn:
        with conn.transaction():
            conn.execute(
                "TRUNCATE users, books, authors, reading_records, reading_list, settings, recommendations RESTART IDENTITY CASCADE"
            )
            # Create a default user
            conn.execute(
                "INSERT INTO users (id, email, name) VALUES (1, 'user1@example.com', 'User 1')"
            )
            conn.execute(
                "INSERT INTO users (id, email, name) VALUES (2, 'user2@example.com', 'User 2')"
            )

    return PostgresStorage(user_id=1)


def test_add_book_and_get_by_isbn(pg_storage):
    pg_storage.add_book(
        isbn13="9780141036144", title="Brave New World", author="Aldous Huxley"
    )

    book = pg_storage.get_book_by_isbn("9780141036144")
    assert book is not None
    assert book["title"] == "Brave New World"
    assert "Aldous Huxley" in book["author"]
    assert book["authors"] == ["Aldous Huxley"]


def test_upsert_book_idempotency(pg_storage):
    # First insert
    pg_storage.upsert_book(
        isbn13="9780141036144", title="Brave New World", author="Aldous Huxley"
    )

    # Second call (update)
    pg_storage.upsert_book(
        isbn13="9780141036144",
        title="Brave New World (Special Edition)",
        author="Aldous Huxley",
    )

    all_books = pg_storage.get_all_books()
    assert len(all_books) == 1
    assert all_books[0]["title"] == "Brave New World (Special Edition)"


def test_multi_user_isolation(pg_storage):
    storage2 = PostgresStorage(user_id=2)

    # Add book for user 1
    book = pg_storage.add_book(isbn13="123", title="Book 1", author="Author 1")
    pg_storage.add_reading_record(
        book_id=book["id"], status="Completed", start_date="2024-01-01"
    )

    # Check user 2 sees no records
    assert len(storage2.get_reading_records()) == 0

    # Add record for user 2
    storage2.add_reading_record(
        book_id=book["id"], status="In Progress", start_date="2024-02-01"
    )

    assert len(pg_storage.get_reading_records()) == 1
    assert pg_storage.get_reading_records()[0]["status"] == "Completed"

    assert len(storage2.get_reading_records()) == 1
    assert storage2.get_reading_records()[0]["status"] == "In Progress"


def test_bulk_import(pg_storage):
    items = [
        {
            "book": {
                "isbn13": "111",
                "title": "Book 1",
                "author": "Author 1",
                "publication_year": 2020,
            },
            "record": {
                "status": "Completed",
                "start_date": "2024-01-01",
                "end_date": "2024-01-10",
                "rating": 5,
            },
        },
        {
            "book": {
                "isbn13": "222",
                "title": "Book 2",
                "author": "Author 2",
                "publication_year": 2021,
            },
            "record": {"status": "In Progress", "start_date": "2024-02-01"},
        },
    ]

    count = pg_storage.bulk_import(items)
    assert count == 2

    history = pg_storage.get_reading_history()
    assert len(history) == 2

    # Test idempotency of bulk import
    count2 = pg_storage.bulk_import(items)
    assert count2 == 2
    assert len(pg_storage.get_all_books()) == 2
    assert len(pg_storage.get_reading_records()) == 2


def test_start_reading(pg_storage):
    book = pg_storage.add_book(isbn13="123", title="Book 1", author="Author 1")
    pg_storage.add_to_reading_list(book["id"])

    assert len(pg_storage.get_reading_list()) == 1

    pg_storage.start_reading(book["id"])

    assert len(pg_storage.get_reading_list()) == 0
    records = pg_storage.get_reading_records()
    assert len(records) == 1
    assert records[0]["status"] == "In Progress"


def test_settings_round_trip(pg_storage):
    pg_storage.update_setting("theme", "dark")
    pg_storage.update_setting("language", "en-GB")

    settings = pg_storage.get_settings()
    assert settings["theme"] == "dark"
    assert settings["language"] == "en-GB"

    pg_storage.update_setting("theme", "light")
    assert pg_storage.get_settings()["theme"] == "light"


def test_recommendations_round_trip(pg_storage):
    recs = [
        {
            "title": "Rec 1",
            "author": "Author A",
            "isbn13": "111",
            "justification": "Because reasons",
        },
        {
            "title": "Rec 2",
            "author": "Author B",
            "isbn13": "222",
            "justification": "More reasons",
        },
    ]

    pg_storage.save_recommendations(recs)

    saved = pg_storage.get_recommendations()
    assert len(saved) == 2
    assert saved[0]["title"] in ["Rec 1", "Rec 2"]
