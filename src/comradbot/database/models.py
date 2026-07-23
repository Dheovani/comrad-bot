"""SQLAlchemy persistence models."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class GuildSettings(Base):
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    default_volume: Mapped[float] = mapped_column(Float, default=0.5)
    ai_enabled: Mapped[bool] = mapped_column(default=True)
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


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    __table_args__ = (UniqueConstraint("guild_id", "scope_id", name="uq_ai_conversation_scope"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
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
