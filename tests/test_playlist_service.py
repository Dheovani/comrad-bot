from pathlib import Path

import pytest

from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.database.repositories import PlaylistRepository
from comradbot.database.session import Database
from comradbot.errors import PermissionDeniedError, ResolverError, ValidationError
from comradbot.services.music import PlaylistService, normalize_playlist_name


class FakeResolver:
    def __init__(self) -> None:
        self.unavailable: set[str] = set()

    async def resolve(self, query: str, requester_id: int) -> AudioItem:
        if query in self.unavailable:
            raise ResolverError("Unavailable")
        return AudioItem(
            AudioItemType.MUSIC,
            f"Resolved {query}",
            f"https://stream.example/{query}",
            requester_id,
            duration_seconds=42,
            webpage_url=f"https://media.example/{query}",
        )

    async def refresh_source(self, item: AudioItem) -> str:
        return item.source


class FakeQueue:
    def __init__(self, remaining_capacity: int) -> None:
        self.remaining_capacity = remaining_capacity


class FakePlayer:
    def __init__(self, remaining_capacity: int) -> None:
        self.queue = FakeQueue(remaining_capacity)
        self.items: list[AudioItem] = []

    async def enqueue(
        self,
        item: AudioItem,
        *,
        next_item: bool = False,
        refresh_if_queued: bool = False,
    ) -> int:
        del next_item, refresh_if_queued
        self.items.append(item)
        return len(self.items)


def test_normalize_playlist_name_is_stable_and_rejects_paths() -> None:
    assert normalize_playlist_name("  Sessão Épica  ") == "sessao-epica"
    with pytest.raises(ValidationError, match="path"):
        normalize_playlist_name("../private")


@pytest.mark.asyncio
async def test_playlist_lifecycle_enforces_ownership_and_limits(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'service.db').as_posix()}")
    await database.migrate()
    resolver = FakeResolver()
    service = PlaylistService(
        PlaylistRepository(database.sessions),
        resolver,
        max_playlists_per_guild=1,
        max_tracks_per_playlist=2,
    )
    try:
        playlist = await service.create(1, "Raid Night", 10)
        assert playlist.normalized_name == "raid-night"
        with pytest.raises(ValidationError, match="limit"):
            await service.create(1, "Second", 10)
        with pytest.raises(PermissionDeniedError):
            await service.add_track(
                guild_id=1,
                playlist_name="Raid Night",
                query="first",
                actor_id=11,
                is_moderator=False,
            )

        first = await service.add_track(
            guild_id=1,
            playlist_name="Raid Night",
            query="first",
            actor_id=10,
            is_moderator=False,
        )
        second = await service.add_track(
            guild_id=1,
            playlist_name="Raid Night",
            query="second",
            actor_id=99,
            is_moderator=True,
        )
        assert (first.position, second.position) == (1, 2)
        with pytest.raises(ValidationError, match="limit"):
            await service.add_track(
                guild_id=1,
                playlist_name="Raid Night",
                query="third",
                actor_id=10,
                is_moderator=False,
            )

        removed = await service.remove_track(
            guild_id=1,
            playlist_name="Raid Night",
            position=1,
            actor_id=10,
            is_moderator=False,
        )
        assert removed.title == "Resolved first"
        details = await service.get(1, "raid-night")
        assert [(track.position, track.title) for track in details.tracks] == [
            (1, "Resolved second")
        ]

        renamed = await service.rename(
            guild_id=1,
            name="Raid Night",
            new_name="Friday Raid",
            actor_id=10,
            is_moderator=False,
        )
        assert renamed.name == "Friday Raid"
        assert renamed.normalized_name == "friday-raid"
        assert (await service.get(1, "Friday Raid")).playlist.id == playlist.id
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_playlist_tracks_can_be_reordered_atomically(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'reorder.db').as_posix()}")
    await database.migrate()
    service = PlaylistService(
        PlaylistRepository(database.sessions),
        FakeResolver(),
        max_playlists_per_guild=5,
        max_tracks_per_playlist=5,
    )
    try:
        await service.create(1, "Mix", 10)
        for query in ("one", "two", "three"):
            await service.add_track(
                guild_id=1,
                playlist_name="Mix",
                query=query,
                actor_id=10,
                is_moderator=False,
            )

        moved = await service.move_track(
            guild_id=1,
            playlist_name="Mix",
            from_position=3,
            to_position=1,
            actor_id=10,
            is_moderator=False,
        )
        details = await service.get(1, "Mix")

        assert moved.title == "Resolved three"
        assert [(track.position, track.title) for track in details.tracks] == [
            (1, "Resolved three"),
            (2, "Resolved one"),
            (3, "Resolved two"),
        ]
        with pytest.raises(ValidationError, match="positions"):
            await service.move_track(
                guild_id=1,
                playlist_name="Mix",
                from_position=4,
                to_position=1,
                actor_id=10,
                is_moderator=False,
            )
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_enqueue_playlist_skips_unavailable_and_respects_queue_capacity(
    tmp_path: Path,
) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'enqueue.db').as_posix()}")
    await database.migrate()
    resolver = FakeResolver()
    service = PlaylistService(
        PlaylistRepository(database.sessions),
        resolver,
        max_playlists_per_guild=5,
        max_tracks_per_playlist=5,
    )
    try:
        await service.create(1, "Mix", 10)
        for query in ("one", "two", "three"):
            await service.add_track(
                guild_id=1,
                playlist_name="Mix",
                query=query,
                actor_id=10,
                is_moderator=False,
            )
        resolver.unavailable.add("https://media.example/one")
        player = FakePlayer(remaining_capacity=2)

        result = await service.enqueue(
            guild_id=1,
            name="Mix",
            requester_id=20,
            player=player,  # type: ignore[arg-type]
        )

        assert result.queued_count == 1
        assert result.skipped_count == 2
        assert [item.title for item in player.items] == ["Resolved https://media.example/two"]
    finally:
        await database.close()
