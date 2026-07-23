"""Small optional player panel; slash commands remain the canonical controls."""

import logging
from typing import Any

import discord

from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands.helpers import ensure_same_voice_channel
from comradbot.errors import AudioPlaybackError, ComradBotError, PermissionDeniedError

logger = logging.getLogger(__name__)


class PlayerControls(discord.ui.View):
    def __init__(self, manager: GuildAudioManager, guild_id: int) -> None:
        super().__init__(timeout=180)
        self._manager = manager
        self._guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.guild_id == self._guild_id:
            return True
        await interaction.response.send_message(
            "This player panel belongs to another server.", ephemeral=True
        )
        return False

    async def on_error(
        self,
        interaction: discord.Interaction,
        error: Exception,
        item: discord.ui.Item[Any],
        /,
    ) -> None:
        control_type = type(item).__name__
        if isinstance(error, PermissionDeniedError):
            message = f"⛔ {error}"
            logger.warning(
                "Player control denied guild_id=%s user_id=%s control=%s",
                interaction.guild_id,
                interaction.user.id,
                control_type,
            )
        elif isinstance(error, ComradBotError):
            message = f"⚠️ {error}"
            logger.info(
                "Player control failed guild_id=%s user_id=%s control=%s error=%s",
                interaction.guild_id,
                interaction.user.id,
                control_type,
                type(error).__name__,
            )
        else:
            message = "💥 The player control failed. Try again in a moment."
            logger.error(
                "Unexpected player control error guild_id=%s user_id=%s control=%s",
                interaction.guild_id,
                interaction.user.id,
                control_type,
                exc_info=(type(error), error, error.__traceback__),
            )
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)

    def _active_player_for_control(self, interaction: discord.Interaction) -> GuildAudioPlayer:
        player = self._manager.get(self._guild_id)
        if player is None or player.voice_client is None:
            raise AudioPlaybackError("The player is not active.")
        ensure_same_voice_channel(interaction, player)
        return player

    @discord.ui.button(label="Pause/resume", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._active_player_for_control(interaction)
        voice_client = player.voice_client
        assert voice_client is not None
        if voice_client.is_paused():
            player.resume()
            message = "Playback resumed."
        else:
            player.pause()
            message = "Playback paused."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Skip", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._active_player_for_control(interaction)
        player.skip()
        await interaction.response.send_message("Current item skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._active_player_for_control(interaction)
        await player.stop()
        await interaction.response.send_message(
            "Playback stopped and queue cleared.", ephemeral=True
        )

    @discord.ui.button(label="Queue", emoji="📋", style=discord.ButtonStyle.secondary)
    async def queue(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("The queue is empty.", ephemeral=True)
            return
        items = await player.queue.snapshot()
        description = "\n".join(f"{index}. {item.title}" for index, item in enumerate(items, 1))
        await interaction.response.send_message(
            description or "The queue is empty.", ephemeral=True
        )
