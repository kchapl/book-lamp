"""Record a Book the reader has without putting it in the queue.

A Reading List row was the only per-reader link to a Book besides a Reading.
`books` is one catalogue for everyone (`isbn13` is unique) and nothing on it
names a reader, so a Book saved with the add form's tickbox clear had no owner:
`get_all_books`, and everything built on it — My Books, the CSV export, the
owned set discovery subtracts — joins through `readings` or `reading_list`.

A row now means the reader has the Book. `queued` narrows that to the queue
they mean to read next, which is what every existing row meant, so they all
start queued.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-16
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE reading_list ADD COLUMN IF NOT EXISTS queued BOOLEAN NOT NULL DEFAULT TRUE")


def downgrade() -> None:
    # A Book the reader never queued has to leave the list: without the column
    # its row would read as queued, and a Book in a queue its reader did not put
    # it in is worse than one the reader can add again.
    op.execute("DELETE FROM reading_list WHERE NOT queued")
    op.execute("ALTER TABLE reading_list DROP COLUMN IF EXISTS queued")
