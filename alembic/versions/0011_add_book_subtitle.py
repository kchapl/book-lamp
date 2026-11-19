"""Store a Book's subtitle as its own field (#384).

A Book's title and subtitle are two facts a metadata provider supplies
separately, and #380 could only guess where one ended and the other began in
the browser. This migration adds the column and splits the titles already
stored, by the rule below, frozen at this revision:

- a colon, or a dash with space on both sides, separates the parts;
- the main title must be longer than three characters, so ``Re: Zero`` and
  ``10:04`` stay whole;
- the remainder must say something;
- a title with no separator is left exactly as it is, because cutting it would
  turn ``Dune Messiah`` into a subtitle of ``Dune``.

Only a row that splits safely is touched. The parts recombine into the original
apart from the whitespace the rule normalises, so no row loses text. A guess
stays a guess: the subtitle backfill only fills a NULL, so it can give a
subtitle to a title this rule left whole, but it never revisits a split made
here. Recovering a wrong split means editing the Book.

The rewrite is visible to a deployment that still serves the previous instance
(DEPLOYMENT.md runs migrations while it does): that instance shows the main
title without the new subtitle until it is replaced, and a Book it edits during
the deploy can be written with the combined title beside the subtitle set here.
Exports, the Reading Log and the statistics and recommendations built from them
read that pair as one name (``full_title``); a detail view shows the stored
fields until the Book is edited, and the next save through the new instance
normalises the pair into its parts, so no row loses text either way.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-19
"""

import re
from typing import Optional

from sqlalchemy import text

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

#: The split rule as the app defined it when this revision was written, frozen
#: here rather than imported: a later change to the app's rule must not rewrite
#: a fresh database differently from one migrated through this revision years
#: earlier. The punctuation that separates the parts is a colon, or a dash with
#: space on both sides; a bare hyphen stays in the word it belongs to.
_SPACED_DASHES = (" - ", " \u2013 ", " \u2014 ")


def _separator_span(text: str) -> Optional[tuple[int, int]]:
    """Where a subtitle separator starts and ends in a ``title``, or None.

    Scanned rather than matched, so the cost stays linear on a title with a long
    run of spaces. The rule it applies is the one frozen above.
    """
    colon = text.find(":")
    dash = min((index for index in (text.find(d) for d in _SPACED_DASHES) if index != -1), default=-1)

    if colon == -1 and dash == -1:
        return None
    if dash == -1 or (colon != -1 and colon < dash):
        return colon, colon + 1
    return dash, dash + 3


def _split_title_parts(title: str) -> tuple[str, Optional[str]]:
    """The stored title and subtitle this revision writes for ``title``."""
    main = re.sub(r"\s+", " ", str(title or "")).strip()
    span = _separator_span(main)
    if span is None:
        return main, None

    start, end = span
    head = main[:start].strip()
    tail = main[end:].strip()
    if len(head) <= 3 or not tail:
        # "Re: Zero", "10:04" and "Colon:" are titles, not a heading with a
        # subtitle: a prefix that short does not stand on its own.
        return main, None
    return head, tail


def upgrade() -> None:
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS subtitle TEXT")

    # Read in one pass so the update below writes rows the rule actually split.
    rows = op.get_bind().execute(text("SELECT id, title FROM books WHERE subtitle IS NULL")).fetchall()
    for book_id, title in rows:
        main, subtitle = _split_title_parts(title)
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
