"""SQLAlchemy persistence models."""

import json
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    default_volume: Mapped[float] = mapped_column(Float, default=0.5)
    ai_enabled: Mapped[bool] = mapped_column(default=True)
    max_sound_count: Mapped[int] = mapped_column(Integer, default=100)
    max_sound_storage_mb: Mapped[int] = mapped_column(Integer, default=500)
    ai_conversation_scope: Mapped[str] = mapped_column(String(20), default="channel")
    ai_retention_days: Mapped[int] = mapped_column(Integer, default=30)
    ai_daily_request_budget: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CustomSound(Base):
    __tablename__ = "custom_sounds"
    __table_args__ = (
        UniqueConstraint("guild_id", "normalized_name", name="uq_sound_guild_name"),
        Index("ix_sound_guild", "guild_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(50), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    play_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str | None] = mapped_column(String(30))
    tags_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)

    @property
    def tags(self) -> tuple[str, ...]:
        try:
            decoded = json.loads(self.tags_json)
        except (TypeError, json.JSONDecodeError):
            return ()
        if not isinstance(decoded, list):
            return ()
        return tuple(tag for tag in decoded if isinstance(tag, str))


class SoundAuditLog(Base):
    __tablename__ = "sound_audit_logs"
    __table_args__ = (Index("ix_sound_audit_guild_created", "guild_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sound_id: Mapped[str] = mapped_column(String(36), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    acted_as_moderator: Mapped[bool] = mapped_column(nullable=False)
    previous_name: Mapped[str] = mapped_column(String(50), nullable=False)
    new_name: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = (
        UniqueConstraint("guild_id", "normalized_name", name="uq_playlist_guild_name"),
        Index("ix_playlist_guild", "guild_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(50), nullable=False)
    creator_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedTrack(Base):
    __tablename__ = "saved_tracks"
    __table_args__ = (
        UniqueConstraint("playlist_id", "position", name="uq_saved_track_position"),
        Index("ix_saved_track_playlist", "playlist_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(2000), nullable=False)
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    added_by_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (
        UniqueConstraint(
            "guild_id",
            "scope_type",
            "scope_id",
            name="uq_ai_conversation_scope",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    scope_type: Mapped[str] = mapped_column(String(20), default="channel", nullable=False)
    scope_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    messages_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AIUsage(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (Index("ix_ai_usage_guild_created", "guild_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operation: Mapped[str] = mapped_column(String(30), nullable=False)
    input_characters: Mapped[int] = mapped_column(Integer, nullable=False)
    output_characters: Mapped[int] = mapped_column(Integer, nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
