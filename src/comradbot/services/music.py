"""Business rules for persistent guild playlists."""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from comradbot.audio.player import GuildAudioPlayer
from comradbot.audio.resolver import AudioResolver
from comradbot.database.models import Playlist, SavedTrack
from comradbot.database.repositories.playlists import PlaylistRepository
from comradbot.errors import (
    OperationTimeoutError,
    PermissionDeniedError,
    ResolverError,
    ValidationError,
)

logger = logging.getLogger(__name__)
_VALID_NAME = re.compile(r"^[a-z0-9](?:[a-z0-9_-]{0,48}[a-z0-9])?$")
_MAX_QUERY_CHARACTERS = 500


@dataclass(frozen=True, slots=True)
class PlaylistDetails:
    playlist: Playlist
    tracks: list[SavedTrack]


@dataclass(frozen=True, slots=True)
class PlaylistEnqueueResult:
    playlist: Playlist
    queued_count: int
    skipped_count: int


def normalize_playlist_name(name: str) -> str:
    if "/" in name or "\\" in name or ".." in name:
        raise ValidationError("The playlist name contains an invalid path sequence.")
    folded = unicodedata.normalize("NFKD", name.strip()).encode("ascii", "ignore").decode()
    normalized = re.sub(r"[^a-z0-9]+", "-", folded.lower()).strip("-")
    if not normalized or not _VALID_NAME.fullmatch(normalized):
        raise ValidationError("Use a name with 1 to 50 letters, numbers, hyphens, or underscores.")
    return normalized


class PlaylistService:
    def __init__(
        self,
        repository: PlaylistRepository,
        resolver: AudioResolver,
        *,
        max_playlists_per_guild: int,
        max_tracks_per_playlist: int,
    ) -> None:
        self._repository = repository
        self._resolver = resolver
        self._max_playlists_per_guild = max_playlists_per_guild
        self._max_tracks_per_playlist = max_tracks_per_playlist

    async def create(self, guild_id: int, name: str, creator_id: int) -> Playlist:
        normalized = normalize_playlist_name(name)
        playlists = await self._repository.list_playlists(guild_id)
        if len(playlists) >= self._max_playlists_per_guild:
            raise ValidationError(
                f"This server has reached its limit of {self._max_playlists_per_guild} playlists."
            )
        if any(playlist.normalized_name == normalized for playlist in playlists):
            raise ValidationError("A playlist with that name already exists in this server.")
        playlist = Playlist(
            guild_id=guild_id,
            name=name.strip(),
            normalized_name=normalized,
            creator_id=creator_id,
        )
        try:
            return await self._repository.add_playlist(playlist)
        except IntegrityError as exc:
            raise ValidationError(
                "A playlist with that name already exists in this server."
            ) from exc

    async def list_playlists(self, guild_id: int) -> list[PlaylistDetails]:
        playlists = await self._repository.list_playlists(guild_id)
        return [
            PlaylistDetails(playlist, await self._repository.list_tracks(playlist.id))
            for playlist in playlists
        ]

    async def search(self, guild_id: int, current: str, *, limit: int = 25) -> list[Playlist]:
        query = current.strip().casefold()
        playlists = await self._repository.list_playlists(guild_id)
        matches = (
            playlist
            for playlist in playlists
            if not query
            or query in playlist.name.casefold()
            or query in playlist.normalized_name.casefold()
        )
        return list(matches)[: max(0, min(limit, 25))]

    async def get(self, guild_id: int, name: str) -> PlaylistDetails:
        playlist = await self._require_playlist(guild_id, name)
        tracks = await self._repository.list_tracks(playlist.id)
        return PlaylistDetails(playlist, tracks)

    async def add_track(
        self,
        *,
        guild_id: int,
        playlist_name: str,
        query: str,
        actor_id: int,
        is_moderator: bool,
    ) -> SavedTrack:
        playlist = await self._require_playlist(guild_id, playlist_name)
        self._ensure_can_modify(playlist, actor_id, is_moderator)
        tracks = await self._repository.list_tracks(playlist.id)
        if len(tracks) >= self._max_tracks_per_playlist:
            raise ValidationError(
                f"This playlist has reached its limit of {self._max_tracks_per_playlist} tracks."
            )
        normalized_query = query.strip()
        if not normalized_query:
            raise ValidationError("Enter a track name or public URL.")
        if len(normalized_query) > _MAX_QUERY_CHARACTERS:
            raise ValidationError(
                f"Track searches are limited to {_MAX_QUERY_CHARACTERS} characters."
            )
        item = await self._resolver.resolve(normalized_query, actor_id)
        reference = item.webpage_url or normalized_query
        if len(reference) > 2000:
            raise ValidationError("The resolved public source reference is too long to save.")
        try:
            return await self._repository.add_track(
                playlist_id=playlist.id,
                title=item.title[:300],
                source_reference=reference,
                duration_seconds=item.duration_seconds,
                added_by_id=actor_id,
            )
        except IntegrityError as exc:
            raise ValidationError("The playlist changed concurrently; please try again.") from exc

    async def remove_track(
        self,
        *,
        guild_id: int,
        playlist_name: str,
        position: int,
        actor_id: int,
        is_moderator: bool,
    ) -> SavedTrack:
        playlist = await self._require_playlist(guild_id, playlist_name)
        self._ensure_can_modify(playlist, actor_id, is_moderator)
        track = await self._repository.remove_track(playlist.id, position)
        if track is None:
            raise ValidationError("That playlist position does not exist.")
        return track

    async def move_track(
        self,
        *,
        guild_id: int,
        playlist_name: str,
        from_position: int,
        to_position: int,
        actor_id: int,
        is_moderator: bool,
    ) -> SavedTrack:
        playlist = await self._require_playlist(guild_id, playlist_name)
        self._ensure_can_modify(playlist, actor_id, is_moderator)
        track = await self._repository.move_track(
            playlist.id,
            from_position,
            to_position,
        )
        if track is None:
            raise ValidationError("One of those playlist positions does not exist.")
        return track

    async def rename(
        self,
        *,
        guild_id: int,
        name: str,
        new_name: str,
        actor_id: int,
        is_moderator: bool,
    ) -> Playlist:
        playlist = await self._require_playlist(guild_id, name)
        self._ensure_can_modify(playlist, actor_id, is_moderator)
        normalized = normalize_playlist_name(new_name)
        duplicate = await self._repository.get_playlist(guild_id, normalized)
        if duplicate is not None and duplicate.id != playlist.id:
            raise ValidationError("A playlist with that name already exists in this server.")
        try:
            renamed = await self._repository.rename_playlist(
                playlist.id,
                name=new_name.strip(),
                normalized_name=normalized,
            )
        except IntegrityError as exc:
            raise ValidationError(
                "A playlist with that name already exists in this server."
            ) from exc
        if renamed is None:
            raise ValidationError("The playlist was deleted before it could be renamed.")
        return renamed

    async def delete(
        self,
        *,
        guild_id: int,
        name: str,
        actor_id: int,
        is_moderator: bool,
    ) -> Playlist:
        playlist = await self._require_playlist(guild_id, name)
        self._ensure_can_modify(playlist, actor_id, is_moderator)
        if not await self._repository.delete_playlist(playlist.id):
            raise ValidationError("The playlist was already deleted.")
        return playlist

    async def enqueue(
        self,
        *,
        guild_id: int,
        name: str,
        requester_id: int,
        player: GuildAudioPlayer,
    ) -> PlaylistEnqueueResult:
        details = await self.get(guild_id, name)
        if not details.tracks:
            raise ValidationError("This playlist has no tracks.")
        capacity = player.queue.remaining_capacity
        if capacity == 0:
            raise ValidationError("The audio queue is full.")

        queued_count = 0
        skipped_count = 0
        for track in details.tracks[:capacity]:
            try:
                item = await self._resolver.resolve(track.source_reference, requester_id)
                await player.enqueue(item, refresh_if_queued=True)
                queued_count += 1
            except (OperationTimeoutError, ResolverError):
                skipped_count += 1
                logger.warning(
                    "Skipped unavailable saved track playlist_id=%s track_id=%s",
                    details.playlist.id,
                    track.id,
                )
        skipped_count += max(0, len(details.tracks) - capacity)
        return PlaylistEnqueueResult(details.playlist, queued_count, skipped_count)

    async def _require_playlist(self, guild_id: int, name: str) -> Playlist:
        playlist = await self._repository.get_playlist(guild_id, normalize_playlist_name(name))
        if playlist is None:
            raise ValidationError("Playlist not found.")
        return playlist

    @staticmethod
    def _ensure_can_modify(playlist: Playlist, actor_id: int, is_moderator: bool) -> None:
        if actor_id != playlist.creator_id and not is_moderator:
            raise PermissionDeniedError("Only the playlist creator or a moderator may modify it.")
