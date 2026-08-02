"""Add per-guild custom sound quotas.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column("max_sound_count", sa.Integer(), server_default="100", nullable=False),
    )
    op.add_column(
        "guild_settings",
        sa.Column("max_sound_storage_mb", sa.Integer(), server_default="500", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "max_sound_storage_mb")
    op.drop_column("guild_settings", "max_sound_count")
