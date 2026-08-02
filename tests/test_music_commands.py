from comradbot.audio.models import AudioItem, AudioItemType, RepeatMode
from comradbot.commands.music import build_queue_embed


def music_item(title: str, requester_id: int = 1) -> AudioItem:
    return AudioItem(
        AudioItemType.MUSIC,
        title,
        "source",
        requester_id=requester_id,
    )


def test_queue_embed_shows_current_and_twenty_queued_items() -> None:
    current = music_item("Current", requester_id=99)
    queued = [music_item(f"Track {index}", requester_id=index) for index in range(1, 23)]

    embed = build_queue_embed(current, queued)
    description = str(embed.description)

    assert "**Now playing:** Current" in description
    assert "`1.` Track 1 — <@1>" in description
    assert "`20.` Track 20 — <@20>" in description
    assert "Track 21" not in description
    assert "…and 2 more item(s)." in description


def test_queue_embed_handles_empty_player() -> None:
    embed = build_queue_embed(None, [])

    assert embed.description == "The queue is empty."


def test_queue_embed_displays_repeat_mode() -> None:
    embed = build_queue_embed(None, [], RepeatMode.QUEUE)

    assert embed.footer.text == "Repeat: queue"
