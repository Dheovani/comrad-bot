"""Administrative Discord adapter for persistent guild configuration."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.commands.helpers import require_guild
from comradbot.errors import PermissionDeniedError

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


def require_manage_guild(interaction: discord.Interaction) -> None:
    if not isinstance(interaction.user, discord.Member):
        raise PermissionDeniedError("Could not verify your server permissions.")
    if not interaction.user.guild_permissions.manage_guild:
        raise PermissionDeniedError("You need Manage Server permission to change bot settings.")


class SettingsCog(commands.Cog):
    guild_settings = app_commands.Group(
        name="settings",
        description="Manage persistent ComradBot settings for this server",
        guild_only=True,
        default_permissions=discord.Permissions(manage_guild=True),
    )

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @guild_settings.command(name="show", description="Show this server's persistent settings.")
    async def show(self, interaction: discord.Interaction) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        settings = await self.bot.guild_settings_service.get(guild.id)
        active_player = self.bot.audio_manager.get(guild.id)
        embed = discord.Embed(title="ComradBot server settings", color=0xD13C3C)
        embed.add_field(
            name="Default volume",
            value=f"{round(settings.default_volume * 100)}%",
            inline=True,
        )
        embed.add_field(
            name="AI features",
            value="Enabled" if settings.ai_enabled else "Disabled",
            inline=True,
        )
        if active_player is not None:
            embed.add_field(
                name="Current player volume",
                value=f"{round(active_player.volume * 100)}%",
                inline=False,
            )
        embed.set_footer(text="Settings are isolated to this Discord server.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @guild_settings.command(
        name="volume",
        description="Set the default playback volume for this server.",
    )
    async def volume(
        self,
        interaction: discord.Interaction,
        value: app_commands.Range[int, 0, 100],
    ) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        settings = await self.bot.guild_settings_service.set_default_volume(
            guild.id,
            value / 100,
        )
        active_player = self.bot.audio_manager.get(guild.id)
        if active_player is not None:
            active_player.set_volume(settings.default_volume)
        await interaction.response.send_message(
            f"🔊 Default server volume set to **{value}%**.",
            ephemeral=True,
        )

    @guild_settings.command(
        name="ai",
        description="Enable or disable AI features for this server.",
    )
    async def ai(self, interaction: discord.Interaction, enabled: bool) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        await self.bot.guild_settings_service.set_ai_enabled(guild.id, enabled)
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"🤖 AI features are now **{state}** for this server.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(SettingsCog(cast(ComradBot, bot)))
