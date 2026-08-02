import asyncio
import threading
from pathlib import Path
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from comradbot.audio.ffmpeg import FFmpegRunner, MediaInfo
from comradbot.audio.models import AudioItemType
from comradbot.database.models import CustomSound
from comradbot.database.repositories.sounds import SoundRepository
from comradbot.errors import PermissionDeniedError, ValidationError
from comradbot.sounds.service import SoundService
from comradbot.sounds.storage import SoundStorage


class FakeFFmpegRunner:
    def __init__(self, *, source_duration: float = 2.0) -> None:
        self.source_duration = source_duration
        self.converted: list[tuple[Path, Path]] = []

    async def probe(self, path: Path) -> MediaInfo:
        if path.suffix == ".opus":
            return MediaInfo(duration_seconds=1.5, format_name="ogg", has_audio=True)
        return MediaInfo(
            duration_seconds=self.source_duration,
            format_name="wav",
            has_audio=True,
        )

    async def convert_to_opus(self, source: Path, destination: Path) -> None:
        self.converted.append((source, destination))
        await asyncio.to_thread(destination.write_bytes, b"converted-opus")


def custom_sound(
    *,
    sound_id: str = "760de197-4148-4d90-8956-26017a03a889",
    guild_id: int = 123,
    name: str = "Air Horn",
    normalized_name: str = "air-horn",
    creator_id: int = 456,
) -> CustomSound:
    return CustomSound(
        id=sound_id,
        guild_id=guild_id,
        name=name,
        normalized_name=normalized_name,
        relative_path=f"{guild_id}/{sound_id}.opus",
        creator_id=creator_id,
        duration_seconds=1.5,
        size_bytes=100,
        format="opus",
        play_count=0,
        category=None,
        tags_json="[]",
    )


def sound_service(
    repository: AsyncMock,
    storage: SoundStorage,
    ffmpeg: FakeFFmpegRunner,
    *,
    max_duration_seconds: int = 30,
) -> SoundService:
    repository.usage.return_value = (0, 0)
    return SoundService(
        cast(SoundRepository, cast(Any, repository)),
        storage,
        cast(FFmpegRunner, cast(Any, ffmpeg)),
        max_size_bytes=1024,
        max_duration_seconds=max_duration_seconds,
    )


@pytest.mark.asyncio
async def test_upload_converts_persists_and_removes_source_file(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    repository.add.side_effect = lambda sound: sound
    storage = SoundStorage(tmp_path)
    ffmpeg = FakeFFmpegRunner()
    service = sound_service(repository, storage, ffmpeg)

    sound = await service.upload(
        guild_id=123,
        creator_id=456,
        name="Air Horn",
        filename="horn.wav",
        content_type="audio/wav",
        data=b"fake-wave",
        category="Memes",
        tags="loud, victory",
    )

    destination = storage.absolute_path(sound.relative_path)
    assert destination.read_bytes() == b"converted-opus"
    assert sound.normalized_name == "air-horn"
    assert sound.duration_seconds == 1.5
    assert sound.size_bytes == len(b"converted-opus")
    assert sound.category == "Memes"
    assert sound.tags == ("loud", "victory")
    assert len(ffmpeg.converted) == 1
    assert not ffmpeg.converted[0][0].exists()
    repository.add.assert_awaited_once()


@pytest.mark.asyncio
async def test_upload_rejects_duration_and_cleans_temporary_files(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    storage = SoundStorage(tmp_path)
    service = sound_service(
        repository,
        storage,
        FakeFFmpegRunner(source_duration=31),
        max_duration_seconds=30,
    )

    with pytest.raises(ValidationError, match="duration limit"):
        await service.upload(
            guild_id=123,
            creator_id=456,
            name="Too Long",
            filename="long.wav",
            content_type="audio/wav",
            data=b"fake-wave",
        )

    assert list(storage.guild_directory(123).iterdir()) == []
    repository.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_upload_enforces_count_and_converted_storage_quotas(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    repository.usage.return_value = (2, 900)
    storage = SoundStorage(tmp_path)

    async def quota(_: int) -> tuple[int, int]:
        return 2, 1000

    service = SoundService(
        cast(SoundRepository, cast(Any, repository)),
        storage,
        cast(FFmpegRunner, cast(Any, FakeFFmpegRunner())),
        max_size_bytes=1024,
        max_duration_seconds=30,
        quota_provider=quota,
    )
    with pytest.raises(ValidationError, match="limit of 2"):
        await service.upload(
            guild_id=123,
            creator_id=456,
            name="Count Limited",
            filename="sound.wav",
            content_type="audio/wav",
            data=b"source",
        )

    repository.usage.return_value = (1, 990)
    with pytest.raises(ValidationError, match="would exceed"):
        await service.upload(
            guild_id=123,
            creator_id=456,
            name="Storage Limited",
            filename="sound.wav",
            content_type="audio/wav",
            data=b"source",
        )
    assert list(storage.guild_directory(123).iterdir()) == []
    repository.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_concurrent_uploads_cannot_exceed_guild_count_quota(tmp_path: Path) -> None:
    class QuotaRepository:
        def __init__(self) -> None:
            self.sounds: list[CustomSound] = []

        async def get(self, guild_id: int, normalized_name: str) -> CustomSound | None:
            return next(
                (
                    sound
                    for sound in self.sounds
                    if sound.guild_id == guild_id and sound.normalized_name == normalized_name
                ),
                None,
            )

        async def usage(self, guild_id: int) -> tuple[int, int]:
            sounds = [sound for sound in self.sounds if sound.guild_id == guild_id]
            return len(sounds), sum(sound.size_bytes for sound in sounds)

        async def add(self, sound: CustomSound) -> CustomSound:
            self.sounds.append(sound)
            return sound

    async def quota(_: int) -> tuple[int, int]:
        return 1, 1024

    repository = QuotaRepository()
    storage = SoundStorage(tmp_path)
    service = SoundService(
        cast(SoundRepository, cast(Any, repository)),
        storage,
        cast(FFmpegRunner, cast(Any, FakeFFmpegRunner())),
        max_size_bytes=1024,
        max_duration_seconds=30,
        quota_provider=quota,
    )

    results = await asyncio.gather(
        service.upload(
            guild_id=123,
            creator_id=456,
            name="First",
            filename="first.wav",
            content_type="audio/wav",
            data=b"first",
        ),
        service.upload(
            guild_id=123,
            creator_id=456,
            name="Second",
            filename="second.wav",
            content_type="audio/wav",
            data=b"second",
        ),
        return_exceptions=True,
    )

    assert sum(isinstance(result, CustomSound) for result in results) == 1
    assert sum(isinstance(result, ValidationError) for result in results) == 1
    assert len(repository.sounds) == 1
    assert len(list(storage.guild_directory(123).glob("*.opus"))) == 1


@pytest.mark.asyncio
async def test_upload_cancellation_waits_for_write_and_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = AsyncMock()
    repository.get.return_value = None
    storage = SoundStorage(tmp_path)
    service = sound_service(repository, storage, FakeFFmpegRunner())
    started = threading.Event()
    release = threading.Event()

    def blocking_write(directory: Path, extension: str, data: bytes) -> Path:
        started.set()
        release.wait(timeout=1)
        temporary = directory / f"pending{extension}"
        temporary.write_bytes(data)
        return temporary

    monkeypatch.setattr(
        SoundService,
        "_write_temporary_upload_sync",
        staticmethod(blocking_write),
    )
    task = asyncio.create_task(
        service.upload(
            guild_id=123,
            creator_id=456,
            name="Cancelled",
            filename="cancelled.wav",
            content_type="audio/wav",
            data=b"fake-wave",
        )
    )
    assert await asyncio.to_thread(started.wait, 0.5)

    task.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert list(storage.guild_directory(123).iterdir()) == []
    repository.add.assert_not_awaited()


@pytest.mark.asyncio
async def test_random_sound_creates_shared_audio_item_and_counts_play(
    tmp_path: Path,
) -> None:
    sound = custom_sound()
    repository = AsyncMock()
    repository.list.return_value = [sound]
    storage = SoundStorage(tmp_path)
    path = storage.absolute_path(sound.relative_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"opus")
    service = sound_service(repository, storage, FakeFFmpegRunner())

    item = await service.get_random_audio_item(sound.guild_id, requester_id=999)

    assert item.item_type is AudioItemType.CUSTOM_SOUND
    assert item.title == sound.name
    assert item.requester_id == 999
    repository.increment_play_count.assert_awaited_once_with(sound.id)


@pytest.mark.asyncio
async def test_random_sound_rejects_empty_guild(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.list.return_value = []
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    with pytest.raises(ValidationError, match="no custom sounds"):
        await service.get_random_audio_item(123, requester_id=999)


@pytest.mark.asyncio
async def test_rename_enforces_ownership_and_duplicate_names(tmp_path: Path) -> None:
    sound = custom_sound()
    repository = AsyncMock()
    repository.get.return_value = sound
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    with pytest.raises(PermissionDeniedError, match="creator"):
        await service.rename(
            sound.guild_id,
            sound.name,
            "New Name",
            actor_id=999,
            is_moderator=False,
        )
    repository.rename.assert_not_awaited()

    duplicate = custom_sound(
        sound_id="c6156fdb-3366-4424-82c4-f830d46a4796",
        name="New Name",
        normalized_name="new-name",
    )
    repository.get.side_effect = [sound, duplicate]
    with pytest.raises(ValidationError, match="already exists"):
        await service.rename(
            sound.guild_id,
            sound.name,
            duplicate.name,
            actor_id=sound.creator_id,
            is_moderator=False,
        )


@pytest.mark.asyncio
async def test_rename_updates_logical_name_without_changing_storage_path(
    tmp_path: Path,
) -> None:
    sound = custom_sound()
    renamed = custom_sound(name="Victory", normalized_name="victory")
    repository = AsyncMock()
    repository.get.side_effect = [sound, None]
    repository.rename.return_value = renamed
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    result = await service.rename(
        sound.guild_id,
        sound.name,
        " Victory ",
        actor_id=999,
        is_moderator=True,
    )

    assert result is renamed
    assert result.relative_path == sound.relative_path
    repository.rename.assert_awaited_once_with(
        sound.id,
        name="Victory",
        normalized_name="victory",
        actor_id=999,
        acted_as_moderator=True,
    )


@pytest.mark.asyncio
async def test_delete_records_actor_authority_and_removes_file(tmp_path: Path) -> None:
    sound = custom_sound()
    repository = AsyncMock()
    repository.get.return_value = sound
    repository.delete.return_value = True
    storage = SoundStorage(tmp_path)
    path = storage.absolute_path(sound.relative_path)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"opus")
    service = sound_service(repository, storage, FakeFFmpegRunner())

    deleted = await service.delete(
        sound.guild_id,
        sound.name,
        actor_id=999,
        is_moderator=True,
    )

    assert deleted is sound
    assert not path.exists()
    repository.delete.assert_awaited_once_with(
        sound.id,
        actor_id=999,
        acted_as_moderator=True,
    )


@pytest.mark.asyncio
async def test_audit_listing_is_bounded(tmp_path: Path) -> None:
    repository = AsyncMock()
    repository.list_audit.return_value = []
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    assert await service.list_audit(123, limit=500) == []
    repository.list_audit.assert_awaited_once_with(123, limit=50)


@pytest.mark.asyncio
async def test_search_filters_names_and_respects_discord_choice_limit(
    tmp_path: Path,
) -> None:
    repository = AsyncMock()
    repository.list.return_value = [
        custom_sound(
            sound_id=f"00000000-0000-0000-0000-{index:012d}",
            name=f"Alert {index}",
            normalized_name=f"alert-{index}",
        )
        for index in range(30)
    ]
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    assert len(await service.search(123, "alert")) == 25
    matches = await service.search(123, "Alert 2")
    assert all("Alert 2" in sound.name for sound in matches)


@pytest.mark.asyncio
async def test_search_filters_category_and_tags(tmp_path: Path) -> None:
    repository = AsyncMock()
    meme = custom_sound(name="Air Horn", normalized_name="air-horn")
    meme.category = "Memes"
    meme.tags_json = '["loud", "victory"]'
    ambient = custom_sound(
        sound_id="c6156fdb-3366-4424-82c4-f830d46a4796",
        name="Rain",
        normalized_name="rain",
    )
    ambient.category = "Ambient"
    ambient.tags_json = '["calm"]'
    repository.list.return_value = [meme, ambient]
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    assert await service.search(123, "category:memes") == [meme]
    assert await service.search(123, "tag:calm") == [ambient]
    assert await service.search(123, "tag:loud horn") == [meme]


@pytest.mark.asyncio
async def test_update_metadata_enforces_ownership_and_persists_normalized_values(
    tmp_path: Path,
) -> None:
    sound = custom_sound()
    updated = custom_sound()
    updated.category = "Reactions"
    updated.tags_json = '["loud", "win"]'
    repository = AsyncMock()
    repository.get.return_value = sound
    repository.update_metadata.return_value = updated
    service = sound_service(repository, SoundStorage(tmp_path), FakeFFmpegRunner())

    with pytest.raises(PermissionDeniedError):
        await service.update_metadata(
            123,
            sound.name,
            actor_id=999,
            category="Reactions",
            tags="loud, win",
            is_moderator=False,
        )

    result = await service.update_metadata(
        123,
        sound.name,
        actor_id=sound.creator_id,
        category=" Reactions ",
        tags="LOUD, win, loud",
        is_moderator=False,
    )

    assert result.tags == ("loud", "win")
    repository.update_metadata.assert_awaited_once_with(
        sound.id,
        category="Reactions",
        tags_json='["loud", "win"]',
    )
