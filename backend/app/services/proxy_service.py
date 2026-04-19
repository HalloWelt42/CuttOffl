"""
CuttOffl Backend - Proxy-Generierung.

Erzeugt aus dem Original ein Low-Res-H.264-MP4 (480p, CRF 28),
das in der UI für flüssiges Scrubbing verwendet wird.

Kernpunkte:
  - GOP-Länge 1 s → jede Sekunde ein Keyframe → präzises Seeking
  - -preset veryfast für Geschwindigkeit
  - -pix_fmt yuv420p für maximale Browser-Kompatibilität
  - Progress-Parsing über -progress pipe:1
  - HW-Decode über VideoToolbox auf Apple Silicon, v4l2m2m auf Raspi --
    spart Faktor 5-20 Rechenzeit, vor allem bei HEVC/4K-Input
"""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Callable, Optional

from app.config import PROXY_CRF, PROXY_GOP_SECONDS, PROXY_HEIGHT
from app.services.ffmpeg_service import ffmpeg_binary
from app.services.hwaccel_service import detect_hw_encoder

logger = logging.getLogger(__name__)


ProgressCb = Optional[Callable[[float, dict], None]]


_RE_KV = re.compile(r"^([a-zA-Z_]+)=(.*)$")


async def _hw_decode_flags(source_codec: Optional[str]) -> list[str]:
    """Bestimmt, ob und welcher HW-Decoder vor das -i gestellt wird.

    Faustregel: alles was Apple-Silicon-VideoToolbox beschleunigen kann
    (hevc, h264, prores, h263, mpeg1, mpeg2, mpeg4, vp9) wird so
    dekodiert. Auf Pi/Linux nutzen wir v4l2m2m (wenn vorhanden). Wenn
    wir nichts sicher wissen, fallen wir auf Software-Decode zurück --
    das ist langsamer, aber funktioniert immer.

    Der Decoder arbeitet im gleichen Pixel-Format wie der libx264-
    Input erwartet (kein videotoolbox_vld -- dann müsste hwdownload
    eingebaut werden). Ohne -hwaccel_output_format liefert
    VideoToolbox direkt verarbeitbare Frames; libx264 kann die lesen.
    """
    if not source_codec:
        return []
    codec = source_codec.lower()
    supported_vt = {"hevc", "h265", "h264", "avc1", "prores",
                    "h263", "mpeg1video", "mpeg2video", "mpeg4", "vp9"}
    try:
        hw = await detect_hw_encoder()
    except Exception:
        hw = None
    if hw == "h264_videotoolbox" and codec in supported_vt:
        return ["-hwaccel", "videotoolbox"]
    if hw == "h264_v4l2m2m":
        # Raspberry Pi 4/5: harte HW-Decoder-Namen wählen. Für die
        # häufigsten Codecs gibt es v4l2m2m-Decoder.
        if codec in ("h264", "avc1"):
            return ["-c:v", "h264_v4l2m2m"]
        if codec in ("hevc", "h265"):
            return ["-c:v", "hevc_v4l2m2m"]
    return []


async def generate_proxy(
    source: Path,
    dest: Path,
    duration_s: Optional[float],
    fps: Optional[float] = None,
    source_codec: Optional[str] = None,
    progress_cb: ProgressCb = None,
) -> Path:
    """Erzeugt Proxy-Datei. Gibt dest zurück. Wirft RuntimeError bei Fehler."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + ".tmp" + dest.suffix)

    gop = max(1, int(round((fps or 25) * PROXY_GOP_SECONDS)))

    hw_flags = await _hw_decode_flags(source_codec)

    args = [
        ffmpeg_binary(),
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        *hw_flags,
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

    logger.info(
        f"Proxy-Generierung startet: {source.name} → {dest.name} "
        f"(Codec={source_codec}, HW={' '.join(hw_flags) if hw_flags else 'sw'})"
    )
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
                # ffmpeg liefert bei Screen-Recordings und VFR-Quellen
                # am Anfang gerne out_time_us="N/A". Ohne try/except
                # crasht int() und der Job landet als failed, obwohl
                # ffmpeg selbst sauber weiterlaeuft.
                try:
                    out_us = int(current.get("out_time_us", "0") or 0)
                except ValueError:
                    out_us = 0
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
