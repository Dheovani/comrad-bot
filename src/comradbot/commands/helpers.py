"""Discord-specific interaction validation kept out of business services."""

from typing import cast

import discord

from comradbot.audio.player import GuildAudioPlayer
from comradbot.errors import PermissionDeniedError, VoiceConnectionError


def can_control_guild_audio(
    *,
    user_channel_id: int | None,
    bot_channel_id: int | None,
    can_move_members: bool,
) -> bool:
    """Return whether a member may mutate the guild audio player."""
    if user_channel_id is None:
        return False
    return bot_channel_id is None or user_channel_id == bot_channel_id or can_move_members


def require_guild(interaction: discord.Interaction) -> discord.Guild:
    if interaction.guild is None:
        raise VoiceConnectionError("This command can only be used in a server.")
    return interaction.guild


def user_voice_channel(
    interaction: discord.Interaction,
) -> discord.VoiceChannel | discord.StageChannel:
    if not isinstance(interaction.user, discord.Member):
        raise VoiceConnectionError("Your voice channel could not be identified.")
    voice = interaction.user.voice
    if voice is None or voice.channel is None:
        raise VoiceConnectionError("Join a voice channel before using this command.")
    return voice.channel


async def connect_player_to_user(
    interaction: discord.Interaction, player: GuildAudioPlayer
) -> None:
    guild = require_guild(interaction)
    channel = user_voice_channel(interaction)
    current = guild.voice_client
    if current is None:
        connected: discord.VoiceProtocol = await channel.connect()
        await player.set_voice_client(cast(discord.VoiceClient, connected))
        return
    voice = cast(discord.VoiceClient, current)
    if voice.channel != channel:
        member = cast(discord.Member, interaction.user)
        if not member.guild_permissions.move_members:
            raise PermissionDeniedError(
                "The bot is in another channel. You need Move Members permission to control it."
            )
        await voice.move_to(channel)
    await player.set_voice_client(voice)


def ensure_same_voice_channel(interaction: discord.Interaction, player: GuildAudioPlayer) -> None:
    channel = user_voice_channel(interaction)
    voice = player.voice_client
    member = cast(discord.Member, interaction.user)
    bot_channel_id = voice.channel.id if voice is not None else None
    if can_control_guild_audio(
        user_channel_id=channel.id,
        bot_channel_id=bot_channel_id,
        can_move_members=member.guild_permissions.move_members,
    ):
        return
    raise PermissionDeniedError("You must be in the same voice channel as the bot.")


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "unknown/live"
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"
