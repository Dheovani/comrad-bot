from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock

import groq
import httpx
import pytest

from comradbot.ai.groq_provider import GroqProvider
from comradbot.ai.models import AIMessage
from comradbot.errors import OperationTimeoutError, RateLimitError


def fake_provider(
    create: AsyncMock,
    *,
    transcription_create: AsyncMock | None = None,
    persona: str = "Custom comrade persona",
) -> GroqProvider:
    provider = GroqProvider(
        api_key="test-key",
        model="test-model",
        transcription_model="whisper-large-v3-turbo",
        persona=persona,
        timeout_seconds=1,
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create)),
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(create=transcription_create or AsyncMock())
        ),
        close=AsyncMock(),
    )
    cast(Any, provider)._client = client
    return provider


@pytest.mark.asyncio
async def test_groq_provider_maps_conversation_and_limits_response() -> None:
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="resposta longa"))]
        )
    )
    provider = fake_provider(create)

    response = await provider.generate_response(
        [
            AIMessage(role="user", content="olá"),
            AIMessage(role="assistant", content="saudações"),
        ],
        max_characters=8,
    )

    assert response == "resposta"
    request = create.await_args.kwargs
    assert request["model"] == "test-model"
    assert request["messages"][0]["role"] == "system"
    assert request["messages"][0]["content"].startswith("Custom comrade persona")
    assert request["messages"][1:] == [
        {"role": "user", "content": "olá"},
        {"role": "assistant", "content": "saudações"},
    ]


@pytest.mark.asyncio
async def test_groq_provider_maps_rate_limit_without_leaking_provider_details() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request)
    create = AsyncMock(
        side_effect=groq.RateLimitError("secret provider detail", response=response, body=None)
    )
    provider = fake_provider(create)

    with pytest.raises(RateLimitError, match="limite gratuito") as captured:
        await provider.generate_response(
            [AIMessage(role="user", content="olá")],
            max_characters=100,
        )
    assert "secret provider detail" not in str(captured.value)


@pytest.mark.asyncio
async def test_groq_provider_maps_sdk_timeout() -> None:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    provider = fake_provider(AsyncMock(side_effect=groq.APITimeoutError(request=request)))

    with pytest.raises(OperationTimeoutError, match="demorou"):
        await provider.generate_response(
            [AIMessage(role="user", content="olá")],
            max_characters=100,
        )


@pytest.mark.asyncio
async def test_groq_provider_transcribes_normalized_audio(tmp_path: Path) -> None:
    transcription_create = AsyncMock(return_value=SimpleNamespace(text="  hello comrades  "))
    provider = fake_provider(AsyncMock(), transcription_create=transcription_create)
    audio = tmp_path / "speech.flac"
    audio.write_bytes(b"normalized-audio")

    result = await provider.transcribe_audio(audio)

    assert result == "hello comrades"
    request = transcription_create.await_args.kwargs
    assert request["model"] == "whisper-large-v3-turbo"
    assert request["file"] == ("speech.flac", b"normalized-audio", "audio/flac")
    assert request["response_format"] == "json"
