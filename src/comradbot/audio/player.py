"""One resilient playback worker per Discord guild."""

import asyncio
import logging

import discord

from comradbot.audio.models import AudioItem, AudioItemType, AudioSourceRefresher, RepeatMode
from comradbot.audio.queue import AudioQueue
from comradbot.errors import AudioPlaybackError, VoiceConnectionError

logger = logging.getLogger(__name__)
LOCAL_FFMPEG_BEFORE_OPTIONS = "-nostdin"
STREAM_FFMPEG_BEFORE_OPTIONS = "-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5"


def ffmpeg_before_options(item: AudioItem) -> str:
    if item.item_type is AudioItemType.MUSIC:
        return STREAM_FFMPEG_BEFORE_OPTIONS
    return LOCAL_FFMPEG_BEFORE_OPTIONS


class GuildAudioPlayer:
    def __init__(
        self,
        guild_id: int,
        *,
        max_queue_size: int,
        idle_timeout: float,
        volume: float,
        source_refresher: AudioSourceRefresher | None = None,
    ) -> None:
        self.guild_id = guild_id
        self.queue = AudioQueue(max_queue_size)
        self.idle_timeout = idle_timeout
        self.volume = volume
        self.current: AudioItem | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.repeat_mode = RepeatMode.OFF
        self._suppress_repeat_once = False
        self._source_refresher = source_refresher
        self._closed = False
        self._playback_done = asyncio.Event()
        self._playback_error: Exception | None = None
        self._worker = asyncio.create_task(self._run(), name=f"audio-player-{guild_id}")

    async def set_voice_client(self, voice_client: discord.VoiceClient) -> None:
        self.voice_client = voice_client

    async def enqueue(
        self,
        item: AudioItem,
        *,
        next_item: bool = False,
        refresh_if_queued: bool = False,
    ) -> int:
        if self._closed:
            raise AudioPlaybackError("This guild player has already been shut down.")
        if refresh_if_queued and (self.current is not None or len(self.queue) > 0):
            item.refresh_before_playback = True
        return await self.queue.put(item, next_item=next_item)

    def _after_playback(self, error: Exception | None) -> None:
        loop = self._worker.get_loop()
        self._playback_error = error
        loop.call_soon_threadsafe(self._playback_done.set)

    async def _run(self) -> None:
        while not self._closed:
            try:
                item = await asyncio.wait_for(self.queue.get(), timeout=self.idle_timeout)
            except TimeoutError:
                await self.disconnect()
                continue
            self.current = item
            retain_item = False
            try:
                await self._refresh_source(item)
                await self._play(item)
                suppress_repeat = self._suppress_repeat_once
                self._suppress_repeat_once = False
                if not suppress_repeat and not self._closed:
                    if self.repeat_mode is RepeatMode.TRACK:
                        await self.queue.put(item, next_item=True)
                        retain_item = True
                    elif self.repeat_mode is RepeatMode.QUEUE:
                        await self.queue.put(item)
                        retain_item = True
            except Exception:
                logger.exception("Failed to play audio item type=%s", item.item_type)
            finally:
                self._suppress_repeat_once = False
                if not retain_item:
                    await item.cleanup()
                self.current = None

    async def _refresh_source(self, item: AudioItem) -> None:
        if not item.refresh_before_playback:
            return
        if self._source_refresher is None:
            raise AudioPlaybackError("This queued source cannot be refreshed.")
        item.source = await self._source_refresher.refresh_source(item)
        item.refresh_before_playback = False

    async def _play(self, item: AudioItem) -> None:
        voice = self.voice_client
        if voice is None or not voice.is_connected():
            raise VoiceConnectionError("The bot is not connected to a voice channel.")
        self._playback_done.clear()
        self._playback_error = None
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                item.source,
                before_options=ffmpeg_before_options(item),
                options="-vn",
            ),
            volume=self.volume,
        )
        voice.play(source, after=self._after_playback)
        await self._playback_done.wait()
        if self._playback_error is not None:
            raise AudioPlaybackError("Audio playback failed.") from self._playback_error

    def pause(self) -> None:
        if self.voice_client is None or not self.voice_client.is_playing():
            raise AudioPlaybackError("There is no playing audio to pause.")
        self.voice_client.pause()

    def resume(self) -> None:
        if self.voice_client is None or not self.voice_client.is_paused():
            raise AudioPlaybackError("There is no paused audio to resume.")
        self.voice_client.resume()

    def skip(self) -> None:
        if self.voice_client is None or not (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            raise AudioPlaybackError("There is no audio to skip.")
        self._suppress_repeat_once = True
        self.voice_client.stop()

    async def remove_queued(self, position: int) -> AudioItem:
        item = await self.queue.remove(position)
        await item.cleanup()
        return item

    async def clear_queue(self) -> int:
        removed = await self.queue.clear()
        for item in removed:
            await item.cleanup()
        return len(removed)

    async def stop(self) -> None:
        await self.clear_queue()
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self._suppress_repeat_once = True
            self.voice_client.stop()

    def set_repeat_mode(self, mode: RepeatMode) -> None:
        self.repeat_mode = mode

    def set_volume(self, value: float) -> None:
        self.volume = min(max(value, 0.0), 1.0)
        if self.voice_client and isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
            self.voice_client.source.volume = self.volume

    async def disconnect(self) -> None:
        if self.voice_client is not None and self.voice_client.is_connected():
            await self.voice_client.disconnect(force=False)
        self.voice_client = None

    async def shutdown(self) -> None:
        self._closed = True
        await self.stop()
        await self.disconnect()
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
