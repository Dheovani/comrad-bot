"""Registry enforcing one isolated player per guild."""

import asyncio
from collections.abc import Awaitable, Callable

from comradbot.audio.models import AudioSourceRefresher
from comradbot.audio.player import GuildAudioPlayer

DefaultVolumeProvider = Callable[[int], Awaitable[float]]


class GuildAudioManager:
    def __init__(
        self,
        *,
        max_queue_size: int,
        idle_timeout: int,
        default_volume: float,
        source_refresher: AudioSourceRefresher | None = None,
        default_volume_provider: DefaultVolumeProvider | None = None,
    ) -> None:
        self._players: dict[int, GuildAudioPlayer] = {}
        self._lock = asyncio.Lock()
        self._max_queue_size = max_queue_size
        self._idle_timeout = idle_timeout
        self._default_volume = default_volume
        self._source_refresher = source_refresher
        self._default_volume_provider = default_volume_provider

    async def get_or_create(self, guild_id: int) -> GuildAudioPlayer:
        player = self._players.get(guild_id)
        if player is not None:
            return player
        volume = self._default_volume
        if self._default_volume_provider is not None:
            volume = await self._default_volume_provider(guild_id)
        async with self._lock:
            player = self._players.get(guild_id)
            if player is None:
                player = GuildAudioPlayer(
                    guild_id,
                    max_queue_size=self._max_queue_size,
                    idle_timeout=self._idle_timeout,
                    volume=volume,
                    source_refresher=self._source_refresher,
                )
                self._players[guild_id] = player
            return player

    def get(self, guild_id: int) -> GuildAudioPlayer | None:
        return self._players.get(guild_id)

    @property
    def active_player_count(self) -> int:
        return len(self._players)

    async def remove(self, guild_id: int) -> None:
        async with self._lock:
            player = self._players.pop(guild_id, None)
        if player is not None:
            await player.shutdown()

    async def close(self) -> None:
        async with self._lock:
            players = list(self._players.values())
            self._players.clear()
        await asyncio.gather(*(player.shutdown() for player in players), return_exceptions=True)
