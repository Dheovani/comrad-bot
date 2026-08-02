"""Business rules for persistent guild configuration."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from comradbot.database.models import GuildSettings
from comradbot.database.repositories.guild_settings import GuildSettingsRepository
from comradbot.errors import ValidationError


@dataclass(frozen=True, slots=True)
class GuildConfiguration:
    default_volume: float
    ai_enabled: bool
    max_sound_count: int
    max_sound_storage_mb: int


class GuildSettingsService:
    def __init__(
        self,
        repository: GuildSettingsRepository,
        *,
        fallback_volume: float,
        fallback_ai_enabled: bool = True,
        fallback_max_sound_count: int = 100,
        fallback_max_sound_storage_mb: int = 500,
    ) -> None:
        self._repository = repository
        self._fallback = GuildConfiguration(
            fallback_volume,
            fallback_ai_enabled,
            fallback_max_sound_count,
            fallback_max_sound_storage_mb,
        )
        self._locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get(self, guild_id: int) -> GuildConfiguration:
        settings = await self._repository.get(guild_id)
        if settings is None:
            return self._fallback
        return self._configuration(settings)

    async def set_default_volume(self, guild_id: int, volume: float) -> GuildConfiguration:
        bounded_volume = min(max(volume, 0.0), 1.0)
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=bounded_volume,
                ai_enabled=current.ai_enabled,
                max_sound_count=current.max_sound_count,
                max_sound_storage_mb=current.max_sound_storage_mb,
            )
        return self._configuration(updated)

    async def set_ai_enabled(self, guild_id: int, enabled: bool) -> GuildConfiguration:
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=current.default_volume,
                ai_enabled=enabled,
                max_sound_count=current.max_sound_count,
                max_sound_storage_mb=current.max_sound_storage_mb,
            )
        return self._configuration(updated)

    async def set_sound_quotas(
        self,
        guild_id: int,
        *,
        max_count: int,
        max_storage_mb: int,
    ) -> GuildConfiguration:
        if not 1 <= max_count <= 10000:
            raise ValidationError("The custom sound count quota must be between 1 and 10000.")
        if not 1 <= max_storage_mb <= 100000:
            raise ValidationError(
                "The custom sound storage quota must be between 1 and 100000 MiB."
            )
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=current.default_volume,
                ai_enabled=current.ai_enabled,
                max_sound_count=max_count,
                max_sound_storage_mb=max_storage_mb,
            )
        return self._configuration(updated)

    async def default_volume_for(self, guild_id: int) -> float:
        return (await self.get(guild_id)).default_volume

    async def ai_enabled_for(self, guild_id: int) -> bool:
        return (await self.get(guild_id)).ai_enabled

    async def sound_quota_for(self, guild_id: int) -> tuple[int, int]:
        settings = await self.get(guild_id)
        return settings.max_sound_count, settings.max_sound_storage_mb * 1024 * 1024

    @staticmethod
    def _configuration(settings: GuildSettings) -> GuildConfiguration:
        return GuildConfiguration(
            default_volume=settings.default_volume,
            ai_enabled=settings.ai_enabled,
            max_sound_count=settings.max_sound_count,
            max_sound_storage_mb=settings.max_sound_storage_mb,
        )
