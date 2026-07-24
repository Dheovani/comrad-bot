"""Async database engine and session lifecycle."""

from pathlib import Path
from typing import cast

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from comradbot.database.migrations import MigrationRunner


class Database:
    def __init__(
        self,
        url: str,
        *,
        alembic_config_file: Path = Path("./alembic.ini"),
        alembic_directory: Path = Path("./alembic"),
    ) -> None:
        self._url = url
        self._alembic_config_file = alembic_config_file
        self._alembic_directory = alembic_directory
        self.engine: AsyncEngine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def migrate(self) -> None:
        """Upgrade the database through Alembic without blocking the event loop."""
        await MigrationRunner(
            self.engine,
            self._url,
            config_file=self._alembic_config_file,
            script_directory=self._alembic_directory,
        ).upgrade()

    async def close(self) -> None:
        await self.engine.dispose()

    async def ping(self) -> bool:
        async with self.engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return cast(int, result.scalar_one()) == 1

    def session(self) -> AsyncSession:
        return self.sessions()
