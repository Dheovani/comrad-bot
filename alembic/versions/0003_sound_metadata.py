"""Add custom sound categories and tags.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("custom_sounds", sa.Column("category", sa.String(length=30), nullable=True))
    op.add_column(
        "custom_sounds",
        sa.Column("tags_json", sa.Text(), server_default="[]", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("custom_sounds", "tags_json")
    op.drop_column("custom_sounds", "category")
