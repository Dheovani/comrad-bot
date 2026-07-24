import asyncio
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

import pytest

from comradbot.ai.models import AIMessage
from comradbot.ai.openai_provider import OpenAIProvider
from comradbot.errors import AIError, OperationTimeoutError


class StreamingContext:
    def __init__(self, response: object) -> None:
        self.response = response

    async def __aenter__(self) -> object:
        return self.response

    async def __aexit__(self, *args: object) -> None:
        return None


def fake_provider(
    *,
    response_create: AsyncMock,
    speech_create: Mock | None = None,
) -> OpenAIProvider:
    provider = OpenAIProvider(
        api_key="test-key",
        model="test-model",
        persona="Test persona",
        tts_model="test-tts",
        tts_voice="test-voice",
        timeout_seconds=1,
    )
    client = SimpleNamespace(
        responses=SimpleNamespace(create=response_create),
        audio=SimpleNamespace(
            speech=SimpleNamespace(
                with_streaming_response=SimpleNamespace(create=speech_create or Mock())
            )
        ),
        close=AsyncMock(),
    )
    cast(Any, provider)._client = client
    return provider


@pytest.mark.asyncio
async def test_openai_provider_maps_messages_and_bounds_response() -> None:
    create = AsyncMock(return_value=SimpleNamespace(output_text="  long response  "))
    provider = fake_provider(response_create=create)

    result = await provider.generate_response(
        [AIMessage(role="user", content="hello")],
        max_characters=4,
    )

    assert result == "long"
    request = create.await_args.kwargs
    assert request["model"] == "test-model"
    assert request["instructions"].startswith("Test persona")
    assert request["input"] == [{"role": "user", "content": "hello"}]


@pytest.mark.asyncio
async def test_openai_provider_rejects_empty_response() -> None:
    provider = fake_provider(
        response_create=AsyncMock(return_value=SimpleNamespace(output_text="   "))
    )

    with pytest.raises(AIError, match="vazia"):
        await provider.generate_response([], max_characters=100)


@pytest.mark.asyncio
async def test_openai_provider_maps_text_timeout() -> None:
    provider = fake_provider(response_create=AsyncMock(side_effect=TimeoutError))

    with pytest.raises(OperationTimeoutError, match="demorou"):
        await provider.generate_response([], max_characters=100)


@pytest.mark.asyncio
async def test_openai_provider_streams_opus_with_configured_voice(tmp_path: Path) -> None:
    destination = tmp_path / "speech.opus"

    async def write_file(path: Path) -> None:
        await asyncio.to_thread(path.write_bytes, b"opus")

    stream_to_file = AsyncMock(side_effect=write_file)
    speech_create = Mock(
        return_value=StreamingContext(SimpleNamespace(stream_to_file=stream_to_file))
    )
    provider = fake_provider(
        response_create=AsyncMock(),
        speech_create=speech_create,
    )

    await provider.generate_speech("hello", destination)

    assert await asyncio.to_thread(destination.read_bytes) == b"opus"
    assert speech_create.call_args.kwargs == {
        "model": "test-tts",
        "voice": "test-voice",
        "input": "hello",
        "response_format": "opus",
    }


@pytest.mark.asyncio
async def test_openai_provider_removes_partial_file_on_tts_timeout(tmp_path: Path) -> None:
    destination = tmp_path / "partial.opus"
    await asyncio.to_thread(destination.write_bytes, b"partial")
    response = SimpleNamespace(stream_to_file=AsyncMock(side_effect=TimeoutError))
    provider = fake_provider(
        response_create=AsyncMock(),
        speech_create=Mock(return_value=StreamingContext(response)),
    )

    with pytest.raises(OperationTimeoutError, match="tempo limite"):
        await provider.generate_speech("hello", destination)

    assert not await asyncio.to_thread(destination.exists)
