"""Small optional player panel; slash commands remain the canonical controls."""

import logging
import math
import re
from typing import Any

import discord

from comradbot.audio.manager import GuildAudioManager
from comradbot.audio.models import AudioItem
from comradbot.audio.player import GuildAudioPlayer
from comradbot.commands.helpers import ensure_same_voice_channel
from comradbot.errors import AudioPlaybackError, ComradBotError, PermissionDeniedError

logger = logging.getLogger(__name__)
PANEL_PAGE_SIZE = 10
PAGE_PATTERN = re.compile(r"Page (\d+)/(\d+)")


def build_player_panel_embed(
    player: GuildAudioPlayer | None,
    items: list[AudioItem],
    *,
    page: int = 0,
) -> tuple[discord.Embed, int]:
    total_pages = max(1, math.ceil(len(items) / PANEL_PAGE_SIZE))
    bounded_page = min(max(page, 0), total_pages - 1)
    start = bounded_page * PANEL_PAGE_SIZE
    lines: list[str] = []
    if player is not None and player.current is not None:
        lines.append(f"**Now playing:** {player.current.title}")
    lines.extend(
        f"`{position}.` {item.title} — <@{item.requester_id}>"
        for position, item in enumerate(
            items[start : start + PANEL_PAGE_SIZE],
            start=start + 1,
        )
    )
    repeat = player.repeat_mode.value if player is not None else "off"
    voice = player.voice_client if player is not None else None
    if voice is not None and voice.is_paused():
        state = "paused"
    elif voice is not None and voice.is_playing():
        state = "playing"
    else:
        state = "idle"
    embed = discord.Embed(
        title="🎛️ ComradBot player",
        description="\n".join(lines) or "The queue is empty.",
        color=0xD13C3C,
    )
    embed.set_footer(
        text=f"Page {bounded_page + 1}/{total_pages} • Repeat: {repeat} • State: {state}"
    )
    return embed, bounded_page


class PlayerControls(discord.ui.View):
    def __init__(self, manager: GuildAudioManager, guild_id: int | None = None) -> None:
        super().__init__(timeout=None)
        self._manager = manager
        self._guild_id = guild_id

    async def interaction_check(self, interaction: discord.Interaction, /) -> bool:
        if interaction.guild_id is not None and (
            self._guild_id is None or interaction.guild_id == self._guild_id
        ):
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
        player = self._manager.get(self._interaction_guild_id(interaction))
        if player is None or player.voice_client is None:
            raise AudioPlaybackError("The player is not active.")
        ensure_same_voice_channel(interaction, player)
        return player

    def _interaction_guild_id(self, interaction: discord.Interaction) -> int:
        guild_id = self._guild_id or interaction.guild_id
        if guild_id is None:
            raise AudioPlaybackError("This player panel is unavailable outside a server.")
        return guild_id

    @staticmethod
    def _current_page(interaction: discord.Interaction) -> int:
        message = interaction.message
        if message is None or not message.embeds or message.embeds[0].footer.text is None:
            return 0
        match = PAGE_PATTERN.search(message.embeds[0].footer.text)
        return max(0, int(match.group(1)) - 1) if match else 0

    async def _render_panel(self, interaction: discord.Interaction, *, page: int) -> None:
        player = self._manager.get(self._interaction_guild_id(interaction))
        items = await player.queue.snapshot() if player is not None else []
        embed, _ = build_player_panel_embed(player, items, page=page)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Pause/resume",
        emoji="⏯️",
        style=discord.ButtonStyle.secondary,
        custom_id="comradbot:player:toggle",
        row=0,
    )
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
        logger.info("Player panel action guild_id=%s action=%s", player.guild_id, message)
        await self._render_panel(interaction, page=self._current_page(interaction))

    @discord.ui.button(
        label="Skip",
        emoji="⏭️",
        style=discord.ButtonStyle.primary,
        custom_id="comradbot:player:skip",
        row=0,
    )
    async def skip(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._active_player_for_control(interaction)
        player.skip()
        await self._render_panel(interaction, page=self._current_page(interaction))

    @discord.ui.button(
        label="Stop",
        emoji="⏹️",
        style=discord.ButtonStyle.danger,
        custom_id="comradbot:player:stop",
        row=0,
    )
    async def stop_button(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        player = self._active_player_for_control(interaction)
        await player.stop()
        await self._render_panel(interaction, page=0)

    @discord.ui.button(
        label="Refresh",
        emoji="🔄",
        style=discord.ButtonStyle.secondary,
        custom_id="comradbot:player:refresh",
        row=0,
    )
    async def refresh(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        await self._render_panel(interaction, page=self._current_page(interaction))

    @discord.ui.button(
        label="Previous",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
        custom_id="comradbot:player:previous",
        row=1,
    )
    async def previous(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        await self._render_panel(interaction, page=self._current_page(interaction) - 1)

    @discord.ui.button(
        label="Next",
        emoji="▶️",
        style=discord.ButtonStyle.secondary,
        custom_id="comradbot:player:next",
        row=1,
    )
    async def next_page(
        self, interaction: discord.Interaction, _: discord.ui.Button[discord.ui.View]
    ) -> None:
        await self._render_panel(interaction, page=self._current_page(interaction) + 1)
