import sqlite3
from pathlib import Path

from alembic.config import Config

from alembic import command


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
    assert {
        "ai_conversations",
        "ai_usage",
        "alembic_version",
        "custom_sounds",
        "guild_settings",
        "playlists",
        "saved_tracks",
    } <= tables
