"""
CuttOffl Backend - FFmpeg Subprocess-Wrapper.

Phase 1: nur Versions-Abfrage und generischer Run-Helper.
Spätere Phasen: Proxy-Gen, Render, Concat.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from typing import Optional

logger = logging.getLogger(__name__)


class FfmpegNotFoundError(RuntimeError):
    pass


def ffmpeg_binary() -> str:
    path = shutil.which("ffmpeg")
    if not path:
        raise FfmpegNotFoundError("ffmpeg nicht im PATH gefunden")
    return path


def ffprobe_binary() -> str:
    path = shutil.which("ffprobe")
    if not path:
        raise FfmpegNotFoundError("ffprobe nicht im PATH gefunden")
    return path


async def get_ffmpeg_version() -> Optional[str]:
    try:
        proc = await asyncio.create_subprocess_exec(
            ffmpeg_binary(), "-version",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()
        if proc.returncode != 0:
            return None
        first_line = stdout.decode("utf-8", errors="replace").splitlines()[0]
        return first_line.strip()
    except Exception as e:
        logger.warning(f"ffmpeg-Version nicht ermittelbar: {e}")
        return None


async def run_ffmpeg(args: list[str], timeout: Optional[float] = None) -> tuple[int, str, str]:
    """Führt ffmpeg mit Argumenten aus, gibt (returncode, stdout, stderr) zurück."""
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_binary(), *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    return (
        proc.returncode or 0,
        stdout.decode("utf-8", errors="replace"),
        stderr.decode("utf-8", errors="replace"),
    )
