"""Custom sound persistence operations."""

from __future__ import annotations

import builtins

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.database.models import CustomSound, SoundAuditLog


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

    async def delete(
        self,
        sound_id: str,
        *,
        actor_id: int,
        acted_as_moderator: bool,
    ) -> bool:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is None:
                return False
            session.add(
                SoundAuditLog(
                    guild_id=sound.guild_id,
                    sound_id=sound.id,
                    action="delete",
                    actor_id=actor_id,
                    owner_id=sound.creator_id,
                    acted_as_moderator=acted_as_moderator,
                    previous_name=sound.name,
                    new_name=None,
                )
            )
            await session.delete(sound)
            return True

    async def rename(
        self,
        sound_id: str,
        *,
        name: str,
        normalized_name: str,
        actor_id: int,
        acted_as_moderator: bool,
    ) -> CustomSound | None:
        async with self._sessions.begin() as session:
            sound = await session.get(CustomSound, sound_id)
            if sound is None:
                return None
            previous_name = sound.name
            sound.name = name
            sound.normalized_name = normalized_name
            session.add(
                SoundAuditLog(
                    guild_id=sound.guild_id,
                    sound_id=sound.id,
                    action="rename",
                    actor_id=actor_id,
                    owner_id=sound.creator_id,
                    acted_as_moderator=acted_as_moderator,
                    previous_name=previous_name,
                    new_name=name,
                )
            )
        return sound

    async def list_audit(self, guild_id: int, *, limit: int) -> builtins.list[SoundAuditLog]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(SoundAuditLog)
                .where(SoundAuditLog.guild_id == guild_id)
                .order_by(SoundAuditLog.created_at.desc(), SoundAuditLog.id.desc())
                .limit(max(1, min(limit, 50)))
            )
            return list(result)

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
