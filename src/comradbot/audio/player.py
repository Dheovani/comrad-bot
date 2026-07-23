"""One resilient playback worker per Discord guild."""

import asyncio
import logging

import discord

from comradbot.audio.models import AudioItem
from comradbot.audio.queue import AudioQueue
from comradbot.errors import AudioPlaybackError, VoiceConnectionError

logger = logging.getLogger(__name__)


class GuildAudioPlayer:
    def __init__(
        self, guild_id: int, *, max_queue_size: int, idle_timeout: int, volume: float
    ) -> None:
        self.guild_id = guild_id
        self.queue = AudioQueue(max_queue_size)
        self.idle_timeout = idle_timeout
        self.volume = volume
        self.current: AudioItem | None = None
        self.voice_client: discord.VoiceClient | None = None
        self.repeat = False
        self._closed = False
        self._playback_done = asyncio.Event()
        self._playback_error: Exception | None = None
        self._worker = asyncio.create_task(self._run(), name=f"audio-player-{guild_id}")

    async def set_voice_client(self, voice_client: discord.VoiceClient) -> None:
        self.voice_client = voice_client

    async def enqueue(self, item: AudioItem, *, next_item: bool = False) -> int:
        if self._closed:
            raise AudioPlaybackError("O player deste servidor já foi encerrado.")
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
            try:
                await self._play(item)
                if self.repeat and not self._closed:
                    await self.queue.put(item, next_item=True)
                    continue
            except Exception:
                logger.exception("Falha ao reproduzir item type=%s", item.item_type)
            finally:
                if not self.repeat or self._closed:
                    await item.cleanup()
                self.current = None

    async def _play(self, item: AudioItem) -> None:
        voice = self.voice_client
        if voice is None or not voice.is_connected():
            raise VoiceConnectionError("O bot não está conectado a um canal de voz.")
        self._playback_done.clear()
        self._playback_error = None
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(
                item.source,
                before_options="-nostdin -reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn",
            ),
            volume=self.volume,
        )
        voice.play(source, after=self._after_playback)
        await self._playback_done.wait()
        if self._playback_error is not None:
            raise AudioPlaybackError("A reprodução falhou.") from self._playback_error

    def pause(self) -> None:
        if self.voice_client is None or not self.voice_client.is_playing():
            raise AudioPlaybackError("Não há áudio em reprodução para pausar.")
        self.voice_client.pause()

    def resume(self) -> None:
        if self.voice_client is None or not self.voice_client.is_paused():
            raise AudioPlaybackError("Não há áudio pausado para continuar.")
        self.voice_client.resume()

    def skip(self) -> None:
        if self.voice_client is None or not (
            self.voice_client.is_playing() or self.voice_client.is_paused()
        ):
            raise AudioPlaybackError("Não há áudio para pular.")
        self.voice_client.stop()

    async def stop(self) -> None:
        removed = await self.queue.clear()
        for item in removed:
            await item.cleanup()
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

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
