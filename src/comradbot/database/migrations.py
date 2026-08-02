"""Controlled Alembic startup migrations and legacy development-schema adoption."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from alembic import command
from comradbot.database.models import Base
from comradbot.errors import DatabaseMigrationError

ALEMBIC_VERSION_TABLE = "alembic_version"
BASELINE_REVISION = "0001"
BASELINE_TABLES = {
    "ai_conversations",
    "ai_usage",
    "custom_sounds",
    "guild_settings",
}
BASELINE_COLUMNS = {
    "guild_settings": frozenset(
        {"guild_id", "default_volume", "ai_enabled", "created_at", "updated_at"}
    ),
    "custom_sounds": frozenset(
        {
            "id",
            "guild_id",
            "name",
            "normalized_name",
            "relative_path",
            "creator_id",
            "created_at",
            "duration_seconds",
            "size_bytes",
            "format",
            "play_count",
        }
    ),
    "ai_conversations": frozenset({"id", "guild_id", "scope_id", "messages_json", "updated_at"}),
    "ai_usage": frozenset(
        {
            "id",
            "guild_id",
            "user_id",
            "operation",
            "input_characters",
            "output_characters",
            "success",
            "created_at",
        }
    ),
}


@dataclass(frozen=True, slots=True)
class SchemaState:
    tables: frozenset[str]
    columns: dict[str, frozenset[str]]
    revision: str | None


class MigrationRunner:
    def __init__(
        self,
        engine: AsyncEngine,
        database_url: str,
        *,
        config_file: Path = Path("./alembic.ini"),
        script_directory: Path = Path("./alembic"),
    ) -> None:
        self._engine = engine
        self._database_url = database_url
        self._config_file = config_file.resolve()
        self._script_directory = script_directory.resolve()

    async def upgrade(self) -> None:
        state = await self._inspect_schema()
        await asyncio.to_thread(self._upgrade_sync, state)

    async def _inspect_schema(self) -> SchemaState:
        async with self._engine.connect() as connection:
            return await connection.run_sync(self._inspect_sync)

    @staticmethod
    def _inspect_sync(connection: Connection) -> SchemaState:
        inspector = inspect(connection)
        tables = frozenset(inspector.get_table_names())
        columns = {
            table: frozenset(column["name"] for column in inspector.get_columns(table))
            for table in tables
        }
        revision = None
        if ALEMBIC_VERSION_TABLE in tables:
            revision = connection.execute(
                text(f"SELECT version_num FROM {ALEMBIC_VERSION_TABLE}")
            ).scalar_one_or_none()
        return SchemaState(tables=tables, columns=columns, revision=revision)

    def _upgrade_sync(self, state: SchemaState) -> None:
        config = self._config()
        application_tables = self._application_tables(state)
        current_tables = frozenset(Base.metadata.tables)
        if state.revision is not None:
            if state.revision == BASELINE_REVISION and application_tables == current_tables:
                self._validate_known_columns(state, current_tables)
                command.stamp(config, "head")
                return
            command.upgrade(config, "head")
            return
        if not application_tables:
            command.upgrade(config, "head")
            return

        if application_tables == current_tables:
            self._validate_known_columns(state, current_tables)
            command.stamp(config, "head")
            return
        if application_tables == BASELINE_TABLES:
            self._validate_columns(state, BASELINE_COLUMNS)
            command.stamp(config, BASELINE_REVISION)
            command.upgrade(config, "head")
            return
        raise DatabaseMigrationError(
            "The database has an unversioned partial schema. Back it up, then reconcile it "
            "with Alembic before starting ComradBot."
        )

    @staticmethod
    def _application_tables(state: SchemaState) -> frozenset[str]:
        return state.tables & frozenset(Base.metadata.tables)

    @staticmethod
    def _validate_known_columns(state: SchemaState, tables: frozenset[str]) -> None:
        expected_columns = {
            table: frozenset(Base.metadata.tables[table].columns.keys()) for table in tables
        }
        MigrationRunner._validate_columns(state, expected_columns)

    @staticmethod
    def _validate_columns(
        state: SchemaState,
        expected_columns: dict[str, frozenset[str]],
    ) -> None:
        for table, expected in expected_columns.items():
            if state.columns.get(table) != expected:
                raise DatabaseMigrationError(
                    f"The unversioned database table '{table}' does not match the known schema. "
                    "Back up and reconcile the database before starting ComradBot."
                )

    def _config(self) -> Config:
        config = Config(self._config_file)
        config.set_main_option("script_location", str(self._script_directory))
        config.set_main_option("sqlalchemy.url", self._database_url.replace("%", "%%"))
        config.attributes["configure_logger"] = False
        return config
