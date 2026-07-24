import asyncio
from pathlib import Path

import pytest

from comradbot.ai.conversation import AIService, SlidingWindowLimiter
from comradbot.audio.ffmpeg import MediaInfo
from comradbot.errors import ValidationError


class FakeRecognitionProvider:
    def __init__(self, *, result: str = "recognized speech") -> None:
        self.result = result
        self.seen_path: Path | None = None
        self.close_calls = 0

    async def transcribe_audio(self, audio: Path) -> str:
        self.seen_path = audio
        assert await asyncio.to_thread(audio.read_bytes) == b"normalized-flac"
        return self.result

    async def close(self) -> None:
        self.close_calls += 1


class FailingRecognitionProvider(FakeRecognitionProvider):
    async def transcribe_audio(self, audio: Path) -> str:
        self.seen_path = audio
        raise RuntimeError("provider failure")


class FakeFFmpeg:
    def __init__(self, *, duration: float = 10) -> None:
        self.duration = duration

    async def probe(self, path: Path) -> MediaInfo:
        assert await asyncio.to_thread(path.exists)
        return MediaInfo(self.duration, "mp3", True)

    async def convert_to_speech_flac(self, source: Path, destination: Path) -> None:
        assert await asyncio.to_thread(source.read_bytes) == b"source-audio"
        await asyncio.to_thread(destination.write_bytes, b"normalized-flac")


class FakeRepository:
    def __init__(self) -> None:
        self.usage: list[dict[str, object]] = []

    async def record_usage(self, **kwargs: object) -> None:
        self.usage.append(kwargs)


def build_service(
    tmp_path: Path,
    *,
    provider: FakeRecognitionProvider,
    ffmpeg: FakeFFmpeg,
    repository: FakeRepository,
) -> AIService:
    return AIService(
        None,
        None,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=100,
        max_response_characters=100,
        temp_directory=tmp_path,
        recognition_provider=provider,
        ffmpeg=ffmpeg,  # type: ignore[arg-type]
        max_transcription_size_bytes=100,
        max_transcription_duration_seconds=30,
        max_transcription_characters=12,
    )


@pytest.mark.asyncio
async def test_transcription_normalizes_bounds_records_and_cleans_files(tmp_path: Path) -> None:
    provider = FakeRecognitionProvider(result="recognized speech")
    repository = FakeRepository()
    service = build_service(
        tmp_path,
        provider=provider,
        ffmpeg=FakeFFmpeg(),
        repository=repository,
    )

    result = await service.transcribe(
        guild_id=1,
        user_id=2,
        filename="voice.mp3",
        content_type="audio/mpeg",
        data=b"source-audio",
    )

    assert result == "recognized s"
    assert provider.seen_path is not None
    assert not provider.seen_path.exists()
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
    assert repository.usage[0]["operation"] == "transcribe"
    assert repository.usage[0]["success"] is True


@pytest.mark.asyncio
async def test_transcription_rejects_duration_and_cleans_files(tmp_path: Path) -> None:
    repository = FakeRepository()
    service = build_service(
        tmp_path,
        provider=FakeRecognitionProvider(),
        ffmpeg=FakeFFmpeg(duration=31),
        repository=repository,
    )

    with pytest.raises(ValidationError, match="duration"):
        await service.transcribe(
            guild_id=1,
            user_id=2,
            filename="voice.mp3",
            content_type="audio/mpeg",
            data=b"source-audio",
        )

    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
    assert repository.usage[0]["success"] is False


@pytest.mark.asyncio
async def test_transcription_provider_failure_is_recorded_and_cleans_files(tmp_path: Path) -> None:
    provider = FailingRecognitionProvider()
    repository = FakeRepository()
    service = build_service(
        tmp_path,
        provider=provider,
        ffmpeg=FakeFFmpeg(),
        repository=repository,
    )

    with pytest.raises(RuntimeError, match="provider failure"):
        await service.transcribe(
            guild_id=1,
            user_id=2,
            filename="voice.mp3",
            content_type="audio/mpeg",
            data=b"source-audio",
        )

    assert provider.seen_path is not None
    assert not provider.seen_path.exists()
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
    assert repository.usage[0]["success"] is False


@pytest.mark.asyncio
async def test_ai_service_closes_independent_recognition_provider(tmp_path: Path) -> None:
    provider = FakeRecognitionProvider()
    service = build_service(
        tmp_path,
        provider=provider,
        ffmpeg=FakeFFmpeg(),
        repository=FakeRepository(),
    )

    await service.close()

    assert provider.close_calls == 1


@pytest.mark.parametrize(
    ("filename", "content_type", "data", "message"),
    [
        ("voice.exe", "application/octet-stream", b"audio", "Unsupported"),
        ("voice.mp3", "text/plain", b"audio", "MIME"),
        ("voice.mp3", "audio/mpeg", b"", "empty"),
        ("voice.mp3", "audio/mpeg", b"x" * 101, "size limit"),
    ],
)
@pytest.mark.asyncio
async def test_transcription_rejects_untrusted_metadata_before_writing(
    tmp_path: Path,
    filename: str,
    content_type: str,
    data: bytes,
    message: str,
) -> None:
    service = build_service(
        tmp_path,
        provider=FakeRecognitionProvider(),
        ffmpeg=FakeFFmpeg(),
        repository=FakeRepository(),
    )

    with pytest.raises(ValidationError, match=message):
        await service.transcribe(
            guild_id=1,
            user_id=2,
            filename=filename,
            content_type=content_type,
            data=data,
        )
    assert await asyncio.to_thread(lambda: list(tmp_path.iterdir())) == []
