"""Rename reading_records to readings.

The domain term is Reading (see CONTEXT.md): the table, its indexes and its
primary-key constraint follow it. 0001 and 0002 are left as they were written
so a database that has already run them converges with a fresh one here.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-12
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLE_OLD = "reading_records"
TABLE_NEW = "readings"

INDEX_RENAMES = [
    ("idx_reading_records_user_id", "idx_readings_user_id"),
    ("idx_reading_records_status", "idx_readings_status"),
    ("idx_reading_records_book_id", "idx_readings_book_id"),
]

# Postgres names the primary-key constraint after the table it was created on
# and does not follow a table rename.
CONSTRAINT_OLD = "reading_records_pkey"
CONSTRAINT_NEW = "readings_pkey"


def upgrade() -> None:
    op.rename_table(TABLE_OLD, TABLE_NEW)
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX IF EXISTS "{old}" RENAME TO "{new}"')
    op.execute(f'ALTER TABLE "{TABLE_NEW}" RENAME CONSTRAINT "{CONSTRAINT_OLD}" TO "{CONSTRAINT_NEW}"')


def downgrade() -> None:
    op.execute(f'ALTER TABLE "{TABLE_NEW}" RENAME CONSTRAINT "{CONSTRAINT_NEW}" TO "{CONSTRAINT_OLD}"')
    for old, new in INDEX_RENAMES:
        op.execute(f'ALTER INDEX IF EXISTS "{new}" RENAME TO "{old}"')
    op.rename_table(TABLE_NEW, TABLE_OLD)
