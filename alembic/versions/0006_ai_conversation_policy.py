"""Add guild AI conversation scope and retention policy.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "ai_conversation_scope",
            sa.String(length=20),
            server_default="channel",
            nullable=False,
        ),
    )
    op.add_column(
        "guild_settings",
        sa.Column("ai_retention_days", sa.Integer(), server_default="30", nullable=False),
    )
    unique_constraints = {
        constraint["name"]
        for constraint in sa.inspect(op.get_bind()).get_unique_constraints("ai_conversations")
    }
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.add_column(
            sa.Column(
                "scope_type",
                sa.String(length=20),
                server_default="channel",
                nullable=False,
            )
        )
        if "uq_ai_conversation_scope" in unique_constraints:
            batch_op.drop_constraint("uq_ai_conversation_scope", type_="unique")
        batch_op.create_unique_constraint(
            "uq_ai_conversation_scope",
            ["guild_id", "scope_type", "scope_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("ai_conversations") as batch_op:
        batch_op.drop_constraint("uq_ai_conversation_scope", type_="unique")
        batch_op.create_unique_constraint(
            "uq_ai_conversation_scope",
            ["guild_id", "scope_id"],
        )
        batch_op.drop_column("scope_type")
    op.drop_column("guild_settings", "ai_retention_days")
    op.drop_column("guild_settings", "ai_conversation_scope")
