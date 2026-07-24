"""Container health-check entry point without external network calls."""

import asyncio
import sys

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from comradbot.audio.ffmpeg import FFmpegRunner
from comradbot.config import Settings
from comradbot.database.session import Database
from comradbot.services.heartbeat import heartbeat_is_fresh


async def check_health(settings: Settings) -> tuple[bool, tuple[str, ...]]:
    failures: list[str] = []
    if not heartbeat_is_fresh(
        settings.healthcheck_heartbeat_file,
        max_age_seconds=settings.healthcheck_max_age_seconds,
    ):
        failures.append("heartbeat")
    try:
        FFmpegRunner.verify_tools()
    except RuntimeError:
        failures.append("audio-tools")
    database = Database(
        settings.database_url,
        alembic_config_file=settings.alembic_config_file,
        alembic_directory=settings.alembic_directory,
    )
    try:
        if not await database.ping():
            failures.append("database")
    except (OSError, RuntimeError, SQLAlchemyError):
        failures.append("database")
    finally:
        await database.close()
    return not failures, tuple(failures)


def main() -> None:
    try:
        settings = Settings()
    except ValidationError:
        print("unhealthy: configuration", file=sys.stderr)
        raise SystemExit(1) from None
    healthy, failures = asyncio.run(check_health(settings))
    if not healthy:
        print(f"unhealthy: {','.join(failures)}", file=sys.stderr)
        raise SystemExit(1)
    print("healthy")


if __name__ == "__main__":
    main()
