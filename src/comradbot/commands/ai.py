"""Thin Discord adapter for generative AI and TTS."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.ai.models import SummaryMessage
from comradbot.commands.helpers import connect_player_to_user, require_guild
from comradbot.errors import PermissionDeniedError, ValidationError
from comradbot.utils.text import split_message

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class AICog(commands.Cog):
    ai = app_commands.Group(name="ai", description="Recursos de inteligência artificial")

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    @ai.command(name="ask", description="Faz uma pergunta ao ComradBot.")
    async def ask(self, interaction: discord.Interaction, prompt: str) -> None:
        guild = require_guild(interaction)
        if interaction.channel_id is None:
            raise ValidationError("Não foi possível identificar o canal desta conversa.")
        await interaction.response.defer(thinking=True)
        response = await self.bot.ai_service.ask(
            guild_id=guild.id,
            scope_id=interaction.channel_id,
            user_id=interaction.user.id,
            prompt=prompt,
        )
        chunks = split_message(response, self.bot.settings.max_ai_response_characters)
        allowed_mentions = discord.AllowedMentions.none()
        await interaction.followup.send(chunks[0], allowed_mentions=allowed_mentions)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, allowed_mentions=allowed_mentions)

    @ai.command(name="reset", description="Limpa a memória de IA deste canal.")
    async def reset(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        if interaction.channel_id is None:
            raise ValidationError("Não foi possível identificar o canal desta conversa.")
        await self.bot.ai_service.reset(guild.id, interaction.channel_id)
        await interaction.response.send_message("🧹 Contexto deste canal removido.", ephemeral=True)

    @ai.command(name="summarize", description="Summarize recent messages in this channel.")
    @app_commands.describe(count="Maximum number of recent user messages to consider.")
    async def summarize(
        self,
        interaction: discord.Interaction,
        count: app_commands.Range[int, 1, 100],
    ) -> None:
        guild = require_guild(interaction)
        if not self.bot.settings.discord_message_content_intent:
            raise ValidationError(
                "Message summaries are disabled. Enable the Message Content Intent "
                "in Discord and set DISCORD_MESSAGE_CONTENT_INTENT=true."
            )
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.Thread, discord.VoiceChannel)):
            raise ValidationError("This channel type does not support message summaries.")
        if not isinstance(interaction.user, discord.Member):
            raise ValidationError("Could not verify your channel permissions.")
        if not channel.permissions_for(interaction.user).read_message_history:
            raise PermissionDeniedError("You need Read Message History in this channel.")
        if not interaction.app_permissions.read_message_history:
            raise PermissionDeniedError("ComradBot needs Read Message History in this channel.")

        requested = min(count, self.bot.settings.max_ai_context_messages)
        scan_limit = min(requested * 3, 300)
        messages: list[SummaryMessage] = []
        await interaction.response.defer(thinking=True)
        async for message in channel.history(
            limit=scan_limit,
            before=interaction.created_at,
        ):
            content = message.content.strip()
            if message.author.bot or not content:
                continue
            messages.append(
                SummaryMessage(
                    author=message.author.display_name,
                    content=content,
                )
            )
            if len(messages) >= requested:
                break
        messages.reverse()
        response, considered = await self.bot.ai_service.summarize(
            guild_id=guild.id,
            user_id=interaction.user.id,
            messages=messages,
        )
        embed = discord.Embed(
            title="Recent conversation summary",
            description=response,
            color=0xD13C3C,
        )
        embed.set_footer(text=f"{considered} message(s) considered • Attachments ignored")
        await interaction.followup.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @ai.command(name="status", description="Show AI availability and configured safeguards.")
    async def status(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        guild_settings = await self.bot.guild_settings_service.get(guild.id)
        provider = self.bot.settings.configured_ai_provider
        if provider == "openai":
            provider_name = "OpenAI"
        elif provider == "groq":
            provider_name = "Groq"
        else:
            provider_name = "Disabled"
        if not guild_settings.ai_enabled:
            summary_status = "Disabled for this server"
        elif provider is None:
            summary_status = "Unavailable (AI provider is disabled)"
        elif not self.bot.settings.discord_message_content_intent:
            summary_status = "Disabled (Message Content Intent is off)"
        else:
            summary_status = "Available"
        embed = discord.Embed(title="ComradBot AI status", color=0xD13C3C)
        embed.add_field(
            name="Text provider",
            value=provider_name if guild_settings.ai_enabled else "Disabled for this server",
            inline=True,
        )
        embed.add_field(
            name="Speech",
            value=(
                "Available"
                if guild_settings.ai_enabled and self.bot.ai_service.speech_enabled
                else "Unavailable"
            ),
            inline=True,
        )
        embed.add_field(
            name="Speech recognition",
            value=(
                "Available for attachments"
                if guild_settings.ai_enabled and self.bot.ai_service.transcription_enabled
                else "Unavailable"
            ),
            inline=True,
        )
        embed.add_field(
            name="Channel summaries",
            value=summary_status,
            inline=False,
        )
        embed.add_field(
            name="Local limits",
            value=(
                f"{self.bot.settings.ai_user_requests_per_minute} request(s)/minute per user\n"
                f"{self.bot.settings.ai_guild_requests_per_minute} request(s)/minute per server\n"
                f"{self.bot.settings.ai_cooldown_seconds:g}s user cooldown\n"
                f"{self.bot.settings.max_ai_context_messages} context message(s) maximum"
            ),
            inline=False,
        )
        embed.set_footer(text="No API keys or conversation content are displayed.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ai.command(name="transcribe", description="Transcribe a supported audio attachment.")
    @app_commands.describe(file="Audio or video file containing speech.")
    async def transcribe(
        self,
        interaction: discord.Interaction,
        file: discord.Attachment,
    ) -> None:
        guild = require_guild(interaction)
        max_size = self.bot.settings.max_transcription_file_size_mb * 1024 * 1024
        if file.size > max_size:
            raise ValidationError(
                f"The attachment exceeds the {self.bot.settings.max_transcription_file_size_mb} MB "
                "transcription limit."
            )
        await interaction.response.defer(thinking=True)
        data = await file.read()
        transcript = await self.bot.ai_service.transcribe(
            guild_id=guild.id,
            user_id=interaction.user.id,
            filename=file.filename,
            content_type=file.content_type,
            data=data,
        )
        chunks = split_message(transcript, self.bot.settings.max_ai_response_characters)
        embed = discord.Embed(
            title="Speech transcription",
            description=chunks[0],
            color=0xD13C3C,
        )
        embed.set_footer(text="Generated from the attached media by Groq speech recognition")
        await interaction.followup.send(
            embed=embed,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        for chunk in chunks[1:]:
            await interaction.followup.send(
                chunk,
                allowed_mentions=discord.AllowedMentions.none(),
            )

    @ai.command(name="speak", description="Gera uma resposta curta e a reproduz no canal de voz.")
    async def speak(self, interaction: discord.Interaction, prompt: str) -> None:
        guild = require_guild(interaction)
        await interaction.response.defer(thinking=True)
        player = await self.bot.audio_manager.get_or_create(guild.id)
        await connect_player_to_user(interaction, player)
        text, item = await self.bot.ai_service.speak(
            guild_id=guild.id, user_id=interaction.user.id, prompt=prompt
        )
        position = await player.enqueue(item, next_item=True)
        await interaction.followup.send(
            embed=discord.Embed(
                title="🗣️ Resposta falada enfileirada",
                description=text,
                color=0xD13C3C,
            ).set_footer(text=f"Posição prioritária: {position} • Voz sintética gerada por IA")
        )


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(AICog(cast(ComradBot, bot)))
