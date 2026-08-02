"""Add immutable custom sound audit records.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sound_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("sound_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("acted_as_moderator", sa.Boolean(), nullable=False),
        sa.Column("previous_name", sa.String(length=50), nullable=False),
        sa.Column("new_name", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_sound_audit_guild_created",
        "sound_audit_logs",
        ["guild_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_sound_audit_guild_created", table_name="sound_audit_logs")
    op.drop_table("sound_audit_logs")
