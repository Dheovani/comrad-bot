from pathlib import Path

import pytest

from comradbot.ai.policy import ConversationPolicy, ConversationScope
from comradbot.database.repositories.guild_settings import GuildSettingsRepository
from comradbot.database.session import Database
from comradbot.errors import FeatureDisabledError, ValidationError
from comradbot.services.settings import GuildFeature, GuildSettingsService


@pytest.mark.asyncio
async def test_guild_settings_persist_and_preserve_independent_values(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'settings.db').as_posix()}")
    await database.migrate()
    service = GuildSettingsService(
        GuildSettingsRepository(database.sessions),
        fallback_volume=0.5,
    )
    try:
        assert (await service.get(123)).default_volume == 0.5
        assert (await service.get(123)).ai_enabled is True
        assert (await service.get(123)).max_sound_count == 100
        assert (await service.get(123)).ai_conversation_scope is ConversationScope.CHANNEL
        assert (await service.get(123)).ai_retention_days == 30
        assert (await service.get(123)).ai_daily_request_budget == 100
        assert (await service.get(123)).disabled_features == frozenset()

        await service.set_default_volume(123, 0.8)
        disabled = await service.set_ai_enabled(123, False)

        assert disabled.default_volume == 0.8
        assert disabled.ai_enabled is False
        reloaded = GuildSettingsService(
            GuildSettingsRepository(database.sessions),
            fallback_volume=0.1,
        )
        assert await reloaded.get(123) == disabled
        assert await reloaded.get(456) != disabled

        quotas = await service.set_sound_quotas(123, max_count=12, max_storage_mb=34)
        assert quotas.max_sound_count == 12
        assert quotas.max_sound_storage_mb == 34
        assert await service.sound_quota_for(123) == (12, 34 * 1024 * 1024)
        with pytest.raises(ValidationError, match="count quota"):
            await service.set_sound_quotas(123, max_count=0, max_storage_mb=34)

        memory = await service.set_ai_conversation_policy(
            123,
            scope=ConversationScope.USER,
            retention_days=14,
        )
        assert memory.ai_conversation_scope is ConversationScope.USER
        assert memory.ai_retention_days == 14
        assert await service.ai_conversation_policy_for(123) == ConversationPolicy(
            scope=ConversationScope.USER,
            retention_days=14,
        )
        with pytest.raises(ValidationError, match="between 1 and 365"):
            await service.set_ai_conversation_policy(
                123,
                scope=ConversationScope.CHANNEL,
                retention_days=0,
            )
        budget = await service.set_ai_daily_request_budget(123, 25)
        assert budget.ai_daily_request_budget == 25
        assert await service.ai_daily_request_budget_for(123) == 25
        with pytest.raises(ValidationError, match="between 0 and 10000"):
            await service.set_ai_daily_request_budget(123, -1)
        disabled = await service.set_feature_enabled(123, GuildFeature.SOCIAL, False)
        assert disabled.disabled_features == frozenset({GuildFeature.SOCIAL})
        assert not await service.feature_enabled_for(123, GuildFeature.SOCIAL)
        with pytest.raises(FeatureDisabledError, match="social command group is disabled"):
            await service.ensure_feature_enabled(123, GuildFeature.SOCIAL)
        enabled = await service.set_feature_enabled(123, GuildFeature.SOCIAL, True)
        assert enabled.disabled_features == frozenset()
        assert await service.feature_enabled_for(123, GuildFeature.SOCIAL)
        ai_disabled = await service.set_feature_enabled(123, GuildFeature.AI, False)
        assert ai_disabled.ai_enabled is False
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_guild_settings_bounds_persisted_volume(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'settings.db').as_posix()}")
    await database.migrate()
    service = GuildSettingsService(
        GuildSettingsRepository(database.sessions),
        fallback_volume=0.5,
    )
    try:
        assert (await service.set_default_volume(1, 2.0)).default_volume == 1.0
        assert (await service.set_default_volume(1, -1.0)).default_volume == 0.0
    finally:
        await database.close()
