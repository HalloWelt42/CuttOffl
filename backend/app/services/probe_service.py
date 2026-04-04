"""
CuttOffl Backend - ffprobe Wrapper.

Liest Metadaten (Dauer, Auflösung, Codec, FPS) aus Video-Dateien.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from app.services.ffmpeg_service import ffprobe_binary

logger = logging.getLogger(__name__)


async def probe_file(path: Path) -> dict:
    """Ruft ffprobe auf und gibt das rohe JSON-Ergebnis zurück."""
    args = [
        ffprobe_binary(),
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe fehlgeschlagen: {stderr.decode('utf-8', errors='replace')}")
    return json.loads(stdout.decode("utf-8", errors="replace"))


def _parse_fps(rate: str) -> Optional[float]:
    if not rate or rate == "0/0":
        return None
    try:
        num, den = rate.split("/")
        den_f = float(den)
        if den_f == 0:
            return None
        return round(float(num) / den_f, 3)
    except Exception:
        return None


def summarize(probe: dict) -> dict:
    """Reduziert das ffprobe-JSON auf die Kernfelder."""
    fmt = probe.get("format") or {}
    streams = probe.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = None
    if fmt.get("duration"):
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            pass

    width = height = fps = None
    video_codec = audio_codec = None
    if video is not None:
        width = video.get("width")
        height = video.get("height")
        fps = _parse_fps(video.get("avg_frame_rate") or video.get("r_frame_rate") or "")
        video_codec = video.get("codec_name")
    if audio is not None:
        audio_codec = audio.get("codec_name")

    return {
        "duration_s": duration,
        "width": width,
        "height": height,
        "fps": fps,
        "video_codec": video_codec,
        "audio_codec": audio_codec,
    }
