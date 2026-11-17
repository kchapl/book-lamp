"""Delete the empty-keyed duplicate of "The Spy in the Archive" (#358).

An edit that cleared a Book's ISBN stored the empty string, and `books.isbn13`
is NOT NULL UNIQUE, so the row stayed in the catalogue keyed on '' beside the
real Book that kept its ISBN: the duplicate reported in #358. The edit path
refuses to clear the ISBN now; this repairs the row it left in production.

That row is "The Spy in the Archive" by Gordon Carera. It agrees with
`9780008644833` in every field but its cover, and carries no Reading and nothing
on a Reading List. A Book with no ISBN names no edition and cannot be edited
back into one, so the empty-keyed row is deleted and its author links go with
it. A cover only the duplicate holds is copied to the real Book before the
delete, so the repair cannot lose the only image.

The delete is limited to an empty-keyed Book whose title and authors match the
real record and that carries no Reading and no Reading List row: a Book with
history is not a duplicate to discard. Anything else stops the migration and is
named, because a row this repair does not recognise needs a person to say which
ISBN it should carry (0007 shows that form). With no empty-keyed Book the repair
has already happened and this is a no-op.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-17
"""

from sqlalchemy import text
from sqlalchemy.engine import RowMapping

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

#: The ISBN the real Book holds; #358 names it.
REAL_ISBN = "9780008644833"

#: A Book's authors in `book_authors.position` order, so two Books' links can be
#: compared as one string. The unit separator cannot appear in a name.
_AUTHORS = """
    COALESCE((SELECT string_agg(btrim(a.name), chr(31) ORDER BY ba.position)
              FROM book_authors ba
              JOIN authors a ON a.id = ba.author_id
              WHERE ba.book_id = b.id), '')
"""

_EMPTY_KEYED_BOOKS = f"""
    SELECT b.id, btrim(b.title) AS title, {_AUTHORS} AS authors,
           b.thumbnail_url, b.cover_url,
           (SELECT count(*) FROM readings r WHERE r.book_id = b.id) AS readings,
           (SELECT count(*) FROM reading_list rl WHERE rl.book_id = b.id) AS listed
    FROM books b
    WHERE btrim(b.isbn13) = ''
"""


def _describe(row: RowMapping) -> str:
    authors = str(row["authors"]).replace(chr(31), ", ")
    return f"#{row['id']} {row['title']!r} by {authors!r}"


def upgrade() -> None:
    bind = op.get_bind()
    empty = bind.execute(text(_EMPTY_KEYED_BOOKS)).mappings().all()
    if not empty:
        return

    real = (
        bind.execute(
            text(f"SELECT btrim(b.title) AS title, {_AUTHORS} AS authors FROM books b WHERE b.isbn13 = :isbn"),
            {"isbn": REAL_ISBN},
        )
        .mappings()
        .first()
    )
    if real is None:
        names = "; ".join(_describe(row) for row in empty)
        raise RuntimeError(
            f"Refusing to repair the ISBN-less Book(s) {names}: {REAL_ISBN} is not in the "
            "catalogue, so there is no record to confirm they duplicate. Give each the ISBN it "
            "should carry in this migration (0007 shows the form)."
        )

    for row in empty:
        reasons = []
        if row["title"] != real["title"]:
            reasons.append(f"its title differs from {REAL_ISBN}'s {real['title']!r}")
        if row["authors"] != real["authors"]:
            reasons.append("its authors differ from that Book's")
        if row["readings"]:
            reasons.append(f"it carries {row['readings']} Reading(s)")
        if row["listed"]:
            reasons.append(f"it is on {row['listed']} Reading List row(s)")
        if reasons:
            raise RuntimeError(
                f"Refusing to delete ISBN-less Book {_describe(row)}: {', '.join(reasons)}. "
                "A Book with history is not a duplicate to discard; give it the ISBN it should "
                "carry, or merge it by hand, before this migration runs."
            )

    for row in empty:
        # Only fills a gap: a cover the real Book already has wins.
        bind.execute(
            text("""
                UPDATE books
                SET thumbnail_url = COALESCE(thumbnail_url, :thumbnail_url),
                    cover_url = COALESCE(cover_url, :cover_url)
                WHERE isbn13 = :isbn
                """),
            {"thumbnail_url": row["thumbnail_url"], "cover_url": row["cover_url"], "isbn": REAL_ISBN},
        )
        # The row's author links go with it (ON DELETE CASCADE). The guard above
        # is what makes the delete safe: it carries no history to lose.
        bind.execute(text("DELETE FROM books WHERE id = :id"), {"id": row["id"]})


def downgrade() -> None:
    # Nothing to put back: the row was a duplicate of a Book that is still here,
    # and re-creating it would restore the defect rather than the data.
    pass
