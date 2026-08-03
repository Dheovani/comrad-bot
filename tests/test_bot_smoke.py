from pathlib import Path

import pytest
from discord import app_commands

from comradbot.bot import EXTENSIONS, ComradBot
from comradbot.config import Settings


@pytest.mark.asyncio
async def test_all_command_extensions_load_without_external_services(tmp_path: Path) -> None:
    bot = ComradBot(
        Settings(
            _env_file=None,
            discord_token="test-token",
            database_url=f"sqlite+aiosqlite:///{(tmp_path / 'bot.db').as_posix()}",
            data_directory=tmp_path,
            sounds_directory=tmp_path / "sounds",
        )
    )
    try:
        assert bot.intents.guild_messages is True
        assert bot.intents.message_content is False
        for extension in EXTENSIONS:
            await bot.load_extension(extension)

        assert {command.name for command in bot.tree.get_commands()} == {
            "ai",
            "health",
            "help",
            "music",
            "ping",
            "settings",
            "social",
            "sound",
        }
        social = bot.tree.get_command("social")
        assert isinstance(social, app_commands.Group)
        assert {command.name for command in social.commands} == {"poll"}
        settings = bot.tree.get_command("settings")
        assert isinstance(settings, app_commands.Group)
        assert {command.name for command in settings.commands} == {
            "ai",
            "ai-budget",
            "ai-memory",
            "feature",
            "show",
            "sounds",
            "volume",
        }
        assert settings.default_permissions.manage_guild is True
        ai = bot.tree.get_command("ai")
        assert isinstance(ai, app_commands.Group)
        assert {command.name for command in ai.commands} == {
            "ask",
            "discover",
            "reset",
            "speak",
            "status",
            "summarize",
            "transcribe",
            "usage",
        }
        music = bot.tree.get_command("music")
        assert isinstance(music, app_commands.Group)
        assert {command.name for command in music.commands} == {
            "clear",
            "disconnect",
            "now",
            "pause",
            "play",
            "playlist",
            "queue",
            "remove",
            "repeat",
            "resume",
            "skip",
            "stop",
            "volume",
        }
        playlist = music.get_command("playlist")
        assert isinstance(playlist, app_commands.Group)
        assert {command.name for command in playlist.commands} == {
            "add",
            "create",
            "delete",
            "list",
            "move",
            "play",
            "remove",
            "rename",
            "show",
        }
        for command_name, parameter_name in (
            ("add", "playlist_name"),
            ("delete", "name"),
            ("move", "name"),
            ("play", "name"),
            ("remove", "name"),
            ("rename", "name"),
            ("show", "name"),
        ):
            command = playlist.get_command(command_name)
            assert isinstance(command, app_commands.Command)
            parameter = next(
                parameter for parameter in command.parameters if parameter.name == parameter_name
            )
            assert parameter.autocomplete is True
        sound = bot.tree.get_command("sound")
        assert isinstance(sound, app_commands.Group)
        assert {command.name for command in sound.commands} == {
            "audit",
            "delete",
            "export",
            "info",
            "list",
            "metadata",
            "play",
            "random",
            "rename",
            "restore",
            "upload",
        }
        for command_name in ("delete", "info", "metadata", "play", "rename"):
            command = sound.get_command(command_name)
            assert isinstance(command, app_commands.Command)
            name_parameter = next(
                parameter for parameter in command.parameters if parameter.name == "name"
            )
            assert name_parameter.autocomplete is True
    finally:
        await bot.close()
