"""Thin Discord adapter for music services and the shared player."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.commands.helpers import (
    connect_player_to_user,
    ensure_same_voice_channel,
    format_duration,
    require_guild,
)
from comradbot.ui.player import PlayerControls

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class MusicCog(commands.Cog):
    music = app_commands.Group(name="music", description="Música no canal de voz")

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @music.command(name="play", description="Busca uma música ou usa uma URL pública.")
    @app_commands.describe(query="Texto da busca ou URL pública")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        item = await self.bot.audio_resolver.resolve(query, interaction.user.id)
        player = await self.bot.audio_manager.get_or_create(guild.id)
        await connect_player_to_user(interaction, player)
        position = await player.enqueue(item)
        embed = discord.Embed(title="🎵 Música adicionada", description=item.title, color=0xD13C3C)
        embed.add_field(name="Solicitante", value=interaction.user.mention)
        embed.add_field(name="Duração", value=format_duration(item.duration_seconds))
        embed.add_field(name="Posição", value=str(position))
        await interaction.followup.send(
            embed=embed, view=PlayerControls(self.bot.audio_manager, guild.id)
        )

    @music.command(name="pause", description="Pausa a reprodução atual.")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.pause()
        await interaction.response.send_message("⏸️ Reprodução pausada.")

    @music.command(name="resume", description="Continua a reprodução pausada.")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.resume()
        await interaction.response.send_message("▶️ Reprodução retomada.")

    @music.command(name="skip", description="Pula o item atual.")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.skip()
        await interaction.response.send_message("⏭️ Item pulado.")

    @music.command(name="stop", description="Para a reprodução e limpa a fila.")
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        await player.stop()
        await interaction.response.send_message("⏹️ Reprodução parada e fila limpa.")

    @music.command(name="queue", description="Exibe a fila deste servidor.")
    async def queue(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None:
            await interaction.response.send_message("A fila está vazia.")
            return
        items = await player.queue.snapshot()
        lines = []
        if player.current:
            lines.append(f"**Tocando:** {player.current.title}")
        lines.extend(
            f"`{index}.` {item.title} — <@{item.requester_id}>"
            for index, item in enumerate(items, 1)
        )
        embed = discord.Embed(
            title="📋 Fila do ComradBot",
            description="\n".join(lines) or "A fila está vazia.",
            color=0xD13C3C,
        )
        await interaction.response.send_message(embed=embed)

    def _player(self, interaction: discord.Interaction):  # type: ignore[no-untyped-def]
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None:
            from comradbot.errors import AudioPlaybackError

            raise AudioPlaybackError("Não há player ativo neste servidor.")
        return player


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(MusicCog(cast(ComradBot, bot)))
