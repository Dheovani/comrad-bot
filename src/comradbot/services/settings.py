"""Business rules for persistent guild configuration."""

import asyncio
from collections import defaultdict
from dataclasses import dataclass

from comradbot.ai.policy import ConversationPolicy, ConversationScope
from comradbot.database.models import GuildSettings
from comradbot.database.repositories.guild_settings import GuildSettingsRepository
from comradbot.errors import ValidationError


@dataclass(frozen=True, slots=True)
class GuildConfiguration:
    default_volume: float
    ai_enabled: bool
    max_sound_count: int
    max_sound_storage_mb: int
    ai_conversation_scope: ConversationScope
    ai_retention_days: int
    ai_daily_request_budget: int


class GuildSettingsService:
    def __init__(
        self,
        repository: GuildSettingsRepository,
        *,
        fallback_volume: float,
        fallback_ai_enabled: bool = True,
        fallback_max_sound_count: int = 100,
        fallback_max_sound_storage_mb: int = 500,
        fallback_ai_conversation_scope: ConversationScope = ConversationScope.CHANNEL,
        fallback_ai_retention_days: int = 30,
        fallback_ai_daily_request_budget: int = 100,
    ) -> None:
        self._repository = repository
        self._fallback = GuildConfiguration(
            fallback_volume,
            fallback_ai_enabled,
            fallback_max_sound_count,
            fallback_max_sound_storage_mb,
            fallback_ai_conversation_scope,
            fallback_ai_retention_days,
            fallback_ai_daily_request_budget,
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
                ai_conversation_scope=current.ai_conversation_scope.value,
                ai_retention_days=current.ai_retention_days,
                ai_daily_request_budget=current.ai_daily_request_budget,
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
                ai_conversation_scope=current.ai_conversation_scope.value,
                ai_retention_days=current.ai_retention_days,
                ai_daily_request_budget=current.ai_daily_request_budget,
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
                ai_conversation_scope=current.ai_conversation_scope.value,
                ai_retention_days=current.ai_retention_days,
                ai_daily_request_budget=current.ai_daily_request_budget,
            )
        return self._configuration(updated)

    async def default_volume_for(self, guild_id: int) -> float:
        return (await self.get(guild_id)).default_volume

    async def ai_enabled_for(self, guild_id: int) -> bool:
        return (await self.get(guild_id)).ai_enabled

    async def sound_quota_for(self, guild_id: int) -> tuple[int, int]:
        settings = await self.get(guild_id)
        return settings.max_sound_count, settings.max_sound_storage_mb * 1024 * 1024

    async def set_ai_conversation_policy(
        self,
        guild_id: int,
        *,
        scope: ConversationScope,
        retention_days: int,
    ) -> GuildConfiguration:
        if not 1 <= retention_days <= 365:
            raise ValidationError("AI conversation retention must be between 1 and 365 days.")
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=current.default_volume,
                ai_enabled=current.ai_enabled,
                max_sound_count=current.max_sound_count,
                max_sound_storage_mb=current.max_sound_storage_mb,
                ai_conversation_scope=scope.value,
                ai_retention_days=retention_days,
                ai_daily_request_budget=current.ai_daily_request_budget,
            )
        return self._configuration(updated)

    async def ai_conversation_policy_for(self, guild_id: int) -> ConversationPolicy:
        settings = await self.get(guild_id)
        return ConversationPolicy(
            scope=settings.ai_conversation_scope,
            retention_days=settings.ai_retention_days,
        )

    async def set_ai_daily_request_budget(
        self,
        guild_id: int,
        daily_requests: int,
    ) -> GuildConfiguration:
        if not 0 <= daily_requests <= 10000:
            raise ValidationError("The daily AI request budget must be between 0 and 10000.")
        async with self._locks[guild_id]:
            current = await self.get(guild_id)
            updated = await self._repository.update(
                guild_id,
                default_volume=current.default_volume,
                ai_enabled=current.ai_enabled,
                max_sound_count=current.max_sound_count,
                max_sound_storage_mb=current.max_sound_storage_mb,
                ai_conversation_scope=current.ai_conversation_scope.value,
                ai_retention_days=current.ai_retention_days,
                ai_daily_request_budget=daily_requests,
            )
        return self._configuration(updated)

    async def ai_daily_request_budget_for(self, guild_id: int) -> int:
        return (await self.get(guild_id)).ai_daily_request_budget

    @staticmethod
    def _configuration(settings: GuildSettings) -> GuildConfiguration:
        return GuildConfiguration(
            default_volume=settings.default_volume,
            ai_enabled=settings.ai_enabled,
            max_sound_count=settings.max_sound_count,
            max_sound_storage_mb=settings.max_sound_storage_mb,
            ai_conversation_scope=ConversationScope(settings.ai_conversation_scope),
            ai_retention_days=settings.ai_retention_days,
            ai_daily_request_budget=settings.ai_daily_request_budget,
        )
