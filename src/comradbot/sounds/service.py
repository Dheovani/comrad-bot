"""Business rules for custom sound lifecycle."""

from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4

from sqlalchemy.exc import IntegrityError

from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.database.models import CustomSound
from comradbot.database.repositories.sounds import SoundRepository
from comradbot.errors import PermissionDeniedError, ValidationError
from comradbot.sounds.storage import SoundStorage
from comradbot.sounds.validation import normalize_sound_name, validate_upload_metadata


class SoundService:
    def __init__(
        self,
        repository: SoundRepository,
        storage: SoundStorage,
        ffmpeg: FFmpegRunner,
        *,
        max_size_bytes: int,
        max_duration_seconds: int,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._ffmpeg = ffmpeg
        self._max_size_bytes = max_size_bytes
        self._max_duration_seconds = max_duration_seconds

    async def upload(
        self,
        *,
        guild_id: int,
        creator_id: int,
        name: str,
        filename: str,
        content_type: str | None,
        data: bytes,
    ) -> CustomSound:
        normalized = normalize_sound_name(name)
        extension = validate_upload_metadata(
            filename=filename,
            content_type=content_type,
            size_bytes=len(data),
            max_size_bytes=self._max_size_bytes,
        )
        if await self._repository.get(guild_id, normalized) is not None:
            raise ValidationError("Já existe um áudio com esse nome neste servidor.")

        sound_id = str(uuid4())
        relative = self._storage.relative_sound_path(guild_id, sound_id)
        destination = self._storage.absolute_path(relative)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(
                mode="wb",
                suffix=extension,
                dir=self._storage.guild_directory(guild_id),
                delete=False,
            ) as upload:
                upload.write(data)
                temporary = Path(upload.name)
            info = await self._ffmpeg.probe(temporary)
            if info.duration_seconds > self._max_duration_seconds:
                raise ValidationError(
                    f"O áudio excede o limite de {self._max_duration_seconds} segundos."
                )
            await self._ffmpeg.convert_to_opus(temporary, destination)
            converted = await self._ffmpeg.probe(destination)
            sound = CustomSound(
                id=sound_id,
                guild_id=guild_id,
                name=name.strip(),
                normalized_name=normalized,
                relative_path=relative.as_posix(),
                creator_id=creator_id,
                duration_seconds=converted.duration_seconds,
                size_bytes=destination.stat().st_size,
                format="opus",
            )
            try:
                return await self._repository.add(sound)
            except IntegrityError as exc:
                raise ValidationError("Já existe um áudio com esse nome neste servidor.") from exc
        except Exception:
            destination.unlink(missing_ok=True)
            raise
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    async def list(self, guild_id: int) -> list[CustomSound]:
        return await self._repository.list(guild_id)

    async def get_audio_item(self, guild_id: int, name: str, requester_id: int) -> AudioItem:
        sound = await self._require_sound(guild_id, name)
        path = self._storage.absolute_path(sound.relative_path)
        if not path.is_file():
            raise ValidationError("O registro existe, mas o arquivo de áudio não foi encontrado.")
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
        if actor_id != sound.creator_id and not is_moderator:
            raise PermissionDeniedError(
                "Somente o criador ou um moderador pode excluir este áudio."
            )
        deleted = await self._repository.delete(sound.id)
        if not deleted:
            raise ValidationError("O áudio já foi excluído.")
        await self._storage.delete(sound.relative_path)
        return sound

    async def _require_sound(self, guild_id: int, name: str) -> CustomSound:
        sound = await self._repository.get(guild_id, normalize_sound_name(name))
        if sound is None:
            raise ValidationError("Áudio personalizado não encontrado.")
        return sound
