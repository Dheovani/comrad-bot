"""OpenAI implementation using the current Responses and Speech APIs."""

import asyncio
from collections.abc import Sequence
from pathlib import Path

import openai
from openai import AsyncOpenAI

from comradbot.ai.models import AIMessage
from comradbot.ai.prompts import COMRADBOT_PERSONA
from comradbot.errors import AIError, OperationTimeoutError, RateLimitError


class OpenAIProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        tts_model: str,
        tts_voice: str,
        timeout_seconds: float,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_seconds, max_retries=1)
        self._model = model
        self._tts_model = tts_model
        self._tts_voice = tts_voice
        self._timeout_seconds = timeout_seconds

    async def generate_response(self, messages: Sequence[AIMessage], *, max_characters: int) -> str:
        input_messages: list[dict[str, str]] = [message.model_dump() for message in messages]
        try:
            response = await asyncio.wait_for(
                self._client.responses.create(
                    model=self._model,
                    instructions=(
                        f"{COMRADBOT_PERSONA}\nResponda com no máximo {max_characters} caracteres."
                    ),
                    input=input_messages,  # type: ignore[arg-type]
                ),
                timeout=self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise OperationTimeoutError("A IA demorou demais para responder.") from exc
        except openai.RateLimitError as exc:
            raise RateLimitError("A IA atingiu o limite do provedor. Tente mais tarde.") from exc
        except openai.APIError as exc:
            raise AIError("O provedor de IA não conseguiu responder.") from exc
        text = response.output_text.strip()
        if not text:
            raise AIError("A IA retornou uma resposta vazia.")
        return text[:max_characters]

    async def generate_speech(self, text: str, destination: Path) -> None:
        try:
            async with self._client.audio.speech.with_streaming_response.create(
                model=self._tts_model,
                voice=self._tts_voice,
                input=text,
                response_format="opus",
            ) as response:
                await asyncio.wait_for(
                    response.stream_to_file(destination), timeout=self._timeout_seconds
                )
        except TimeoutError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise OperationTimeoutError("A geração de voz excedeu o tempo limite.") from exc
        except openai.RateLimitError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise RateLimitError("O TTS atingiu o limite do provedor.") from exc
        except openai.APIError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise AIError("O provedor não conseguiu gerar a fala.") from exc
