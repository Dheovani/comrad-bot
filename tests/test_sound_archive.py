import hashlib
import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

import pytest

from comradbot.database.models import CustomSound
from comradbot.errors import ValidationError
from comradbot.sounds.archive import SoundArchive
from comradbot.sounds.storage import SoundStorage

SOUND_ID = "760de197-4148-4d90-8956-26017a03a889"


def archived_sound() -> CustomSound:
    return CustomSound(
        id=SOUND_ID,
        guild_id=123,
        name="Air Horn",
        normalized_name="air-horn",
        relative_path=f"123/{SOUND_ID}.opus",
        creator_id=456,
        duration_seconds=1.5,
        size_bytes=10,
        format="opus",
        category="Memes",
        tags_json='["loud", "victory"]',
    )


@pytest.mark.asyncio
async def test_archive_round_trip_preserves_metadata_and_audio(tmp_path: Path) -> None:
    storage = SoundStorage(tmp_path / "sounds")
    sound = archived_sound()
    source = storage.absolute_path(sound.relative_path)
    source.parent.mkdir(parents=True)
    source.write_bytes(b"valid-opus")
    archives = SoundArchive(storage, max_archive_size_bytes=1024 * 1024)

    exported = await archives.export(123, [sound])
    try:
        restored = await archives.read(
            123,
            exported.path.read_bytes(),
            max_sounds=10,
            max_uncompressed_bytes=1024,
        )
        assert exported.sound_count == 1
        assert len(restored) == 1
        assert restored[0].name == "Air Horn"
        assert restored[0].category == "Memes"
        assert restored[0].tags == ("loud", "victory")
        assert restored[0].data == b"valid-opus"
    finally:
        await archives.delete_export(exported)
    assert not exported.path.exists()


@pytest.mark.asyncio
async def test_archive_is_scoped_to_its_original_guild(tmp_path: Path) -> None:
    storage = SoundStorage(tmp_path / "sounds")
    sound = archived_sound()
    source = storage.absolute_path(sound.relative_path)
    source.parent.mkdir(parents=True)
    source.write_bytes(b"valid-opus")
    archives = SoundArchive(storage, max_archive_size_bytes=1024 * 1024)
    exported = await archives.export(123, [sound])
    try:
        with pytest.raises(ValidationError, match="different Discord server"):
            await archives.read(
                999,
                exported.path.read_bytes(),
                max_sounds=10,
                max_uncompressed_bytes=1024,
            )
    finally:
        await archives.delete_export(exported)


@pytest.mark.asyncio
async def test_archive_rejects_path_traversal_without_extracting(tmp_path: Path) -> None:
    data = BytesIO()
    with ZipFile(data, "w", compression=ZIP_STORED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {"format": "comradbot-sounds", "version": 1, "guild_id": "123", "sounds": []}
            ),
        )
        archive.writestr("../escape.opus", b"malicious")
    archives = SoundArchive(SoundStorage(tmp_path), max_archive_size_bytes=1024 * 1024)

    with pytest.raises(ValidationError, match="unsafe file path"):
        await archives.read(123, data.getvalue(), max_sounds=10, max_uncompressed_bytes=1024)
    assert not (tmp_path.parent / "escape.opus").exists()


@pytest.mark.asyncio
async def test_archive_rejects_checksum_mismatch_and_unexpected_files(tmp_path: Path) -> None:
    payload = b"audio"
    manifest = {
        "format": "comradbot-sounds",
        "version": 1,
        "guild_id": "123",
        "sounds": [
            {
                "id": SOUND_ID,
                "name": "Air Horn",
                "category": None,
                "tags": [],
                "file": f"sounds/{SOUND_ID}.opus",
                "sha256": hashlib.sha256(b"different").hexdigest(),
            }
        ],
    }
    data = BytesIO()
    with ZipFile(data, "w", compression=ZIP_STORED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        archive.writestr(f"sounds/{SOUND_ID}.opus", payload)
    archives = SoundArchive(SoundStorage(tmp_path), max_archive_size_bytes=1024 * 1024)

    with pytest.raises(ValidationError, match="checksum"):
        await archives.read(123, data.getvalue(), max_sounds=10, max_uncompressed_bytes=1024)


@pytest.mark.asyncio
async def test_archive_rejects_compressed_size_expansion(tmp_path: Path) -> None:
    data = BytesIO()
    with ZipFile(data, "w", compression=ZIP_STORED) as archive:
        archive.writestr(
            "manifest.json",
            json.dumps(
                {"format": "comradbot-sounds", "version": 1, "guild_id": "123", "sounds": []}
            ),
        )
        archive.writestr("sounds/unexpected.opus", b"x" * 2048)
    archives = SoundArchive(SoundStorage(tmp_path), max_archive_size_bytes=4096)

    with pytest.raises(ValidationError, match="storage limit"):
        await archives.read(123, data.getvalue(), max_sounds=10, max_uncompressed_bytes=100)
