"""Give book_authors an order, and stop requiring a stored author string.

Dropping `books.author` needs two things in place first, and neither changes what
any query returns today.

`book_authors` has no order: its primary key is `(book_id, author_id)`, so the
order authors appear in is whatever the join happens to produce, and the three
`array_agg(a.name)` reads carry no `ORDER BY`. The order that exists today is by
`author_id`, which is insertion order — the order `split_authors` returned them.
`position` records that explicitly, so a query can ask for it rather than hope.

`books.author` is `NOT NULL` (0001). The application stops writing it in this
release, and the column is dropped in the next one (0008): while a release
rolls out, the instance it replaces is still serving, and that instance writes
the string. Dropping the column in the same release as the write would fail
every insert it made. Allowing NULL lets the write go first and the column
follow.

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-14
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE book_authors ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0")

    # Backfill to the order in use: a Book's authors were inserted in the order
    # split_authors produced them, so author_id is that order.
    op.execute("""
        UPDATE book_authors ba
        SET position = ordered.position
        FROM (
            SELECT book_id, author_id,
                   row_number() OVER (PARTITION BY book_id ORDER BY author_id) AS position
            FROM book_authors
        ) AS ordered
        WHERE ba.book_id = ordered.book_id AND ba.author_id = ordered.author_id
    """)

    op.execute("ALTER TABLE books ALTER COLUMN author DROP NOT NULL")


def downgrade() -> None:
    # NOT NULL cannot come back while any Book lacks an author string, so this
    # restores nullability as it was only if the data allows it.
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM books WHERE author IS NULL) THEN
                ALTER TABLE books ALTER COLUMN author SET NOT NULL;
            END IF;
        END
        $$
    """)
    op.execute("ALTER TABLE book_authors DROP COLUMN IF EXISTS position")
