"""Opt-in live checks for external services used by scheduled maintenance CI."""

import argparse
import asyncio
import os
import shlex
import subprocess

from groq import Groq

from comradbot.audio.player import ffmpeg_before_options
from comradbot.audio.resolver import YtDlpAudioResolver


def check_youtube() -> None:
    """Resolve public media and make FFmpeg consume a short stream segment."""
    item = asyncio.run(
        YtDlpAudioResolver(timeout_seconds=30).resolve(
            "Rick Astley Never Gonna Give You Up",
            requester_id=0,
        )
    )
    command = [
        "ffmpeg",
        "-v",
        "error",
        *shlex.split(ffmpeg_before_options(item)),
        "-t",
        "2",
        "-i",
        item.source,
        "-f",
        "null",
        "-",
    ]
    result = subprocess.run(command, capture_output=True, timeout=45, check=False)
    if result.returncode != 0:
        raise RuntimeError(
            f"FFmpeg could not consume the resolved stream (exit {result.returncode})."
        )
    print("YouTube resolver and FFmpeg stream check passed.")


def check_groq_model() -> None:
    """Confirm that the configured Groq model remains available without inference."""
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    model = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is required for the Groq compatibility check.")
    if not model:
        raise RuntimeError("GROQ_MODEL must not be blank.")

    with Groq(api_key=api_key, timeout=20, max_retries=1) as client:
        available_models = {entry.id for entry in client.models.list().data}
    if model not in available_models:
        raise RuntimeError(f"The configured Groq model is unavailable: {model}")
    print(f"Groq model availability check passed: {model}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("check", choices=("youtube", "groq"))
    arguments = parser.parse_args()
    if arguments.check == "youtube":
        check_youtube()
    else:
        check_groq_model()


if __name__ == "__main__":
    main()
