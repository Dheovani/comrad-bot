"""Small general commands used to verify bot health."""

import discord
from discord import app_commands
from discord.ext import commands


class GeneralCog(commands.Cog):
    @app_commands.command(name="ping", description="Verifica se o ComradBot está respondendo.")
    async def ping(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"Pong! `{round(interaction.client.latency * 1000)} ms`"
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(GeneralCog())
