"""Thin Discord adapter for music services and the shared player."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.audio.models import AudioItem, RepeatMode
from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands.helpers import (
    connect_player_to_user,
    ensure_same_voice_channel,
    format_duration,
    require_guild,
)
from comradbot.errors import AudioPlaybackError
from comradbot.services.music import PlaylistDetails
from comradbot.ui.player import PlayerControls

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


def build_queue_embed(
    current: AudioItem | None,
    items: list[AudioItem],
    repeat_mode: RepeatMode = RepeatMode.OFF,
) -> discord.Embed:
    lines: list[str] = []
    if current is not None:
        lines.append(f"**Now playing:** {current.title}")
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
    embed.set_footer(text=f"Repeat: {repeat_mode.value}")
    return embed


def build_playlist_embed(details: PlaylistDetails) -> discord.Embed:
    lines = [
        f"`{track.position}.` **{track.title}** — {format_duration(track.duration_seconds)}"
        for track in details.tracks[:20]
    ]
    if len(details.tracks) > 20:
        lines.append(f"*…and {len(details.tracks) - 20} more track(s).*")
    embed = discord.Embed(
        title=f"🎼 {details.playlist.name}",
        description="\n".join(lines) or "This playlist has no tracks.",
        color=0xD13C3C,
    )
    embed.add_field(name="Tracks", value=str(len(details.tracks)))
    embed.add_field(name="Created by", value=f"<@{details.playlist.creator_id}>")
    return embed


class MusicCog(commands.Cog):
    music = app_commands.Group(name="music", description="Music playback in a voice channel")
    playlist = app_commands.Group(
        name="playlist",
        description="Manage persistent server playlists",
        parent=music,
    )

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
        position = await player.enqueue(item, refresh_if_queued=True)
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
        await interaction.response.send_message(
            embed=build_queue_embed(player.current, items, player.repeat_mode)
        )

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
        embed.add_field(name="Repeat", value=player.repeat_mode.value.title())
        await interaction.response.send_message(embed=embed)

    @music.command(name="repeat", description="Set the repeat mode for this server's player.")
    @app_commands.describe(mode="Off, repeat the current item, or repeat the complete queue")
    async def repeat(self, interaction: discord.Interaction, mode: RepeatMode) -> None:
        player = self._player(interaction)
        ensure_same_voice_channel(interaction, player)
        player.set_repeat_mode(mode)
        messages = {
            RepeatMode.OFF: "➡️ Repeat disabled.",
            RepeatMode.TRACK: "🔂 Repeating the current audio item.",
            RepeatMode.QUEUE: "🔁 Repeating the complete queue.",
        }
        await interaction.response.send_message(messages[mode])

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

    @playlist.command(name="create", description="Create a persistent server playlist.")
    async def playlist_create(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        playlist = await self.bot.playlist_service.create(
            guild.id,
            name,
            interaction.user.id,
        )
        await interaction.response.send_message(
            f"✅ Playlist **{playlist.name}** created.", ephemeral=True
        )

    @playlist.command(name="add", description="Resolve and save a track to a playlist.")
    @app_commands.describe(playlist_name="Playlist name", query="Track name or public URL")
    @app_commands.rename(playlist_name="playlist")
    async def playlist_add(
        self,
        interaction: discord.Interaction,
        playlist_name: str,
        query: str,
    ) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(ephemeral=True, thinking=True)
        track = await self.bot.playlist_service.add_track(
            guild_id=guild.id,
            playlist_name=playlist_name,
            query=query,
            actor_id=interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.followup.send(
            f"✅ Added **{track.title}** at position **{track.position}**.",
            ephemeral=True,
        )

    @playlist_add.autocomplete("playlist_name")
    async def playlist_add_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="list", description="List this server's playlists.")
    async def playlist_list(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        playlists = await self.bot.playlist_service.list_playlists(guild.id)
        description = "\n".join(
            f"• **{details.playlist.name}** — {len(details.tracks)} track(s)"
            for details in playlists
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🎼 Server playlists",
                description=description or "This server has no playlists yet.",
                color=0xD13C3C,
            )
        )

    @playlist.command(name="show", description="Show the tracks in a playlist.")
    async def playlist_show(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        details = await self.bot.playlist_service.get(guild.id, name)
        await interaction.response.send_message(embed=build_playlist_embed(details))

    @playlist_show.autocomplete("name")
    async def playlist_show_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="play", description="Queue all available tracks from a playlist.")
    async def playlist_play(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        player = await self.bot.audio_manager.get_or_create(guild.id)
        await connect_player_to_user(interaction, player)
        result = await self.bot.playlist_service.enqueue(
            guild_id=guild.id,
            name=name,
            requester_id=interaction.user.id,
            player=player,
        )
        embed = discord.Embed(
            title="🎵 Playlist queued",
            description=result.playlist.name,
            color=0xD13C3C,
        )
        embed.add_field(name="Queued", value=str(result.queued_count))
        embed.add_field(name="Skipped or queue-limited", value=str(result.skipped_count))
        await interaction.followup.send(
            embed=embed,
            view=PlayerControls(self.bot.audio_manager, guild.id),
        )

    @playlist_play.autocomplete("name")
    async def playlist_play_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="remove", description="Remove a track from a playlist.")
    @app_commands.describe(name="Playlist name", position="Displayed track position")
    async def playlist_remove(
        self,
        interaction: discord.Interaction,
        name: str,
        position: app_commands.Range[int, 1, 500],
    ) -> None:
        guild = require_guild(interaction)
        track = await self.bot.playlist_service.remove_track(
            guild_id=guild.id,
            playlist_name=name,
            position=position,
            actor_id=interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"🗑️ Removed **{track.title}** from the playlist.",
            ephemeral=True,
        )

    @playlist_remove.autocomplete("name")
    async def playlist_remove_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="move", description="Move a track to another playlist position.")
    @app_commands.describe(
        name="Playlist name",
        from_position="Current displayed position",
        to_position="New displayed position",
    )
    async def playlist_move(
        self,
        interaction: discord.Interaction,
        name: str,
        from_position: app_commands.Range[int, 1, 500],
        to_position: app_commands.Range[int, 1, 500],
    ) -> None:
        guild = require_guild(interaction)
        track = await self.bot.playlist_service.move_track(
            guild_id=guild.id,
            playlist_name=name,
            from_position=from_position,
            to_position=to_position,
            actor_id=interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"↕️ Moved **{track.title}** to position **{to_position}**.",
            ephemeral=True,
        )

    @playlist_move.autocomplete("name")
    async def playlist_move_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="rename", description="Rename a playlist you manage.")
    @app_commands.describe(name="Current playlist name", new_name="New playlist name")
    @app_commands.rename(new_name="new-name")
    async def playlist_rename(
        self,
        interaction: discord.Interaction,
        name: str,
        new_name: str,
    ) -> None:
        guild = require_guild(interaction)
        playlist = await self.bot.playlist_service.rename(
            guild_id=guild.id,
            name=name,
            new_name=new_name,
            actor_id=interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"✏️ Playlist renamed to **{playlist.name}**.",
            ephemeral=True,
        )

    @playlist_rename.autocomplete("name")
    async def playlist_rename_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    @playlist.command(name="delete", description="Delete a playlist you manage.")
    async def playlist_delete(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        playlist = await self.bot.playlist_service.delete(
            guild_id=guild.id,
            name=name,
            actor_id=interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"🗑️ Playlist **{playlist.name}** deleted.",
            ephemeral=True,
        )

    @playlist_delete.autocomplete("name")
    async def playlist_delete_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._playlist_choices(interaction, current)

    def _player(self, interaction: discord.Interaction) -> GuildAudioPlayer:
        guild = require_guild(interaction)
        player = self.bot.audio_manager.get(guild.id)
        if player is None:
            raise AudioPlaybackError("There is no active player in this server.")
        return player

    async def _playlist_choices(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        playlists = await self.bot.playlist_service.search(interaction.guild_id, current)
        return [
            app_commands.Choice(name=playlist.name, value=playlist.name) for playlist in playlists
        ]

    @staticmethod
    def _is_moderator(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and (
            interaction.user.guild_permissions.manage_messages
            or interaction.user.guild_permissions.manage_guild
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(MusicCog(cast(ComradBot, bot)))
