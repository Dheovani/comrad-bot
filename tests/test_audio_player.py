import asyncio
import shlex
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import discord
import pytest

from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.models import AudioItem, AudioItemType, RepeatMode
from comradbot.audio.player import GuildAudioPlayer, ffmpeg_before_options
from comradbot.errors import AudioPlaybackError, ResolverError


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


def test_ffmpeg_reconnect_options_are_only_used_for_streaming_music() -> None:
    music = audio_item("music")
    custom_sound = AudioItem(
        item_type=AudioItemType.CUSTOM_SOUND,
        title="sound",
        source="sound.opus",
        requester_id=1,
    )
    tts = AudioItem(
        item_type=AudioItemType.TTS,
        title="tts",
        source="speech.opus",
        requester_id=1,
    )

    assert "-reconnect 1" in ffmpeg_before_options(music)
    assert ffmpeg_before_options(custom_sound) == "-nostdin"
    assert ffmpeg_before_options(tts) == "-nostdin"


def test_ffmpeg_forwards_resolver_headers_as_one_safe_argument() -> None:
    music = audio_item("music")
    music.metadata["http_headers"] = {
        "User-Agent": "media client",
        "Accept-Language": "en-US,en;q=0.5",
    }

    arguments = shlex.split(ffmpeg_before_options(music))

    header_index = arguments.index("-headers")
    assert arguments[header_index + 1] == (
        "User-Agent: media client\r\nAccept-Language: en-US,en;q=0.5\r\n"
    )


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
        await asyncio.wait_for(player.wait_until_idle(), timeout=0.5)
        assert not second_path.exists()
        assert player.current is None
    finally:
        release_second.set()
        await player.shutdown()


@pytest.mark.asyncio
async def test_track_repeat_replays_current_item_before_next_item() -> None:
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    played: list[str] = []
    repeated = asyncio.Event()

    async def fake_play(item: AudioItem) -> None:
        await asyncio.sleep(0)
        played.append(item.title)
        if played == ["first", "first"]:
            repeated.set()

    player._play = AsyncMock(side_effect=fake_play)
    player.set_repeat_mode(RepeatMode.TRACK)
    try:
        await player.enqueue(audio_item("first"))
        await player.enqueue(audio_item("second"))
        await asyncio.wait_for(repeated.wait(), timeout=0.5)

        assert played[:2] == ["first", "first"]
    finally:
        player.set_repeat_mode(RepeatMode.OFF)
        await player.shutdown()


@pytest.mark.asyncio
async def test_queue_repeat_cycles_completed_items_to_the_end() -> None:
    player = GuildAudioPlayer(1, max_queue_size=5, idle_timeout=300, volume=0.5)
    played: list[str] = []
    cycled = asyncio.Event()

    async def fake_play(item: AudioItem) -> None:
        await asyncio.sleep(0)
        played.append(item.title)
        if played == ["first", "second", "first"]:
            cycled.set()

    player._play = AsyncMock(side_effect=fake_play)
    player.set_repeat_mode(RepeatMode.QUEUE)
    try:
        await player.enqueue(audio_item("first"))
        await player.enqueue(audio_item("second"))
        await asyncio.wait_for(cycled.wait(), timeout=0.5)

        assert played[:3] == ["first", "second", "first"]
    finally:
        player.set_repeat_mode(RepeatMode.OFF)
        await player.shutdown()


@pytest.mark.asyncio
async def test_queued_music_refreshes_source_immediately_before_playback() -> None:
    refresher = SimpleNamespace(
        refresh_source=AsyncMock(return_value="fresh-source"),
    )
    player = GuildAudioPlayer(
        1,
        max_queue_size=5,
        idle_timeout=300,
        volume=0.5,
        source_refresher=cast(Any, refresher),
    )
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()
    release_second = asyncio.Event()

    async def fake_play(item: AudioItem) -> None:
        if item.title == "first":
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
            await release_second.wait()

    player._play = AsyncMock(side_effect=fake_play)
    first = audio_item("first")
    second = audio_item("second")
    second.webpage_url = "https://example.test/watch/2"
    try:
        await player.enqueue(first, refresh_if_queued=True)
        await asyncio.wait_for(first_started.wait(), timeout=0.5)
        await player.enqueue(second, refresh_if_queued=True)
        assert first.refresh_before_playback is False
        assert second.refresh_before_playback is True

        release_first.set()
        await asyncio.wait_for(second_started.wait(), timeout=0.5)

        assert second.source == "fresh-source"
        assert second.refresh_before_playback is False
        refresher.refresh_source.assert_awaited_once_with(second)
    finally:
        release_first.set()
        release_second.set()
        await player.shutdown()


@pytest.mark.asyncio
async def test_refresh_failure_skips_broken_music_and_advances_queue() -> None:
    refresher = SimpleNamespace(
        refresh_source=AsyncMock(side_effect=[ResolverError("expired"), "fresh-second-source"]),
    )
    player = GuildAudioPlayer(
        1,
        max_queue_size=5,
        idle_timeout=300,
        volume=0.5,
        source_refresher=cast(Any, refresher),
    )
    second_started = asyncio.Event()
    release_second = asyncio.Event()

    async def fake_play(item: AudioItem) -> None:
        assert item.title == "second"
        second_started.set()
        await release_second.wait()

    player._play = AsyncMock(side_effect=fake_play)
    first = audio_item("first")
    first.refresh_before_playback = True
    second = audio_item("second")
    second.refresh_before_playback = True
    try:
        await player.enqueue(first)
        await player.enqueue(second)
        await asyncio.wait_for(second_started.wait(), timeout=0.5)

        assert second.source == "fresh-second-source"
        assert player._play.await_count == 1
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


@pytest.mark.asyncio
async def test_audio_manager_uses_persistent_guild_default_for_new_player() -> None:
    requested_guilds: list[int] = []

    async def default_volume(guild_id: int) -> float:
        requested_guilds.append(guild_id)
        return 0.75

    manager = GuildAudioManager(
        max_queue_size=5,
        idle_timeout=300,
        default_volume=0.5,
        default_volume_provider=default_volume,
    )
    try:
        first = await manager.get_or_create(123)
        second = await manager.get_or_create(123)

        assert first is second
        assert first.volume == 0.75
        assert requested_guilds == [123]
    finally:
        await manager.close()
