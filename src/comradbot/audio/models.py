"""Domain models shared by music, custom sounds and TTS."""

import asyncio
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol


class AudioItemType(StrEnum):
    MUSIC = "music"
    CUSTOM_SOUND = "custom_sound"
    TTS = "tts"


class AudioSourceRefresher(Protocol):
    async def refresh_source(self, item: "AudioItem") -> str: ...


@dataclass(slots=True)
class AudioItem:
    item_type: AudioItemType
    title: str
    source: str
    requester_id: int
    duration_seconds: float | None = None
    webpage_url: str | None = None
    cleanup_path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    refresh_before_playback: bool = False

    async def cleanup(self) -> None:
        if self.cleanup_path is not None:
            await asyncio.to_thread(self.cleanup_path.unlink, missing_ok=True)
