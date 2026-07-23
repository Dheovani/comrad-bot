"""Thin Discord adapter for generative AI and TTS."""

from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.commands.helpers import connect_player_to_user, require_guild
from comradbot.errors import ValidationError
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
        await interaction.followup.send(chunks[0])
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk)

    @ai.command(name="reset", description="Limpa a memória de IA deste canal.")
    async def reset(self, interaction: discord.Interaction) -> None:
        guild = require_guild(interaction)
        if interaction.channel_id is None:
            raise ValidationError("Não foi possível identificar o canal desta conversa.")
        await self.bot.ai_service.reset(guild.id, interaction.channel_id)
        await interaction.response.send_message("🧹 Contexto deste canal removido.", ephemeral=True)

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
