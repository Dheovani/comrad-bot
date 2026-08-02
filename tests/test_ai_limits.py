import asyncio
from pathlib import Path

import pytest

from comradbot.ai.conversation import AIService, SlidingWindowLimiter, build_summary_prompt
from comradbot.ai.models import AIMessage, SummaryMessage
from comradbot.ai.policy import ConversationPolicy, ConversationScope
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
        self.get_calls: list[tuple[int, ConversationScope, int]] = []
        self.save_calls: list[tuple[int, ConversationScope, int]] = []
        self.purge_calls = 0

    async def get_messages(
        self, guild_id: int, scope: ConversationScope, scope_id: int
    ) -> list[AIMessage]:
        self.get_calls.append((guild_id, scope, scope_id))
        return list(self.messages)

    async def save_messages(  # type: ignore[no-untyped-def]
        self, guild_id: int, scope: ConversationScope, scope_id: int, messages
    ) -> None:
        self.save_calls.append((guild_id, scope, scope_id))
        self.messages = list(messages)

    async def reset(self, guild_id: int, scope: ConversationScope, scope_id: int) -> None:
        self.messages = []

    async def reset_guild(self, guild_id: int) -> None:
        self.messages = []

    async def purge_expired(self, guild_id: int, cutoff) -> int:  # type: ignore[no-untyped-def]
        self.purge_calls += 1
        return 0

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

    response = await service.ask(guild_id=1, channel_id=2, user_id=3, prompt="nova")

    assert response == "resposta"
    assert [message.content for message in provider.seen] == ["old-2", "old-3", "nova"]
    assert len(repository.messages) == 3
    assert repository.usage[0]["success"] is True
    with pytest.raises(ValidationError, match="máximo"):
        await service.ask(guild_id=1, channel_id=2, user_id=4, prompt="x" * 21)


@pytest.mark.asyncio
async def test_ai_service_applies_user_scope_and_retention(tmp_path: Path) -> None:
    provider = FakeProvider()
    repository = FakeRepository()

    async def policy_provider(guild_id: int) -> ConversationPolicy:
        return ConversationPolicy(scope=ConversationScope.USER, retention_days=7)

    service = AIService(
        provider,
        provider,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
        conversation_policy_provider=policy_provider,
    )

    await service.ask(guild_id=1, channel_id=2, user_id=3, prompt="hello")

    assert repository.get_calls == [(1, ConversationScope.USER, 3)]
    assert repository.save_calls == [(1, ConversationScope.USER, 3)]
    assert repository.purge_calls == 1


@pytest.mark.asyncio
async def test_ai_service_none_scope_does_not_read_or_persist_messages(tmp_path: Path) -> None:
    provider = FakeProvider()
    repository = FakeRepository()
    repository.messages = [AIMessage(role="user", content="must not be loaded")]

    async def policy_provider(guild_id: int) -> ConversationPolicy:
        return ConversationPolicy(scope=ConversationScope.NONE, retention_days=30)

    service = AIService(
        provider,
        provider,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
        conversation_policy_provider=policy_provider,
    )

    await service.ask(guild_id=1, channel_id=2, user_id=3, prompt="stateless")

    assert [message.content for message in provider.seen] == ["stateless"]
    assert repository.get_calls == []
    assert repository.save_calls == []
    assert repository.purge_calls == 0


@pytest.mark.asyncio
async def test_guild_memory_reset_prevents_in_flight_response_from_restoring_context(
    tmp_path: Path,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class SlowProvider(FakeProvider):
        async def generate_response(  # type: ignore[no-untyped-def]
            self, messages, *, max_characters: int
        ) -> str:
            started.set()
            await release.wait()
            return "response"

    repository = FakeRepository()
    service = AIService(
        SlowProvider(),
        None,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
    )

    request = asyncio.create_task(service.ask(guild_id=1, channel_id=2, user_id=3, prompt="hello"))
    await started.wait()
    await service.reset_guild(1)
    release.set()
    assert await request == "response"
    assert repository.save_calls == []


def test_summary_prompt_prioritizes_recent_messages_and_stays_bounded() -> None:
    prompt, considered = build_summary_prompt(
        [
            SummaryMessage(author="one", content="old " * 100),
            SummaryMessage(author="two", content="middle"),
            SummaryMessage(author="three", content="newest"),
        ],
        max_messages=2,
        max_characters=150,
    )

    assert "one:" not in prompt
    assert "two: middle" in prompt
    assert "three: newest" in prompt
    assert len(prompt) <= 150
    assert considered == 2


def test_summary_prompt_supports_the_smallest_valid_prompt_limit() -> None:
    prompt, considered = build_summary_prompt(
        [SummaryMessage(author="a very long display name", content="a long message")],
        max_messages=1,
        max_characters=100,
    )

    assert len(prompt) <= 100
    assert considered == 1


@pytest.mark.asyncio
async def test_ai_service_summarizes_without_persisting_conversation(tmp_path: Path) -> None:
    provider = FakeProvider()
    repository = FakeRepository()
    repository.messages = [AIMessage(role="user", content="existing conversation")]
    service = AIService(
        provider,
        provider,
        repository,  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=2,
        max_prompt_characters=500,
        max_response_characters=20,
        temp_directory=tmp_path,
    )

    response, considered = await service.summarize(
        guild_id=1,
        user_id=3,
        messages=[
            SummaryMessage(author="Ana", content="first"),
            SummaryMessage(author="Beto", content="second"),
            SummaryMessage(author="Caio", content="third"),
        ],
    )

    assert response == "resposta"
    assert considered == 2
    assert len(provider.seen) == 1
    assert "Ana: first" not in provider.seen[0].content
    assert "Beto: second" in provider.seen[0].content
    assert "Caio: third" in provider.seen[0].content
    assert repository.messages == [AIMessage(role="user", content="existing conversation")]
    assert repository.usage == [
        {
            "guild_id": 1,
            "user_id": 3,
            "operation": "summarize",
            "input_characters": len(provider.seen[0].content),
            "output_characters": len(response),
            "success": True,
        }
    ]


@pytest.mark.asyncio
async def test_ai_service_rejects_empty_summary_without_provider_call(tmp_path: Path) -> None:
    provider = FakeProvider()
    service = AIService(
        provider,
        provider,
        FakeRepository(),  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=3, guild_limit=3),
        max_context_messages=2,
        max_prompt_characters=500,
        max_response_characters=20,
        temp_directory=tmp_path,
    )

    with pytest.raises(ValidationError, match="no eligible messages"):
        await service.summarize(guild_id=1, user_id=3, messages=[])
    assert provider.seen == []


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
        await service.ask(guild_id=1, channel_id=2, user_id=3, prompt="oi")


@pytest.mark.asyncio
async def test_guild_can_disable_ai_without_disabling_provider(tmp_path: Path) -> None:
    provider = FakeProvider()

    async def guild_ai_enabled(guild_id: int) -> bool:
        return guild_id != 1

    service = AIService(
        provider,
        provider,
        FakeRepository(),  # type: ignore[arg-type]
        SlidingWindowLimiter(user_limit=1, guild_limit=1),
        max_context_messages=3,
        max_prompt_characters=20,
        max_response_characters=20,
        temp_directory=tmp_path,
        guild_ai_enabled=guild_ai_enabled,
    )

    with pytest.raises(AIDisabledError, match="disabled for this server"):
        await service.ask(guild_id=1, channel_id=2, user_id=3, prompt="oi")
    assert provider.seen == []


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
        await service.speak(guild_id=1, channel_id=2, user_id=3, prompt="oi")
    assert provider.seen == []
