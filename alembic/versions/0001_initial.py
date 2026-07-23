"""Initial ComradBot schema.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guild_settings",
        sa.Column("guild_id", sa.BigInteger(), autoincrement=False, nullable=False),
        sa.Column("default_volume", sa.Float(), nullable=False),
        sa.Column("ai_enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("guild_id"),
    )
    op.create_table(
        "custom_sounds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("normalized_name", sa.String(length=50), nullable=False),
        sa.Column("relative_path", sa.String(length=255), nullable=False),
        sa.Column("creator_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("duration_seconds", sa.Float(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("play_count", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "normalized_name", name="uq_sound_guild_name"),
        sa.UniqueConstraint("relative_path"),
    )
    op.create_index("ix_sound_guild", "custom_sounds", ["guild_id"], unique=False)
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=False),
        sa.Column("messages_json", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "scope_id", name="uq_ai_conversation_scope"),
    )
    op.create_table(
        "ai_usage",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("operation", sa.String(length=30), nullable=False),
        sa.Column("input_characters", sa.Integer(), nullable=False),
        sa.Column("output_characters", sa.Integer(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_usage_guild_created",
        "ai_usage",
        ["guild_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ai_usage_guild_created", table_name="ai_usage")
    op.drop_table("ai_usage")
    op.drop_table("ai_conversations")
    op.drop_index("ix_sound_guild", table_name="custom_sounds")
    op.drop_table("custom_sounds")
    op.drop_table("guild_settings")
