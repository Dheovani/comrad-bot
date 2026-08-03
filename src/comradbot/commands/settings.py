"""Administrative Discord adapter for persistent guild configuration."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.ai.policy import ConversationScope
from comradbot.commands.helpers import require_guild
from comradbot.errors import PermissionDeniedError
from comradbot.services.settings import GuildFeature

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
        embed.add_field(
            name="AI conversation memory",
            value=(
                f"Scope: {settings.ai_conversation_scope.value}\n"
                f"Retention: {settings.ai_retention_days} day(s)"
            ),
            inline=True,
        )
        embed.add_field(
            name="Command groups",
            value="\n".join(
                f"{feature.value}: "
                f"{'Disabled' if feature in settings.disabled_features else 'Enabled'}"
                for feature in (GuildFeature.MUSIC, GuildFeature.SOUNDS, GuildFeature.SOCIAL)
            ),
            inline=True,
        )
        embed.add_field(
            name="Daily AI request budget",
            value=(
                "Unlimited"
                if settings.ai_daily_request_budget == 0
                else str(settings.ai_daily_request_budget)
            ),
            inline=True,
        )
        embed.add_field(
            name="Custom sound quotas",
            value=(
                f"Count: {settings.max_sound_count}\nStorage: {settings.max_sound_storage_mb} MiB"
            ),
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

    @guild_settings.command(
        name="feature",
        description="Enable or disable a command group for this server.",
    )
    async def feature(
        self,
        interaction: discord.Interaction,
        feature: GuildFeature,
        enabled: bool,
    ) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        await self.bot.guild_settings_service.set_feature_enabled(guild.id, feature, enabled)
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(
            f"The **{feature.value}** command group is now **{state}** for this server.",
            ephemeral=True,
        )

    @guild_settings.command(
        name="ai-memory",
        description="Set AI conversation scope and retention for this server.",
    )
    @app_commands.rename(retention_days="retention-days")
    async def ai_memory(
        self,
        interaction: discord.Interaction,
        scope: ConversationScope,
        retention_days: app_commands.Range[int, 1, 365] = 30,
    ) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        settings = await self.bot.guild_settings_service.set_ai_conversation_policy(
            guild.id,
            scope=scope,
            retention_days=retention_days,
        )
        await self.bot.ai_service.reset_guild(guild.id)
        await interaction.response.send_message(
            "🧠 AI conversation policy updated to "
            f"**{settings.ai_conversation_scope.value}** scope with "
            f"**{settings.ai_retention_days} day(s)** retention. "
            "Previous conversation memory was removed.",
            ephemeral=True,
        )

    @guild_settings.command(
        name="ai-budget",
        description="Set the daily UTC AI request budget for this server.",
    )
    @app_commands.describe(daily_requests="0 disables the daily budget")
    @app_commands.rename(daily_requests="daily-requests")
    async def ai_budget(
        self,
        interaction: discord.Interaction,
        daily_requests: app_commands.Range[int, 0, 10000],
    ) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        settings = await self.bot.guild_settings_service.set_ai_daily_request_budget(
            guild.id,
            daily_requests,
        )
        value = (
            "unlimited"
            if settings.ai_daily_request_budget == 0
            else f"{settings.ai_daily_request_budget} request(s)"
        )
        await interaction.response.send_message(
            f"📊 Daily AI budget set to **{value}**; the window resets at 00:00 UTC.",
            ephemeral=True,
        )

    @guild_settings.command(
        name="sounds",
        description="Set custom sound count and storage quotas for this server.",
    )
    @app_commands.describe(max_count="Maximum saved sounds", storage_mb="Maximum Opus storage")
    @app_commands.rename(max_count="max-count", storage_mb="storage-mb")
    async def sounds(
        self,
        interaction: discord.Interaction,
        max_count: app_commands.Range[int, 1, 10000],
        storage_mb: app_commands.Range[int, 1, 100000],
    ) -> None:
        require_manage_guild(interaction)
        guild = require_guild(interaction)
        settings = await self.bot.guild_settings_service.set_sound_quotas(
            guild.id,
            max_count=max_count,
            max_storage_mb=storage_mb,
        )
        await interaction.response.send_message(
            "🔊 Custom sound quotas set to "
            f"**{settings.max_sound_count} sounds** and "
            f"**{settings.max_sound_storage_mb} MiB**.",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(SettingsCog(cast(ComradBot, bot)))
