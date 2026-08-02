"""Portuguese-capable TTS through the official asynchronous ElevenLabs SDK."""

import asyncio
from pathlib import Path

import httpx
from elevenlabs.client import AsyncElevenLabs
from elevenlabs.core.api_error import ApiError
from elevenlabs.core.request_options import RequestOptions

from comradbot.errors import AIError, OperationTimeoutError, RateLimitError


class ElevenLabsSpeechProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        voice_id: str,
        timeout_seconds: float,
        max_file_size_bytes: int,
    ) -> None:
        self._http_client = httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True)
        self._client = AsyncElevenLabs(api_key=api_key, httpx_client=self._http_client)
        self._model = model
        self._voice_id = voice_id
        self._timeout_seconds = timeout_seconds
        self._max_file_size_bytes = max_file_size_bytes

    async def generate_speech(self, text: str, destination: Path) -> None:
        written = 0
        try:
            async with asyncio.timeout(self._timeout_seconds):
                audio = await self._client.text_to_speech.convert(
                    self._voice_id,
                    text=text,
                    model_id=self._model,
                    output_format="opus_48000_64",
                    language_code="pt",
                    request_options=RequestOptions(max_retries=1),
                )
                with destination.open("wb") as output:
                    async for chunk in audio:
                        written += len(chunk)
                        if written > self._max_file_size_bytes:
                            raise AIError("A fala gerada excedeu o limite de tamanho configurado.")
                        await asyncio.to_thread(output.write, chunk)
                if written == 0:
                    raise AIError("A ElevenLabs retornou um áudio vazio.")
        except TimeoutError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise OperationTimeoutError("A geração de voz excedeu o tempo limite.") from exc
        except ApiError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            if exc.status_code == 429:
                raise RateLimitError("O TTS atingiu o limite gratuito da ElevenLabs.") from exc
            raise AIError("A ElevenLabs não conseguiu gerar a fala.") from exc
        except httpx.HTTPError as exc:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise AIError("A ElevenLabs não conseguiu gerar a fala.") from exc
        except BaseException:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise

    async def close(self) -> None:
        await self._http_client.aclose()
