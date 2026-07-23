import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest
from yt_dlp.utils import DownloadError

from comradbot.audio import resolver as resolver_module
from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.audio.resolver import YtDlpAudioResolver, audio_item_from_info
from comradbot.errors import OperationTimeoutError, ResolverError


def test_audio_item_from_search_result_uses_first_playable_entry() -> None:
    item = audio_item_from_info(
        {
            "entries": [
                None,
                {
                    "url": "https://media.example/audio",
                    "title": " Example Track ",
                    "duration": "123.5",
                    "webpage_url": "https://example.test/watch/1",
                },
            ]
        },
        query="example",
        requester_id=42,
    )

    assert item.item_type is AudioItemType.MUSIC
    assert item.title == "Example Track"
    assert item.source == "https://media.example/audio"
    assert item.duration_seconds == 123.5
    assert item.webpage_url == "https://example.test/watch/1"
    assert item.requester_id == 42


@pytest.mark.parametrize("duration", [None, True, 0, -1, "unknown", object()])
def test_audio_item_ignores_invalid_duration(duration: object) -> None:
    item = audio_item_from_info(
        {"url": "https://media.example/audio", "duration": duration},
        query="example",
        requester_id=42,
    )

    assert item.duration_seconds is None


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"entries": []},
        {"entries": "invalid"},
        {"url": ""},
        {"url": 123},
    ],
)
def test_audio_item_rejects_unplayable_results(payload: Any) -> None:
    with pytest.raises(ResolverError):
        audio_item_from_info(payload, query="example", requester_id=42)


@pytest.mark.asyncio
async def test_resolver_rejects_blank_query_without_starting_worker() -> None:
    resolver = YtDlpAudioResolver(timeout_seconds=1)

    with pytest.raises(ResolverError, match="track name"):
        await resolver.resolve("   ", requester_id=42)


@pytest.mark.asyncio
async def test_resolver_maps_worker_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    async def blocked_to_thread(*args: object, **kwargs: object) -> object:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    monkeypatch.setattr(resolver_module.asyncio, "to_thread", blocked_to_thread)
    resolver = YtDlpAudioResolver(timeout_seconds=0.01)

    with pytest.raises(OperationTimeoutError, match="timed out"):
        await resolver.resolve("example", requester_id=42)


@pytest.mark.asyncio
async def test_refresh_source_resolves_original_public_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = YtDlpAudioResolver(timeout_seconds=1)
    refreshed = AudioItem(
        AudioItemType.MUSIC,
        "Track",
        "https://media.example/fresh",
        requester_id=42,
    )
    resolve = AsyncMock(return_value=refreshed)
    monkeypatch.setattr(resolver, "resolve", resolve)
    queued = AudioItem(
        AudioItemType.MUSIC,
        "Track",
        "https://media.example/expired",
        requester_id=42,
        webpage_url="https://example.test/watch/1",
        refresh_before_playback=True,
    )

    source = await resolver.refresh_source(queued)

    assert source == "https://media.example/fresh"
    resolve.assert_awaited_once_with("https://example.test/watch/1", 42)


@pytest.mark.asyncio
async def test_refresh_source_rejects_non_music_item() -> None:
    resolver = YtDlpAudioResolver(timeout_seconds=1)
    sound = AudioItem(
        AudioItemType.CUSTOM_SOUND,
        "Sound",
        "local.opus",
        requester_id=42,
    )

    with pytest.raises(ResolverError, match="does not have"):
        await resolver.refresh_source(sound)


def test_yt_dlp_resolution_uses_search_without_downloading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, Any]) -> None:
            captured["options"] = options

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_info(self, target: str, *, download: bool) -> dict[str, Any]:
            captured["target"] = target
            captured["download"] = download
            return {"url": "https://media.example/audio", "title": "Track"}

    monkeypatch.setattr(resolver_module, "YoutubeDL", FakeYoutubeDL)

    item = YtDlpAudioResolver._resolve_sync("search terms", requester_id=42)

    assert item.title == "Track"
    assert captured["target"] == "ytsearch1:search terms"
    assert captured["download"] is False
    assert captured["options"]["skip_download"] is True
    assert captured["options"]["noplaylist"] is True


def test_yt_dlp_download_error_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingYoutubeDL:
        def __init__(self, options: dict[str, Any]) -> None:
            pass

        def __enter__(self) -> "FailingYoutubeDL":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def extract_info(self, target: str, *, download: bool) -> None:
            raise DownloadError("provider detail")

    monkeypatch.setattr(resolver_module, "YoutubeDL", FailingYoutubeDL)

    with pytest.raises(ResolverError, match="public source") as error:
        YtDlpAudioResolver._resolve_sync("search terms", requester_id=42)

    assert "provider detail" not in str(error.value)
