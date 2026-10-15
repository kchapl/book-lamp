"""Drop indexes that repeat an access path the table already has.

0002 added four indexes whose leading column is already the leading column of an
index that exists: three of the primary keys, and the unique constraint on
`users(email)`. A B-tree is usable whenever its leading column is, so each of
these is a second copy — write time on every insert and update, for no read it
can serve that its twin cannot.

`idx_users_email` is the plainest case: 0001 declares `email TEXT NOT NULL
UNIQUE`, which created `users_email_key` on that column, so 0002's comment
("for login lookups") described a lookup the constraint already served. The
other three repeat a primary key: `book_authors (book_id, author_id)`,
`reading_list (user_id, book_id)` and `settings (user_id, key)`.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-14
"""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users(email) is UNIQUE in 0001, so users_email_key already indexes it.
    op.execute("DROP INDEX IF EXISTS idx_users_email")

    # book_authors' primary key is (book_id, author_id): it leads with book_id.
    op.execute("DROP INDEX IF EXISTS idx_book_authors_book_id")

    # reading_list's primary key is (user_id, book_id): it leads with user_id.
    op.execute("DROP INDEX IF EXISTS idx_reading_list_user_id")

    # settings' primary key is (user_id, key): it leads with user_id.
    op.execute("DROP INDEX IF EXISTS idx_settings_user_id")


def downgrade() -> None:
    # The same statements 0002 ran, so the pair stays reversible.
    op.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_book_authors_book_id ON book_authors(book_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_reading_list_user_id ON reading_list(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id)")
