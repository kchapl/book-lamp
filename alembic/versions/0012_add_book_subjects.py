"""Store every subject a Book carries (#407).

A Book used to store exactly one subject in three columns. This revision adds
the list beside them. A row written before it keeps its category in those
columns, and the application reads such a row as its one entry, so no data is
rewritten here: the migration is only the new column.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS subjects JSONB NOT NULL DEFAULT '[]'::jsonb")


def downgrade() -> None:
    # The legacy columns still carry each Book's first subject, so dropping the
    # list loses only the extra entries this revision made possible.
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS subjects")
