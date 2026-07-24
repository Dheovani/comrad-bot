"""Business rules for persistent guild configuration."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from comradbot.database.repositories.guild_settings import GuildSettingsRepository


@dataclass(frozen=True, slots=True)
class GuildConfiguration:
    default_volume: float
    ai_enabled: bool


class GuildSettingsService:
    def __init__(
        self,
        repository: GuildSettingsRepository,
        *,
        fallback_volume: float,
        fallback_ai_enabled: bool = True,
    ) -> None:
        self._repository = repository
        self._fallback = GuildConfiguration(fallback_volume, fallback_ai_enabled)
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get(self, guild_id: int) -> GuildConfiguration:
        settings = await self._repository.get(guild_id)
        if settings is None:
            return self._fallback
        return GuildConfiguration(settings.default_volume, settings.ai_enabled)

    async def set_default_volume(self, guild_id: int, volume: float) -> GuildConfiguration:
        bounded_volume = min(max(volume, 0.0), 1.0)
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=bounded_volume,
                ai_enabled=current.ai_enabled,
            )
        return GuildConfiguration(updated.default_volume, updated.ai_enabled)

    async def set_ai_enabled(self, guild_id: int, enabled: bool) -> GuildConfiguration:
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=current.default_volume,
                ai_enabled=enabled,
            )
        return GuildConfiguration(updated.default_volume, updated.ai_enabled)

    async def default_volume_for(self, guild_id: int) -> float:
        return (await self.get(guild_id)).default_volume

    async def ai_enabled_for(self, guild_id: int) -> bool:
        return (await self.get(guild_id)).ai_enabled
