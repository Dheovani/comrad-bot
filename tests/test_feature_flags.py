from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from comradbot.commands.ai import AICog
from comradbot.commands.music import MusicCog
from comradbot.commands.social import SocialCog
from comradbot.commands.sounds import SoundsCog
from comradbot.services.settings import GuildFeature


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cog_type", "feature"),
    [
        (AICog, GuildFeature.AI),
        (MusicCog, GuildFeature.MUSIC),
        (SoundsCog, GuildFeature.SOUNDS),
        (SocialCog, GuildFeature.SOCIAL),
    ],
)
async def test_command_cogs_enforce_their_guild_feature(
    cog_type: type[AICog] | type[MusicCog] | type[SoundsCog] | type[SocialCog],
    feature: GuildFeature,
) -> None:
    ensure_enabled = AsyncMock()
    bot = SimpleNamespace(
        guild_settings_service=SimpleNamespace(ensure_feature_enabled=ensure_enabled)
    )
    cog = cog_type(cast(Any, bot))

    assert await cog.interaction_check(cast(Any, SimpleNamespace(guild_id=123)))
    ensure_enabled.assert_awaited_once_with(123, feature)


@pytest.mark.asyncio
async def test_feature_check_leaves_dm_validation_to_the_command() -> None:
    ensure_enabled = AsyncMock()
    bot = SimpleNamespace(
        guild_settings_service=SimpleNamespace(ensure_feature_enabled=ensure_enabled)
    )

    assert await MusicCog(cast(Any, bot)).interaction_check(
        cast(Any, SimpleNamespace(guild_id=None))
    )
    ensure_enabled.assert_not_awaited()
