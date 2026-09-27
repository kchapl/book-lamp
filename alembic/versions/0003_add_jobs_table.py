"""Add jobs table for background operations persistence.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-07
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id            TEXT PRIMARY KEY,
            user_id       INTEGER REFERENCES users(id) ON DELETE CASCADE,
            function_name TEXT NOT NULL,
            status        TEXT NOT NULL DEFAULT 'pending',
            progress      INTEGER NOT NULL DEFAULT 0,
            result        TEXT,
            error         TEXT,
            created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
            started_at    TIMESTAMPTZ,
            completed_at  TIMESTAMPTZ
        )
    """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON jobs(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_jobs_status")
    op.execute("DROP INDEX IF EXISTS idx_jobs_user_id")
    op.execute("DROP TABLE IF EXISTS jobs")
