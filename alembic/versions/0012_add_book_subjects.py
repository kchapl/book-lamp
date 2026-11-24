"""Store every subject a Book carries (#407).

A Book used to store exactly one subject in three columns. This revision adds
the list, and gives every existing Book its current subject as the list's one
entry. A row whose stored category names no subject (a Dewey code, a language
code, a media type) gets an empty list rather than a junk entry.

The normalisation is the application's own rule, imported here so the migration
and every read agree on what a subject is.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""

import json

from sqlalchemy import text

from alembic import op
from book_lamp.utils.books import normalise_subjects

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS subjects JSONB NOT NULL DEFAULT '[]'::jsonb")

    conn = op.get_bind()
    rows = conn.execute(text("""
            SELECT id, bisac_category, bisac_main_category
            FROM books
            WHERE subjects = '[]'::jsonb
            """)).mappings()
    for row in rows:
        raw_category = row["bisac_category"] or row["bisac_main_category"]
        subjects = normalise_subjects([raw_category]) if raw_category else []
        if not subjects:
            continue
        conn.execute(
            text("UPDATE books SET subjects = CAST(:subjects AS jsonb) WHERE id = :id"),
            {"subjects": json.dumps(subjects), "id": row["id"]},
        )


def downgrade() -> None:
    # The legacy columns still carry each Book's first subject, so dropping the
    # list loses only the extra entries this revision made possible.
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS subjects")
