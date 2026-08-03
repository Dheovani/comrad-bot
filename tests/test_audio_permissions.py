from types import SimpleNamespace
from typing import Any, cast

import discord
import pytest

from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.models import AudioItem, AudioItemType, RepeatMode
from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands import helpers
from comradbot.commands.helpers import can_control_guild_audio
from comradbot.errors import PermissionDeniedError
from comradbot.ui.player import PlayerControls, build_player_panel_embed


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


def panel_item(position: int) -> AudioItem:
    return AudioItem(
        AudioItemType.MUSIC,
        f"Track {position}",
        "source",
        requester_id=position,
    )


def test_player_panel_embed_paginates_and_clamps_changed_queue() -> None:
    voice = SimpleNamespace(is_paused=lambda: False, is_playing=lambda: True)
    player = cast(
        GuildAudioPlayer,
        cast(
            Any,
            SimpleNamespace(
                current=panel_item(0), repeat_mode=RepeatMode.QUEUE, voice_client=voice
            ),
        ),
    )
    items = [panel_item(position) for position in range(1, 26)]

    middle, middle_page = build_player_panel_embed(player, items, page=1)
    final, final_page = build_player_panel_embed(player, items, page=99)

    assert middle_page == 1
    assert "`11.` Track 11" in str(middle.description)
    assert "Track 21" not in str(middle.description)
    assert middle.footer.text == "Page 2/3 • Repeat: queue • State: playing"
    assert final_page == 2
    assert "`21.` Track 21" in str(final.description)
    assert final.footer.text == "Page 3/3 • Repeat: queue • State: playing"


@pytest.mark.asyncio
async def test_player_panel_is_persistent_with_stable_custom_ids() -> None:
    manager = cast(GuildAudioManager, cast(Any, SimpleNamespace(get=lambda guild_id: None)))
    view = PlayerControls(manager)
    custom_ids = [
        child.custom_id for child in view.children if isinstance(child, discord.ui.Button)
    ]

    assert view.timeout is None
    assert view.is_persistent() is True
    assert len(custom_ids) == 6
    assert len(set(custom_ids)) == len(custom_ids)
    assert all(custom_id and custom_id.startswith("comradbot:player:") for custom_id in custom_ids)
