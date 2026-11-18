"""Delete the empty-keyed duplicate of "The Spy in the Archive" (#358).

An edit that cleared a Book's ISBN stored the empty string, and `books.isbn13`
is NOT NULL UNIQUE, so the row stayed in the catalogue keyed on '' beside the
real Book that kept its ISBN: the duplicate reported in #358. The edit path
refuses to clear the ISBN now; this repairs the row it left in production.

That row is "The Spy in the Archive" by Gordon Carera. It agrees with
`9780008644833` in every field but its cover. A Book with no ISBN names no
edition and cannot be edited back into one, so the empty-keyed row is deleted
and its author links go with it. A cover only the duplicate holds is copied to
the real Book before the delete, so the repair cannot lose the only image.

The duplicate's history is the reader's, so it moves to the surviving Book
first. Reading List entries move across; a reader who already queued the real
Book keeps that entry rather than gaining a second. A Reading moves unless the
same reader logged the same reading (status, dates and rating) against the real
Book, in which case the duplicate entry is folded away -- one surviving Reading
per duplicate Reading, so a re-read logged on both records folds entry for
entry. A reading that says something different is never folded: the migration
stops, names it, and leaves the decision to a person.

The delete is limited to an empty-keyed Book whose title and authors match the
real record. Anything else stops the migration and is named, because a row this
repair does not recognise needs a person to say which ISBN it should carry (0007
shows that form). With no empty-keyed Book the repair has already happened and
this is a no-op.

The candidate row is locked before its history is read, and the lock is held
through the delete. A deployment runs this while the previous instance is still
serving requests (DEPLOYMENT.md), so a reader can save a Reading between the
check and the delete; that insert takes FOR KEY SHARE on its Book and waits for
this migration's FOR UPDATE, so a Reading saved before the lock is moved with
the rest, and one that starts mid-migration waits and then finds its Book gone
rather than being cascade-deleted unseen.

The Reading List moves before those Book locks are taken, and no queue row is
touched after them. `start_reading()` deletes its queue row and then inserts its
Reading, which takes FOR KEY SHARE on the Book: queue row first, Book second. A
migration that held a Book lock and then waited on a queue row would close that
order into a deadlock that aborts the reader's request, so the queue is moved
first and both sides take the queue row before the Book. A queue row a reader
adds after the move is deleted with the Book by ON DELETE CASCADE instead of
moving, which is where an entry for a Book that no longer exists would end.

The Readings are locked before they are compared. `update_reading()` rewrites
a Reading without taking its Book's lock, so a fold that compared a snapshot
could delete the row an edit committed while the delete waited on that row:
the delete would go on to fold the Reading away at its old values. With both
sides' rows held first, the comparison runs on the values the edits left.

The surviving Book is locked the same way, and the cover is copied to it by id.
An edit may change a Book's ISBN while the deployment still serves requests, so
matching the survivor by ISBN alone could find it, then have an edit commit
before the copy: the copy would match nothing while the duplicate, holding the
only image, was still deleted. With the lock held through the delete, the row
that was matched is the row that receives the cover.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-17
"""

from sqlalchemy import text
from sqlalchemy.engine import Connection, RowMapping

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

#: The ISBN the real Book holds; #358 names it.
REAL_ISBN = "9780008644833"

#: Raised when an ISBN moves between the Reading List transfer and the Book
#: locks; the rows the queue moved to could then no longer be the rows this
#: repair deletes.
_CATALOGUE_CHANGED = (
    "Refusing to repair the ISBN-less Book(s): the catalogue changed while the Reading List "
    "moved, so a reader's entry may now sit on a Book this repair keeps or deletes. Run this "
    "migration again once the catalogue is quiet."
)

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
           b.thumbnail_url, b.cover_url
    FROM books b
    WHERE btrim(b.isbn13) = ''
"""


def _describe(row: RowMapping) -> str:
    authors = str(row["authors"]).replace(chr(31), ", ")
    return f"#{row['id']} {row['title']!r} by {authors!r}"


def _move_queue(bind: Connection, real_id: int, duplicate_ids: list[int]) -> None:
    """Carry the duplicates' Reading List rows to the survivor.

    Runs before any Book is locked, and nothing here may run after those locks
    are taken: `start_reading()` takes the queue row and then the Book, so a
    migration waiting on a queue row under a Book lock would deadlock with it.

    The queue is keyed by (user_id, book_id), so a reader who already queued the
    real Book keeps that entry and the position it already has.
    """
    for duplicate_id in duplicate_ids:
        # Move what the delete returned rather than what a read saw before it:
        # a request already deleting its own entry (start_reading) is resolved
        # by waiting for its row, and the entry it removed must not be
        # resurrected on the survivor from a snapshot that predates the commit.
        bind.execute(
            text("""
                WITH removed AS (
                    DELETE FROM reading_list WHERE book_id = :duplicate
                    RETURNING user_id, position
                )
                INSERT INTO reading_list (user_id, book_id, position)
                SELECT user_id, :real, position FROM removed
                ON CONFLICT (user_id, book_id) DO NOTHING
                """),
            {"real": real_id, "duplicate": duplicate_id},
        )


def _move_readings(bind: Connection, row: RowMapping, real_id: int) -> None:
    """Carry the duplicate's Readings to the survivor, under both sides' locks."""
    duplicate_id = row["id"]

    # update_reading() rewrites a Reading without taking its Book's lock, so a
    # fold that compared a snapshot could delete the row an edit committed while
    # the delete waited on it. Hold both sides' Readings first: the comparisons
    # below then run on the values the edits left, and an edited Reading that no
    # longer matches is refused rather than folded away.
    bind.execute(
        text("SELECT 1 FROM readings WHERE book_id IN (:duplicate, :real) FOR UPDATE"),
        {"real": real_id, "duplicate": duplicate_id},
    )

    # A reader with no Reading of the real Book keeps this one, moved across.
    bind.execute(
        text("""
            UPDATE readings SET book_id = :real
            WHERE book_id = :duplicate
              AND user_id NOT IN (SELECT user_id FROM readings WHERE book_id = :real)
            """),
        {"real": real_id, "duplicate": duplicate_id},
    )

    # The same read logged against both records is one entry: a duplicate
    # Reading is folded away when the survivor has a match for it on what the
    # Reading says, paired one for one so a re-read logged on both sides is
    # matched entry for entry rather than only on its first entry. A Reading
    # left over is one the survivor cannot account for; a person decides below.
    bind.execute(
        text("""
            DELETE FROM readings r
            USING (
                SELECT id, user_id, status, rating, start_date, end_date,
                       row_number() OVER (
                           PARTITION BY user_id, status, rating, start_date, end_date ORDER BY id
                       ) AS occurrence
                FROM readings WHERE book_id = :duplicate
            ) d
            WHERE r.id = d.id
              AND EXISTS (
                  SELECT 1 FROM (
                      SELECT user_id, status, rating, start_date, end_date,
                             row_number() OVER (
                                 PARTITION BY user_id, status, rating, start_date, end_date ORDER BY id
                             ) AS occurrence
                      FROM readings WHERE book_id = :real
                  ) kept
                  WHERE kept.user_id = d.user_id
                    AND kept.status = d.status
                    AND kept.rating IS NOT DISTINCT FROM d.rating
                    AND kept.start_date IS NOT DISTINCT FROM d.start_date
                    AND kept.end_date IS NOT DISTINCT FROM d.end_date
                    AND kept.occurrence = d.occurrence
              )
            """),
        {"real": real_id, "duplicate": duplicate_id},
    )

    remaining = bind.execute(
        text("SELECT id, user_id, status, rating FROM readings WHERE book_id = :duplicate ORDER BY id"),
        {"duplicate": duplicate_id},
    ).fetchall()
    if remaining:
        details = "; ".join(
            f"#{reading_id} for user {user_id} ({status}, rating {rating})"
            for reading_id, user_id, status, rating in remaining
        )
        raise RuntimeError(
            f"Refusing to delete ISBN-less Book {_describe(row)}: its Reading(s) {details} differ "
            f"from the Reading the same reader has of {REAL_ISBN}, so folding them would choose one "
            "history over the other. Merge them by hand before this migration runs."
        )


def upgrade() -> None:
    bind = op.get_bind()
    # The queue moves before any Book is locked (see _move_queue), so the
    # candidates are read without one here and the Book locks are taken below.
    candidates = bind.execute(text("SELECT id FROM books WHERE btrim(isbn13) = ''")).fetchall()
    if not candidates:
        return
    duplicate_ids = [row[0] for row in candidates]

    survivor = bind.execute(text("SELECT id FROM books WHERE isbn13 = :isbn"), {"isbn": REAL_ISBN}).first()
    survivor_id = survivor[0] if survivor else None
    if survivor_id is not None:
        _move_queue(bind, survivor_id, duplicate_ids)

    # Lock the candidates before reading what depends on them. A Reading insert
    # takes FOR KEY SHARE on its Book and conflicts with this FOR UPDATE, so the
    # history read below cannot go stale: the write either lands before the lock
    # (and is moved) or waits until the migration has finished. Read the same
    # rows again under the lock: if an ISBN moved while the queue moved, the
    # entries may have gone to a Book this repair keeps or deletes.
    locked = bind.execute(text("SELECT id FROM books WHERE btrim(isbn13) = '' FOR UPDATE")).fetchall()
    if {row[0] for row in locked} != set(duplicate_ids):
        raise RuntimeError(_CATALOGUE_CHANGED)
    empty = bind.execute(text(_EMPTY_KEYED_BOOKS)).mappings().all()

    # Lock the survivor too, and copy to it by id below: an edit can change its
    # ISBN, so a match by ISBN alone could be undone before the copy lands.
    real = (
        bind.execute(
            text(
                f"SELECT b.id, btrim(b.title) AS title, {_AUTHORS} AS authors "
                "FROM books b WHERE b.isbn13 = :isbn FOR UPDATE"
            ),
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
    if real["id"] != survivor_id:
        raise RuntimeError(_CATALOGUE_CHANGED)

    for row in empty:
        reasons = []
        if row["title"] != real["title"]:
            reasons.append(f"its title differs from {REAL_ISBN}'s {real['title']!r}")
        if row["authors"] != real["authors"]:
            reasons.append("its authors differ from that Book's")
        if reasons:
            raise RuntimeError(
                f"Refusing to delete ISBN-less Book {_describe(row)}: {', '.join(reasons)}. "
                "A row this repair does not recognise needs a person to say which ISBN it should "
                "carry, or to merge it by hand, before this migration runs."
            )

    for row in empty:
        _move_readings(bind, row, real["id"])
        # Only fills a gap: a cover the real Book already has wins. An empty
        # string is how an import records a missing cover, so it is no cover to
        # keep either. The row is the id matched above and held by its lock, so
        # the ISBN cannot move it away.
        bind.execute(
            text("""
                UPDATE books
                SET thumbnail_url = COALESCE(NULLIF(thumbnail_url, ''), NULLIF(:thumbnail_url, '')),
                    cover_url = COALESCE(NULLIF(cover_url, ''), NULLIF(:cover_url, ''))
                WHERE id = :id
                """),
            {"thumbnail_url": row["thumbnail_url"], "cover_url": row["cover_url"], "id": real["id"]},
        )
        # The row's author links go with it (ON DELETE CASCADE). The move above
        # is what makes the delete safe: its history has left with it.
        bind.execute(text("DELETE FROM books WHERE id = :id"), {"id": row["id"]})


def downgrade() -> None:
    # Nothing to put back: the row was a duplicate of a Book that is still here,
    # and re-creating it would restore the defect rather than the data.
    pass
