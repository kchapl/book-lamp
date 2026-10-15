"""Drop books.author, now that every Book's links reproduce it.

A Book's authors live in `authors` and `book_authors`, ordered by
`book_authors.position` (0006). `books.author` held the same names as one string,
and every write path derived the links *from* it — so the column was the input and
the links were the copy. The application stopped writing it in the release before
this one, because the instance it replaces is still serving while this builds, and
that instance writes the string (see DEPLOYMENT.md).

This refuses to run while any Book's author text would go missing: a Book whose
links, in `position` order, do not join back to exactly the string it holds is
named and the drop stops. That covers the Book with no links at all and the Book
whose links are a different set of names. Migration 0007 makes the two Books that
failed this pass; anything else that fails it is a Book edited since, which a
person decides, not this migration.

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-14
"""

from sqlalchemy import text

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A link written by the release before 0006 has no position (that migration's
    # default) and leaves its Book's order undefined. Those instances wrote
    # split_authors' order, which is author_id order, so renumber such a Book
    # from it. After this, no row has an unset position.
    op.execute("""
        UPDATE book_authors ba
        SET position = ordered.position
        FROM (
            SELECT book_id, author_id,
                   row_number() OVER (PARTITION BY book_id ORDER BY author_id) AS position
            FROM book_authors
            WHERE book_id IN (SELECT book_id FROM book_authors WHERE position = 0)
        ) AS ordered
        WHERE ba.book_id = ordered.book_id AND ba.author_id = ordered.author_id
    """)

    # The string is compared trimmed: a stray leading or trailing space is not an
    # author, and one Book holds exactly that.
    lost = op.get_bind().execute(text("""
            SELECT b.title, b.author,
                   (SELECT string_agg(a.name, ', ' ORDER BY ba.position)
                    FROM book_authors ba
                    JOIN authors a ON a.id = ba.author_id
                    WHERE ba.book_id = b.id) AS linked
            FROM books b
            WHERE btrim(COALESCE(b.author, '')) <> ''
              AND btrim(b.author) IS DISTINCT FROM (
                    SELECT string_agg(a.name, ', ' ORDER BY ba.position)
                    FROM book_authors ba
                    JOIN authors a ON a.id = ba.author_id
                    WHERE ba.book_id = b.id)
            ORDER BY b.title
        """)).fetchall()

    if lost:
        shown = ", ".join(f"{row[0]!r} ({row[1]!r} -> {row[2]!r})" for row in lost[:10])
        raise RuntimeError(
            f"Refusing to drop books.author: {len(lost)} Book(s) hold author text their links cannot "
            f"reproduce — {shown}. Set the authors through the application, which writes the links, or "
            "correct them in a migration as 0007 does."
        )

    op.execute("ALTER TABLE books DROP COLUMN author")

    # Every link now carries the order it was written in, so position is required
    # and 0 is not a position. The default belonged to the release that could not
    # write one; nothing writes a link without one now.
    op.execute("ALTER TABLE book_authors ALTER COLUMN position DROP DEFAULT")
    op.execute("ALTER TABLE book_authors ADD CONSTRAINT book_authors_position_check CHECK (position > 0)")


def downgrade() -> None:
    op.execute("ALTER TABLE book_authors DROP CONSTRAINT IF EXISTS book_authors_position_check")
    op.execute("ALTER TABLE book_authors ALTER COLUMN position SET DEFAULT 0")

    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS author TEXT")
    # Lossy by construction: the string is rebuilt from the links, so the
    # separators are this migration's (", ") rather than whatever the Book was
    # entered with (" and ", "; "). Nullability stays as 0006 left it. For the two
    # Books 0007 repaired this reproduces the original text exactly, which is why
    # that repair reads the string rather than re-splitting it.
    op.execute("""
        UPDATE books b
        SET author = joined.names
        FROM (
            SELECT ba.book_id, string_agg(a.name, ', ' ORDER BY ba.position) AS names
            FROM book_authors ba
            JOIN authors a ON a.id = ba.author_id
            GROUP BY ba.book_id
        ) AS joined
        WHERE joined.book_id = b.id
    """)
