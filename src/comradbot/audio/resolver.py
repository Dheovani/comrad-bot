"""Public media source resolution behind a platform-neutral interface."""

import asyncio
from collections.abc import Iterable, Mapping
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from comradbot.audio.models import AudioItem, AudioItemType, AudioSourceRefresher
from comradbot.errors import OperationTimeoutError, ResolverError


class AudioResolver(AudioSourceRefresher, Protocol):
    async def resolve(self, query: str, requester_id: int) -> AudioItem: ...


def audio_item_from_info(raw: Any, *, query: str, requester_id: int) -> AudioItem:
    """Map yt-dlp output into a provider-neutral audio item."""
    if not isinstance(raw, Mapping):
        raise ResolverError("No playable result was found.")

    info: Mapping[str, Any] | None = raw
    entries = raw.get("entries")
    if entries is not None:
        if not isinstance(entries, Iterable) or isinstance(entries, (str, bytes, Mapping)):
            raise ResolverError("The resolver returned an invalid result collection.")
        info = next((entry for entry in entries if isinstance(entry, Mapping)), None)
    if info is None:
        raise ResolverError("No playable result was found.")

    stream_url = info.get("url")
    if not isinstance(stream_url, str) or not stream_url.strip():
        raise ResolverError("The resolved source did not provide an audio stream.")

    title = info.get("title")
    webpage_url = info.get("webpage_url")
    return AudioItem(
        item_type=AudioItemType.MUSIC,
        title=title.strip() if isinstance(title, str) and title.strip() else "Untitled track",
        source=stream_url,
        requester_id=requester_id,
        duration_seconds=_optional_positive_float(info.get("duration")),
        webpage_url=webpage_url if isinstance(webpage_url, str) else query,
    )


def _optional_positive_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        converted = float(value)
    except (TypeError, ValueError):
        return None
    return converted if converted > 0 else None


class YtDlpAudioResolver:
    """Resolve public sources to temporary stream URLs; it never downloads media."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def refresh_source(self, item: AudioItem) -> str:
        if item.item_type is not AudioItemType.MUSIC or item.webpage_url is None:
            raise ResolverError("This audio item does not have a refreshable public source.")
        refreshed = await self.resolve(item.webpage_url, item.requester_id)
        return refreshed.source

    async def resolve(self, query: str, requester_id: int) -> AudioItem:
        normalized_query = query.strip()
        if not normalized_query:
            raise ResolverError("Enter a track name or public URL.")
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._resolve_sync, normalized_query, requester_id),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise OperationTimeoutError("Music resolution timed out.") from exc

    @staticmethod
    def _resolve_sync(query: str, requester_id: int) -> AudioItem:
        target = query if "://" in query else f"ytsearch1:{query}"
        options: dict[str, Any] = {
            "format": "bestaudio/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "extract_flat": False,
            "skip_download": True,
            "socket_timeout": 15,
        }
        try:
            with YoutubeDL(options) as ydl:
                raw = ydl.extract_info(target, download=False)
        except DownloadError as exc:
            raise ResolverError("No playable public source could be resolved.") from exc
        return audio_item_from_info(raw, query=query, requester_id=requester_id)
