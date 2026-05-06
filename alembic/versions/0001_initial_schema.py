"""Initial schema.

Revision ID: 0001
Revises:
Create Date: 2026-05-04
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id         SERIAL PRIMARY KEY,
            email      TEXT NOT NULL UNIQUE,
            name       TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS books (
            id                  SERIAL PRIMARY KEY,
            isbn13              TEXT NOT NULL UNIQUE,
            title               TEXT NOT NULL,
            author              TEXT NOT NULL,
            publication_year    INTEGER,
            thumbnail_url       TEXT,
            publisher           TEXT,
            description         TEXT,
            series              TEXT,
            bisac_category      TEXT,
            bisac_main_category TEXT,
            bisac_sub_category  TEXT,
            language            TEXT,
            page_count          INTEGER,
            physical_format     TEXT,
            edition             TEXT,
            cover_url           TEXT,
            created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS authors (
            id   SERIAL PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS book_authors (
            book_id   INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            author_id INTEGER NOT NULL REFERENCES authors(id) ON DELETE CASCADE,
            PRIMARY KEY (book_id, author_id)
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_records (
            id         SERIAL PRIMARY KEY,
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            status     TEXT NOT NULL,
            start_date DATE,
            end_date   DATE,
            rating     INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reading_list (
            user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            book_id    INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            position   INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (user_id, book_id)
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS recommendations (
            id            SERIAL PRIMARY KEY,
            user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            author        TEXT NOT NULL,
            isbn13        TEXT,
            justification TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS settings (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            key     TEXT NOT NULL,
            value   TEXT NOT NULL,
            PRIMARY KEY (user_id, key)
        )
    """
    )


def downgrade() -> None:
    for table in [
        "settings",
        "recommendations",
        "reading_list",
        "reading_records",
        "book_authors",
        "authors",
        "books",
        "users",
    ]:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
