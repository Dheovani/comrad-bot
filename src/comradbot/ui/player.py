"""Small optional player panel; slash commands remain the canonical controls."""

import discord

from comradbot.audio.manager import GuildAudioManager


class PlayerControls(discord.ui.View):
    def __init__(self, manager: GuildAudioManager, guild_id: int) -> None:
        super().__init__(timeout=180)
        self._manager = manager
        self._guild_id = guild_id

    @discord.ui.button(label="Pausar/continuar", emoji="⏯️", style=discord.ButtonStyle.secondary)
    async def toggle(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None or player.voice_client is None:
            await interaction.response.send_message("O player não está ativo.", ephemeral=True)
            return
        if player.voice_client.is_paused():
            player.resume()
            message = "Reprodução retomada."
        else:
            player.pause()
            message = "Reprodução pausada."
        await interaction.response.send_message(message, ephemeral=True)

    @discord.ui.button(label="Pular", emoji="⏭️", style=discord.ButtonStyle.primary)
    async def skip(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("O player não está ativo.", ephemeral=True)
            return
        player.skip()
        await interaction.response.send_message("Item pulado.", ephemeral=True)

    @discord.ui.button(label="Parar", emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop_button(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("O player não está ativo.", ephemeral=True)
            return
        await player.stop()
        await interaction.response.send_message("Fila e reprodução encerradas.", ephemeral=True)

    @discord.ui.button(label="Fila", emoji="📋", style=discord.ButtonStyle.secondary)
    async def queue(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._manager.get(self._guild_id)
        if player is None:
            await interaction.response.send_message("A fila está vazia.", ephemeral=True)
            return
        items = await player.queue.snapshot()
        description = "\n".join(f"{index}. {item.title}" for index, item in enumerate(items, 1))
        await interaction.response.send_message(description or "A fila está vazia.", ephemeral=True)
