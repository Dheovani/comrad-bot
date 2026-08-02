from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from elevenlabs.core.api_error import ApiError

from comradbot.ai.elevenlabs_provider import ElevenLabsSpeechProvider
from comradbot.errors import AIError, RateLimitError


class FakeTextToSpeech:
    def __init__(self, *, chunks: tuple[bytes, ...] = (), error: Exception | None = None) -> None:
        self.chunks = chunks
        self.error = error
        self.calls: list[dict[str, Any]] = []

    async def convert(self, voice_id: str, **kwargs: Any) -> AsyncIterator[bytes]:
        self.calls.append({"voice_id": voice_id, **kwargs})
        if self.error is not None:
            raise self.error

        async def generate() -> AsyncIterator[bytes]:
            for chunk in self.chunks:
                yield chunk

        return generate()


def provider(fake: FakeTextToSpeech, *, max_bytes: int = 100) -> ElevenLabsSpeechProvider:
    result = ElevenLabsSpeechProvider(
        api_key="test-key",
        model="eleven_flash_v2_5",
        voice_id="official-voice",
        timeout_seconds=1,
        max_file_size_bytes=max_bytes,
    )
    result._client = cast(Any, SimpleNamespace(text_to_speech=fake))
    return result


@pytest.mark.asyncio
async def test_elevenlabs_provider_streams_bounded_portuguese_opus(tmp_path: Path) -> None:
    fake = FakeTextToSpeech(chunks=(b"first", b"second"))
    speech = provider(fake)
    destination = tmp_path / "speech.opus"

    try:
        await speech.generate_speech("Olá, camarada", destination)
    finally:
        await speech.close()

    assert destination.read_bytes() == b"firstsecond"
    assert fake.calls[0]["voice_id"] == "official-voice"
    assert fake.calls[0]["text"] == "Olá, camarada"
    assert fake.calls[0]["model_id"] == "eleven_flash_v2_5"
    assert fake.calls[0]["language_code"] == "pt"
    assert fake.calls[0]["output_format"] == "opus_48000_64"


@pytest.mark.asyncio
async def test_elevenlabs_provider_maps_rate_limit_and_removes_partial_file(tmp_path: Path) -> None:
    fake = FakeTextToSpeech(error=ApiError(status_code=429))
    speech = provider(fake)
    destination = tmp_path / "speech.opus"

    try:
        with pytest.raises(RateLimitError, match="ElevenLabs"):
            await speech.generate_speech("Olá", destination)
    finally:
        await speech.close()

    assert not destination.exists()


@pytest.mark.asyncio
async def test_elevenlabs_provider_rejects_oversized_output(tmp_path: Path) -> None:
    fake = FakeTextToSpeech(chunks=(b"1234", b"5678"))
    speech = provider(fake, max_bytes=5)
    destination = tmp_path / "speech.opus"

    try:
        with pytest.raises(AIError, match="tamanho"):
            await speech.generate_speech("Olá", destination)
    finally:
        await speech.close()

    assert not destination.exists()


@pytest.mark.asyncio
async def test_elevenlabs_provider_rejects_empty_output(tmp_path: Path) -> None:
    speech = provider(FakeTextToSpeech())
    destination = tmp_path / "speech.opus"

    try:
        with pytest.raises(AIError, match="vazio"):
            await speech.generate_speech("Olá", destination)
    finally:
        await speech.close()

    assert not destination.exists()
