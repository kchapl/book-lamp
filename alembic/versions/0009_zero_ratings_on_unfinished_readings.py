"""Zero the ratings stored on Readings that never reached Completed.

A rating is the reader's verdict on a Reading, and only a Completed Reading has
one (see `book_lamp/utils/readings.py`). Every write path enforces that now, but
rows written before it may still carry a rating beside 'In Progress' or
'Abandoned'. The pages hide those ratings, yet the data behind them is still
read: `filter_reading_log`'s min-rating filter keeps the Reading, `rating_desc`
sorts by the hidden score, and the MCP tool reports it. Hiding a value that is
still queried leaves the Reading Log and the API disagreeing about the same row.

The repair zeroes the stale value rather than deleting the Reading: the Reading
is real history, and 0 is what "no rating" already means in the column. Each
statement is limited to a non-zero rating, so a database that has none is left
untouched and re-running this is a no-op.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-17
"""

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

#: The only Reading Status that may carry a rating, spelled as the rows hold it.
RATED_STATUS = "Completed"


def upgrade() -> None:
    op.execute(f"""
        UPDATE readings
        SET rating = 0
        WHERE status <> '{RATED_STATUS}'
          AND COALESCE(rating, 0) <> 0
        """)


def downgrade() -> None:
    # Nothing to put back: the values this zeroed were not a verdict on the
    # Reading, and no other column recorded them. A downgrade cannot invent a
    # rating the reader never gave.
    pass
