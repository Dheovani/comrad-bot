"""Bounded in-process metrics and dependency health checks."""

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.exc import SQLAlchemyError

from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.audio.resolver import ResolverOperation, ResolverOutcome
from comradbot.database.session import Database


@dataclass(frozen=True, slots=True)
class ResolverStats:
    successful: int
    failed: int
    timed_out: int
    average_latency_ms: int


@dataclass(frozen=True, slots=True)
class HealthSnapshot:
    discord_ready: bool
    database_ready: bool
    audio_tools_ready: bool
    latency_ms: int
    uptime_seconds: int
    active_audio_players: int
    successful_commands: int
    failed_commands: int
    resolver_initial: ResolverStats
    resolver_refresh: ResolverStats

    @property
    def healthy(self) -> bool:
        return self.discord_ready and self.database_ready and self.audio_tools_ready


class ObservabilityService:
    def __init__(
        self,
        database: Database,
        ffmpeg: FFmpegRunner,
        active_player_count: Callable[[], int],
        *,
        health_timeout_seconds: float = 2.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._database = database
        self._ffmpeg = ffmpeg
        self._active_player_count = active_player_count
        self._health_timeout = health_timeout_seconds
        self._clock = clock
        self._started_at = clock()
        self._successful_commands = 0
        self._failed_commands = 0
        self._resolver_counts = {
            operation: {outcome: 0 for outcome in ResolverOutcome}
            for operation in ResolverOperation
        }
        self._resolver_latency_totals = {operation: 0 for operation in ResolverOperation}

    def record_command_success(self) -> None:
        self._successful_commands += 1

    def record_command_failure(self) -> None:
        self._failed_commands += 1

    def record_resolver_result(
        self,
        operation: ResolverOperation,
        outcome: ResolverOutcome,
        latency_ms: int,
    ) -> None:
        self._resolver_counts[operation][outcome] += 1
        self._resolver_latency_totals[operation] += max(0, latency_ms)

    async def snapshot(self, *, discord_ready: bool, latency_seconds: float) -> HealthSnapshot:
        database_ready = await self._database_ready()
        try:
            self._ffmpeg.verify_tools()
            audio_tools_ready = True
        except RuntimeError:
            audio_tools_ready = False
        return HealthSnapshot(
            discord_ready=discord_ready,
            database_ready=database_ready,
            audio_tools_ready=audio_tools_ready,
            latency_ms=max(0, round(latency_seconds * 1000)),
            uptime_seconds=max(0, int(self._clock() - self._started_at)),
            active_audio_players=self._active_player_count(),
            successful_commands=self._successful_commands,
            failed_commands=self._failed_commands,
            resolver_initial=self._resolver_stats(ResolverOperation.RESOLVE),
            resolver_refresh=self._resolver_stats(ResolverOperation.REFRESH),
        )

    def _resolver_stats(self, operation: ResolverOperation) -> ResolverStats:
        counts = self._resolver_counts[operation]
        total = sum(counts.values())
        return ResolverStats(
            successful=counts[ResolverOutcome.SUCCESS],
            failed=counts[ResolverOutcome.FAILURE],
            timed_out=counts[ResolverOutcome.TIMEOUT],
            average_latency_ms=(
                round(self._resolver_latency_totals[operation] / total) if total else 0
            ),
        )

    async def _database_ready(self) -> bool:
        try:
            return await asyncio.wait_for(
                self._database.ping(),
                timeout=self._health_timeout,
            )
        except (TimeoutError, OSError, SQLAlchemyError):
            return False
