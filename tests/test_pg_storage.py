"""PostgreSQL storage integration tests.

These tests need a running Postgres, which pytest-docker provides by bringing up
compose.yaml with podman-compose. A host that cannot start containers skips them
(see `podman_services` in conftest) rather than erroring.
"""

import os
import shutil

import psycopg
import pytest

from alembic import command
from alembic.config import Config
from book_lamp.services.pg_storage import PostgresStorage

# The compose command is only the first hurdle: whether the runtime can actually
# start a container is settled by the `podman_services` fixture.
pytestmark = pytest.mark.skipif(
    shutil.which("podman-compose") is None,
    reason="podman-compose is not installed",
)


@pytest.fixture(scope="session")
def db_url(docker_ip, podman_services):
    """Get the database URL for tests, waiting for the container to be ready."""
    port = podman_services.port_for("db", 5432)
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

    podman_services.wait_until_responsive(timeout=30.0, pause=0.5, check=lambda: is_responsive(url))

    # Ensure the test database exists
    base_url = url.rsplit("/", 1)[0] + "/postgres"
    with psycopg.connect(base_url, autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = 'book_lamp_test'").fetchone()
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
                "TRUNCATE users, books, authors, readings, reading_list, settings, recommendations RESTART IDENTITY CASCADE"
            )
            # Create a default user
            conn.execute("INSERT INTO users (id, email, name) VALUES (1, 'user1@example.com', 'User 1')")
            conn.execute("INSERT INTO users (id, email, name) VALUES (2, 'user2@example.com', 'User 2')")

    return PostgresStorage(user_id=1)


def test_add_book_and_get_by_isbn(pg_storage):
    pg_storage.add_book(isbn13="9780141036144", title="Brave New World", author="Aldous Huxley")

    book = pg_storage.get_book_by_isbn("9780141036144")
    assert book is not None
    assert book["title"] == "Brave New World"
    assert "Aldous Huxley" in book["author"]
    assert book["authors"] == ["Aldous Huxley"]


def test_upsert_book_idempotency(pg_storage):
    # First insert
    pg_storage.upsert_book(isbn13="9780141036144", title="Brave New World", author="Aldous Huxley")

    # Second call (update)
    pg_storage.upsert_book(
        isbn13="9780141036144",
        title="Brave New World (Special Edition)",
        author="Aldous Huxley",
    )

    # Directly check the database books table for the upsert result
    with pg_storage.pool.connection() as conn:
        all_books = conn.execute("SELECT * FROM books WHERE isbn13 = '9780141036144'").fetchall()
    assert len(all_books) == 1
    assert all_books[0]["title"] == "Brave New World (Special Edition)"


def test_multi_user_isolation(pg_storage):
    storage2 = PostgresStorage(user_id=2)

    # Add book for user 1
    book = pg_storage.add_book(isbn13="123", title="Book 1", author="Author 1")
    pg_storage.add_reading(book_id=book["id"], status="Completed", start_date="2024-01-01", end_date="2024-01-10")

    # Check user 2 sees no records
    assert len(storage2.get_readings()) == 0

    # Add record for user 2
    storage2.add_reading(book_id=book["id"], status="In Progress", start_date="2024-02-01")

    assert len(pg_storage.get_readings()) == 1
    assert pg_storage.get_readings()[0]["status"] == "Completed"

    assert len(storage2.get_readings()) == 1
    assert storage2.get_readings()[0]["status"] == "In Progress"


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
    assert len(pg_storage.get_readings()) == 2


def test_start_reading(pg_storage):
    book = pg_storage.add_book(isbn13="123", title="Book 1", author="Author 1")
    pg_storage.add_to_reading_list(book["id"])

    assert len(pg_storage.get_reading_list()) == 1

    pg_storage.start_reading(book["id"])

    assert len(pg_storage.get_reading_list()) == 0
    records = pg_storage.get_readings()
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


def test_upsert_book_does_not_replace_a_real_category(pg_storage):
    """A Dewey code must not undo a category the Book already has (ADR-0002)."""
    pg_storage.add_book(
        isbn13="9780141036144",
        title="Brave New World",
        author="Aldous Huxley",
        bisac_category="FICTION / General",
        bisac_main_category="FICTION",
        bisac_sub_category="General",
    )

    pg_storage.upsert_book(
        isbn13="9780141036144",
        title="Brave New World",
        author="Aldous Huxley",
        bisac_category="823.914",
        bisac_main_category="823.914",
    )

    book = pg_storage.get_book_by_isbn("9780141036144")
    assert book["bisac_category"] == "FICTION / General"
    assert book["bisac_main_category"] == "FICTION"


def test_bulk_import_does_not_replace_a_real_category(pg_storage):
    """The enrichment backfill writes through bulk_import; it must not clobber.

    This is the Postgres half of `test_enhance_books_preserves_bisac`, which only
    ever ran against the in-memory adapter.
    """
    book = pg_storage.add_book(
        isbn13="9780141036144",
        title="Brave New World",
        author="Aldous Huxley",
        bisac_category="HISTORY / Europe",
        bisac_main_category="HISTORY",
        bisac_sub_category="Europe",
    )

    pg_storage.bulk_import(
        [
            {
                "book": {
                    "isbn13": "9780141036144",
                    "title": "Brave New World",
                    "author": "Aldous Huxley",
                    "publication_year": 1932,
                    "bisac_category": "823.914",
                },
                "record": None,
            }
        ]
    )

    updated = pg_storage.get_book_by_id(book["id"])
    assert updated["bisac_category"] == "HISTORY / Europe"
    assert updated["bisac_main_category"] == "HISTORY"


def test_bulk_import_keeps_a_category_when_the_row_carries_none(pg_storage):
    """An import row with no category must not erase the stored one.

    The in-memory adapter already preserved it; Postgres wrote NULL over it.
    """
    book = pg_storage.add_book(
        isbn13="9780141036144",
        title="Brave New World",
        author="Aldous Huxley",
        bisac_category="FICTION / General",
        bisac_main_category="FICTION",
        bisac_sub_category="General",
    )

    pg_storage.bulk_import(
        [
            {
                "book": {
                    "isbn13": "9780141036144",
                    "title": "Brave New World",
                    "author": "Aldous Huxley",
                    "publication_year": 1932,
                },
                "record": None,
            }
        ]
    )

    updated = pg_storage.get_book_by_id(book["id"])
    assert updated["bisac_category"] == "FICTION / General"
    assert updated["bisac_main_category"] == "FICTION"


def test_bulk_import_replaces_a_dewey_category(pg_storage):
    """The other half of the rule: a real category still replaces a Dewey one."""
    book = pg_storage.add_book(
        isbn13="9780141036144",
        title="Brave New World",
        author="Aldous Huxley",
        bisac_category="823.914",
    )

    pg_storage.bulk_import(
        [
            {
                "book": {
                    "isbn13": "9780141036144",
                    "title": "Brave New World",
                    "author": "Aldous Huxley",
                    "publication_year": 1932,
                    "bisac_category": "FICTION / General",
                    "bisac_main_category": "FICTION",
                    "bisac_sub_category": "General",
                },
                "record": None,
            }
        ]
    )

    updated = pg_storage.get_book_by_id(book["id"])
    assert updated["bisac_category"] == "FICTION / General"
    assert updated["bisac_main_category"] == "FICTION"


def test_find_user_id_by_email_resolves_the_reader_and_refuses_strangers(pg_storage):
    """The MCP service resolves its reader this way, and must not create one.

    An address the database has never seen is a refusal rather than a new
    account: the server reads as one configured reader, so it cannot be talked
    into serving somebody else.
    """
    assert PostgresStorage.find_user_id_by_email("user1@example.com") == 1
    assert PostgresStorage.find_user_id_by_email("user2@example.com") == 2
    assert PostgresStorage.find_user_id_by_email("stranger@example.com") is None

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 2


def test_the_rename_migration_left_the_table_indexes_and_constraint_renamed(pg_storage):
    """0004 renames the table, its three indexes and its primary-key constraint.

    Asserted against the schema rather than the rows: a migration that ran but
    left the old index or constraint names behind would still pass every storage
    test, because Postgres does not care what an index is called.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        tables = {
            row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
        }
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'readings'"
            ).fetchall()
        }
        constraints = {
            row[0]
            for row in conn.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid = 'readings'::regclass"
            ).fetchall()
        }

    assert "readings" in tables
    assert "reading_records" not in tables
    assert {"idx_readings_user_id", "idx_readings_status", "idx_readings_book_id"} <= indexes
    assert "readings_pkey" in constraints
