"""Small general commands used to verify bot health."""

import discord
from discord import app_commands
from discord.ext import commands


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
    @app_commands.command(name="ping", description="Check whether ComradBot is responding.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Pong! `{round(interaction.client.latency * 1000)} ms`"
        )

    @app_commands.command(name="help", description="Show ComradBot's available commands.")
    async def help_command(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_help_embed(), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog())
