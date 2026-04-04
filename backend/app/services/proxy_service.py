"""
CuttOffl Backend - Proxy-Generierung.

Erzeugt aus dem Original ein Low-Res-H.264-MP4 (480p, CRF 28),
das in der UI für flüssiges Scrubbing verwendet wird.

Kernpunkte:
  - GOP-Länge 1 s → jede Sekunde ein Keyframe → präzises Seeking
  - -preset veryfast für Geschwindigkeit
  - -pix_fmt yuv420p für maximale Browser-Kompatibilität
  - Progress-Parsing über -progress pipe:1
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Callable, Optional

from app.config import PROXY_CRF, PROXY_GOP_SECONDS, PROXY_HEIGHT
from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


ProgressCb = Optional[Callable[[float, dict], None]]


_RE_KV = re.compile(r"^([a-zA-Z_]+)=(.*)$")


async def generate_proxy(
    source: Path,
    dest: Path,
    duration_s: Optional[float],
    fps: Optional[float] = None,
    progress_cb: ProgressCb = None,
) -> Path:
    """Erzeugt Proxy-Datei. Gibt dest zurück. Wirft RuntimeError bei Fehler."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".tmp" + dest.suffix)

    gop = max(1, int(round((fps or 25) * PROXY_GOP_SECONDS)))

    args = [
        ffmpeg_binary(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-i", str(source),
        "-vf", f"scale=-2:{PROXY_HEIGHT}",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", str(PROXY_CRF),
        "-pix_fmt", "yuv420p",
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-force_key_frames", f"expr:gte(t,n_forced*{PROXY_GOP_SECONDS})",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        "-progress", "pipe:1",
        "-nostats",
        str(tmp),
    ]

    logger.info(f"Proxy-Generierung startet: {source.name} → {dest.name}")
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    assert proc.stdout is not None
    current: dict = {}
    try:
        async for line in proc.stdout:
            text = line.decode("utf-8", errors="replace").strip()
            m = _RE_KV.match(text)
            if not m:
                continue
            key, value = m.group(1), m.group(2)
            current[key] = value
            if key == "progress":
                out_us = int(current.get("out_time_us", "0") or 0)
                out_s = out_us / 1_000_000.0
                pct = 0.0
                if duration_s and duration_s > 0:
                    pct = max(0.0, min(1.0, out_s / duration_s))
                if progress_cb is not None:
                    try:
                        progress_cb(pct, dict(current))
                    except Exception as e:
                        logger.debug(f"progress_cb Fehler: {e}")
                current.clear()
                if value in ("end",):
                    break
    finally:
        await proc.wait()

    if proc.returncode != 0:
        err = (await proc.stderr.read()).decode("utf-8", errors="replace") if proc.stderr else ""
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"Proxy-Generierung fehlgeschlagen: {err.strip()}")

    tmp.replace(dest)
    logger.info(f"Proxy fertig: {dest.name}")
    if progress_cb is not None:
        try:
            progress_cb(1.0, {"progress": "end"})
        except Exception:
            pass
    return dest
