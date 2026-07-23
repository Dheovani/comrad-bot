"""Initial ComradBot schema.

Revision ID: 0001
Revises: None
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The metadata is the single schema definition during this initial MVP.
    from comradbot.database.models import Base

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from comradbot.database.models import Base

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
