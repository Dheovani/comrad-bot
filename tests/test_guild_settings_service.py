from pathlib import Path

import pytest

from comradbot.database.repositories.guild_settings import GuildSettingsRepository
from comradbot.database.session import Database
from comradbot.errors import ValidationError
from comradbot.services.settings import GuildSettingsService


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
