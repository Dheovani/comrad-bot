"""Thin Discord adapter for custom sound management."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.audio.models import AudioItem
from comradbot.commands.helpers import connect_player_to_user, require_guild
from comradbot.errors import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class SoundsCog(commands.Cog):
    sound = app_commands.Group(name="sound", description="Manage this server's custom sounds")

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @sound.command(name="upload", description="Upload a custom sound.")
    async def upload(
        self, interaction: discord.Interaction, name: str, file: discord.Attachment
    ) -> None:
        guild = require_guild(interaction)
        if not interaction.permissions.attach_files:
            raise PermissionDeniedError("You cannot attach files in this channel.")
        if file.size > self.bot.settings.max_sound_file_size_mb * 1024 * 1024:
            raise ValidationError("The file exceeds the configured size limit.")
        await interaction.response.defer(ephemeral=True, thinking=True)
        data = await file.read(use_cached=True)
        sound = await self.bot.sound_service.upload(
            guild_id=guild.id,
            creator_id=interaction.user.id,
            name=name,
            filename=file.filename,
            content_type=file.content_type,
            data=data,
        )
        await interaction.followup.send(
            f"✅ Sound **{sound.name}** saved as Opus ({sound.duration_seconds:.1f}s).",
            ephemeral=True,
        )

    @sound.command(name="play", description="Play a custom sound next.")
    async def play(
        self, interaction: discord.Interaction, name: str, interrupt: bool = False
    ) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        item = await self.bot.sound_service.get_audio_item(guild.id, name, interaction.user.id)
        await self._enqueue_sound(interaction, guild.id, item, interrupt=interrupt)
        await interaction.followup.send(f"🔊 **{item.title}** is next in the queue.")

    @play.autocomplete("name")
    async def play_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sound_choices(interaction, current)

    @sound.command(name="random", description="Play a random custom sound next.")
    async def random_sound(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        item = await self.bot.sound_service.get_random_audio_item(guild.id, interaction.user.id)
        await self._enqueue_sound(interaction, guild.id, item, interrupt=False)
        await interaction.followup.send(f"🎲 The committee selected **{item.title}**.")

    @sound.command(name="list", description="List this server's custom sounds.")
    async def list_sounds(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        sounds = await self.bot.sound_service.list_sounds(guild.id)
        description = "\n".join(
            f"• **{sound.name}** — {sound.duration_seconds:.1f}s ({sound.play_count} plays)"
            for sound in sounds
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔊 Custom sounds",
                description=description or "No custom sounds have been uploaded.",
                color=0xD13C3C,
            )
        )

    @sound.command(name="info", description="Show details about a custom sound.")
    async def info(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        sound = await self.bot.sound_service.get(guild.id, name)
        embed = discord.Embed(title=f"🔊 {sound.name}", color=0xD13C3C)
        embed.add_field(name="Duration", value=f"{sound.duration_seconds:.1f}s")
        embed.add_field(name="Format", value=sound.format.upper())
        embed.add_field(name="Size", value=f"{sound.size_bytes / 1024:.1f} KiB")
        embed.add_field(name="Plays", value=str(sound.play_count))
        embed.add_field(name="Created by", value=f"<@{sound.creator_id}>")
        embed.add_field(
            name="Created at",
            value=sound.created_at.strftime("%Y-%m-%d %H:%M UTC"),
        )
        await interaction.response.send_message(embed=embed)

    @info.autocomplete("name")
    async def info_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sound_choices(interaction, current)

    @sound.command(name="rename", description="Rename a custom sound you manage.")
    @app_commands.rename(new_name="new-name")
    async def rename(self, interaction: discord.Interaction, name: str, new_name: str) -> None:
        guild = require_guild(interaction)
        sound = await self.bot.sound_service.rename(
            guild.id,
            name,
            new_name,
            interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"✏️ Sound renamed to **{sound.name}**.", ephemeral=True
        )

    @rename.autocomplete("name")
    async def rename_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sound_choices(interaction, current)

    @sound.command(name="delete", description="Delete a custom sound you manage.")
    async def delete(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        sound = await self.bot.sound_service.delete(
            guild.id,
            name,
            interaction.user.id,
            is_moderator=self._is_moderator(interaction),
        )
        await interaction.response.send_message(
            f"🗑️ Sound **{sound.name}** deleted.", ephemeral=True
        )

    @delete.autocomplete("name")
    async def delete_name_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        return await self._sound_choices(interaction, current)

    async def _enqueue_sound(
        self,
        interaction: discord.Interaction,
        guild_id: int,
        item: AudioItem,
        *,
        interrupt: bool,
    ) -> None:
        player = await self.bot.audio_manager.get_or_create(guild_id)
        await connect_player_to_user(interaction, player)
        if interrupt and player.current is not None:
            player.skip()
        await player.enqueue(item, next_item=True)

    async def _sound_choices(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        if interaction.guild_id is None:
            return []
        sounds = await self.bot.sound_service.search(interaction.guild_id, current)
        return [app_commands.Choice(name=sound.name, value=sound.name) for sound in sounds]

    @staticmethod
    def _is_moderator(interaction: discord.Interaction) -> bool:
        return isinstance(interaction.user, discord.Member) and (
            interaction.user.guild_permissions.manage_messages
            or interaction.user.guild_permissions.manage_guild
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(SoundsCog(cast(ComradBot, bot)))
