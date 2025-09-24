"""Add timezone column to user settings.

Revision ID: a24f8c67e4f3
Revises: d65e92630518
Create Date: 2024-10-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a24f8c67e4f3"
down_revision = "d65e92630518"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add timezone column with UTC default."""

    op.add_column(
        "user_settings",
        sa.Column(
            "timezone",
            sa.String(length=50),
            nullable=False,
            server_default="UTC",
        ),
    )

    # Ensure existing rows have UTC populated
    op.execute("UPDATE user_settings SET timezone = 'UTC' WHERE timezone IS NULL")


def downgrade() -> None:
    """Remove timezone column."""

    op.drop_column("user_settings", "timezone")
