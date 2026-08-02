"""Versioned and bounded custom sound archive handling."""

from __future__ import annotations

import asyncio
import hashlib
import json
import stat
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from comradbot.database.models import CustomSound
from comradbot.errors import ValidationError
from comradbot.sounds.storage import SoundStorage
from comradbot.sounds.validation import (
    normalize_sound_category,
    normalize_sound_name,
    normalize_sound_tags,
)

ARCHIVE_FORMAT = "comradbot-sounds"
ARCHIVE_VERSION = 1
MANIFEST_NAME = "manifest.json"
MAX_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True, slots=True)
class SoundArchiveExport:
    path: Path
    sound_count: int


@dataclass(frozen=True, slots=True)
class ArchivedSound:
    name: str
    category: str | None
    tags: tuple[str, ...]
    data: bytes


@dataclass(frozen=True, slots=True)
class SoundRestoreResult:
    imported: tuple[str, ...]
    skipped: tuple[str, ...]
    failed: tuple[str, ...]


class SoundArchive:
    """Create and validate portable archives without extracting untrusted paths."""

    def __init__(self, storage: SoundStorage, *, max_archive_size_bytes: int) -> None:
        self._storage = storage
        self._max_archive_size_bytes = max_archive_size_bytes

    async def export(self, guild_id: int, sounds: list[CustomSound]) -> SoundArchiveExport:
        sources = [(sound, self._storage.absolute_path(sound.relative_path)) for sound in sounds]
        return await asyncio.to_thread(self._export_sync, guild_id, sources)

    async def read(
        self,
        guild_id: int,
        data: bytes,
        *,
        max_sounds: int,
        max_uncompressed_bytes: int,
    ) -> tuple[ArchivedSound, ...]:
        if len(data) > self._max_archive_size_bytes:
            raise ValidationError("The sound archive exceeds the configured archive size limit.")
        return await asyncio.to_thread(
            self._read_sync,
            guild_id,
            data,
            max_sounds,
            min(max_uncompressed_bytes, self._max_archive_size_bytes),
        )

    @staticmethod
    async def delete_export(export: SoundArchiveExport) -> None:
        await asyncio.to_thread(export.path.unlink, missing_ok=True)

    def _export_sync(
        self,
        guild_id: int,
        sources: list[tuple[CustomSound, Path]],
    ) -> SoundArchiveExport:
        manifest_sounds: list[dict[str, Any]] = []
        for sound, source in sources:
            if not source.is_file():
                raise ValidationError(
                    f"Sound **{sound.name}** cannot be exported because its audio file is missing."
                )
            archive_name = f"sounds/{sound.id}.opus"
            manifest_sounds.append(
                {
                    "id": sound.id,
                    "name": sound.name,
                    "category": sound.category,
                    "tags": list(sound.tags),
                    "file": archive_name,
                    "sha256": self._sha256_file(source),
                }
            )
        manifest = {
            "format": ARCHIVE_FORMAT,
            "version": ARCHIVE_VERSION,
            "guild_id": str(guild_id),
            "sounds": manifest_sounds,
        }
        temporary = NamedTemporaryFile(prefix="comradbot-sounds-", suffix=".zip", delete=False)
        path = Path(temporary.name)
        temporary.close()
        try:
            with ZipFile(path, "w", compression=ZIP_STORED) as archive:
                archive.writestr(
                    MANIFEST_NAME,
                    json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
                )
                for (_, source), item in zip(sources, manifest_sounds, strict=True):
                    archive.write(source, item["file"])
            if path.stat().st_size > self._max_archive_size_bytes:
                raise ValidationError("The generated archive exceeds the configured size limit.")
            return SoundArchiveExport(path=path, sound_count=len(sources))
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def _read_sync(
        self,
        guild_id: int,
        data: bytes,
        max_sounds: int,
        max_uncompressed_bytes: int,
    ) -> tuple[ArchivedSound, ...]:
        try:
            with ZipFile(BytesIO(data), "r") as archive:
                infos = archive.infolist()
                self._validate_infos(infos, max_sounds, max_uncompressed_bytes)
                manifest_info = archive.getinfo(MANIFEST_NAME)
                if manifest_info.file_size > MAX_MANIFEST_BYTES:
                    raise ValidationError("The archive manifest is too large.")
                manifest = json.loads(archive.read(manifest_info))
                return self._parse_manifest(archive, manifest, guild_id, max_sounds)
        except (BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValidationError("The attachment is not a valid ComradBot sound archive.") from exc

    @staticmethod
    def _validate_infos(infos: list[ZipInfo], max_sounds: int, max_uncompressed_bytes: int) -> None:
        if len(infos) > max_sounds + 1:
            raise ValidationError("The archive contains too many entries.")
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise ValidationError("The archive contains duplicate file entries.")
        total_size = 0
        for info in infos:
            path = PurePosixPath(info.filename)
            mode = info.external_attr >> 16
            if (
                info.is_dir()
                or path.is_absolute()
                or ".." in path.parts
                or "\\" in info.filename
                or stat.S_ISLNK(mode)
            ):
                raise ValidationError("The archive contains an unsafe file path.")
            if info.flag_bits & 0x1:
                raise ValidationError("Encrypted sound archives are not supported.")
            if info.compress_type not in {ZIP_STORED, ZIP_DEFLATED}:
                raise ValidationError("The archive uses an unsupported compression method.")
            if info.filename == MANIFEST_NAME:
                if info.file_size > MAX_MANIFEST_BYTES:
                    raise ValidationError("The archive manifest is too large.")
                continue
            total_size += info.file_size
            if total_size > max_uncompressed_bytes:
                raise ValidationError("The archive expands beyond the configured storage limit.")

    @staticmethod
    def _parse_manifest(
        archive: ZipFile,
        manifest: object,
        guild_id: int,
        max_sounds: int,
    ) -> tuple[ArchivedSound, ...]:
        if not isinstance(manifest, dict):
            raise ValidationError("The archive manifest must be a JSON object.")
        if manifest.get("format") != ARCHIVE_FORMAT or manifest.get("version") != ARCHIVE_VERSION:
            raise ValidationError("The archive format or version is not supported.")
        if manifest.get("guild_id") != str(guild_id):
            raise ValidationError("This archive belongs to a different Discord server.")
        raw_sounds = manifest.get("sounds")
        if not isinstance(raw_sounds, list) or len(raw_sounds) > max_sounds:
            raise ValidationError("The archive contains an invalid number of sounds.")

        restored: list[ArchivedSound] = []
        expected_files = {MANIFEST_NAME}
        normalized_names: set[str] = set()
        for raw in raw_sounds:
            if not isinstance(raw, dict):
                raise ValidationError("The archive contains invalid sound metadata.")
            sound_id = SoundArchive._required_string(raw, "id")
            try:
                UUID(sound_id)
            except ValueError as exc:
                raise ValidationError("The archive contains an invalid sound identifier.") from exc
            file_name = SoundArchive._required_string(raw, "file")
            if file_name != f"sounds/{sound_id}.opus":
                raise ValidationError("The archive contains an invalid sound file reference.")
            name = SoundArchive._required_string(raw, "name")
            normalized_name = normalize_sound_name(name)
            if normalized_name in normalized_names:
                raise ValidationError("The archive contains duplicate logical sound names.")
            normalized_names.add(normalized_name)
            category_value = raw.get("category")
            if category_value is not None and not isinstance(category_value, str):
                raise ValidationError("The archive contains an invalid sound category.")
            category = normalize_sound_category(category_value)
            raw_tags = raw.get("tags")
            if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
                raise ValidationError("The archive contains invalid sound tags.")
            tags = normalize_sound_tags(",".join(raw_tags))
            expected_hash = SoundArchive._required_string(raw, "sha256")
            if len(expected_hash) != 64 or any(
                char not in "0123456789abcdef" for char in expected_hash
            ):
                raise ValidationError("The archive contains an invalid sound checksum.")
            try:
                sound_data = archive.read(file_name)
            except KeyError as exc:
                raise ValidationError("The archive is missing a referenced sound file.") from exc
            if hashlib.sha256(sound_data).hexdigest() != expected_hash:
                raise ValidationError("A sound file does not match its archive checksum.")
            expected_files.add(file_name)
            restored.append(ArchivedSound(name=name, category=category, tags=tags, data=sound_data))

        if set(archive.namelist()) != expected_files:
            raise ValidationError("The archive contains files not declared in its manifest.")
        return tuple(restored)

    @staticmethod
    def _required_string(data: dict[str, Any], key: str) -> str:
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise ValidationError(f"The archive contains an invalid {key} value.")
        return value

    @staticmethod
    def _sha256_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
