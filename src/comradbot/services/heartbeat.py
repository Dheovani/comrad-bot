"""Managed heartbeat used by container health checks."""

import asyncio
import logging
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)
MAX_CLOCK_SKEW_SECONDS = 5.0


def heartbeat_is_fresh(
    path: Path,
    *,
    max_age_seconds: float,
    now: float | None = None,
) -> bool:
    try:
        modified_at = path.stat().st_mtime
    except OSError:
        return False
    timestamp = time.time() if now is None else now
    age = timestamp - modified_at
    return -MAX_CLOCK_SKEW_SECONDS <= age <= max_age_seconds


class HeartbeatService:
    def __init__(
        self,
        path: Path,
        *,
        interval_seconds: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = path
        self._interval = interval_seconds
        self._clock = clock
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        await self._write()
        self._task = asyncio.create_task(self._run(), name="comradbot-heartbeat")

    async def close(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await asyncio.to_thread(self._path.unlink, missing_ok=True)

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            try:
                await self._write()
            except OSError:
                logger.exception("Failed to update the runtime heartbeat")

    async def _write(self) -> None:
        write_task = asyncio.create_task(asyncio.to_thread(self._write_sync))
        try:
            await asyncio.shield(write_task)
        except asyncio.CancelledError:
            await write_task
            raise

    def _write_sync(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(f"{self._path.suffix}.tmp")
        temporary.write_text(f"{self._clock():.6f}\n", encoding="ascii")
        temporary.replace(self._path)
