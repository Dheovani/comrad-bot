"""Public media source resolution behind a platform-neutral interface."""

import asyncio
from typing import Any, Protocol

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from comradbot.audio.models import AudioItem, AudioItemType
from comradbot.errors import OperationTimeoutError, ResolverError


class AudioResolver(Protocol):
    async def resolve(self, query: str, requester_id: int) -> AudioItem: ...


class YtDlpAudioResolver:
    """Resolve public sources to temporary stream URLs; it never downloads media."""

    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def resolve(self, query: str, requester_id: int) -> AudioItem:
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(self._resolve_sync, query, requester_id),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise OperationTimeoutError("A busca da música excedeu o tempo limite.") from exc

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
            raise ResolverError(
                "Não foi possível encontrar uma fonte pública reproduzível."
            ) from exc
        if raw is None:
            raise ResolverError("Nenhum resultado foi encontrado.")
        info = raw
        entries = raw.get("entries") if hasattr(raw, "get") else None
        if entries:
            info = next((entry for entry in entries if entry), None)
        if not info or not hasattr(info, "get"):
            raise ResolverError("Nenhum resultado reproduzível foi encontrado.")
        stream_url = info.get("url")
        if not isinstance(stream_url, str):
            raise ResolverError("A fonte encontrada não forneceu um stream de áudio.")
        duration = info.get("duration")
        return AudioItem(
            item_type=AudioItemType.MUSIC,
            title=str(info.get("title") or "Faixa sem título"),
            source=stream_url,
            requester_id=requester_id,
            duration_seconds=float(duration) if duration is not None else None,
            webpage_url=str(info.get("webpage_url") or query),
        )
