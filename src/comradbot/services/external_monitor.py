"""Optional outbound heartbeat for externally monitored deployments."""

import asyncio
import logging

import httpx

logger = logging.getLogger(__name__)


class ExternalMonitorService:
    def __init__(
        self,
        ping_url: str | None,
        *,
        interval_seconds: float,
        timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._ping_url = ping_url
        self._interval = interval_seconds
        self._client = client or httpx.AsyncClient(
            timeout=timeout_seconds,
            follow_redirects=False,
        )
        self._owns_client = client is None
        self._task: asyncio.Task[None] | None = None

    @property
    def enabled(self) -> bool:
        return self._ping_url is not None

    async def start(self) -> None:
        if not self.enabled or (self._task is not None and not self._task.done()):
            return
        await self._ping()
        self._task = asyncio.create_task(self._run(), name="comradbot-external-monitor")

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if self._owns_client:
            await self._client.aclose()

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            await self._ping()

    async def _ping(self) -> None:
        if self._ping_url is None:
            return
        try:
            response = await self._client.get(self._ping_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "External monitor heartbeat failed: %s",
                type(exc).__name__,
            )
