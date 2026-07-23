from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands import helpers
from comradbot.commands.helpers import can_control_guild_audio
from comradbot.errors import PermissionDeniedError
from comradbot.ui.player import PlayerControls


@pytest.mark.parametrize(
    ("user_channel_id", "bot_channel_id", "can_move_members", "expected"),
    [
        (10, 10, False, True),
        (10, None, False, True),
        (10, 20, False, False),
        (10, 20, True, True),
        (None, 20, False, False),
        (None, 20, True, False),
    ],
)
def test_audio_control_permission_policy(
    user_channel_id: int | None,
    bot_channel_id: int | None,
    can_move_members: bool,
    expected: bool,
) -> None:
    assert (
        can_control_guild_audio(
            user_channel_id=user_channel_id,
            bot_channel_id=bot_channel_id,
            can_move_members=can_move_members,
        )
        is expected
    )


@pytest.mark.asyncio
async def test_player_panel_rejects_member_in_another_voice_channel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    member = SimpleNamespace(
        guild_permissions=SimpleNamespace(move_members=False),
    )
    interaction = cast(
        discord.Interaction,
        cast(Any, SimpleNamespace(user=member)),
    )
    voice_client = SimpleNamespace(channel=SimpleNamespace(id=20))
    player = cast(
        GuildAudioPlayer,
        cast(Any, SimpleNamespace(voice_client=voice_client)),
    )
    manager = cast(
        GuildAudioManager,
        cast(Any, SimpleNamespace(get=lambda guild_id: player)),
    )
    monkeypatch.setattr(
        helpers,
        "user_voice_channel",
        lambda interaction: SimpleNamespace(id=10),
    )
    view = PlayerControls(manager, guild_id=1)

    with pytest.raises(PermissionDeniedError, match="same voice channel"):
        view._active_player_for_control(interaction)
