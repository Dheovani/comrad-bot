from pathlib import Path

import pytest

from comradbot.ai.models import AIMessage
from comradbot.database.models import CustomSound
from comradbot.database.repositories import AIRepository, SoundRepository
from comradbot.database.session import Database


@pytest.mark.asyncio
async def test_sound_repository_round_trip(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}")
    await database.create_schema()
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
    )
    try:
        await repository.add(sound)
        found = await repository.get(123, "risada")
        assert found is not None and found.creator_id == 456
        await repository.increment_play_count(sound.id)
        found = await repository.get(123, "risada")
        assert found is not None and found.play_count == 1
        assert await repository.delete(sound.id) is True
        assert await repository.get(123, "risada") is None
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_ai_repository_trims_only_what_service_provides(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'ai.db').as_posix()}")
    await database.create_schema()
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
