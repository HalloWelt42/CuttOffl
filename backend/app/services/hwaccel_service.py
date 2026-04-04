"""
CuttOffl Backend - HW-Encoder-Detection.

Prüft zur Laufzeit welche Hardware-Encoder ffmpeg kennt:
  - h264_videotoolbox  (Mac M-Serie)
  - h264_v4l2m2m       (Raspberry Pi 5 via V4L2)
  - Fallback: libx264  (Software)
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


_cached: Optional[str] = None


async def _list_encoders() -> str:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_binary(), "-hide_banner", "-encoders",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


async def detect_hw_encoder(force: bool = False) -> str:
    """Liefert den Namen des besten H.264-Encoders für diese Maschine."""
    global _cached
    if _cached and not force:
        return _cached

    try:
        encoders = await _list_encoders()
    except Exception as e:
        logger.warning(f"Encoder-Liste nicht ermittelbar: {e}")
        _cached = "libx264"
        return _cached

    if "h264_videotoolbox" in encoders:
        _cached = "h264_videotoolbox"
    elif "h264_v4l2m2m" in encoders and Path("/dev/video11").exists():
        _cached = "h264_v4l2m2m"
    else:
        _cached = "libx264"

    logger.info(f"HW-Encoder erkannt: {_cached}")
    return _cached
