import asyncio
from pathlib import Path
from typing import Any

import pytest

from comradbot.audio.ffmpeg import FFmpegRunner


class HangingProcess:
    def __init__(self) -> None:
        self.returncode = 0
        self.communicate_started = asyncio.Event()
        self.killed = False
        self.waited = False

    async def communicate(self) -> tuple[bytes, bytes]:
        self.communicate_started.set()
        await asyncio.Event().wait()
        return b"", b""

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        self.waited = True
        return self.returncode


@pytest.mark.asyncio
async def test_probe_cancellation_terminates_ffprobe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = HangingProcess()
    runner = FFmpegRunner()
    monkeypatch.setattr(runner, "verify_tools", lambda: ("ffmpeg", "ffprobe"))

    async def create_process(*args: object, **kwargs: object) -> Any:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    task = asyncio.create_task(runner.probe(tmp_path / "sound.wav"))
    await asyncio.wait_for(process.communicate_started.wait(), timeout=0.5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.killed is True
    assert process.waited is True


@pytest.mark.asyncio
async def test_conversion_cancellation_terminates_ffmpeg_and_removes_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    process = HangingProcess()
    runner = FFmpegRunner()
    destination = tmp_path / "converted.opus"
    destination.write_bytes(b"partial")
    monkeypatch.setattr(runner, "verify_tools", lambda: ("ffmpeg", "ffprobe"))

    async def create_process(*args: object, **kwargs: object) -> Any:
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", create_process)
    task = asyncio.create_task(runner.convert_to_opus(tmp_path / "source.wav", destination))
    await asyncio.wait_for(process.communicate_started.wait(), timeout=0.5)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert process.killed is True
    assert process.waited is True
    assert not destination.exists()
