"""Small optional player panel; slash commands remain the canonical controls."""

import discord

from comradbot.audio.manager import GuildAudioManager


class PlayerControls(discord.ui.View):
    def __init__(self, manager: GuildAudioManager, guild_id: int) -> None:
        super().__init__(timeout=180)
        self._manager = manager
        self._guild_id = guild_id

    @discord.ui.button(label="Pause/resume", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None or player.voice_client is None:
            await interaction.response.send_message("The player is not active.", ephemeral=True)
            return
        if player.voice_client.is_paused():
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
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("The player is not active.", ephemeral=True)
            return
        player.skip()
        await interaction.response.send_message("Current item skipped.", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("The player is not active.", ephemeral=True)
            return
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
