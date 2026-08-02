"""Add per-guild daily AI request budgets.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "guild_settings",
        sa.Column(
            "ai_daily_request_budget",
            sa.Integer(),
            server_default="100",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("guild_settings", "ai_daily_request_budget")
