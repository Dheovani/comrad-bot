import pytest

from comradbot.ai.groq_provider import GroqProvider
from comradbot.bot import build_ai_providers
from comradbot.config import Settings


def test_ai_provider_auto_selection_preserves_openai_precedence() -> None:
    settings = Settings(
        discord_token="test",
        openai_api_key="openai-key",
        groq_api_key="groq-key",
    )

    assert settings.configured_ai_provider == "openai"
    assert settings.ai_enabled is True


def test_ai_provider_can_select_groq_and_requires_its_key() -> None:
    configured = Settings(
        discord_token="test",
        ai_provider="groq",
        groq_api_key="groq-key",
    )
    missing_key = Settings(
        discord_token="test",
        ai_provider="groq",
        openai_api_key="openai-key",
    )

    assert configured.configured_ai_provider == "groq"
    assert missing_key.configured_ai_provider is None
    assert missing_key.ai_enabled is False


@pytest.mark.asyncio
async def test_groq_selection_builds_text_only_provider() -> None:
    settings = Settings(
        discord_token="test",
        ai_provider="groq",
        groq_api_key="groq-key",
    )

    provider, speech_provider = build_ai_providers(settings)

    assert isinstance(provider, GroqProvider)
    assert speech_provider is None
    await provider.close()
