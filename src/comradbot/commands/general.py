"""Small general commands used to verify bot health."""

import logging
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

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


def build_help_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🤝 ComradBot command guide",
        description=(
            "Use the slash commands below. Discord will show each command's parameters "
            "while you type."
        ),
        color=0xD13C3C,
    )
    embed.add_field(
        name="🎵 Music",
        value=(
            "`/music play` — search for or play a public URL\n"
            "`/music pause` · `/music resume` · `/music skip`\n"
            "`/music stop` · `/music disconnect`\n"
            "`/music queue` · `/music now`\n"
            "`/music volume` · `/music remove` · `/music clear`\n"
            "`/music playlist` — persistent server playlists"
        ),
        inline=False,
    )
    embed.add_field(
        name="🔊 Custom sounds",
        value=(
            "`/sound upload` · `/sound play` · `/sound random`\n"
            "`/sound list` · `/sound info`\n"
            "`/sound rename` · `/sound delete`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🤖 AI",
        value=(
            "`/ai ask` · `/ai reset` · `/ai speak`\n"
            "AI commands require `OPENAI_API_KEY`; audio features work without it."
        ),
        inline=False,
    )
    embed.add_field(
        name="Getting started",
        value=(
            "Join a voice channel before starting music or sounds. Use `/ping` to check "
            "whether the bot is responding."
        ),
        inline=False,
    )
    embed.set_footer(text="ComradBot — organized audio for the collective.")
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
        try:
            await message.reply(
                "At your service, comrade! Use `/help` to see everything I can do.",
                mention_author=False,
                allowed_mentions=discord.AllowedMentions.none(),
            )
        except discord.Forbidden:
            logger.warning(
                "Cannot reply to a bot mention because the channel denies message access"
            )
        except discord.HTTPException:
            logger.exception("Failed to reply to a bot mention")

    @app_commands.command(name="ping", description="Check whether ComradBot is responding.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Pong! `{round(interaction.client.latency * 1000)} ms`"
        )

    @app_commands.command(name="help", description="Show ComradBot's available commands.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_help_embed(), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(GeneralCog(cast(ComradBot, bot)))
