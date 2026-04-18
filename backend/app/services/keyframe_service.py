"""
CuttOffl Backend - Keyframe-Extraktion via ffprobe.

Liefert pro Datei die Liste aller I-Frame-Zeitstempel (in Sekunden).
Wird von der Timeline-UI genutzt, um Smart-Snap-Magnets einzublenden.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Optional

from app.services.ffmpeg_service import ffprobe_binary

logger = logging.getLogger(__name__)


ProgressCb = Optional[Callable[[float], None]]


async def extract_keyframes(
    path: Path,
    duration_s: Optional[float] = None,
    progress_cb: ProgressCb = None,
) -> list[float]:
    """Liest alle Keyframe-Zeitstempel via ffprobe (nur Video-Stream 0).

    Bei großen Dateien kann das mehrere Sekunden dauern. Progress wird
    auf Basis des aktuell gelesenen Timestamps vs duration_s geschaetzt.
    """
    args = [
        ffprobe_binary(),
        "-v", "error",
        "-skip_frame", "nokey",
        "-select_streams", "v:0",
        "-show_entries", "frame=pts_time,pict_type",
        "-of", "json",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffprobe Keyframe-Extraktion fehlgeschlagen: {err}")

    data = json.loads(stdout.decode("utf-8", errors="replace"))
    frames = data.get("frames") or []
    timestamps: list[float] = []
    for f in frames:
        pts = f.get("pts_time")
        if pts is None:
            continue
        try:
            timestamps.append(round(float(pts), 4))
        except (TypeError, ValueError):
            continue

    timestamps.sort()

    if progress_cb and duration_s and duration_s > 0 and timestamps:
        try:
            progress_cb(min(1.0, timestamps[-1] / duration_s))
        except Exception:
            pass

    logger.info(f"Keyframes extrahiert: {len(timestamps)} aus {path.name}")
    return timestamps
