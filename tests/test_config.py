from pathlib import Path

import pytest

from comradbot.ai.groq_provider import GroqProvider
from comradbot.bot import build_ai_providers
from comradbot.config import Settings


def test_ai_provider_auto_selection_preserves_openai_precedence() -> None:
    settings = Settings(
        _env_file=None,
        discord_token="test",
        openai_api_key="openai-key",
        groq_api_key="groq-key",
    )

    assert settings.configured_ai_provider == "openai"
    assert settings.ai_enabled is True


def test_ai_provider_can_select_groq_and_requires_its_key() -> None:
    configured = Settings(
        _env_file=None,
        discord_token="test",
        ai_provider="groq",
        groq_api_key="groq-key",
    )
    missing_key = Settings(
        _env_file=None,
        discord_token="test",
        ai_provider="groq",
        openai_api_key="openai-key",
    )

    assert configured.configured_ai_provider == "groq"
    assert missing_key.configured_ai_provider is None
    assert missing_key.ai_enabled is False


def test_custom_persona_is_trimmed_and_blank_value_is_disabled() -> None:
    configured = Settings(
        _env_file=None,
        discord_token="test",
        custom_comradbot_persona="  A custom persona  ",
    )
    blank = Settings(
        _env_file=None,
        discord_token="test",
        custom_comradbot_persona="   ",
    )

    assert configured.custom_comradbot_persona == "A custom persona"
    assert blank.custom_comradbot_persona is None


def test_message_content_intent_is_opt_in() -> None:
    default = Settings(_env_file=None, discord_token="test")
    enabled = Settings(
        _env_file=None,
        discord_token="test",
        discord_message_content_intent=True,
    )

    assert default.discord_message_content_intent is False
    assert enabled.discord_message_content_intent is True


def test_custom_multiline_persona_loads_from_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'DISCORD_TOKEN=test\nCUSTOM_COMRADBOT_PERSONA="First line\\nCall users \\"comrade\\"."\n',
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.custom_comradbot_persona == 'First line\nCall users "comrade".'


@pytest.mark.asyncio
async def test_groq_selection_builds_text_and_recognition_provider() -> None:
    settings = Settings(
        _env_file=None,
        discord_token="test",
        ai_provider="groq",
        groq_api_key="groq-key",
    )

    provider, speech_provider, recognition_provider = build_ai_providers(settings)

    assert isinstance(provider, GroqProvider)
    assert speech_provider is None
    assert recognition_provider is provider
    await provider.close()
