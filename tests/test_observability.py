from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import pytest

from comradbot.audio.resolver import ResolverOperation, ResolverOutcome
from comradbot.commands.general import build_health_embed
from comradbot.database.session import Database
from comradbot.services.observability import ObservabilityService


class FakeFFmpeg:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    def verify_tools(self) -> tuple[str, str]:
        if not self.available:
            raise RuntimeError("missing tools")
        return "ffmpeg", "ffprobe"


@pytest.mark.asyncio
async def test_health_snapshot_reports_metrics_and_dependencies() -> None:
    times = iter((100.0, 3761.9))
    database = SimpleNamespace(ping=AsyncMock(return_value=True))
    service = ObservabilityService(
        cast(Any, database),
        cast(Any, FakeFFmpeg()),
        lambda: 2,
        clock=lambda: next(times),
    )
    service.record_command_success()
    service.record_command_success()
    service.record_command_failure()
    service.record_resolver_result(ResolverOperation.RESOLVE, ResolverOutcome.SUCCESS, 40)
    service.record_resolver_result(ResolverOperation.RESOLVE, ResolverOutcome.TIMEOUT, 60)
    service.record_resolver_result(ResolverOperation.REFRESH, ResolverOutcome.FAILURE, 30)

    snapshot = await service.snapshot(discord_ready=True, latency_seconds=0.042)

    assert snapshot.healthy is True
    assert snapshot.uptime_seconds == 3661
    assert snapshot.latency_ms == 42
    assert snapshot.active_audio_players == 2
    assert snapshot.successful_commands == 2
    assert snapshot.failed_commands == 1
    assert snapshot.resolver_initial.successful == 1
    assert snapshot.resolver_initial.timed_out == 1
    assert snapshot.resolver_initial.average_latency_ms == 50
    assert snapshot.resolver_refresh.failed == 1
    assert snapshot.resolver_refresh.average_latency_ms == 30
    embed = build_health_embed(snapshot)
    assert "Healthy" in (embed.title or "")
    assert "1h 1m 1s" in str(embed.fields[1].value)
    assert "Initial" in str(embed.fields[3].value)


@pytest.mark.asyncio
async def test_health_snapshot_degrades_without_database_or_audio_tools() -> None:
    async def unavailable_database() -> bool:
        raise TimeoutError

    database = SimpleNamespace(ping=unavailable_database)
    service = ObservabilityService(
        cast(Any, database),
        cast(Any, FakeFFmpeg(available=False)),
        lambda: 0,
        clock=lambda: 10.0,
    )

    snapshot = await service.snapshot(discord_ready=True, latency_seconds=-1)

    assert snapshot.healthy is False
    assert snapshot.database_ready is False
    assert snapshot.audio_tools_ready is False
    assert snapshot.latency_ms == 0
    assert "Degraded" in (build_health_embed(snapshot).title or "")


@pytest.mark.asyncio
async def test_database_ping_uses_live_connection(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'health.db').as_posix()}")
    try:
        assert await database.ping() is True
    finally:
        await database.close()
