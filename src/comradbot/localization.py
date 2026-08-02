"""Runtime messages and Discord application-command localization."""

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Literal, cast

import discord
from discord import app_commands

LocaleCode = Literal["en-US", "pt-BR"]
SUPPORTED_LOCALES: tuple[LocaleCode, ...] = ("en-US", "pt-BR")


@dataclass(frozen=True, slots=True)
class TranslationCatalog:
    commands: dict[str, str]
    messages: dict[str, str]


class Localizer:
    def __init__(self, *, default_locale: LocaleCode = "en-US") -> None:
        self.default_locale = default_locale
        self._catalogs = {locale: self._load_catalog(locale) for locale in SUPPORTED_LOCALES}
        default_keys = self._catalogs["en-US"].messages.keys()
        for locale, catalog in self._catalogs.items():
            if catalog.messages.keys() != default_keys:
                raise ValueError(f"Locale {locale} does not contain the complete message catalog")

    def text(self, key: str, locale: discord.Locale | str | None = None, **values: object) -> str:
        resolved = self.resolve_locale(locale)
        template = self._catalogs[resolved].messages.get(key)
        if template is None:
            template = self._catalogs["en-US"].messages.get(key)
        if template is None:
            raise KeyError(f"Unknown localization key: {key}")
        return template.format_map(values)

    def command_translation(self, message: str, locale: discord.Locale) -> str | None:
        resolved = self.resolve_locale(locale)
        if resolved == "en-US":
            return None
        return self._catalogs[resolved].commands.get(message)

    def resolve_locale(self, locale: discord.Locale | str | None) -> LocaleCode:
        value = locale.value if isinstance(locale, discord.Locale) else locale
        if value in SUPPORTED_LOCALES:
            return cast(LocaleCode, value)
        return self.default_locale

    @staticmethod
    def _load_catalog(locale: LocaleCode) -> TranslationCatalog:
        raw = resources.files("comradbot.locales").joinpath(f"{locale}.json").read_text("utf-8")
        decoded = json.loads(raw)
        if not isinstance(decoded, dict):
            raise ValueError(f"Locale {locale} must contain a JSON object")
        commands = decoded.get("commands")
        messages = decoded.get("messages")
        if not isinstance(commands, dict) or not isinstance(messages, dict):
            raise ValueError(f"Locale {locale} must define commands and messages")
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in commands.items()
        ):
            raise ValueError(f"Locale {locale} contains an invalid command translation")
        if not all(
            isinstance(key, str) and isinstance(value, str) for key, value in messages.items()
        ):
            raise ValueError(f"Locale {locale} contains an invalid message translation")
        return TranslationCatalog(commands=commands, messages=messages)


class ComradBotTranslator(app_commands.Translator):
    def __init__(self, localizer: Localizer) -> None:
        self._localizer = localizer

    async def translate(
        self,
        string: app_commands.locale_str,
        locale: discord.Locale,
        context: app_commands.TranslationContextTypes,
    ) -> str | None:
        return self._localizer.command_translation(string.message, locale)


@lru_cache(maxsize=1)
def default_localizer() -> Localizer:
    return Localizer()
