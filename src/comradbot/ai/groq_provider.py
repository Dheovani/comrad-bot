"""Groq text generation through its official asynchronous Python SDK."""

import asyncio
from collections.abc import Sequence
from pathlib import Path

import groq
from groq import AsyncGroq
from groq.types.chat import (
    ChatCompletionAssistantMessageParam,
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from comradbot.ai.models import AIMessage
from comradbot.errors import AIError, OperationTimeoutError, RateLimitError


class GroqProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        transcription_model: str,
        persona: str,
        timeout_seconds: float,
    ) -> None:
        self._client = AsyncGroq(
            api_key=api_key,
            timeout=timeout_seconds,
            max_retries=1,
        )
        self._model = model
        self._transcription_model = transcription_model
        self._persona = persona
        self._timeout_seconds = timeout_seconds

    async def generate_response(
        self,
        messages: Sequence[AIMessage],
        *,
        max_characters: int,
    ) -> str:
        system_message: ChatCompletionSystemMessageParam = {
            "role": "system",
            "content": (f"{self._persona}\nResponda com no máximo {max_characters} caracteres."),
        }
        request_messages: list[ChatCompletionMessageParam] = [system_message]
        for message in messages:
            if message.role == "user":
                user_message: ChatCompletionUserMessageParam = {
                    "role": "user",
                    "content": message.content,
                }
                request_messages.append(user_message)
            else:
                assistant_message: ChatCompletionAssistantMessageParam = {
                    "role": "assistant",
                    "content": message.content,
                }
                request_messages.append(assistant_message)
        try:
            completion = await asyncio.wait_for(
                self._client.chat.completions.create(
                    model=self._model,
                    messages=request_messages,
                    max_completion_tokens=min(max(max_characters, 64), 2048),
                ),
                timeout=self._timeout_seconds,
            )
        except (TimeoutError, groq.APITimeoutError) as exc:
            raise OperationTimeoutError("A Groq demorou demais para responder.") from exc
        except groq.RateLimitError as exc:
            raise RateLimitError(
                "O limite gratuito da Groq foi atingido. Tente novamente mais tarde."
            ) from exc
        except groq.APIError as exc:
            raise AIError("A Groq não conseguiu gerar uma resposta.") from exc

        content = completion.choices[0].message.content if completion.choices else None
        if not content or not content.strip():
            raise AIError("A Groq retornou uma resposta vazia.")
        return content.strip()[:max_characters]

    async def transcribe_audio(self, audio: Path) -> str:
        payload = await asyncio.to_thread(audio.read_bytes)
        try:
            transcription = await asyncio.wait_for(
                self._client.audio.transcriptions.create(
                    model=self._transcription_model,
                    file=(audio.name, payload, "audio/flac"),
                    response_format="json",
                ),
                timeout=self._timeout_seconds,
            )
        except (TimeoutError, groq.APITimeoutError) as exc:
            raise OperationTimeoutError("Groq speech recognition timed out.") from exc
        except groq.RateLimitError as exc:
            raise RateLimitError(
                "The Groq speech recognition limit was reached. Try again later."
            ) from exc
        except groq.APIError as exc:
            raise AIError("Groq could not transcribe the audio.") from exc

        text = transcription.text.strip()
        if not text:
            raise AIError("Groq returned an empty transcription.")
        return text

    async def close(self) -> None:
        await self._client.close()
