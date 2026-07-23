"""Safe FFmpeg and FFprobe process wrapper."""

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from comradbot.errors import AudioPlaybackError, OperationTimeoutError, ValidationError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MediaInfo:
    duration_seconds: float
    format_name: str
    has_audio: bool


class FFmpegRunner:
    def __init__(self, *, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    @staticmethod
    def verify_tools() -> tuple[str, str]:
        ffmpeg = shutil.which("ffmpeg")
        ffprobe = shutil.which("ffprobe")
        if ffmpeg is None or ffprobe is None:
            missing = ", ".join(
                name for name, path in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)) if path is None
            )
            raise RuntimeError(
                f"Missing tools on PATH: {missing}. Install FFmpeg and restart the terminal."
            )
        return ffmpeg, ffprobe

    async def probe(self, path: Path) -> MediaInfo:
        _, ffprobe = self.verify_tools()
        process = await asyncio.create_subprocess_exec(
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,format_name:stream=codec_type",
            "-of",
            "json",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, _stderr = await asyncio.wait_for(
                process.communicate(), timeout=self.timeout_seconds
            )
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            raise
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            raise OperationTimeoutError("FFprobe timed out.") from exc
        if process.returncode != 0:
            raise ValidationError("The file does not contain valid supported audio.")
        try:
            payload = json.loads(stdout)
            duration = float(payload["format"]["duration"])
            format_name = str(payload["format"].get("format_name", "unknown"))
            has_audio = any(stream.get("codec_type") == "audio" for stream in payload["streams"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValidationError("The audio metadata could not be read.") from exc
        if not has_audio or duration <= 0:
            raise ValidationError("The file does not contain a playable audio stream.")
        return MediaInfo(duration_seconds=duration, format_name=format_name, has_audio=has_audio)

    async def convert_to_opus(self, source: Path, destination: Path) -> None:
        ffmpeg, _ = self.verify_tools()
        process = await asyncio.create_subprocess_exec(
            ffmpeg,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source),
            "-vn",
            "-map_metadata",
            "-1",
            "-c:a",
            "libopus",
            "-b:a",
            "96k",
            "-y",
            str(destination),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=self.timeout_seconds)
        except asyncio.CancelledError:
            process.kill()
            await process.wait()
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise
        except TimeoutError as exc:
            process.kill()
            await process.wait()
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            raise OperationTimeoutError("Audio conversion timed out.") from exc
        if process.returncode != 0:
            await asyncio.to_thread(destination.unlink, missing_ok=True)
            detail = stderr.decode(errors="replace")[-500:]
            logger.error(
                "FFmpeg conversion failed returncode=%s detail=%s", process.returncode, detail
            )
            raise AudioPlaybackError("FFmpeg could not convert the audio.")
