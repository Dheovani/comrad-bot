"""Thin Discord adapter for music services and the shared player."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands.helpers import (
    connect_player_to_user,
    ensure_same_voice_channel,
    format_duration,
    require_guild,
)
from comradbot.errors import AudioPlaybackError
from comradbot.ui.player import PlayerControls

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class MusicCog(commands.Cog):
    music = app_commands.Group(name="music", description="Music playback in a voice channel")

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @music.command(name="play", description="Search for music or play a public URL.")
    @app_commands.describe(query="Search text or public URL")
    async def play(self, interaction: discord.Interaction, query: str) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        item = await self.bot.audio_resolver.resolve(query, interaction.user.id)
        player = await self.bot.audio_manager.get_or_create(guild.id)
        await connect_player_to_user(interaction, player)
        position = await player.enqueue(item)
        embed = discord.Embed(title="🎵 Music queued", description=item.title, color=0xD13C3C)
        embed.add_field(name="Requested by", value=interaction.user.mention)
        embed.add_field(name="Duration", value=format_duration(item.duration_seconds))
        embed.add_field(name="Queue position", value=str(position))
        await interaction.followup.send(
            embed=embed, view=PlayerControls(self.bot.audio_manager, guild.id)
        )

    @music.command(name="pause", description="Pause the current audio.")
    async def pause(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.pause()
        await interaction.response.send_message("⏸️ Playback paused.")

    @music.command(name="resume", description="Resume paused audio.")
    async def resume(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.resume()
        await interaction.response.send_message("▶️ Playback resumed.")

    @music.command(name="skip", description="Skip the current audio item.")
    async def skip(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.skip()
        await interaction.response.send_message("⏭️ Current item skipped.")

    @music.command(name="stop", description="Stop playback and clear the queue.")
    async def stop(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        await player.stop()
        await interaction.response.send_message("⏹️ Playback stopped and queue cleared.")

    @music.command(name="queue", description="Show this server's audio queue.")
    async def queue(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None:
            await interaction.response.send_message("The queue is empty.")
            return
        items = await player.queue.snapshot()
        lines: list[str] = []
        if player.current:
            lines.append(f"**Now playing:** {player.current.title}")
        lines.extend(
            f"`{index}.` {item.title} — <@{item.requester_id}>"
            for index, item in enumerate(items[:20], 1)
        )
        if len(items) > 20:
            lines.append(f"*…and {len(items) - 20} more item(s).*")
        embed = discord.Embed(
            title="📋 ComradBot queue",
            description="\n".join(lines) or "The queue is empty.",
            color=0xD13C3C,
        )
        await interaction.response.send_message(embed=embed)

    @music.command(name="now", description="Show the current audio item.")
    async def now(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None or player.current is None:
            await interaction.response.send_message("Nothing is playing right now.")
            return
        item = player.current
        embed = discord.Embed(title="🎶 Now playing", description=item.title, color=0xD13C3C)
        embed.add_field(name="Type", value=item.item_type.value.replace("_", " ").title())
        embed.add_field(name="Requested by", value=f"<@{item.requester_id}>")
        embed.add_field(name="Duration", value=format_duration(item.duration_seconds))
        await interaction.response.send_message(embed=embed)

    @music.command(name="volume", description="Set playback volume from 0 to 100.")
    async def volume(
        self, interaction: discord.Interaction, value: app_commands.Range[int, 0, 100]
    ) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.set_volume(value / 100)
        await interaction.response.send_message(f"🔊 Volume set to **{value}%**.")

    @music.command(name="remove", description="Remove a queued item by its displayed position.")
    async def remove(
        self, interaction: discord.Interaction, position: app_commands.Range[int, 1, 1000]
    ) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        removed = await player.remove_queued(position)
        await interaction.response.send_message(f"🗑️ Removed **{removed.title}** from the queue.")

    @music.command(name="clear", description="Remove all queued items without stopping playback.")
    async def clear(self, interaction: discord.Interaction) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        removed_count = await player.clear_queue()
        await interaction.response.send_message(f"🧹 Removed **{removed_count}** queued item(s).")

    @music.command(name="disconnect", description="Stop playback and disconnect the bot.")
    async def disconnect(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        await self.bot.audio_manager.remove(guild.id)
        await interaction.response.send_message("👋 Disconnected from the voice channel.")

    def _player(self, interaction: discord.Interaction) -> GuildAudioPlayer:
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None:
            raise AudioPlaybackError("There is no active player in this server.")
        return player


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(MusicCog(cast(ComradBot, bot)))
