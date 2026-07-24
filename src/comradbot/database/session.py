"""Async database engine and session lifecycle."""

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
    def __init__(self, url: str) -> None:
        self._url = url
        self.engine: AsyncEngine = create_async_engine(url)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def migrate(self) -> None:
        """Upgrade the database through Alembic without blocking the event loop."""
        await MigrationRunner(self.engine, self._url).upgrade()

    async def close(self) -> None:
        await self.engine.dispose()

    async def ping(self) -> bool:
        async with self.engine.connect() as connection:
            result = await connection.execute(text("SELECT 1"))
            return cast(int, result.scalar_one()) == 1

    def session(self) -> AsyncSession:
        return self.sessions()
