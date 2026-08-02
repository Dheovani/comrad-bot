from typing import Any, cast

import discord
import pytest
from discord import app_commands

from comradbot.commands.general import build_help_embed
from comradbot.localization import ComradBotTranslator, Localizer


def test_localizer_uses_interaction_locale_and_falls_back_to_default() -> None:
    english = Localizer(default_locale="en-US")
    portuguese = Localizer(default_locale="pt-BR")

    assert english.text("help.start.name", discord.Locale.brazil_portuguese) == "Primeiros passos"
    assert english.text("help.start.name", discord.Locale.german) == "Getting started"
    assert portuguese.text("help.start.name", discord.Locale.german) == "Primeiros passos"


@pytest.mark.asyncio
async def test_discord_translator_localizes_known_descriptions_only() -> None:
    translator = ComradBotTranslator(Localizer())
    context = cast(Any, object())

    translated = await translator.translate(
        app_commands.locale_str("Check whether ComradBot is responding."),
        discord.Locale.brazil_portuguese,
        context,
    )
    missing = await translator.translate(
        app_commands.locale_str("unknown command text"),
        discord.Locale.brazil_portuguese,
        context,
    )

    assert translated == "Verifica se o ComradBot está respondendo."
    assert missing is None


def test_help_embed_uses_portuguese_catalog() -> None:
    embed = build_help_embed(Localizer(), discord.Locale.brazil_portuguese)

    assert embed.title == "🤝 Guia de comandos do ComradBot"
    assert embed.fields[0].name == "🎵 Música"
    assert embed.footer.text == "ComradBot — áudio organizado para o coletivo."
