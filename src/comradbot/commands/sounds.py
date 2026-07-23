"""Thin Discord adapter for custom sound management."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.commands.helpers import connect_player_to_user, require_guild
from comradbot.errors import PermissionDeniedError, ValidationError

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class SoundsCog(commands.Cog):
    sound = app_commands.Group(name="sound", description="Áudios personalizados do servidor")

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @sound.command(name="upload", description="Envia um áudio personalizado.")
    async def upload(
        self, interaction: discord.Interaction, name: str, file: discord.Attachment
    ) -> None:
        guild = require_guild(interaction)
        if not interaction.permissions.attach_files:
            raise PermissionDeniedError("Você não tem permissão para anexar arquivos neste canal.")
        if file.size > self.bot.settings.max_sound_file_size_mb * 1024 * 1024:
            raise ValidationError("O arquivo excede o limite de tamanho configurado.")
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
            f"✅ Áudio **{sound.name}** salvo em Opus ({sound.duration_seconds:.1f}s).",
            ephemeral=True,
        )

    @sound.command(name="play", description="Reproduz um áudio personalizado.")
    async def play(
        self, interaction: discord.Interaction, name: str, interrupt: bool = False
    ) -> None:
        guild = require_guild(interaction)
        item = await self.bot.sound_service.get_audio_item(guild.id, name, interaction.user.id)
        player = await self.bot.audio_manager.get_or_create(guild.id)
        await connect_player_to_user(interaction, player)
        if interrupt and player.current is not None:
            player.skip()
        await player.enqueue(item, next_item=True)
        await interaction.response.send_message(f"🔊 **{item.title}** será o próximo áudio.")

    @sound.command(name="list", description="Lista os áudios personalizados.")
    async def list_sounds(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        sounds = await self.bot.sound_service.list(guild.id)
        description = "\n".join(
            f"• **{sound.name}** — {sound.duration_seconds:.1f}s ({sound.play_count} reproduções)"
            for sound in sounds
        )
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🔊 Áudios personalizados",
                description=description or "Nenhum áudio cadastrado.",
                color=0xD13C3C,
            )
        )

    @sound.command(name="delete", description="Exclui um áudio criado por você ou pela moderação.")
    async def delete(self, interaction: discord.Interaction, name: str) -> None:
        guild = require_guild(interaction)
        moderator = isinstance(interaction.user, discord.Member) and (
            interaction.user.guild_permissions.manage_messages
            or interaction.user.guild_permissions.manage_guild
        )
        sound = await self.bot.sound_service.delete(
            guild.id, name, interaction.user.id, is_moderator=moderator
        )
        await interaction.response.send_message(
            f"🗑️ Áudio **{sound.name}** excluído.", ephemeral=True
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(SoundsCog(cast(ComradBot, bot)))
