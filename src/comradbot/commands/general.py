"""Small general commands used to verify bot health."""

import logging
import re
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.errors import ComradBotError
from comradbot.localization import Localizer, default_localizer
from comradbot.services.observability import HealthSnapshot
from comradbot.utils.text import split_message

if TYPE_CHECKING:
    from comradbot.bot import ComradBot

logger = logging.getLogger(__name__)


def should_respond_to_mention(
    *,
    author_is_bot: bool,
    mentioned_user_ids: set[int],
    bot_user_id: int,
) -> bool:
    return not author_is_bot and bot_user_id in mentioned_user_ids


def extract_mention_prompt(content: str, bot_user_id: int) -> str:
    without_bot = re.sub(rf"<@!?{bot_user_id}>", "", content)
    sanitized = re.sub(r"<@!?\d+>", "@member", without_bot)
    sanitized = re.sub(r"<@&\d+>", "@role", sanitized)
    sanitized = re.sub(r"<#\d+>", "#channel", sanitized).strip()
    return sanitized or (
        "Você foi chamado por um usuário sem uma pergunta específica. "
        "Cumprimente-o brevemente e pergunte como pode ajudar."
    )


def build_help_embed(
    localizer: Localizer | None = None,
    locale: discord.Locale | str | None = None,
) -> discord.Embed:
    localizer = localizer or default_localizer()
    embed = discord.Embed(
        title=localizer.text("help.title", locale),
        description=localizer.text("help.description", locale),
        color=0xD13C3C,
    )
    embed.add_field(
        name=localizer.text("help.music.name", locale),
        value=localizer.text("help.music.value", locale),
        inline=False,
    )
    embed.add_field(
        name=localizer.text("help.sounds.name", locale),
        value=localizer.text("help.sounds.value", locale),
        inline=False,
    )
    embed.add_field(
        name=localizer.text("help.ai.name", locale),
        value=localizer.text("help.ai.value", locale),
        inline=False,
    )
    embed.add_field(
        name=localizer.text("help.start.name", locale),
        value=localizer.text("help.start.value", locale),
        inline=False,
    )
    embed.add_field(
        name=localizer.text("help.settings.name", locale),
        value=localizer.text("help.settings.value", locale),
        inline=False,
    )
    embed.add_field(
        name=localizer.text("help.social.name", locale),
        value=localizer.text("help.social.value", locale),
        inline=False,
    )
    embed.set_footer(text=localizer.text("help.footer", locale))
    return embed


def build_health_embed(snapshot: HealthSnapshot) -> discord.Embed:
    status = "Healthy" if snapshot.healthy else "Degraded"
    color = 0x3BA55D if snapshot.healthy else 0xFAA61A
    uptime_hours, remainder = divmod(snapshot.uptime_seconds, 3600)
    uptime_minutes, uptime_seconds = divmod(remainder, 60)
    embed = discord.Embed(title=f"ComradBot health — {status}", color=color)
    embed.add_field(
        name="Dependencies",
        value=(
            f"Discord: {'ready' if snapshot.discord_ready else 'unavailable'}\n"
            f"Database: {'ready' if snapshot.database_ready else 'unavailable'}\n"
            f"FFmpeg/FFprobe: {'ready' if snapshot.audio_tools_ready else 'unavailable'}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Runtime",
        value=(
            f"Latency: {snapshot.latency_ms} ms\n"
            f"Uptime: {uptime_hours}h {uptime_minutes}m {uptime_seconds}s\n"
            f"Active audio players: {snapshot.active_audio_players}"
        ),
        inline=True,
    )
    embed.add_field(
        name="Slash commands since startup",
        value=(f"Successful: {snapshot.successful_commands}\nFailed: {snapshot.failed_commands}"),
        inline=False,
    )
    embed.add_field(
        name="Music resolver since startup",
        value=(
            "Initial — "
            f"successful: {snapshot.resolver_initial.successful}, "
            f"failed: {snapshot.resolver_initial.failed}, "
            f"timed out: {snapshot.resolver_initial.timed_out}, "
            f"average: {snapshot.resolver_initial.average_latency_ms} ms\n"
            "Refresh — "
            f"successful: {snapshot.resolver_refresh.successful}, "
            f"failed: {snapshot.resolver_refresh.failed}, "
            f"timed out: {snapshot.resolver_refresh.timed_out}, "
            f"average: {snapshot.resolver_refresh.average_latency_ms} ms"
        ),
        inline=False,
    )
    embed.set_footer(text="In-memory counters reset whenever the bot restarts.")
    return embed


class GeneralCog(commands.Cog):
    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        bot_user = self.bot.user
        if (
            not self.bot.settings.discord_respond_to_mentions
            or message.guild is None
            or bot_user is None
            or not should_respond_to_mention(
                author_is_bot=message.author.bot,
                mentioned_user_ids={user.id for user in message.mentions},
                bot_user_id=bot_user.id,
            )
        ):
            return
        prompt = extract_mention_prompt(message.content, bot_user.id)
        try:
            async with message.channel.typing():
                response = await self.bot.ai_service.ask(
                    guild_id=message.guild.id,
                    channel_id=message.channel.id,
                    user_id=message.author.id,
                    prompt=prompt,
                )
            chunks = split_message(
                response,
                self.bot.settings.max_ai_response_characters,
            )
        except ComradBotError as exc:
            logger.info(
                "Expected mention conversation failure type=%s guild=%s user=%s",
                type(exc).__name__,
                message.guild.id,
                message.author.id,
            )
            chunks = [f"⚠️ {exc}"]
        except discord.Forbidden:
            logger.warning(
                "Cannot reply to a bot mention because the channel denies message access"
            )
            return
        except discord.HTTPException:
            logger.exception("Discord failed while preparing a mention conversation response")
            return
        except Exception:
            logger.exception(
                "Unexpected mention conversation failure guild=%s user=%s",
                message.guild.id,
                message.author.id,
            )
            chunks = [self.bot.localizer.text("error.unexpected")]

        try:
            await message.reply(
                chunks[0],
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            for chunk in chunks[1:]:
                await message.channel.send(
                    chunk,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        except discord.Forbidden:
            logger.warning(
                "Cannot reply to a bot mention because the channel denies message access"
            )
        except discord.HTTPException:
            logger.exception("Failed to send a mention conversation response")

    @app_commands.command(name="ping", description="Check whether ComradBot is responding.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Pong! `{round(interaction.client.latency * 1000)} ms`"
        )

    @app_commands.command(name="health", description="Show dependency health and runtime metrics.")
    async def health(self, interaction: discord.Interaction) -> None:
        snapshot = await self.bot.observability.snapshot(
            discord_ready=self.bot.is_ready(),
            latency_seconds=self.bot.latency,
        )
        await interaction.response.send_message(
            embed=build_health_embed(snapshot),
            ephemeral=True,
        )

    @app_commands.command(name="help", description="Show ComradBot's available commands.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            embed=build_help_embed(self.bot.localizer, interaction.locale),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(GeneralCog(cast(ComradBot, bot)))
