"""
CuttOffl Backend - Audio-Wellenform-Extraktion.

Extrahiert eine kompakte Peak-Repräsentation der Audio-Spur über ffmpeg
als Roh-PCM (16-bit mono, 8 kHz), bucketed in N Samples/Sekunde und
als JSON abgelegt. Das Frontend malt daraus die Waveform unter das
Thumbnail-Band.

Format (klein und schnell):
  {
    "samples_per_second": 50,
    "count": 12345,
    "peaks": [0.0, 0.1, 0.8, ...]    // Werte 0..1
  }
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import struct
from pathlib import Path
from typing import Optional

from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


DEFAULT_SAMPLES_PER_SECOND = 50
PCM_RATE = 8000  # Hz für die Zwischenberechnung (reicht für Waveform)


async def generate_waveform(
    source: Path,
    dest: Path,
    duration_s: Optional[float],
    samples_per_second: int = DEFAULT_SAMPLES_PER_SECOND,
) -> dict:
    """Liest Audio aus `source`, berechnet Peaks und schreibt JSON nach `dest`."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    # ffmpeg liefert rohes PCM s16le mono 8000 Hz auf stdout
    args = [
        ffmpeg_binary(),
        "-hide_banner", "-loglevel", "error",
        "-i", str(source),
        "-vn",
        "-ac", "1",
        "-ar", str(PCM_RATE),
        "-f", "s16le",
        "-",
    ]
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err = stderr.decode("utf-8", errors="replace").strip()
        # Video ohne Audio → leere Waveform schreiben statt zu failen
        if "does not contain any stream" in err or "Invalid data" in err or not stdout:
            payload = {"samples_per_second": samples_per_second, "count": 0, "peaks": []}
            dest.write_text(json.dumps(payload), encoding="utf-8")
            return {"samples": 0, "rate": float(samples_per_second)}
        raise RuntimeError(f"Waveform-Extraktion fehlgeschlagen: {err}")

    total_samples = len(stdout) // 2
    if total_samples == 0:
        payload = {"samples_per_second": samples_per_second, "count": 0, "peaks": []}
        dest.write_text(json.dumps(payload), encoding="utf-8")
        return {"samples": 0, "rate": float(samples_per_second)}

    bucket_size = max(1, int(PCM_RATE // samples_per_second))
    count = int(math.ceil(total_samples / bucket_size))
    peaks: list[float] = [0.0] * count

    fmt = f"<{bucket_size}h"
    fmt_size = bucket_size * 2
    data = stdout
    max_abs = 32767.0

    # Block-weise scannen, Peak pro Bucket
    for i in range(count):
        start = i * fmt_size
        chunk = data[start:start + fmt_size]
        if len(chunk) == fmt_size:
            vals = struct.unpack(fmt, chunk)
        elif len(chunk) >= 2:
            # letzter, evtl. kleinerer Bucket
            vals = struct.unpack(f"<{len(chunk)//2}h", chunk[: (len(chunk)//2) * 2])
        else:
            vals = (0,)
        peak = max(abs(v) for v in vals)
        peaks[i] = round(peak / max_abs, 4)

    payload = {
        "samples_per_second": samples_per_second,
        "count": count,
        "peaks": peaks,
    }
    dest.write_text(json.dumps(payload), encoding="utf-8")
    logger.info(f"Waveform fertig: {dest.name} ({count} Peaks, {samples_per_second}/s)")
    return {"samples": count, "rate": float(samples_per_second)}
