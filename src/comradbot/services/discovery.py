"""Read-only coordination for queue and custom-sound discovery."""

from dataclasses import dataclass

from comradbot.ai.conversation import AIService
from comradbot.ai.discovery import DiscoveryCandidate
from comradbot.audio.manager import GuildAudioManager
from comradbot.sounds.service import SoundService


@dataclass(frozen=True, slots=True)
class AudioDiscoveryResult:
    response: str
    queue_items_considered: int
    sounds_considered: int


class AudioDiscoveryService:
    def __init__(
        self,
        ai_service: AIService,
        audio_manager: GuildAudioManager,
        sound_service: SoundService,
        *,
        max_items: int,
    ) -> None:
        self._ai = ai_service
        self._audio = audio_manager
        self._sounds = sound_service
        self._max_items = max_items

    async def discover(self, *, guild_id: int, user_id: int, query: str) -> AudioDiscoveryResult:
        queue_candidates: list[DiscoveryCandidate] = []
        player = self._audio.get(guild_id)
        if player is not None:
            if player.current is not None:
                queue_candidates.append(
                    DiscoveryCandidate(
                        kind="now_playing",
                        name=player.current.title,
                        details=player.current.item_type.value,
                    )
                )
            for position, item in enumerate(await player.queue.snapshot(), start=1):
                queue_candidates.append(
                    DiscoveryCandidate(
                        kind="queued",
                        name=item.title,
                        details=f"position {position}; {item.item_type.value}",
                    )
                )

        sounds = await self._sounds.list_sounds(guild_id)
        sound_candidates = [
            DiscoveryCandidate(
                kind="sound",
                name=sound.name,
                details=self._sound_details(sound.category, sound.tags, sound.play_count),
            )
            for sound in sounds
        ]
        candidates = self._balanced_candidates(queue_candidates, sound_candidates)
        response, considered = await self._ai.discover(
            guild_id=guild_id,
            user_id=user_id,
            query=query,
            candidates=candidates,
            max_items=self._max_items,
        )
        return AudioDiscoveryResult(
            response=response,
            queue_items_considered=sum(item.kind != "sound" for item in considered),
            sounds_considered=sum(item.kind == "sound" for item in considered),
        )

    def _balanced_candidates(
        self,
        queue: list[DiscoveryCandidate],
        sounds: list[DiscoveryCandidate],
    ) -> list[DiscoveryCandidate]:
        queue_limit = self._max_items // 2
        selected_queue = queue[:queue_limit]
        selected_sounds = sounds[: self._max_items - len(selected_queue)]
        remaining = self._max_items - len(selected_queue) - len(selected_sounds)
        if remaining:
            selected_queue.extend(queue[len(selected_queue) : len(selected_queue) + remaining])
        return [*selected_queue, *selected_sounds]

    @staticmethod
    def _sound_details(category: str | None, tags: tuple[str, ...], play_count: int) -> str:
        details = [f"played {play_count} time(s)"]
        if category:
            details.append(f"category {category}")
        if tags:
            details.append(f"tags {', '.join(tags)}")
        return "; ".join(details)
