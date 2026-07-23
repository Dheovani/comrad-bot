"""Guild-scoped playlist persistence operations."""

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from comradbot.database.models import Playlist, SavedTrack


class PlaylistRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def add_playlist(self, playlist: Playlist) -> Playlist:
        async with self._sessions.begin() as session:
            session.add(playlist)
        return playlist

    async def get_playlist(self, guild_id: int, normalized_name: str) -> Playlist | None:
        async with self._sessions() as session:
            result = await session.execute(
                select(Playlist).where(
                    Playlist.guild_id == guild_id,
                    Playlist.normalized_name == normalized_name,
                )
            )
            return result.scalar_one_or_none()

    async def list_playlists(self, guild_id: int) -> list[Playlist]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(Playlist).where(Playlist.guild_id == guild_id).order_by(Playlist.name)
            )
            return list(result)

    async def add_track(
        self,
        *,
        playlist_id: int,
        title: str,
        source_reference: str,
        duration_seconds: float | None,
        added_by_id: int,
    ) -> SavedTrack:
        async with self._sessions.begin() as session:
            last_position = await session.scalar(
                select(func.max(SavedTrack.position)).where(SavedTrack.playlist_id == playlist_id)
            )
            track = SavedTrack(
                playlist_id=playlist_id,
                position=(last_position or 0) + 1,
                title=title,
                source_reference=source_reference,
                duration_seconds=duration_seconds,
                added_by_id=added_by_id,
            )
            session.add(track)
        return track

    async def list_tracks(self, playlist_id: int) -> list[SavedTrack]:
        async with self._sessions() as session:
            result = await session.scalars(
                select(SavedTrack)
                .where(SavedTrack.playlist_id == playlist_id)
                .order_by(SavedTrack.position)
            )
            return list(result)

    async def remove_track(self, playlist_id: int, position: int) -> SavedTrack | None:
        async with self._sessions.begin() as session:
            result = await session.execute(
                select(SavedTrack).where(
                    SavedTrack.playlist_id == playlist_id,
                    SavedTrack.position == position,
                )
            )
            track = result.scalar_one_or_none()
            if track is None:
                return None
            await session.delete(track)
            await session.execute(
                update(SavedTrack)
                .where(
                    SavedTrack.playlist_id == playlist_id,
                    SavedTrack.position > position,
                )
                .values(position=SavedTrack.position - 1)
            )
        return track

    async def delete_playlist(self, playlist_id: int) -> bool:
        async with self._sessions.begin() as session:
            playlist = await session.get(Playlist, playlist_id)
            if playlist is None:
                return False
            await session.execute(delete(SavedTrack).where(SavedTrack.playlist_id == playlist_id))
            await session.delete(playlist)
            return True
