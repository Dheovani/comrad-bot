"""Business rules for custom sound lifecycle."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from random import choice
from tempfile import NamedTemporaryFile
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.database.models import CustomSound, SoundAuditLog
from comradbot.database.repositories.sounds import SoundRepository
from comradbot.errors import PermissionDeniedError, ValidationError
from comradbot.sounds.storage import SoundStorage
from comradbot.sounds.validation import (
    normalize_sound_category,
    normalize_sound_name,
    normalize_sound_tags,
    validate_upload_metadata,
)


class SoundService:
    def __init__(
        self,
        repository: SoundRepository,
        storage: SoundStorage,
        ffmpeg: FFmpegRunner,
        *,
        max_size_bytes: int,
        max_duration_seconds: int,
        quota_provider: Callable[[int], Awaitable[tuple[int, int]]] | None = None,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._ffmpeg = ffmpeg
        self._max_size_bytes = max_size_bytes
        self._max_duration_seconds = max_duration_seconds
        self._quota_provider = quota_provider
        self._upload_locks: defaultdict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def upload(
        self,
        *,
        guild_id: int,
        creator_id: int,
        name: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        category: str | None = None,
        tags: str | None = None,
    ) -> CustomSound:
        async with self._upload_locks[guild_id]:
            return await self._upload_locked(
                guild_id=guild_id,
                creator_id=creator_id,
                name=name,
                filename=filename,
                content_type=content_type,
                data=data,
                category=category,
                tags=tags,
            )

    async def _upload_locked(
        self,
        *,
        guild_id: int,
        creator_id: int,
        name: str,
        filename: str,
        content_type: str | None,
        data: bytes,
        category: str | None,
        tags: str | None,
    ) -> CustomSound:
        normalized = normalize_sound_name(name)
        normalized_category = normalize_sound_category(category)
        normalized_tags = normalize_sound_tags(tags)
        extension = validate_upload_metadata(
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            max_size_bytes=self._max_size_bytes,
        )
        if await self._repository.get(guild_id, normalized) is not None:
            raise ValidationError("A sound with that name already exists in this server.")
        max_count, max_storage_bytes = await self._sound_quota(guild_id)
        sound_count, stored_bytes = await self._repository.usage(guild_id)
        if sound_count >= max_count:
            raise ValidationError(
                f"This server has reached its limit of {max_count} custom sounds."
            )
        if stored_bytes >= max_storage_bytes:
            raise ValidationError("This server has reached its custom sound storage quota.")

        sound_id = str(uuid4())
        relative = self._storage.relative_sound_path(guild_id, sound_id)
        destination = self._storage.absolute_path(relative)
        temporary: Path | None = None
        try:
            guild_directory = await asyncio.to_thread(self._storage.guild_directory, guild_id)
            temporary = await self._write_temporary_upload(
                guild_directory,
                extension,
                data,
            )
            info = await self._ffmpeg.probe(temporary)
            if info.duration_seconds > self._max_duration_seconds:
                raise ValidationError(
                    f"The sound exceeds the {self._max_duration_seconds}-second duration limit."
                )
            await self._ffmpeg.convert_to_opus(temporary, destination)
            converted = await self._ffmpeg.probe(destination)
            converted_size = (await asyncio.to_thread(destination.stat)).st_size
            if stored_bytes + converted_size > max_storage_bytes:
                raise ValidationError("This upload would exceed the server's sound storage quota.")
            sound = CustomSound(
                id=sound_id,
                guild_id=guild_id,
                name=name.strip(),
                normalized_name=normalized,
                relative_path=relative.as_posix(),
                creator_id=creator_id,
                duration_seconds=converted.duration_seconds,
                size_bytes=converted_size,
                format="opus",
                category=normalized_category,
                tags_json=json.dumps(normalized_tags),
            )
            try:
                return await self._repository.add(sound)
            except IntegrityError as exc:
                raise ValidationError(
                    "A sound with that name already exists in this server."
                ) from exc
        except asyncio.CancelledError:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise
        except Exception:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise
        finally:
            if temporary is not None:
                await asyncio.to_thread(temporary.unlink, missing_ok=True)

    async def _sound_quota(self, guild_id: int) -> tuple[int, int]:
        if self._quota_provider is None:
            return 10000, 100000 * 1024 * 1024
        return await self._quota_provider(guild_id)

    async def list_sounds(self, guild_id: int) -> list[CustomSound]:
        return await self._repository.list(guild_id)

    async def search(self, guild_id: int, current: str, *, limit: int = 25) -> list[CustomSound]:
        text_query, category, tag = self._parse_search(current)
        sounds = await self._repository.list(guild_id)
        matches = (
            sound
            for sound in sounds
            if (category is None or (sound.category or "").casefold() == category)
            and (tag is None or tag in sound.tags)
            and (
                not text_query
                or text_query
                in " ".join(
                    (sound.name, sound.normalized_name, sound.category or "", *sound.tags)
                ).casefold()
            )
        )
        return list(matches)[: max(0, min(limit, 25))]

    async def update_metadata(
        self,
        guild_id: int,
        name: str,
        actor_id: int,
        *,
        category: str | None,
        tags: str | None,
        is_moderator: bool,
    ) -> CustomSound:
        sound = await self._require_sound(guild_id, name)
        self._ensure_can_modify(sound, actor_id, is_moderator)
        updated = await self._repository.update_metadata(
            sound.id,
            category=normalize_sound_category(category),
            tags_json=json.dumps(normalize_sound_tags(tags)),
        )
        if updated is None:
            raise ValidationError("The sound was deleted before its metadata could be updated.")
        return updated

    async def get(self, guild_id: int, name: str) -> CustomSound:
        return await self._require_sound(guild_id, name)

    async def get_audio_item(self, guild_id: int, name: str, requester_id: int) -> AudioItem:
        sound = await self._require_sound(guild_id, name)
        return await self._audio_item(sound, requester_id)

    async def get_random_audio_item(self, guild_id: int, requester_id: int) -> AudioItem:
        sounds = await self._repository.list(guild_id)
        if not sounds:
            raise ValidationError("This server has no custom sounds yet.")
        return await self._audio_item(choice(sounds), requester_id)

    async def rename(
        self,
        guild_id: int,
        name: str,
        new_name: str,
        actor_id: int,
        *,
        is_moderator: bool,
    ) -> CustomSound:
        sound = await self._require_sound(guild_id, name)
        self._ensure_can_modify(sound, actor_id, is_moderator)
        normalized = normalize_sound_name(new_name)
        duplicate = await self._repository.get(guild_id, normalized)
        if duplicate is not None and duplicate.id != sound.id:
            raise ValidationError("A sound with that name already exists in this server.")
        try:
            renamed = await self._repository.rename(
                sound.id,
                name=new_name.strip(),
                normalized_name=normalized,
                actor_id=actor_id,
                acted_as_moderator=is_moderator and actor_id != sound.creator_id,
            )
        except IntegrityError as exc:
            raise ValidationError("A sound with that name already exists in this server.") from exc
        if renamed is None:
            raise ValidationError("The sound was deleted before it could be renamed.")
        return renamed

    async def _audio_item(self, sound: CustomSound, requester_id: int) -> AudioItem:
        path = self._storage.absolute_path(sound.relative_path)
        if not await asyncio.to_thread(path.is_file):
            raise ValidationError("The sound record exists, but its audio file is missing.")
        await self._repository.increment_play_count(sound.id)
        return AudioItem(
            item_type=AudioItemType.CUSTOM_SOUND,
            title=sound.name,
            source=str(path),
            requester_id=requester_id,
            duration_seconds=sound.duration_seconds,
        )

    async def delete(
        self, guild_id: int, name: str, actor_id: int, *, is_moderator: bool
    ) -> CustomSound:
        sound = await self._require_sound(guild_id, name)
        self._ensure_can_modify(sound, actor_id, is_moderator)
        deleted = await self._repository.delete(
            sound.id,
            actor_id=actor_id,
            acted_as_moderator=is_moderator and actor_id != sound.creator_id,
        )
        if not deleted:
            raise ValidationError("The sound was already deleted.")
        await self._storage.delete(sound.relative_path)
        return sound

    async def list_audit(self, guild_id: int, *, limit: int = 20) -> list[SoundAuditLog]:
        return await self._repository.list_audit(guild_id, limit=max(1, min(limit, 50)))

    async def _require_sound(self, guild_id: int, name: str) -> CustomSound:
        sound = await self._repository.get(guild_id, normalize_sound_name(name))
        if sound is None:
            raise ValidationError("Custom sound not found.")
        return sound

    @staticmethod
    def _parse_search(query: str) -> tuple[str, str | None, str | None]:
        terms: list[str] = []
        category: str | None = None
        tag: str | None = None
        for token in query.casefold().split():
            if token.startswith("category:") and len(token) > len("category:"):
                category = token.removeprefix("category:")
            elif token.startswith("tag:") and len(token) > len("tag:"):
                tag = token.removeprefix("tag:")
            else:
                terms.append(token)
        return " ".join(terms), category, tag

    @staticmethod
    def _ensure_can_modify(sound: CustomSound, actor_id: int, is_moderator: bool) -> None:
        if actor_id != sound.creator_id and not is_moderator:
            raise PermissionDeniedError("Only the sound creator or a moderator may modify it.")

    @classmethod
    async def _write_temporary_upload(cls, directory: Path, extension: str, data: bytes) -> Path:
        write_task = asyncio.create_task(
            asyncio.to_thread(cls._write_temporary_upload_sync, directory, extension, data)
        )
        try:
            return await asyncio.shield(write_task)
        except asyncio.CancelledError:
            temporary = await write_task
            await asyncio.to_thread(temporary.unlink, missing_ok=True)
            raise

    @staticmethod
    def _write_temporary_upload_sync(directory: Path, extension: str, data: bytes) -> Path:
        with NamedTemporaryFile(
            mode="wb",
            suffix=extension,
            dir=directory,
            delete=False,
        ) as upload:
            upload.write(data)
            return Path(upload.name)
