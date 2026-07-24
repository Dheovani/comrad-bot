import asyncio
import io
import shutil
import wave
from pathlib import Path

import pytest

from comradbot.ai.conversation import AIService, SlidingWindowLimiter
from comradbot.audio.ffmpeg import FFmpegRunner

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tests require ffmpeg and ffprobe on PATH",
)


def wav_bytes(duration_seconds: float, *, sample_rate: int = 48_000) -> bytes:
    output = io.BytesIO()
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(output, "wb") as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00\x00\x00" * frame_count)
    return output.getvalue()


class InspectingRecognitionProvider:
    def __init__(self) -> None:
        self.seen_format: str | None = None

    async def transcribe_audio(self, audio: Path) -> str:
        info = await FFmpegRunner(timeout_seconds=10).probe(audio)
        self.seen_format = info.format_name
        return "integration transcript"

    async def close(self) -> None:
        return None


class FakeRepository:
    async def record_usage(self, **kwargs: object) -> None:
        return None


@pytest.mark.asyncio
async def test_real_transcription_pipeline_normalizes_to_flac_and_cleans(
    tmp_path: Path,
) -> None:
    provider = InspectingRecognitionProvider()
    service = AIService(
        None,
        None,
        FakeRepository(),  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=100,
        max_response_characters=100,
        temp_directory=tmp_path,
        recognition_provider=provider,
        ffmpeg=FFmpegRunner(timeout_seconds=10),
    )

    result = await service.transcribe(
        guild_id=1,
        user_id=2,
        filename="voice.wav",
        content_type="audio/wav",
        data=wav_bytes(0.2),
    )

    assert result == "integration transcript"
    assert provider.seen_format == "flac"
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
