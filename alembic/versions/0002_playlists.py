"""Add persistent guild playlists and saved tracks.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "playlists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("guild_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("normalized_name", sa.String(length=50), nullable=False),
        sa.Column("creator_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("guild_id", "normalized_name", name="uq_playlist_guild_name"),
    )
    op.create_index("ix_playlist_guild", "playlists", ["guild_id"], unique=False)
    op.create_table(
        "saved_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("playlist_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("source_reference", sa.String(length=2000), nullable=False),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("added_by_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["playlist_id"], ["playlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("playlist_id", "position", name="uq_saved_track_position"),
    )
    op.create_index("ix_saved_track_playlist", "saved_tracks", ["playlist_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_saved_track_playlist", table_name="saved_tracks")
    op.drop_table("saved_tracks")
    op.drop_index("ix_playlist_guild", table_name="playlists")
    op.drop_table("playlists")
