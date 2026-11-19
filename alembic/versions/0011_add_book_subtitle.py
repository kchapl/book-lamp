"""Store a Book's subtitle as its own field (#384).

A Book's title and subtitle are two facts a metadata provider supplies
separately, and #380 could only guess where one ended and the other began in
the browser. This revision adds the column and nothing else.

The build command runs ``alembic upgrade head`` before the instance written for
it starts, while the instance it replaces is still serving (DEPLOYMENT.md,
"Schema changes that span two releases"). That instance writes the combined
title it always has, so a rewrite here could be undone by an edit opened before
the deploy and saved after it: the row would hold the combined title beside the
subtitle this revision wrote, and every display would show the subtitle twice.
Splitting the stored titles is therefore left to
``scripts/backfill_subtitles.py``, which runs once the old instance has stopped,
by the same rule the application shares: a colon or a spaced dash, a main title
longer than three characters, and a non-empty remainder. ``Re: Zero``, ``10:04``,
``Spider-Man`` and a title with no separator stay whole, and a wrong split is
recovered by editing the Book.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-19
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS subtitle TEXT")


def downgrade() -> None:
    # Put the two parts back into the title before dropping the column, so a
    # downgrade loses no text, whichever release filled the subtitles.
    op.execute("""
        UPDATE books
        SET title = title || ': ' || subtitle
        WHERE NULLIF(btrim(subtitle), '') IS NOT NULL
        """)
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS subtitle")
