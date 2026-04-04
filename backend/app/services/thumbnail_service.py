"""
CuttOffl Backend - Thumbnail-Extraktion.

Erzeugt ein einzelnes JPEG-Standbild aus dem Originalvideo
(Breite = config.THUMB_WIDTH). Default-Position: 1/10 der Laufzeit
oder 1 s, je nachdem was später kommt.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.config import THUMB_WIDTH
from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


async def generate_thumbnail(
    source: Path,
    dest: Path,
    duration_s: Optional[float] = None,
    position_s: Optional[float] = None,
) -> Path:
    """Erzeugt ein JPEG-Thumbnail. Gibt dest zurück."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if position_s is None:
        if duration_s and duration_s > 0:
            position_s = max(1.0, duration_s / 10.0)
        else:
            position_s = 1.0

    args = [
        ffmpeg_binary(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-ss", f"{position_s:.3f}",
        "-i", str(source),
        "-frames:v", "1",
        "-vf", f"scale={THUMB_WIDTH}:-2",
        "-q:v", "3",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(
            f"Thumbnail-Generierung fehlgeschlagen: {stderr.decode('utf-8', errors='replace')}"
        )
    return dest
