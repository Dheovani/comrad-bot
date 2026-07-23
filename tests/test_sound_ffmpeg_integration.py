import io
import shutil
import wave
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.database.repositories.sounds import SoundRepository
from comradbot.errors import ValidationError
from comradbot.sounds.service import SoundService
from comradbot.sounds.storage import SoundStorage

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="FFmpeg integration tests require ffmpeg and ffprobe on PATH",
)


def wav_bytes(duration_seconds: float, *, sample_rate: int = 48_000) -> bytes:
    output = io.BytesIO()
    frame_count = int(duration_seconds * sample_rate)
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(b"\x00\x00" * frame_count)
    return output.getvalue()


def real_sound_service(
    repository: AsyncMock,
    storage: SoundStorage,
    *,
    max_size_bytes: int = 500_000,
    max_duration_seconds: int = 30,
) -> SoundService:
    return SoundService(
        cast(SoundRepository, cast(Any, repository)),
        storage,
        FFmpegRunner(timeout_seconds=10),
        max_size_bytes=max_size_bytes,
        max_duration_seconds=max_duration_seconds,
    )


@pytest.mark.asyncio
async def test_real_upload_probes_and_converts_wav_to_opus(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    repository.add.side_effect = lambda sound: sound
    storage = SoundStorage(tmp_path)
    service = real_sound_service(repository, storage)

    sound = await service.upload(
        guild_id=123,
        creator_id=456,
        name="Short Signal",
        filename="signal.wav",
        content_type="application/octet-stream",
        data=wav_bytes(0.2),
    )

    destination = storage.absolute_path(sound.relative_path)
    media = await FFmpegRunner(timeout_seconds=10).probe(destination)
    assert destination.suffix == ".opus"
    assert destination.is_file()
    assert media.has_audio is True
    assert "ogg" in media.format_name
    assert sound.format == "opus"
    assert sound.duration_seconds == pytest.approx(0.2, abs=0.05)
    assert list(destination.parent.iterdir()) == [destination]
    repository.add.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_validation_rejects_metadata_content_and_duration(
    tmp_path: Path,
) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    storage = SoundStorage(tmp_path)
    service = real_sound_service(
        repository,
        storage,
        max_size_bytes=500_000,
        max_duration_seconds=1,
    )
    base = {
        "guild_id": 123,
        "creator_id": 456,
        "name": "Signal",
        "filename": "signal.wav",
        "content_type": "audio/wav",
        "data": wav_bytes(0.1),
    }

    with pytest.raises(ValidationError, match="path"):
        await service.upload(**(base | {"name": "../signal"}))
    with pytest.raises(ValidationError, match="Unsupported format"):
        await service.upload(**(base | {"filename": "signal.exe"}))
    with pytest.raises(ValidationError, match="MIME"):
        await service.upload(**(base | {"content_type": "image/png"}))
    with pytest.raises(ValidationError, match="size limit"):
        await service.upload(**(base | {"data": b"x" * 500_001}))
    with pytest.raises(ValidationError, match="valid supported audio"):
        await service.upload(**(base | {"data": b"not a real wave file"}))
    with pytest.raises(ValidationError, match="duration limit"):
        await service.upload(**(base | {"data": wav_bytes(1.2)}))

    guild_directory = storage.guild_directory(123)
    assert list(guild_directory.iterdir()) == []
    repository.add.assert_not_awaited()
