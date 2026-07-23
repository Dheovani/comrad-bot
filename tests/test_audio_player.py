import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.audio.player import GuildAudioPlayer
from comradbot.errors import AudioPlaybackError


class FakeVoiceClient:
    def __init__(self) -> None:
        self.connected = True
        self.playing = True
        self.paused = False
        self.stopped = False
        self.disconnected = asyncio.Event()
        self.source: object = SimpleNamespace(volume=0.5)

    def is_connected(self) -> bool:
        return self.connected

    def is_playing(self) -> bool:
        return self.playing

    def is_paused(self) -> bool:
        return self.paused

    def pause(self) -> None:
        self.playing = False
        self.paused = True

    def resume(self) -> None:
        self.playing = True
        self.paused = False

    def stop(self) -> None:
        self.playing = False
        self.paused = False
        self.stopped = True

    async def disconnect(self, *, force: bool) -> None:
        self.connected = False
        self.disconnected.set()


def audio_item(title: str, cleanup_path: Path | None = None) -> AudioItem:
    return AudioItem(
        item_type=AudioItemType.MUSIC,
        title=title,
        source="source",
        requester_id=1,
        cleanup_path=cleanup_path,
    )


def voice_client(fake: FakeVoiceClient) -> discord.VoiceClient:
    return cast(discord.VoiceClient, cast(Any, fake))


@pytest.mark.asyncio
async def test_player_pause_resume_skip_and_volume() -> None:
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    voice = FakeVoiceClient()
    await player.set_voice_client(voice_client(voice))
    try:
        player.pause()
        assert voice.paused is True

        player.resume()
        assert voice.playing is True

        player.set_volume(0.75)
        assert player.volume == 0.75

        player.skip()
        assert voice.stopped is True
    finally:
        await player.shutdown()


@pytest.mark.asyncio
async def test_player_controls_reject_missing_playback() -> None:
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    try:
        with pytest.raises(AudioPlaybackError, match="playing audio"):
            player.pause()
        with pytest.raises(AudioPlaybackError, match="paused audio"):
            player.resume()
        with pytest.raises(AudioPlaybackError, match="audio to skip"):
            player.skip()
    finally:
        await player.shutdown()


@pytest.mark.asyncio
async def test_remove_and_clear_clean_temporary_items(tmp_path: Path) -> None:
    removed_path = tmp_path / "removed.opus"
    cleared_path = tmp_path / "cleared.opus"
    await asyncio.to_thread(removed_path.write_bytes, b"removed")
    await asyncio.to_thread(cleared_path.write_bytes, b"cleared")
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    removed = audio_item("removed", removed_path)
    cleared = audio_item("cleared", cleared_path)
    player.queue.remove = AsyncMock(return_value=removed)
    player.queue.clear = AsyncMock(return_value=[cleared])
    try:
        assert await player.remove_queued(2) is removed
        assert not removed_path.exists()
        player.queue.remove.assert_awaited_once_with(2)

        assert await player.clear_queue() == 1
        assert not cleared_path.exists()
        player.queue.clear.assert_awaited_once_with()
    finally:
        await player.shutdown()


@pytest.mark.asyncio
async def test_stop_clears_queued_items_and_stops_current_playback(
    tmp_path: Path,
) -> None:
    queued_path = tmp_path / "queued.opus"
    await asyncio.to_thread(queued_path.write_bytes, b"queued")
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    voice = FakeVoiceClient()
    player.queue.clear = AsyncMock(return_value=[audio_item("queued", queued_path)])
    await player.set_voice_client(voice_client(voice))
    try:
        await player.stop()

        assert voice.stopped is True
        assert not queued_path.exists()
        player.queue.clear.assert_awaited_once_with()
    finally:
        await player.shutdown()


@pytest.mark.asyncio
async def test_player_advances_and_cleans_each_completed_item(tmp_path: Path) -> None:
    first_path = tmp_path / "first.opus"
    second_path = tmp_path / "second.opus"
    await asyncio.to_thread(first_path.write_bytes, b"first")
    await asyncio.to_thread(second_path.write_bytes, b"second")
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    second_started = asyncio.Event()
    release_second = asyncio.Event()

    async def fake_play(item: AudioItem) -> None:
        if item.title == "second":
            second_started.set()
            await release_second.wait()

    player._play = AsyncMock(side_effect=fake_play)
    try:
        await player.enqueue(audio_item("first", first_path))
        await player.enqueue(audio_item("second", second_path))
        await asyncio.wait_for(second_started.wait(), timeout=0.5)

        assert not first_path.exists()
        assert player.current is not None and player.current.title == "second"

        release_second.set()
        for _ in range(100):
            if not second_path.exists() and player.current is None:
                break
            await asyncio.sleep(0)
        assert not second_path.exists()
        assert player.current is None
    finally:
        release_second.set()
        await player.shutdown()


@pytest.mark.asyncio
async def test_idle_player_disconnects_automatically() -> None:
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=0.01, volume=0.5)
    voice = FakeVoiceClient()
    voice.playing = False
    await player.set_voice_client(voice_client(voice))
    try:
        await asyncio.wait_for(voice.disconnected.wait(), timeout=0.5)
        assert player.voice_client is None
    finally:
        await player.shutdown()
