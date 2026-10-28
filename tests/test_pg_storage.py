"""PostgreSQL storage integration tests.

These tests need a running Postgres, which pytest-docker provides by bringing up
compose.yaml with podman-compose. A host that cannot start containers skips them
(see `podman_services` in conftest) rather than erroring.
"""

import os
import shutil
from uuid import uuid4

import psycopg
import pytest

from alembic import command
from alembic.config import Config
from book_lamp.services.pg_storage import PostgresStorage
from book_lamp.utils.authors import parse

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
    pg_storage.add_book(isbn13="9780141036144", title="Brave New World", authors=["Aldous Huxley"])

    book = pg_storage.get_book_by_isbn("9780141036144")
    assert book is not None
    assert book["title"] == "Brave New World"
    assert "Aldous Huxley" in book["author"]
    assert book["authors"] == ["Aldous Huxley"]


def test_upsert_book_idempotency(pg_storage):
    # First insert
    pg_storage.upsert_book(isbn13="9780141036144", title="Brave New World", authors=["Aldous Huxley"])

    # Second call (update)
    pg_storage.upsert_book(
        isbn13="9780141036144",
        title="Brave New World (Special Edition)",
        authors=["Aldous Huxley"],
    )

    # Directly check the database books table for the upsert result
    with pg_storage.pool.connection() as conn:
        all_books = conn.execute("SELECT * FROM books WHERE isbn13 = '9780141036144'").fetchall()
    assert len(all_books) == 1
    assert all_books[0]["title"] == "Brave New World (Special Edition)"


def test_multi_user_isolation(pg_storage):
    storage2 = PostgresStorage(user_id=2)

    # Add book for user 1
    book = pg_storage.add_book(isbn13="123", title="Book 1", authors=["Author 1"])
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
    book = pg_storage.add_book(isbn13="123", title="Book 1", authors=["Author 1"])
    pg_storage.add_to_reading_list(book["id"])

    assert len(pg_storage.get_reading_list()) == 1

    pg_storage.start_reading(book["id"])

    assert len(pg_storage.get_reading_list()) == 0
    records = pg_storage.get_readings()
    assert len(records) == 1
    assert records[0]["status"] == "In Progress"


def test_add_reading_again_with_the_same_status_and_start_date(pg_storage):
    """A second Reading may match the first and must still be a second Reading.

    A Reading is one attempt at a Book, so the same status and start date is a
    re-read rather than a duplicate. The adapter used to treat the match as a
    duplicate and return the earlier row, discarding what had just been entered.
    """
    book = pg_storage.add_book(isbn13="123", title="Book 1", authors=["Author 1"])

    first = pg_storage.add_reading(book_id=book["id"], status="In Progress", start_date="2024-01-01")
    second = pg_storage.add_reading(book_id=book["id"], status="In Progress", start_date="2024-01-01", rating=5)

    assert second["id"] != first["id"]
    assert second["rating"] == 5
    assert len(pg_storage.get_readings(book_id=book["id"])) == 2


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
        authors=["Aldous Huxley"],
        bisac_category="FICTION / General",
        bisac_main_category="FICTION",
        bisac_sub_category="General",
    )

    pg_storage.upsert_book(
        isbn13="9780141036144",
        title="Brave New World",
        authors=["Aldous Huxley"],
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
        authors=["Aldous Huxley"],
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
        authors=["Aldous Huxley"],
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
        authors=["Aldous Huxley"],
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


def test_a_books_authors_keep_the_order_they_were_entered_in(pg_storage):
    """A Book's authors are its links, in `position` order (ADR-0005).

    William Gibson is created first here, so ordering the links by `author_id` —
    what the reads did before 0006 — would name this Book the other way round.
    """
    pg_storage.add_book(isbn13="9780441013593", title="Neuromancer", authors=["William Gibson"])
    book = pg_storage.add_book(
        isbn13="9780575081567",
        title="The Difference Engine",
        authors=["Bruce Sterling", "William Gibson"],
    )
    pg_storage.add_to_reading_list(book["id"])

    expected = ["Bruce Sterling", "William Gibson"]
    display = "Bruce Sterling, William Gibson"

    for read in (
        pg_storage.get_book_by_id(book["id"]),
        pg_storage.get_book_by_isbn("9780575081567"),
        next(b for b in pg_storage.get_all_books() if b["id"] == book["id"]),
    ):
        assert read["authors"] == expected
        assert read["author"] == display

    assert pg_storage.get_reading_list()[0]["author"] == display

    pg_storage.start_reading(book["id"])
    history = pg_storage.get_reading_history()[0]
    assert history["book_authors"] == expected
    assert history["book_author"] == display


def test_both_adapters_present_a_books_authors_the_same_way(pg_storage):
    """The in-memory adapter and Postgres agree on a Book's authors (ADR-0005)."""
    from book_lamp.services.mock_storage import MockStorage

    authors = ["Bruce Sterling", "William Gibson"]
    book = pg_storage.add_book(isbn13="9780575081567", title="The Difference Engine", authors=authors)
    in_memory = MockStorage().add_book(isbn13="9780575081567", title="The Difference Engine", authors=authors)

    read = pg_storage.get_book_by_id(book["id"])
    assert read["authors"] == in_memory["authors"]
    assert read["author"] == in_memory["author"]


def test_0008_left_a_required_position_and_no_author_column(pg_storage):
    """The schema 0008 writes, asserted rather than the rows it leaves.

    A migration that ran but left the column, the default or the check behind
    would still pass every storage test, because nothing reads the column any
    more — so the shape is read off the catalogue here.
    """
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        book_columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'books'"
            ).fetchall()
        }
        position = conn.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'book_authors' AND column_name = 'position'"
        ).fetchone()
        check = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'book_authors'::regclass AND conname = 'book_authors_position_check'"
        ).fetchone()

    assert "author" not in book_columns
    assert position is not None
    assert position[0] == "NO"
    assert position[1] is None  # nothing may write a link without an order
    assert check is not None
    assert "position" in check[0] and "> 0" in check[0]


@pytest.fixture
def own_database(setup_database, monkeypatch):
    """A database of this test's own, so a migration can be stopped part-way.

    `alembic/env.py` prefers `DATABASE_URL` to the config's URL, so the migrations
    are aimed at this database by aiming that variable at it. The shared pool is
    opened against the test database first: it keeps the conninfo it was built
    with, so nothing reconnects here.
    """
    from book_lamp.services.pg_storage import get_pool

    get_pool()

    server = setup_database.rsplit("/", 1)[0]
    name = f"book_lamp_migration_{uuid4().hex[:8]}"
    with psycopg.connect(f"{server}/postgres", autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')

    monkeypatch.setenv("DATABASE_URL", f"{server}/{name}")
    try:
        yield f"{server}/{name}"
    finally:
        with psycopg.connect(f"{server}/postgres", autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def _upgrade_database(url, revision):
    """Run the migrations up to `revision` against the database at `url`."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, revision)


def _write_book_as_the_release_before_0006_did(url, isbn13, title, author):
    """A Book as that release left it: the string, and links in split order.

    `book_authors` had no `position` then, so its `_update_book_authors` inserted
    one row per name `parse` returned, in that order.
    """
    with psycopg.connect(url) as conn:
        book_id = conn.execute(
            "INSERT INTO books (isbn13, title, author) VALUES (%s, %s, %s) RETURNING id",
            [isbn13, title, author],
        ).fetchone()[0]
        for name in parse(author):
            author_id = conn.execute(
                "INSERT INTO authors (name) VALUES (%s) ON CONFLICT (name) DO UPDATE "
                "SET name = EXCLUDED.name RETURNING id",
                [name],
            ).fetchone()[0]
            conn.execute("INSERT INTO book_authors (book_id, author_id) VALUES (%s, %s)", [book_id, author_id])
    return book_id


def _author_names_in_order(url, isbn13):
    """The names of the authors one Book links to, in `position` order."""
    with psycopg.connect(url) as conn:
        return conn.execute(
            """
            SELECT array_agg(a.name ORDER BY ba.position)
            FROM books b
            JOIN book_authors ba ON ba.book_id = b.id
            JOIN authors a ON a.id = ba.author_id
            WHERE b.isbn13 = %s
            """,
            [isbn13],
        ).fetchone()[0]


def test_0007_repairs_the_two_strings_the_splitter_mangled(own_database):
    """The repair reads the string, so what it writes joins back to it exactly."""
    _upgrade_database(own_database, "0005")
    _write_book_as_the_release_before_0006_did(
        own_database, "9781398505292", "A Book", "To Be To Be Confirmed Simon & Schuster"
    )
    _write_book_as_the_release_before_0006_did(
        own_database, "9781785781438", "Another Book", "Sutherland, John, John Crace"
    )
    # A Book whose string really is comma-separated authors, which the splitter
    # read correctly; the repair must leave it alone.
    _write_book_as_the_release_before_0006_did(
        own_database, "9780441013593", "Dune", "Frank Herbert, Kevin J. Anderson, Brian Herbert"
    )

    _upgrade_database(own_database, "head")

    assert _author_names_in_order(own_database, "9781398505292") == ["To Be To Be Confirmed Simon & Schuster"]
    assert _author_names_in_order(own_database, "9781785781438") == ["Sutherland, John", "John Crace"]
    assert _author_names_in_order(own_database, "9780441013593") == [
        "Frank Herbert",
        "Kevin J. Anderson",
        "Brian Herbert",
    ]

    with psycopg.connect(own_database) as conn:
        # The halves the bad split invented are referenced by nothing now, so
        # they go: they named no Book and no person (ADR-0005).
        leftovers = conn.execute(
            "SELECT name FROM authors WHERE name IN "
            "('To Be To Be Confirmed Simon', 'Schuster', 'Sutherland', 'John')"
        ).fetchall()
    assert leftovers == []


def test_0008_numbers_a_link_the_release_before_0006_wrote(own_database):
    """Such a link carries the default 0, and 0008 leaves no link unordered."""
    _upgrade_database(own_database, "0007")
    _write_book_as_the_release_before_0006_did(
        own_database, "9780441013593", "Dune", "Frank Herbert, Kevin J. Anderson, Brian Herbert"
    )
    with psycopg.connect(own_database) as conn:
        assert conn.execute("SELECT DISTINCT position FROM book_authors").fetchall() == [(0,)]

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        numbered = conn.execute("""
            SELECT a.name, ba.position
            FROM book_authors ba
            JOIN authors a ON a.id = ba.author_id
            JOIN books b ON b.id = ba.book_id
            WHERE b.isbn13 = '9780441013593'
            ORDER BY ba.position
            """).fetchall()
    assert numbered == [("Frank Herbert", 1), ("Kevin J. Anderson", 2), ("Brian Herbert", 3)]


def test_0008_refuses_a_book_whose_links_cannot_reproduce_its_string(own_database):
    """A Book needing attention stops the drop instead of losing its author."""
    _upgrade_database(own_database, "0007")
    with psycopg.connect(own_database) as conn:
        book_id = conn.execute(
            "INSERT INTO books (isbn13, title, author) VALUES ('9780441013593', 'Dune', 'Frank Herbert') RETURNING id"
        ).fetchone()[0]
        author_id = conn.execute("INSERT INTO authors (name) VALUES ('Somebody Else') RETURNING id").fetchone()[0]
        conn.execute(
            "INSERT INTO book_authors (book_id, author_id, position) VALUES (%s, %s, 1)",
            [book_id, author_id],
        )

    with pytest.raises(RuntimeError, match="Refusing to drop books.author"):
        _upgrade_database(own_database, "head")

    # The refusal is the whole migration, not just the drop: the column is still
    # there and the revision is not stamped.
    with psycopg.connect(own_database) as conn:
        held = conn.execute("SELECT author FROM books WHERE isbn13 = '9780441013593'").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert held == "Frank Herbert"
    assert stamped == "0007"
