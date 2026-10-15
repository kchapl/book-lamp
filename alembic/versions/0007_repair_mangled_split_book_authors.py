"""Repair the two Book author strings the splitter mangled, before the column goes.

Every write path derives a Book's links *from* `books.author` (`split_authors`),
so for 268 of 270 Books the links reproduce that string exactly. Two do not, and
neither is reachable by re-running a rule:

- `9781398505292`: the whole string is one name, and `split_authors` breaks it on
  " & " — a separator between authors, and a character inside this one. Two links
  where the string has one.
- `9781785781438` "Sutherland, John, John Crace": a "Last, First" name beside a
  plain one. The splitter cuts on the commas instead, giving three names where
  the string has two.

Dropping the column without this would cement both readings, and the strings are
the only record of what was meant. The four other Books whose authors really are
separated by commas ("A, B, C") are syntactically identical to the second case, so
no rule separates them: the correction is written out per Book, read from the
string (see ADR-0005).

Each statement is limited to the string it was written for, so a Book corrected
through the application since is left alone and re-running this is a no-op.
Migration 0008 refuses to drop the column while any Book's links cannot reproduce
its string, so a Book this did not reach stops the drop rather than losing its
author.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-14
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One name that contains " & ", not two names joined by it. The string is the
    # author, verbatim, so nothing is read off the splitter.
    op.execute("""
        DELETE FROM book_authors
        WHERE book_id IN (
            SELECT id FROM books
            WHERE isbn13 = '9781398505292' AND author = 'To Be To Be Confirmed Simon & Schuster'
        )
        """)
    op.execute("""
        INSERT INTO authors (name)
        SELECT author FROM books
        WHERE isbn13 = '9781398505292' AND author = 'To Be To Be Confirmed Simon & Schuster'
        ON CONFLICT (name) DO NOTHING
        """)
    op.execute("""
        INSERT INTO book_authors (book_id, author_id, position)
        SELECT b.id, a.id, 1
        FROM books b
        JOIN authors a ON a.name = b.author
        WHERE b.isbn13 = '9781398505292' AND b.author = 'To Be To Be Confirmed Simon & Schuster'
        """)

    # "Last, First" beside a plain name, kept in the spelling the string used so
    # the two links join back to it character for character.
    op.execute("""
        DELETE FROM book_authors
        WHERE book_id IN (
            SELECT id FROM books
            WHERE isbn13 = '9781785781438' AND author = 'Sutherland, John, John Crace'
        )
        """)
    op.execute("""
        INSERT INTO authors (name)
        SELECT name FROM (VALUES ('Sutherland, John'), ('John Crace')) AS v(name)
        ON CONFLICT (name) DO NOTHING
        """)
    op.execute("""
        INSERT INTO book_authors (book_id, author_id, position)
        SELECT b.id, a.id, v.position
        FROM books b
        JOIN (VALUES ('Sutherland, John', 1), ('John Crace', 2)) AS v(name, position) ON TRUE
        JOIN authors a ON a.name = v.name
        WHERE b.isbn13 = '9781785781438' AND b.author = 'Sutherland, John, John Crace'
        """)

    # The halves the splitter invented are now referenced by nothing. Authors with
    # no Book stay in the table otherwise (41 already do), but these four name no
    # Book and no author: they were a defect, not a person.
    op.execute("""
        DELETE FROM authors a
        WHERE a.name IN ('To Be To Be Confirmed Simon', 'Schuster', 'Sutherland', 'John')
          AND NOT EXISTS (SELECT 1 FROM book_authors ba WHERE ba.author_id = a.id)
        """)


def downgrade() -> None:
    # Puts back the split the repair replaced, not a re-split: the rule that
    # produced it is what this migration exists to correct. Guarded by the same
    # string, so a Book edited since keeps the authors it has.
    op.execute("""
        DELETE FROM book_authors
        WHERE book_id IN (
            SELECT id FROM books
            WHERE isbn13 = '9781398505292' AND author = 'To Be To Be Confirmed Simon & Schuster'
        )
        """)
    op.execute("""
        INSERT INTO authors (name)
        SELECT name FROM (VALUES ('To Be To Be Confirmed Simon'), ('Schuster')) AS v(name)
        ON CONFLICT (name) DO NOTHING
        """)
    op.execute("""
        INSERT INTO book_authors (book_id, author_id, position)
        SELECT b.id, a.id, v.position
        FROM books b
        JOIN (VALUES ('To Be To Be Confirmed Simon', 1), ('Schuster', 2)) AS v(name, position) ON TRUE
        JOIN authors a ON a.name = v.name
        WHERE b.isbn13 = '9781398505292' AND b.author = 'To Be To Be Confirmed Simon & Schuster'
        """)

    op.execute("""
        DELETE FROM book_authors
        WHERE book_id IN (
            SELECT id FROM books
            WHERE isbn13 = '9781785781438' AND author = 'Sutherland, John, John Crace'
        )
        """)
    op.execute("""
        INSERT INTO authors (name)
        SELECT name FROM (VALUES ('Sutherland'), ('John'), ('John Crace')) AS v(name)
        ON CONFLICT (name) DO NOTHING
        """)
    op.execute("""
        INSERT INTO book_authors (book_id, author_id, position)
        SELECT b.id, a.id, v.position
        FROM books b
        JOIN (VALUES ('Sutherland', 1), ('John', 2), ('John Crace', 3)) AS v(name, position) ON TRUE
        JOIN authors a ON a.name = v.name
        WHERE b.isbn13 = '9781785781438' AND b.author = 'Sutherland, John, John Crace'
        """)

    op.execute("""
        DELETE FROM authors a
        WHERE a.name = 'Sutherland, John'
          AND NOT EXISTS (SELECT 1 FROM book_authors ba WHERE ba.author_id = a.id)
        """)
