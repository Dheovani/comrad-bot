"""Custom sound persistence operations."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.database.models import CustomSound


class SoundRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add(self, sound: CustomSound) -> CustomSound:
        async with self._sessions.begin() as session:
            session.add(sound)
        return sound

    async def get(self, guild_id: int, normalized_name: str) -> CustomSound | None:
        async with self._sessions() as session:
            result = await session.execute(
                select(CustomSound).where(
                    CustomSound.guild_id == guild_id,
                    CustomSound.normalized_name == normalized_name,
                )
            )
            return result.scalar_one_or_none()

    async def list(self, guild_id: int) -> list[CustomSound]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(CustomSound)
                .where(CustomSound.guild_id == guild_id)
                .order_by(CustomSound.name)
            )
            return list(result)

    async def usage(self, guild_id: int) -> tuple[int, int]:
        async with self._sessions() as session:
            result = await session.execute(
                select(
                    func.count(CustomSound.id),
                    func.coalesce(func.sum(CustomSound.size_bytes), 0),
                ).where(CustomSound.guild_id == guild_id)
            )
            count, size_bytes = result.one()
            return int(count), int(size_bytes)

    async def delete(self, sound_id: str) -> bool:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is None:
                return False
            await session.delete(sound)
            return True

    async def rename(self, sound_id: str, *, name: str, normalized_name: str) -> CustomSound | None:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is None:
                return None
            sound.name = name
            sound.normalized_name = normalized_name
        return sound

    async def update_metadata(
        self,
        sound_id: str,
        *,
        category: str | None,
        tags_json: str,
    ) -> CustomSound | None:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is None:
                return None
            sound.category = category
            sound.tags_json = tags_json
        return sound

    async def increment_play_count(self, sound_id: str) -> None:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is not None:
                sound.play_count += 1
