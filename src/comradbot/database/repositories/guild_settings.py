"""Persistence operations for guild-scoped configuration."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.database.models import GuildSettings


class GuildSettingsRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def get(self, guild_id: int) -> GuildSettings | None:
        async with self._sessions() as session:
            return await session.get(GuildSettings, guild_id)

    async def update(
        self,
        guild_id: int,
        *,
        default_volume: float,
        ai_enabled: bool,
        max_sound_count: int,
        max_sound_storage_mb: int,
        ai_conversation_scope: str,
        ai_retention_days: int,
        ai_daily_request_budget: int,
    ) -> GuildSettings:
        async with self._sessions.begin() as session:
            result = await session.execute(
                select(GuildSettings).where(GuildSettings.guild_id == guild_id)
            )
            settings = result.scalar_one_or_none()
            if settings is None:
                settings = GuildSettings(
                    guild_id=guild_id,
                    default_volume=default_volume,
                    ai_enabled=ai_enabled,
                    max_sound_count=max_sound_count,
                    max_sound_storage_mb=max_sound_storage_mb,
                    ai_conversation_scope=ai_conversation_scope,
                    ai_retention_days=ai_retention_days,
                    ai_daily_request_budget=ai_daily_request_budget,
                )
                session.add(settings)
            else:
                settings.default_volume = default_volume
                settings.ai_enabled = ai_enabled
                settings.max_sound_count = max_sound_count
                settings.max_sound_storage_mb = max_sound_storage_mb
                settings.ai_conversation_scope = ai_conversation_scope
                settings.ai_retention_days = ai_retention_days
                settings.ai_daily_request_budget = ai_daily_request_budget
            await session.flush()
            return settings
