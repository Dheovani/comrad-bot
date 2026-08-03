"""Lightweight social commands backed by Discord-native features."""

from datetime import timedelta
from typing import TYPE_CHECKING, cast

import discord
from discord import app_commands
from discord.ext import commands

from comradbot.errors import PermissionDeniedError
from comradbot.services.settings import GuildFeature
from comradbot.services.social import MAX_POLL_DURATION_HOURS, prepare_poll

if TYPE_CHECKING:
    from comradbot.bot import ComradBot


class SocialCog(commands.Cog):
    social = app_commands.Group(
        name="social",
        description="Plan game nights and other activities with friends.",
        guild_only=True,
    )

    def __init__(self, bot: "ComradBot") -> None:
        self.bot = bot

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.guild_id is not None:
            await self.bot.guild_settings_service.ensure_feature_enabled(
                interaction.guild_id, GuildFeature.SOCIAL
            )
        return True

    @social.command(name="poll", description="Create a poll for a game night or group decision.")
    @app_commands.describe(
        question="Question shown above the poll.",
        options="Two to ten options separated by |, for example Friday | Saturday.",
        duration_hours="How many hours voting remains open.",
        multiple="Allow each member to choose more than one option.",
    )
    async def poll(
        self,
        interaction: discord.Interaction,
        question: app_commands.Range[str, 1, 300],
        options: app_commands.Range[str, 3, 600],
        duration_hours: app_commands.Range[int, 1, MAX_POLL_DURATION_HOURS] = 24,
        multiple: bool = False,
    ) -> None:
        if not interaction.app_permissions.create_polls:
            raise PermissionDeniedError(
                "ComradBot needs the Create Polls permission in this channel."
            )
        plan = prepare_poll(
            question=question,
            options=options,
            duration_hours=duration_hours,
            multiple=multiple,
        )
        poll = discord.Poll(
            question=plan.question,
            duration=timedelta(hours=plan.duration_hours),
            multiple=plan.multiple,
        )
        for answer in plan.answers:
            poll.add_answer(text=answer)
        await interaction.response.send_message(poll=poll)


async def setup(bot: commands.Bot) -> None:
    from comradbot.bot import ComradBot

    await bot.add_cog(SocialCog(cast(ComradBot, bot)))
