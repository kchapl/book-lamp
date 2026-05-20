"""Add indexes for query performance.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-13
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reading records indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_records_user_id ON reading_records(user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_records_status ON reading_records(status)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_records_book_id ON reading_records(book_id)"
    )

    # Reading list indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_reading_list_user_id ON reading_list(user_id)"
    )

    # Settings index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_settings_user_id ON settings(user_id)"
    )

    # Book authors junction table indexes
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_book_authors_book_id ON book_authors(book_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_book_authors_author_id ON book_authors(author_id)"
    )

    # Users email index for login lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"
    )

    # Recommendations index
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_recommendations_user_id ON recommendations(user_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_reading_records_user_id")
    op.execute("DROP INDEX IF EXISTS idx_reading_records_status")
    op.execute("DROP INDEX IF EXISTS idx_reading_records_book_id")
    op.execute("DROP INDEX IF EXISTS idx_reading_list_user_id")
    op.execute("DROP INDEX IF EXISTS idx_settings_user_id")
    op.execute("DROP INDEX IF EXISTS idx_book_authors_book_id")
    op.execute("DROP INDEX IF EXISTS idx_book_authors_author_id")
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("DROP INDEX IF EXISTS idx_recommendations_user_id")