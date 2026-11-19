"""Store a Book's subtitle as its own field (#384).

A Book's title and subtitle are two facts a metadata provider supplies
separately, and #380 could only guess where one ended and the other began in
the browser. This migration adds the column and splits the titles already
stored, by the one rule the app now uses:

- a colon, or a dash with space on both sides, separates the parts;
- the main title must be longer than three characters, so ``Re: Zero`` and
  ``10:04`` stay whole;
- the remainder must say something;
- a title with no separator is left exactly as it is, because cutting it would
  turn ``Dune Messiah`` into a subtitle of ``Dune``.

Only a row that splits safely is touched. The parts recombine into the original
apart from the whitespace the rule normalises, so no row loses text. A provider
that knows the real subtitle can still correct a guess later: the subtitle
backfill only fills a NULL, and never rewrites ``title``.

The rewrite is visible to a deployment that still serves the previous instance
(DEPLOYMENT.md runs migrations while it does): that instance shows the main
title without the new subtitle until it is replaced. This is a presentation
difference during the deploy, not data loss.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-19
"""

from sqlalchemy import text

from alembic import op
from book_lamp.utils.books import split_title_parts

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS subtitle TEXT")

    # Read in one pass so the update below writes rows the rule actually split.
    # The split is done by the same helper the write paths use, so the backfill
    # cannot disagree with where a newly stored Book divides its title.
    rows = op.get_bind().execute(text("SELECT id, title FROM books WHERE subtitle IS NULL")).fetchall()
    for book_id, title in rows:
        main, subtitle = split_title_parts(title)
        if subtitle is None:
            continue
        op.get_bind().execute(
            text("UPDATE books SET title = :title, subtitle = :subtitle WHERE id = :id"),
            {"title": main, "subtitle": subtitle, "id": book_id},
        )


def downgrade() -> None:
    # Put the two parts back into the title before dropping the column, so a
    # downgrade loses no text.
    op.execute("""
        UPDATE books
        SET title = title || ': ' || subtitle
        WHERE NULLIF(btrim(subtitle), '') IS NOT NULL
        """)
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS subtitle")
