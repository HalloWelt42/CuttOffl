"""
CuttOffl Backend - Thumbnail-Sprite-Erzeugung.

Ein Sprite ist ein einziges JPEG, auf dem regelmäßig gesampelte Frames
des Videos in einem Raster nebeneinander liegen. Die Timeline legt das
Bild als Hintergrund über das Video-Band und zeigt so auf einen Blick,
was an welcher Position passiert.

  - Interval: jede Sekunde oder alle N Sekunden ein Frame
  - Tile-Größe: 160×90 (16:9), klein genug für schnelles Laden
  - Cols: 10 Tiles pro Zeile
"""

from __future__ import annotations

import asyncio
import logging
import math
from pathlib import Path
from typing import Optional

from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


DEFAULT_INTERVAL = 2.0
DEFAULT_TILE_W = 160
DEFAULT_TILE_H = 90
DEFAULT_COLS = 10


async def generate_sprite(
    source: Path,
    dest: Path,
    duration_s: Optional[float],
    interval: float = DEFAULT_INTERVAL,
    tile_w: int = DEFAULT_TILE_W,
    tile_h: int = DEFAULT_TILE_H,
    cols: int = DEFAULT_COLS,
) -> dict:
    """Erzeugt ein Sprite-JPEG aus `source` und gibt Meta-Daten zurück."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    if not duration_s or duration_s <= 0:
        raise RuntimeError("sprite: duration unbekannt")

    # Bei sehr langen Videos das Interval so erhöhen, dass Sprite-Dimensionen
    # handhabbar bleiben (Max ca. 8192 Pixel Höhe).
    count = max(1, int(math.ceil(duration_s / interval)))
    rows = max(1, int(math.ceil(count / cols)))
    if rows * tile_h > 8000:
        # Interval nachjustieren
        interval = math.ceil(duration_s / (cols * (8000 // tile_h)))
        count = max(1, int(math.ceil(duration_s / interval)))
        rows = max(1, int(math.ceil(count / cols)))

    fps = 1.0 / interval
    # Scale + Tile in einem Durchgang
    vf = f"fps={fps:.6f},scale={tile_w}:{tile_h}:force_original_aspect_ratio=decrease," \
         f"pad={tile_w}:{tile_h}:(ow-iw)/2:(oh-ih)/2,tile={cols}x{rows}"

    args = [
        ffmpeg_binary(),
        "-y", "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-frames:v", "1",
        "-vf", vf,
        "-q:v", "4",
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
            f"Sprite-Generierung fehlgeschlagen: {stderr.decode('utf-8', errors='replace')}"
        )
    logger.info(f"Sprite fertig: {dest.name} ({count} Tiles, {cols}x{rows}, {interval:.1f}s)")
    return {
        "interval": float(interval),
        "tile_w": tile_w,
        "tile_h": tile_h,
        "cols": cols,
        "rows": rows,
        "count": count,
    }
