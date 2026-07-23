from pathlib import Path

import pytest
from discord import app_commands

from comradbot.bot import EXTENSIONS, ComradBot
from comradbot.config import Settings


@pytest.mark.asyncio
async def test_all_command_extensions_load_without_external_services(tmp_path: Path) -> None:
    bot = ComradBot(
        Settings(
            discord_token="test-token",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'bot.db').as_posix()}",
            data_directory=tmp_path,
            sounds_directory=tmp_path / "sounds",
        )
    )
    try:
        for extension in EXTENSIONS:
            await bot.load_extension(extension)

        assert {command.name for command in bot.tree.get_commands()} == {
            "ai",
            "music",
            "ping",
            "sound",
        }
        music = bot.tree.get_command("music")
        assert isinstance(music, app_commands.Group)
        assert {command.name for command in music.commands} == {
            "clear",
            "disconnect",
            "now",
            "pause",
            "play",
            "queue",
            "remove",
            "resume",
            "skip",
            "stop",
            "volume",
        }
    finally:
        await bot.close()
