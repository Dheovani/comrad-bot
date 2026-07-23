import asyncio
from pathlib import Path

import pytest

from comradbot.ai.conversation import AIService, SlidingWindowLimiter
from comradbot.ai.models import AIMessage
from comradbot.errors import AIDisabledError, RateLimitError, ValidationError


class FakeProvider:
    def __init__(self) -> None:
        self.seen: list[AIMessage] = []

    async def generate_response(self, messages, *, max_characters: int) -> str:  # type: ignore[no-untyped-def]
        self.seen = list(messages)
        return "resposta"[:max_characters]

    async def generate_speech(self, text: str, destination: Path) -> None:
        await asyncio.to_thread(destination.write_bytes, b"fake-opus")

    async def close(self) -> None:
        return None


class FakeRepository:
    def __init__(self) -> None:
        self.messages: list[AIMessage] = []
        self.usage: list[dict[str, object]] = []

    async def get_messages(self, guild_id: int, scope_id: int) -> list[AIMessage]:
        return list(self.messages)

    async def save_messages(self, guild_id: int, scope_id: int, messages) -> None:  # type: ignore[no-untyped-def]
        self.messages = list(messages)

    async def reset(self, guild_id: int, scope_id: int) -> None:
        self.messages = []

    async def record_usage(self, **kwargs) -> None:  # type: ignore[no-untyped-def]
        self.usage.append(kwargs)


@pytest.mark.asyncio
async def test_sliding_window_enforces_user_and_expires_events() -> None:
    limiter = SlidingWindowLimiter(user_limit=1, guild_limit=3, window_seconds=10)
    await limiter.acquire(1, 10, now=1)
    with pytest.raises(RateLimitError, match="Você"):
        await limiter.acquire(1, 10, now=2)
    await limiter.acquire(1, 10, now=11.1)


@pytest.mark.asyncio
async def test_sliding_window_enforces_cooldown() -> None:
    limiter = SlidingWindowLimiter(
        user_limit=3, guild_limit=10, window_seconds=60, cooldown_seconds=5
    )
    await limiter.acquire(1, 10, now=10)
    with pytest.raises(RateLimitError, match="Aguarde"):
        await limiter.acquire(1, 10, now=12)
    await limiter.acquire(1, 10, now=15)


@pytest.mark.asyncio
async def test_ai_service_limits_context_and_records_usage(tmp_path: Path) -> None:
    provider = FakeProvider()
    repository = FakeRepository()
    repository.messages = [AIMessage(role="user", content=f"old-{index}") for index in range(4)]
    service = AIService(
        provider,
        provider,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
    )

    response = await service.ask(guild_id=1, scope_id=2, user_id=3, prompt="nova")

    assert response == "resposta"
    assert [message.content for message in provider.seen] == ["old-2", "old-3", "nova"]
    assert len(repository.messages) == 3
    assert repository.usage[0]["success"] is True
    with pytest.raises(ValidationError, match="máximo"):
        await service.ask(guild_id=1, scope_id=2, user_id=4, prompt="x" * 21)


@pytest.mark.asyncio
async def test_disabled_ai_is_friendly(tmp_path: Path) -> None:
    service = AIService(
        None,
        None,
        FakeRepository(),  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=1, guild_limit=1),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
    )
    with pytest.raises(AIDisabledError, match="GROQ_API_KEY"):
        await service.ask(guild_id=1, scope_id=2, user_id=3, prompt="oi")


@pytest.mark.asyncio
async def test_text_only_provider_rejects_speech_before_generating_text(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = AIService(
        provider,
        None,
        FakeRepository(),  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=1, guild_limit=1),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
    )

    with pytest.raises(AIDisabledError, match="TTS"):
        await service.speak(guild_id=1, user_id=3, prompt="oi")
    assert provider.seen == []
