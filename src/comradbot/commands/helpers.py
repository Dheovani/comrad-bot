"""Discord-specific interaction validation kept out of business services."""

from typing import cast

import discord

from comradbot.audio.player import GuildAudioPlayer
from comradbot.errors import PermissionDeniedError, VoiceConnectionError


def require_guild(interaction: discord.Interaction) -> discord.Guild:
    if interaction.guild is None:
        raise VoiceConnectionError("Este comando só pode ser usado em um servidor.")
    return interaction.guild


def user_voice_channel(
    interaction: discord.Interaction,
) -> discord.VoiceChannel | discord.StageChannel:
    if not isinstance(interaction.user, discord.Member):
        raise VoiceConnectionError("Não foi possível identificar seu canal de voz.")
    voice = interaction.user.voice
    if voice is None or voice.channel is None:
        raise VoiceConnectionError("Entre em um canal de voz antes de usar este comando.")
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
                "O bot está em outro canal. É preciso a permissão Mover membros para controlá-lo."
            )
        await voice.move_to(channel)
    await player.set_voice_client(voice)


def ensure_same_voice_channel(interaction: discord.Interaction, player: GuildAudioPlayer) -> None:
    channel = user_voice_channel(interaction)
    voice = player.voice_client
    if voice is None or voice.channel == channel:
        return
    member = cast(discord.Member, interaction.user)
    if not member.guild_permissions.move_members:
        raise PermissionDeniedError("Você precisa estar no mesmo canal de voz que o bot.")


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "desconhecida/ao vivo"
    total = int(seconds)
    return f"{total // 60}:{total % 60:02d}"
