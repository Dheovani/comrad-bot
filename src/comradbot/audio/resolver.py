"""Public media source resolution behind a platform-neutral interface."""

import asyncio
import logging
import time
from collections.abc import Callable, Iterable, Mapping
from enum import StrEnum
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from comradbot.audio.models import AudioItem, AudioItemType, AudioSourceRefresher
from comradbot.errors import OperationTimeoutError, ResolverError

logger = logging.getLogger(__name__)


class ResolverOperation(StrEnum):
    RESOLVE = "resolve"
    REFRESH = "refresh"


class ResolverOutcome(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"


class ResolverMetricsSink(Protocol):
    def record_resolver_result(
        self,
        operation: ResolverOperation,
        outcome: ResolverOutcome,
        latency_ms: int,
    ) -> None: ...


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

    def __init__(
        self,
        timeout_seconds: float,
        *,
        metrics: ResolverMetricsSink | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._metrics = metrics
        self._clock = clock

    async def refresh_source(self, item: AudioItem) -> str:
        if item.item_type is not AudioItemType.MUSIC or item.webpage_url is None:
            raise ResolverError("This audio item does not have a refreshable public source.")
        refreshed = await self._resolve(
            item.webpage_url,
            item.requester_id,
            ResolverOperation.REFRESH,
        )
        return refreshed.source

    async def resolve(self, query: str, requester_id: int) -> AudioItem:
        return await self._resolve(query, requester_id, ResolverOperation.RESOLVE)

    async def _resolve(
        self,
        query: str,
        requester_id: int,
        operation: ResolverOperation,
    ) -> AudioItem:
        normalized_query = query.strip()
        if not normalized_query:
            raise ResolverError("Enter a track name or public URL.")
        started_at = self._clock()
        query_kind = "url" if "://" in normalized_query else "search"
        try:
            item = await asyncio.wait_for(
                asyncio.to_thread(self._resolve_sync, normalized_query, requester_id),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            self._record_result(operation, ResolverOutcome.TIMEOUT, started_at, query_kind)
            raise OperationTimeoutError("Music resolution timed out.") from exc
        except ResolverError:
            self._record_result(operation, ResolverOutcome.FAILURE, started_at, query_kind)
            raise
        self._record_result(operation, ResolverOutcome.SUCCESS, started_at, query_kind)
        return item

    def _record_result(
        self,
        operation: ResolverOperation,
        outcome: ResolverOutcome,
        started_at: float,
        query_kind: str,
    ) -> None:
        latency_ms = max(0, round((self._clock() - started_at) * 1000))
        if self._metrics is not None:
            self._metrics.record_resolver_result(operation, outcome, latency_ms)
        log = logger.info if outcome is ResolverOutcome.SUCCESS else logger.warning
        log(
            "Music resolver operation=%s outcome=%s latency_ms=%d query_kind=%s",
            operation.value,
            outcome.value,
            latency_ms,
            query_kind,
        )

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
