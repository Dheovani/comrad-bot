"""Protocol implemented by concrete AI providers."""

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from comradbot.ai.models import AIMessage


class AIProvider(Protocol):
    async def generate_response(
        self, messages: Sequence[AIMessage], *, max_characters: int
    ) -> str: ...

    async def close(self) -> None: ...


class SpeechProvider(Protocol):
    async def generate_speech(self, text: str, destination: Path) -> None: ...


class SpeechRecognitionProvider(Protocol):
    async def transcribe_audio(self, audio: Path) -> str: ...

    async def close(self) -> None: ...
