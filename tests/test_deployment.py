import asyncio
import shutil
import time
from pathlib import Path

import pytest

from comradbot.config import Settings
from comradbot.healthcheck import check_health
from comradbot.services.heartbeat import HeartbeatService, heartbeat_is_fresh


@pytest.mark.asyncio
async def test_heartbeat_lifecycle_creates_refreshes_and_removes_file(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / ".heartbeat"
    service = HeartbeatService(path, interval_seconds=0.01)

    await service.start()
    first = await asyncio.to_thread(path.stat)
    await asyncio.sleep(0.03)
    refreshed = await asyncio.to_thread(path.stat)

    assert refreshed.st_mtime >= first.st_mtime
    assert heartbeat_is_fresh(path, max_age_seconds=5)
    await service.close()
    assert not await asyncio.to_thread(path.exists)


def test_heartbeat_freshness_rejects_missing_future_and_stale_files(tmp_path: Path) -> None:
    path = tmp_path / ".heartbeat"
    assert heartbeat_is_fresh(path, max_age_seconds=10, now=100) is False
    path.write_text("heartbeat", encoding="ascii")
    path.touch()
    modified = path.stat().st_mtime

    assert heartbeat_is_fresh(path, max_age_seconds=10, now=modified + 5)
    assert heartbeat_is_fresh(path, max_age_seconds=10, now=modified - 1)
    assert heartbeat_is_fresh(path, max_age_seconds=10, now=modified - 6) is False
    assert heartbeat_is_fresh(path, max_age_seconds=10, now=modified + 11) is False


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="Deployment health integration requires ffmpeg and ffprobe on PATH",
)
@pytest.mark.asyncio
async def test_healthcheck_uses_heartbeat_audio_tools_and_database(tmp_path: Path) -> None:
    heartbeat = tmp_path / ".heartbeat"
    await asyncio.to_thread(heartbeat.write_text, f"{time.time()}\n", encoding="ascii")
    settings = Settings(
        _env_file=None,
        discord_token="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}",
        healthcheck_heartbeat_file=heartbeat,
        healthcheck_max_age_seconds=30,
    )

    healthy, failures = await check_health(settings)

    assert failures == ()
    assert healthy is True

    await asyncio.to_thread(heartbeat.unlink)
    healthy, failures = await check_health(settings)
    assert healthy is False
    assert failures == ("heartbeat",)
