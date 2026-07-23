"""Safe filesystem storage scoped by guild and UUID."""

import asyncio
from pathlib import Path
from uuid import UUID

from comradbot.errors import ValidationError


class SoundStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def guild_directory(self, guild_id: int) -> Path:
        if guild_id <= 0:
            raise ValidationError("Invalid guild ID.")
        path = (self.root / str(guild_id)).resolve()
        if not path.is_relative_to(self.root):
            raise ValidationError("Invalid storage path.")
        path.mkdir(parents=True, exist_ok=True)
        return path

    def relative_sound_path(self, guild_id: int, sound_id: str) -> Path:
        safe_id = str(UUID(sound_id))
        return Path(str(guild_id)) / f"{safe_id}.opus"

    def absolute_path(self, relative_path: str | Path) -> Path:
        path = (self.root / relative_path).resolve()
        if not path.is_relative_to(self.root):
            raise ValidationError("The sound path would escape the configured storage directory.")
        return path

    async def delete(self, relative_path: str | Path) -> None:
        path = self.absolute_path(relative_path)
        await asyncio.to_thread(path.unlink, missing_ok=True)
