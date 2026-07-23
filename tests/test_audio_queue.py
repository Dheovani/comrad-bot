import asyncio
from pathlib import Path

import pytest

from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.audio.queue import AudioQueue
from comradbot.errors import ValidationError


def item(title: str) -> AudioItem:
    return AudioItem(AudioItemType.MUSIC, title, "source", requester_id=1)


@pytest.mark.asyncio
async def test_priority_item_is_selected_next() -> None:
    queue = AudioQueue(max_size=3)
    await queue.put(item("normal-1"))
    await queue.put(item("normal-2"))
    position = await queue.put(item("priority"), next_item=True)

    assert position == 1
    assert (await queue.get()).title == "priority"
    assert [queued.title for queued in await queue.snapshot()] == ["normal-1", "normal-2"]


@pytest.mark.asyncio
async def test_queue_limit_remove_and_clear() -> None:
    queue = AudioQueue(max_size=2)
    await queue.put(item("one"))
    await queue.put(item("two"))
    assert queue.remaining_capacity == 0

    with pytest.raises(ValidationError, match="limit"):
        await queue.put(item("three"))

    assert (await queue.remove(2)).title == "two"
    assert queue.remaining_capacity == 1
    assert [queued.title for queued in await queue.clear()] == ["one"]
    assert len(queue) == 0


@pytest.mark.asyncio
async def test_remove_rejects_invalid_position() -> None:
    queue = AudioQueue(max_size=2)
    with pytest.raises(ValidationError, match="position"):
        await queue.remove(1)


@pytest.mark.asyncio
async def test_audio_item_cleans_up_temporary_file(tmp_path: Path) -> None:
    temporary = tmp_path / "speech.opus"
    await asyncio.to_thread(temporary.write_bytes, b"audio")
    audio = item("speech")
    audio.cleanup_path = temporary

    await audio.cleanup()

    assert not temporary.exists()
