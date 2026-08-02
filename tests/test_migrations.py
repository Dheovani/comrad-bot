import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

from alembic import command
from comradbot.database.migrations import BASELINE_COLUMNS, BASELINE_TABLES
from comradbot.database.models import Base, GuildSettings
from comradbot.database.session import Database
from comradbot.errors import DatabaseMigrationError


def test_alembic_upgrade_builds_current_schema(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "migrated.db"
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )

    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        sound_columns = {row[1] for row in connection.execute("PRAGMA table_info(custom_sounds)")}
        settings_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(guild_settings)")
        }
    assert {
        "ai_conversations",
        "ai_usage",
        "alembic_version",
        "custom_sounds",
        "guild_settings",
        "playlists",
        "saved_tracks",
        "sound_audit_logs",
    } <= tables
    assert {"category", "tags_json"} <= sound_columns
    assert {
        "max_sound_count",
        "max_sound_storage_mb",
        "ai_conversation_scope",
        "ai_retention_days",
    } <= settings_columns


def test_ai_policy_migration_preserves_existing_channel_conversations(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    database_path = tmp_path / "policy-upgrade.db"
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        f"sqlite+aiosqlite:///{database_path.as_posix()}",
    )
    command.upgrade(config, "0005")
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO ai_conversations (guild_id, scope_id, messages_json) VALUES (?, ?, ?)",
            (123, 456, "[]"),
        )
    command.upgrade(config, "head")

    with sqlite3.connect(database_path) as connection:
        conversation = connection.execute(
            "SELECT guild_id, scope_type, scope_id, messages_json FROM ai_conversations"
        ).fetchone()
    assert conversation == (123, "channel", 456, "[]")


@pytest.mark.asyncio
async def test_startup_migration_upgrades_fresh_database(tmp_path: Path) -> None:
    database_path = tmp_path / "startup.db"
    database = Database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    try:
        await database.migrate()
    finally:
        await database.close()

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert revision == ("0006",)


@pytest.mark.asyncio
async def test_startup_migration_adopts_complete_legacy_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-current.db"
    database = Database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with database.sessions.begin() as session:
        session.add(GuildSettings(guild_id=123, default_volume=0.7, ai_enabled=False))
    try:
        await database.migrate()
    finally:
        await database.close()

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        settings = connection.execute(
            "SELECT default_volume, ai_enabled FROM guild_settings WHERE guild_id = 123"
        ).fetchone()
    assert revision == ("0006",)
    assert settings == (0.7, 0)


@pytest.mark.asyncio
async def test_startup_migration_adopts_versioned_hybrid_legacy_schema(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-hybrid.db"
    database = Database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.exec_driver_sql(
            "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
        )
        await connection.exec_driver_sql(
            "INSERT INTO alembic_version (version_num) VALUES ('0001')"
        )
    try:
        await database.migrate()
    finally:
        await database.close()

    with sqlite3.connect(database_path) as connection:
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert revision == ("0006",)


@pytest.mark.asyncio
async def test_startup_migration_upgrades_known_legacy_baseline(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy-baseline.db"
    database = Database(f"sqlite+aiosqlite:///{database_path.as_posix()}")
    async with database.engine.begin() as connection:
        for table_name in sorted(BASELINE_TABLES):
            columns = BASELINE_COLUMNS[table_name]
            definitions = ", ".join(
                f"{column} INTEGER" if column == "id" else f"{column} TEXT" for column in columns
            )
            await connection.exec_driver_sql(f"CREATE TABLE {table_name} ({definitions})")
    try:
        await database.migrate()
    finally:
        await database.close()

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        revision = connection.execute("SELECT version_num FROM alembic_version").fetchone()
    assert {"playlists", "saved_tracks"} <= tables
    assert revision == ("0006",)


@pytest.mark.asyncio
async def test_startup_migration_rejects_partial_unversioned_schema(tmp_path: Path) -> None:
    database = Database(f"sqlite+aiosqlite:///{(tmp_path / 'partial.db').as_posix()}")
    async with database.engine.begin() as connection:
        await connection.run_sync(
            lambda sync_connection: Base.metadata.create_all(
                sync_connection,
                tables=[Base.metadata.tables["guild_settings"]],
            )
        )
    try:
        with pytest.raises(DatabaseMigrationError, match="unversioned partial schema"):
            await database.migrate()
    finally:
        await database.close()
