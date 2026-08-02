from pathlib import Path

import pytest

from comradbot.ai.models import AIMessage
from comradbot.database.models import CustomSound, Playlist
from comradbot.database.repositories import (
    AIRepository,
    GuildSettingsRepository,
    PlaylistRepository,
    SoundRepository,
)
from comradbot.database.session import Database


@pytest.mark.asyncio
async def test_sound_repository_round_trip(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    await database.migrate()
    repository = SoundRepository(database.sessions)
    sound = CustomSound(
        id="760de197-4148-4d90-8956-26017a03a889",
        guild_id=123,
        name="Risada",
        normalized_name="risada",
        relative_path="123/760de197-4148-4d90-8956-26017a03a889.opus",
        creator_id=456,
        duration_seconds=1.5,
        size_bytes=100,
        format="opus",
        category="Memes",
        tags_json='["loud"]',
    )
    try:
        await repository.add(sound)
        found = await repository.get(123, "risada")
        assert found is not None and found.creator_id == 456
        await repository.increment_play_count(sound.id)
        found = await repository.get(123, "risada")
        assert found is not None and found.play_count == 1
        assert found.category == "Memes"
        assert found.tags == ("loud",)
        renamed = await repository.rename(sound.id, name="Air Horn", normalized_name="air-horn")
        assert renamed is not None and renamed.name == "Air Horn"
        assert await repository.get(123, "risada") is None
        assert await repository.get(123, "air-horn") is not None
        assert await repository.delete(sound.id) is True
        assert await repository.get(123, "air-horn") is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_ai_repository_trims_only_what_service_provides(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'ai.db').as_posix()}")
    await database.migrate()
    repository = AIRepository(database.sessions)
    messages = [AIMessage(role="user", content="oi"), AIMessage(role="assistant", content="olá")]
    try:
        await repository.save_messages(1, 2, messages)
        assert await repository.get_messages(1, 2) == messages
        await repository.record_usage(
            guild_id=1,
            user_id=3,
            operation="ask",
            input_characters=2,
            output_characters=3,
            success=True,
        )
        await repository.reset(1, 2)
        assert await repository.get_messages(1, 2) == []
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_guild_settings_repository_round_trip(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'guild.db').as_posix()}")
    await database.migrate()
    repository = GuildSettingsRepository(database.sessions)
    try:
        assert await repository.get(123) is None
        await repository.update(
            123,
            default_volume=0.7,
            ai_enabled=False,
            max_sound_count=20,
            max_sound_storage_mb=30,
        )
        found = await repository.get(123)
        assert found is not None
        assert found.default_volume == 0.7
        assert found.ai_enabled is False
        assert found.max_sound_count == 20
        assert found.max_sound_storage_mb == 30
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_playlist_repository_orders_and_renumbers_tracks(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'playlist.db').as_posix()}")
    await database.migrate()
    repository = PlaylistRepository(database.sessions)
    playlist = Playlist(guild_id=123, name="Raid", normalized_name="raid", creator_id=456)
    try:
        await repository.add_playlist(playlist)
        await repository.add_track(
            playlist_id=playlist.id,
            title="First",
            source_reference="https://example.com/first",
            duration_seconds=10,
            added_by_id=456,
        )
        await repository.add_track(
            playlist_id=playlist.id,
            title="Second",
            source_reference="https://example.com/second",
            duration_seconds=None,
            added_by_id=456,
        )

        removed = await repository.remove_track(playlist.id, 1)
        assert removed is not None and removed.title == "First"
        tracks = await repository.list_tracks(playlist.id)
        assert [(track.position, track.title) for track in tracks] == [(1, "Second")]
        assert await repository.delete_playlist(playlist.id) is True
        assert await repository.list_tracks(playlist.id) == []
    finally:
        await database.close()
