"""PostgreSQL storage integration tests.

These tests need a running Postgres, which pytest-docker provides by bringing up
compose.yaml with podman-compose. A host that cannot start containers skips them
(see `podman_services` in conftest) rather than erroring.
"""

import os
import shutil
import threading
import time
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


def test_the_subtitle_fill_does_not_land_beside_an_edited_title(pg_storage):
    """A provider answer is dropped when the reader changed the title meanwhile.

    The edit route can store ``Piranesi: A Novel`` with no subtitle while the
    provider is being asked; writing ``A Novel`` beside that title would store
    the same words twice, so the write guards on the title it read.
    """
    from scripts.backfill_subtitles import _write_subtitle

    book = pg_storage.add_book(isbn13="9780241181346", title="Piranesi", authors=["Susanna Clarke"])
    read_book = {"id": book["id"], "title": "Piranesi"}
    pg_storage.update_book(
        book_id=book["id"],
        isbn13="9780241181346",
        title="Piranesi: A Novel",
        authors=["Susanna Clarke"],
    )

    wrote = _write_subtitle(pg_storage.pool, read_book, "9780241181346", "A Novel")

    assert wrote is False
    stored = pg_storage.get_book_by_id(book["id"])
    assert stored["title"] == "Piranesi: A Novel"
    assert stored["subtitle"] is None


def test_subtitle_is_stored_and_updated(pg_storage):
    pg_storage.add_book(
        isbn13="9780241181346",
        title="The Spy and the Traitor",
        subtitle="The Greatest Espionage Story of the Cold War",
        authors=["Ben Macintyre"],
    )
    book = pg_storage.get_book_by_isbn("9780241181346")
    assert book["title"] == "The Spy and the Traitor"
    assert book["subtitle"] == "The Greatest Espionage Story of the Cold War"

    pg_storage.update_book(
        book_id=book["id"],
        isbn13="9780241181346",
        title="The Spy and the Traitor",
        subtitle="A True Story",
        authors=["Ben Macintyre"],
    )
    assert pg_storage.get_book_by_id(book["id"])["subtitle"] == "A True Story"

    pg_storage.add_reading(book["id"], "Completed", "2024-01-01", "2024-01-10")
    assert pg_storage.get_reading_history()[0]["book_title"] == ("The Spy and the Traitor: A True Story")


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


def test_bulk_import_keeps_a_title_the_reader_kept_whole(pg_storage):
    """A metadata backfill resends every stored Book; it must not re-split one.

    Clearing the subtitle is how a wrong split is undone, and the backfill runs
    even when a lookup finds nothing new, so the stored pair has to survive it.
    """
    book = pg_storage.add_book(isbn13="9780241181346", title="Foo Bar: Baz", authors=["An Author"])

    pg_storage.bulk_import(
        [
            {
                "book": {
                    "isbn13": "9780241181346",
                    "title": "Foo Bar: Baz",
                    "author": "An Author",
                    "publication_year": None,
                },
                "record": None,
            }
        ]
    )

    stored = pg_storage.get_book_by_id(book["id"])
    assert stored["title"] == "Foo Bar: Baz"
    assert stored["subtitle"] is None


def test_reading_history_matches_the_mock_adapter_shape(pg_storage):
    """Both adapters return ISO dates and the same Book fields for the log."""
    from book_lamp.services.mock_storage import MockStorage

    isbn = "9780241181349"
    mock = MockStorage()
    books = {
        "pg": pg_storage.add_book(
            isbn13=isbn,
            title="Piranesi",
            subtitle="A Novel",
            authors=["Susanna Clarke"],
            publication_year=2020,
            cover_url="https://example.com/cover.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        ),
        "mock": mock.add_book(
            isbn13=isbn,
            title="Piranesi",
            subtitle="A Novel",
            authors=["Susanna Clarke"],
            publication_year=2020,
            cover_url="https://example.com/cover.jpg",
            thumbnail_url="https://example.com/thumb.jpg",
        ),
    }
    pg_storage.add_reading(books["pg"]["id"], "Completed", "2024-03-01", "2024-03-20", 5)
    mock.add_reading(books["mock"]["id"], "Completed", "2024-03-01", "2024-03-20", 5)

    rows = [pg_storage.get_reading_history()[0], mock.get_reading_history()[0]]
    for row in rows:
        assert row["start_date"] == "2024-03-01"
        assert row["end_date"] == "2024-03-20"
        assert isinstance(row["created_at"], str)
        assert row["book_title"] == "Piranesi: A Novel"
        assert row["book_title_main"] == "Piranesi"
        assert row["book_subtitle"] == "A Novel"
        assert row["book_author"] == "Susanna Clarke"
        assert row["book_cover_url"] == "https://example.com/cover.jpg"
        assert row["book_publication_year"] == 2020
        assert row["latest_status"] == "Completed"


def test_bulk_import_can_leave_a_name_changed_since_the_snapshot(pg_storage):
    """A metadata refresh must not write the title its snapshot carried."""
    isbn = "9780241181348"
    book = pg_storage.add_book(isbn13=isbn, title="Piranesi: A Novel", authors=["An Author"])
    stale = dict(book)

    pg_storage.update_book(
        book_id=book["id"],
        isbn13=isbn,
        title="Piranesi",
        subtitle="A Novel",
        authors=["An Author"],
    )

    pg_storage.bulk_import([{"book": stale, "record": None}], write_names=False)

    stored = pg_storage.get_book_by_id(book["id"])
    assert (stored["title"], stored["subtitle"]) == ("Piranesi", "A Novel")


def test_bulk_import_splits_a_combined_title_only_when_asked(pg_storage):
    """An imported file is external text, so its caller asks for the split."""
    pg_storage.bulk_import(
        [
            {
                "book": {
                    "isbn13": "9780241181347",
                    "title": "Piranesi: A Novel",
                    "author": "Susanna Clarke",
                    "publication_year": None,
                },
                "record": None,
            }
        ],
        infer_subtitles=True,
    )

    stored = pg_storage.get_book_by_isbn("9780241181347")
    assert (stored["title"], stored["subtitle"]) == ("Piranesi", "A Novel")


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


def test_removing_a_book_leaves_the_queue_numbered_from_one(pg_storage):
    """The CSV export writes the queue position, so it has to start at one."""
    first = pg_storage.add_book(isbn13="9990000000004", title="First", authors=["Author"])
    second = pg_storage.add_book(isbn13="9990000000005", title="Second", authors=["Author"])
    pg_storage.add_to_reading_list(first["id"])
    pg_storage.add_to_reading_list(second["id"])

    pg_storage.remove_from_reading_list(first["id"])

    queue = pg_storage.get_reading_list()
    assert [item["book_id"] for item in queue] == [second["id"]]
    assert queue[0]["position"] == 1


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
    second = pg_storage.add_reading(book_id=book["id"], status="In Progress", start_date="2024-01-01")

    assert second["id"] != first["id"]
    assert second["rating"] == 0
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


def _write_book(url, isbn13, title, authors, thumbnail_url=None):
    """A Book with its author links in the order given, as the schema holds it."""
    with psycopg.connect(url) as conn:
        book_id = conn.execute(
            "INSERT INTO books (isbn13, title, thumbnail_url) VALUES (%s, %s, %s) RETURNING id",
            [isbn13, title, thumbnail_url],
        ).fetchone()[0]
        for position, name in enumerate(authors, start=1):
            author_id = conn.execute(
                "INSERT INTO authors (name) VALUES (%s) ON CONFLICT (name) DO UPDATE "
                "SET name = EXCLUDED.name RETURNING id",
                [name],
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO book_authors (book_id, author_id, position) VALUES (%s, %s, %s)",
                [book_id, author_id, position],
            )
    return book_id


def _wait_for_lock_wait(url):
    """Block until a backend in `url`'s database is waiting for a lock.

    The migration under test is the only writer there while these tests run, so
    an ungranted lock is the migration waiting on a row the test holds. Waiting
    for it to be seen, rather than sleeping, is what proves the lock is taken.
    """
    database = url.rsplit("/", 1)[-1]
    deadline = time.monotonic() + 30
    with psycopg.connect(url) as watcher:
        while time.monotonic() < deadline:
            waiting = watcher.execute(
                "SELECT count(*) FROM pg_locks l "
                "JOIN pg_stat_activity a ON a.pid = l.pid "
                "WHERE NOT l.granted AND a.datname = %s",
                [database],
            ).fetchone()[0]
            if waiting:
                return
            time.sleep(0.05)
    pytest.fail("the migration never waited on the Book's lock")


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


def test_0009_zeroes_a_rating_on_a_reading_that_never_completed(own_database):
    """Rows written before the rule still carry a score; the repair zeroes it.

    Completed keeps its rating, because that is the reading's verdict. The other
    statuses do not, so the min-rating filter and the rating order cannot select
    a Reading whose score the pages refuse to show.
    """
    _upgrade_database(own_database, "0008")
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        book_id = conn.execute(
            "INSERT INTO books (isbn13, title) VALUES ('9780441013593', 'Dune') RETURNING id"
        ).fetchone()[0]
        for status, rating in (("Completed", 5), ("Abandoned", 3), ("In Progress", 4)):
            conn.execute(
                "INSERT INTO readings (user_id, book_id, status, rating) VALUES (%s, %s, %s, %s)",
                [user_id, book_id, status, rating],
            )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        ratings = dict(conn.execute("SELECT status, rating FROM readings").fetchall())

    assert ratings == {"Completed": 5, "Abandoned": 0, "In Progress": 0}


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


@pytest.mark.parametrize(
    ("real_cover", "kept_cover"),
    [
        (None, "http://example.com/duplicate.jpg"),
        # Imports record a missing cover as an empty string, so it must not block
        # the only image from being copied.
        ("", "http://example.com/duplicate.jpg"),
        ("http://example.com/real.jpg", "http://example.com/real.jpg"),
    ],
)
def test_0010_deletes_the_empty_keyed_duplicate_of_the_real_book(own_database, real_cover, kept_cover):
    """#358's two records become one, and the cover one of them holds survives.

    The duplicate is the only record with an image, so deleting it must not take
    the image with it; when both hold one, the real Book's wins.
    """
    _upgrade_database(own_database, "0009")
    _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"], thumbnail_url=real_cover)
    _write_book(
        own_database,
        "",
        "The Spy in the Archive",
        ["Gordon Carera"],
        thumbnail_url="http://example.com/duplicate.jpg",
    )
    _write_book(own_database, "9780441013593", "Dune", ["Frank Herbert"])

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        books = conn.execute("SELECT isbn13, title, thumbnail_url FROM books ORDER BY id").fetchall()
        links = conn.execute("SELECT count(*) FROM book_authors").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert books == [
        ("9780008644833", "The Spy in the Archive", kept_cover),
        ("9780441013593", "Dune", None),
    ]
    assert links == 2
    assert stamped == "0011"


def test_0011_adds_the_column_and_leaves_the_titles_to_the_backfill(own_database):
    """Deferred: a late save by the old instance must not be able to double."""
    _upgrade_database(own_database, "0010")
    titles = {
        "9780000000001": "A History of England in 100 Places: From Stonehenge to the Gherkin",
        "9780000000002": "The Spy in the Archive — A Novel",
        "9780000000003": "Re: Zero",
        "9780000000004": "10:04",
        "9780000000005": "Spider-Man",
        "9780000000006": "Dune Messiah",
    }
    with psycopg.connect(own_database) as conn:
        for isbn, title in titles.items():
            conn.execute("INSERT INTO books (isbn13, title) VALUES (%s, %s)", [isbn, title])

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        rows = {
            isbn: (title, subtitle)
            for isbn, title, subtitle in conn.execute("SELECT isbn13, title, subtitle FROM books ORDER BY isbn13")
        }
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    # Splitting here would race the instance still writing combined titles, so
    # every stored title stays as it is until the backfill script runs.
    assert rows == {isbn: (title, None) for isbn, title in titles.items()}
    assert stamped == "0011"


def test_0010_moves_a_duplicates_history_to_the_real_book(own_database):
    """The reader's history moves with the Book it belongs to.

    A Reading and a queue entry that only the duplicate holds move to the real
    Book, so deleting the duplicate cannot take them with it.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute(
            "INSERT INTO readings (user_id, book_id, status, rating) VALUES (%s, %s, 'Completed', 5)",
            [user_id, duplicate_id],
        )
        conn.execute(
            "INSERT INTO reading_list (user_id, book_id) VALUES (%s, %s)",
            [user_id, duplicate_id],
        )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status, rating FROM readings").fetchall()
        queued = conn.execute("SELECT book_id FROM reading_list").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "Completed", 5)]
    assert queued == [(real_id,)]
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_keeps_a_queue_entry_the_reader_already_has_for_the_real_book(own_database):
    """Queueing both records leaves one entry, at the position it already had.

    The move inserts what the duplicate's queue held, so a reader who already
    queued the real Book must keep that entry rather than gaining a second one
    ahead of, or behind, the rest of their list.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO reading_list (user_id, book_id, position) VALUES (%s, %s, 1)", [user_id, real_id])
        conn.execute(
            "INSERT INTO reading_list (user_id, book_id, position) VALUES (%s, %s, 2)", [user_id, duplicate_id]
        )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        queued = conn.execute("SELECT book_id, position FROM reading_list").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert queued == [(real_id, 1)]
    assert stamped == "0011"


def test_0010_does_not_deadlock_a_reading_started_while_it_runs(own_database):
    """`start_reading()` takes the queue row and then the Book; so must this.

    The reader deletes its Reading List entry and stays open, exactly as
    `start_reading()` does before it inserts the Reading. A migration that took
    the Book lock first would then wait on that queue row while the reader's
    insert waits on the Book: a deadlock, which Postgres resolves by aborting
    one of the two. Moving the queue before the Book locks leaves the reader
    free to finish, and the Reading it saves moves with the rest.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO reading_list (user_id, book_id) VALUES (%s, %s)", [user_id, duplicate_id])

    reader = psycopg.connect(own_database)
    failure = []
    try:
        # The queue row is deleted but the request's transaction stays open.
        reader.execute("DELETE FROM reading_list WHERE user_id = %s AND book_id = %s", [user_id, duplicate_id])

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # pragma: no cover - the repair must not fail
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # Wait until the migration is blocked on the queue row this request
        # holds, then save the Reading as start_reading() would. Under the old
        # order that insert waited on the Book the migration had already locked.
        _wait_for_lock_wait(own_database)
        reader.execute(
            "INSERT INTO readings (user_id, book_id, status) VALUES (%s, %s, 'In Progress')",
            [user_id, duplicate_id],
        )
        reader.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        reader.close()

    assert not failure, f"the migration failed: {failure}"

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status FROM readings").fetchall()
        queued = conn.execute("SELECT book_id FROM reading_list").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "In Progress")]
    assert queued == []
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_folds_a_reading_logged_against_both_records(own_database):
    """The same read on both records is one entry, left on the real Book."""
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        for book_id in (real_id, duplicate_id):
            conn.execute(
                "INSERT INTO readings (user_id, book_id, status, rating, start_date, end_date) "
                "VALUES (%s, %s, 'Completed', 4, DATE '2026-07-30', DATE '2026-08-12')",
                [user_id, book_id],
            )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status, rating FROM readings").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "Completed", 4)]
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_folds_a_reread_logged_against_both_records(own_database):
    """Every duplicate Reading folds into its own match on the survivor.

    Two identical Readings on each record are a re-read logged twice. Pairing
    them one for one folds both and the repair finishes; folding only the
    duplicate's first would leave one behind and refuse a history it can fully
    account for.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        for book_id in (real_id, duplicate_id):
            for _ in range(2):
                conn.execute(
                    "INSERT INTO readings (user_id, book_id, status, rating, start_date, end_date) "
                    "VALUES (%s, %s, 'Completed', 4, DATE '2026-07-30', DATE '2026-08-12')",
                    [user_id, book_id],
                )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status FROM readings").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "Completed"), (real_id, "Completed")]
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_pairs_each_duplicate_reading_with_its_own_match(own_database):
    """A match is found per Reading, not only for the duplicate's first one.

    The same two Readings sit in the opposite order on each record, so the
    duplicate's later Reading matches the survivor's earlier one. Pairing per
    Reading folds both; matching only the duplicate's earliest would fold the
    one that happens to line up and refuse a history that pairs exactly.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        # The same two Readings, logged in the opposite order on each record.
        for book_id, statuses in ((real_id, ("Abandoned", "Completed")), (duplicate_id, ("Completed", "Abandoned"))):
            for status in statuses:
                conn.execute(
                    "INSERT INTO readings (user_id, book_id, status, rating, start_date, end_date) "
                    "VALUES (%s, %s, %s, %s, DATE '2026-07-30', DATE '2026-08-12')",
                    [user_id, book_id, status, 4 if status == "Completed" else 0],
                )

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status FROM readings ORDER BY id").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "Abandoned"), (real_id, "Completed")]
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_keeps_a_rating_edited_while_the_fold_runs(own_database):
    """update_reading() rewrites a Reading without taking its Book's lock.

    An edit can raise the duplicate's rating while the fold compares Readings.
    The fold must see what the edit committed, not the snapshot it started from,
    and refuse a Reading that no longer matches the survivor rather than folding
    the newly saved rating away.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        reading_ids = {}
        for book_id in (real_id, duplicate_id):
            reading_ids[book_id] = conn.execute(
                "INSERT INTO readings (user_id, book_id, status, rating, start_date, end_date) "
                "VALUES (%s, %s, 'Completed', 4, DATE '2026-07-30', DATE '2026-08-12') RETURNING id",
                [user_id, book_id],
            ).fetchone()[0]

    editor = psycopg.connect(own_database)
    failure = []
    try:
        # Like the update endpoint: keyed by the Reading, so it needs no Book lock.
        editor.execute("UPDATE readings SET rating = 5 WHERE id = %s", [reading_ids[duplicate_id]])

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # the refusal is the expected outcome
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # Wait until the fold is blocked on this row, then let the edit commit
        # so the fold has to compare against the rating that was saved.
        _wait_for_lock_wait(own_database)
        editor.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        editor.close()

    assert failure, "the migration folded the rating the edit saved"
    assert "differ" in str(failure[0])

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, rating FROM readings ORDER BY id").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, 4), (duplicate_id, 5)]
    assert stamped == "0009"


def test_0010_refuses_a_reading_that_differs_from_the_real_books(own_database):
    """Two different readings of one work are a person's merge, not a fold."""
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute(
            "INSERT INTO readings (user_id, book_id, status) VALUES (%s, %s, 'Completed')",
            [user_id, real_id],
        )
        conn.execute(
            "INSERT INTO readings (user_id, book_id, status) VALUES (%s, %s, 'Abandoned')",
            [user_id, duplicate_id],
        )

    with pytest.raises(RuntimeError, match="differ"):
        _upgrade_database(own_database, "head")

    # The refusal is the whole migration: neither the Book nor either Reading
    # has moved, and the revision is not stamped.
    with psycopg.connect(own_database) as conn:
        held = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        readings = conn.execute("SELECT count(*) FROM readings").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert held == 1
    assert readings == 2
    assert stamped == "0009"


@pytest.mark.parametrize(
    ("title", "authors", "reason"),
    [
        ("A Different Book", ["Gordon Carera"], "its title differs"),
        ("The Spy in the Archive", ["Somebody Else"], "its authors differ"),
    ],
)
def test_0010_refuses_an_empty_keyed_book_that_is_not_the_duplicate(own_database, title, authors, reason):
    """An ISBN-less Book this repair does not recognise is a person's call."""
    _upgrade_database(own_database, "0009")
    _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    _write_book(own_database, "", title, authors)

    with pytest.raises(RuntimeError, match=reason):
        _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        held = conn.execute("SELECT title FROM books WHERE btrim(isbn13) = ''").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert held == [(title,)]
    assert stamped == "0009"


def test_0010_refuses_when_the_real_book_is_missing(own_database):
    """With no ISBN-ed record there is nothing to confirm the duplicate against."""
    _upgrade_database(own_database, "0009")
    _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])

    with pytest.raises(RuntimeError, match="is not in the catalogue"):
        _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        held = conn.execute("SELECT count(*) FROM books").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert held == 1
    assert stamped == "0009"


def test_0010_is_a_no_op_when_no_isbn_less_book_remains(own_database):
    """The repair may already have happened by hand; it must then do nothing."""
    _upgrade_database(own_database, "0009")
    _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])

    _upgrade_database(own_database, "head")

    with psycopg.connect(own_database) as conn:
        books = conn.execute("SELECT isbn13, title FROM books").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert books == [("9780008644833", "The Spy in the Archive")]
    assert stamped == "0011"


def test_0010_does_not_lose_a_reading_saved_while_it_runs(own_database):
    """A deployment serves requests while migrations run (DEPLOYMENT.md).

    The Reading is inserted but its transaction stays open while the migration
    starts, so a migration that moved history before the commit would see none
    and then cascade the Reading away with the duplicate. Because the candidate
    is locked first, the migration waits; once the Reading commits it moves to
    the surviving Book. The commit happens only once the migration is seen
    waiting on that lock; without the lock nothing waits and the Reading is
    deleted, so the assertions below fail.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])

    reader = psycopg.connect(own_database)
    failure = []
    try:
        user_id = reader.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        reader.execute(
            "INSERT INTO readings (user_id, book_id, status) VALUES (%s, %s, 'In Progress')",
            [user_id, duplicate_id],
        )

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # pragma: no cover - the repair must not fail
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # The migration cannot get past the Book this transaction holds, so wait
        # for its ungranted lock before committing. The wait is observed rather
        # than timed, so the test proves the lock is taken before history moves.
        _wait_for_lock_wait(own_database)
        reader.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        reader.close()

    assert not failure, f"the migration failed: {failure}"

    with psycopg.connect(own_database) as conn:
        readings = conn.execute("SELECT book_id, status FROM readings").fetchall()
        duplicate = conn.execute("SELECT count(*) FROM books WHERE btrim(isbn13) = ''").fetchone()[0]
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert readings == [(real_id, "In Progress")]
    assert duplicate == 0
    assert stamped == "0011"


def test_0010_refuses_when_an_edit_changes_the_real_books_isbn_mid_migration(own_database):
    """An edit can move the survivor after the duplicate was matched to it.

    Deployments still serve edits while migrations run, and an edit may change a
    Book's ISBN. If that commit lands between the survivor being matched and the
    cover being copied, an ISBN-keyed copy would find nothing to update while the
    duplicate, holding the only image, was still deleted. The survivor is locked
    for the whole copy, so the match and the write see the same row: here the
    ISBN moves and the repair refuses instead of losing the image.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    _write_book(
        own_database,
        "",
        "The Spy in the Archive",
        ["Gordon Carera"],
        thumbnail_url="http://example.com/duplicate.jpg",
    )

    editor = psycopg.connect(own_database)
    failure = []
    try:
        # Like the update endpoint: keyed by id, so the row keeps its identity
        # while its ISBN changes. Uncommitted, so the migration must wait.
        editor.execute("UPDATE books SET isbn13 = '9780441013593' WHERE id = %s", [real_id])

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # the refusal is the expected outcome
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # Wait until the migration is blocked on the row this edit holds, then
        # let the edit commit so the migration sees the Book under its new ISBN.
        _wait_for_lock_wait(own_database)
        editor.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        editor.close()

    assert failure, "the migration copied nothing and deleted the duplicate anyway"
    assert "is not in the catalogue" in str(failure[0])

    with psycopg.connect(own_database) as conn:
        books = conn.execute("SELECT isbn13, thumbnail_url FROM books ORDER BY id").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert books == [
        ("9780441013593", None),
        ("", "http://example.com/duplicate.jpg"),
    ]
    assert stamped == "0009"


def test_0010_refuses_when_a_duplicates_isbn_moves_while_the_queue_moves(own_database):
    """The queue moves before the Books are locked, so the candidates are re-read.

    An edit can give the duplicate an ISBN while the Reading List transfer runs.
    Its entry has by then already moved to the survivor, while the row itself is
    no longer one this repair deletes, so the migration refuses and the move
    rolls back instead of leaving the entry on a Book it has to keep.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO reading_list (user_id, book_id) VALUES (%s, %s)", [user_id, duplicate_id])

    # A request still holding this queue row stops the transfer part-way through,
    # which is the window an edit lands in.
    holder = psycopg.connect(own_database)
    failure = []
    try:
        holder.execute(
            "SELECT 1 FROM reading_list WHERE user_id = %s AND book_id = %s FOR UPDATE",
            [user_id, duplicate_id],
        )

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # the refusal is the expected outcome
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # The candidate was read before this edit commits and is re-read after
        # it, so the two disagree and the repair must not go on.
        _wait_for_lock_wait(own_database)
        with psycopg.connect(own_database) as editor:
            editor.execute("UPDATE books SET isbn13 = '9780441013593' WHERE id = %s", [duplicate_id])
        holder.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        holder.close()

    assert failure, "the migration moved the queue entry and repaired around the edit"
    assert "catalogue changed while the Reading List moved" in str(failure[0])

    with psycopg.connect(own_database) as conn:
        books = conn.execute("SELECT id, isbn13 FROM books ORDER BY id").fetchall()
        queued = conn.execute("SELECT book_id FROM reading_list").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert books == [(real_id, "9780008644833"), (duplicate_id, "9780441013593")]
    assert queued == [(duplicate_id,)]
    assert stamped == "0009"


def test_0010_refuses_when_the_real_book_moves_to_another_row_mid_migration(own_database):
    """The queue moves to an id; if REAL_ISBN lands on another row, refuse.

    An edit can change the surviving Book's ISBN while the Reading List transfer
    runs, and another row can take that ISBN. The entries were moved to the id
    matched before that, which is no longer the row this repair keeps, so the
    migration refuses and the move rolls back.
    """
    _upgrade_database(own_database, "0009")
    real_id = _write_book(own_database, "9780008644833", "The Spy in the Archive", ["Gordon Carera"])
    duplicate_id = _write_book(own_database, "", "The Spy in the Archive", ["Gordon Carera"])
    other_id = _write_book(own_database, "9780141036144", "Brave New World", ["Aldous Huxley"])
    with psycopg.connect(own_database) as conn:
        user_id = conn.execute("INSERT INTO users (email) VALUES ('reader@example.com') RETURNING id").fetchone()[0]
        conn.execute("INSERT INTO reading_list (user_id, book_id) VALUES (%s, %s)", [user_id, duplicate_id])

    holder = psycopg.connect(own_database)
    failure = []
    try:
        holder.execute(
            "SELECT 1 FROM reading_list WHERE user_id = %s AND book_id = %s FOR UPDATE",
            [user_id, duplicate_id],
        )

        def migrate():
            try:
                _upgrade_database(own_database, "head")
            except Exception as exc:  # the refusal is the expected outcome
                failure.append(exc)

        worker = threading.Thread(target=migrate)
        worker.start()

        # Wait until the transfer is under way, then move the ISBN the repair
        # matched on to a different row while the queue entries sit on the old
        # one.
        _wait_for_lock_wait(own_database)
        with psycopg.connect(own_database) as editor:
            editor.execute("UPDATE books SET isbn13 = '9780441013593' WHERE id = %s", [real_id])
            editor.execute("UPDATE books SET isbn13 = '9780008644833' WHERE id = %s", [other_id])
        holder.commit()
        worker.join(timeout=30)
        assert not worker.is_alive(), "the migration did not finish"
    finally:
        holder.close()

    assert failure, "the migration moved the queue entry onto a Book it keeps"
    assert "catalogue changed while the Reading List moved" in str(failure[0])

    with psycopg.connect(own_database) as conn:
        books = conn.execute("SELECT id, isbn13 FROM books ORDER BY id").fetchall()
        queued = conn.execute("SELECT book_id FROM reading_list").fetchall()
        stamped = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    assert books == [
        (real_id, "9780441013593"),
        (duplicate_id, ""),
        (other_id, "9780008644833"),
    ]
    assert queued == [(duplicate_id,)]
    assert stamped == "0009"


def test_the_missing_covers_run_reads_and_writes_only_covers(pg_storage):
    """The missing-covers run's storage seam, against real Postgres.

    A cover is missing when both fields are NULL or blank; the read is scoped to
    the collection and the ids asked for; the write never touches another field.
    """
    covered = pg_storage.add_book(
        isbn13="9780000000101",
        title="Covered",
        authors=["A"],
        publisher="Kept House",
        thumbnail_url="https://example.com/old.jpg",
    )
    missing = pg_storage.add_book(isbn13="9780000000102", title="Missing", authors=["B"], publisher="Kept House")
    blank = pg_storage.add_book(isbn13="9780000000103", title="Blank", authors=["C"], thumbnail_url="   ")
    for book in (covered, missing, blank):
        pg_storage.add_to_reading_list(book["id"])

    missing_ids = {book["id"] for book in pg_storage.get_books_missing_covers()}
    assert missing_ids == {missing["id"], blank["id"]}

    scoped = pg_storage.get_books_missing_covers([missing["id"], covered["id"]])
    assert {book["id"] for book in scoped} == {missing["id"]}

    assert pg_storage.set_book_cover(
        missing["id"],
        "9780000000102",
        thumbnail_url="https://example.com/new-M.jpg",
        cover_url="https://example.com/new-L.jpg",
    )

    kept = pg_storage.get_book_by_id(covered["id"])
    assert kept["thumbnail_url"] == "https://example.com/old.jpg"
    assert kept["publisher"] == "Kept House"

    filled = pg_storage.get_book_by_id(missing["id"])
    assert filled["thumbnail_url"] == "https://example.com/new-M.jpg"
    assert filled["cover_url"] == "https://example.com/new-L.jpg"
    assert filled["title"] == "Missing"
    assert filled["publisher"] == "Kept House"

    # A cover on a host that serves placeholders is included in the read, and
    # may be replaced once the run has fingerprinted it as one.
    placeholder_url = "https://images.penguinrandomhouse.com/cover/9780000000105"
    placeholder_book = pg_storage.add_book(
        isbn13="9780000000105",
        title="Placeholder",
        authors=["D"],
        thumbnail_url=placeholder_url,
    )
    pg_storage.add_to_reading_list(placeholder_book["id"])
    widened = {
        book["id"] for book in pg_storage.get_books_missing_covers(placeholder_hosts=["images.penguinrandomhouse.com"])
    }
    assert placeholder_book["id"] in widened
    assert placeholder_book["id"] not in {book["id"] for book in pg_storage.get_books_missing_covers()}
    assert not pg_storage.set_book_cover(
        placeholder_book["id"], "9780000000105", thumbnail_url="https://example.com/real.jpg"
    )
    assert pg_storage.set_book_cover(
        placeholder_book["id"],
        "9780000000105",
        thumbnail_url="https://example.com/real.jpg",
        replace_urls=[placeholder_url],
    )

    # A real cover saved mid-run is never overwritten just because the other
    # field still holds a placeholder.
    stuck = pg_storage.add_book(
        isbn13="9780000000106",
        title="Stuck",
        authors=["E"],
        thumbnail_url=f"{placeholder_url}/thumb",
        cover_url=f"{placeholder_url}/cover",
    )
    pg_storage.add_to_reading_list(stuck["id"])
    assert pg_storage.set_book_cover(
        stuck["id"],
        "9780000000106",
        thumbnail_url="https://example.com/reader.jpg",
        cover_url="https://example.com/reader2.jpg",
        replace_urls=[f"{placeholder_url}/thumb", f"{placeholder_url}/cover"],
    )
    assert not pg_storage.set_book_cover(
        stuck["id"],
        "9780000000106",
        thumbnail_url="https://example.com/run.jpg",
        replace_urls=[f"{placeholder_url}/thumb"],
    )

    still_missing = {book["id"] for book in pg_storage.get_books_missing_covers()}
    assert still_missing == {blank["id"]}

    # A cover added while the run was looking is not replaced.
    assert not pg_storage.set_book_cover(
        missing["id"],
        "9780000000102",
        thumbnail_url="https://example.com/later.jpg",
    )
    assert pg_storage.get_book_by_id(missing["id"])["thumbnail_url"] == "https://example.com/new-M.jpg"

    # A cover the lookup found for an ISBN the row no longer has is not written:
    # the reader corrected the edition while the run was looking.
    assert not pg_storage.set_book_cover(
        blank["id"],
        "9780000000104",
        thumbnail_url="https://example.com/stale.jpg",
    )
    assert pg_storage.get_book_by_id(blank["id"])["thumbnail_url"] == "   "
