"""
CuttOffl Backend - Codec-Empfehlungen je nach erkannter Umgebung.

Die optimale Codec-Wahl haengt stark vom Host ab:

  - Mac (Apple Silicon, VideoToolbox): H.264 und HEVC werden beide in
    Hardware beschleunigt. HEVC kostet kaum mehr Zeit, erzeugt aber
    30-50 % kleinere Dateien. Standardempfehlung: HEVC, mit H.264 als
    Kompatibilitaets-Option.

  - Raspberry Pi 5 (ARM Cortex-A76, V4L2): der V4L2-HW-Encoder
    (h264_v4l2m2m) kann nur H.264 und liefert oft schlechtere Qualitaet
    als libx264. HEVC gibt es nur via libx265 -- deutlich langsamer.
    Standardempfehlung: libx264 -preset fast.

  - Linux/andere ohne HW-Accel: Software-libx264 ist der Allrounder.
"""

from __future__ import annotations

import asyncio
import logging
import platform
from typing import Optional

from app.services.ffmpeg_service import ffmpeg_binary

logger = logging.getLogger(__name__)


_cache: Optional[dict] = None


async def _list_encoders() -> str:
    proc = await asyncio.create_subprocess_exec(
        ffmpeg_binary(), "-hide_banner", "-encoders",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    return stdout.decode("utf-8", errors="replace")


async def get_recommendations(force: bool = False) -> dict:
    """Liefert Plattform-Info + Codec-Empfehlungen in UI-freundlicher Form."""
    global _cache
    if _cache is not None and not force:
        return _cache

    encoders = ""
    try:
        encoders = await _list_encoders()
    except Exception as e:
        logger.warning(f"Encoder-Liste nicht ermittelbar: {e}")

    sys = platform.system()
    mach = platform.machine()

    have_vt_h264 = "h264_videotoolbox" in encoders
    have_vt_hevc = "hevc_videotoolbox" in encoders
    have_v4l2    = "h264_v4l2m2m"      in encoders
    have_x264    = "libx264"           in encoders
    have_x265    = "libx265"           in encoders

    if have_vt_h264 or have_vt_hevc:
        env = "apple-silicon"
        env_label = "Apple Silicon (Mac)"
    elif have_v4l2:
        env = "raspberry-pi"
        env_label = "Raspberry Pi / V4L2"
    else:
        env = "software"
        env_label = "Software-Encoder"

    recs: list[dict] = []

    if env == "apple-silicon":
        if have_vt_hevc:
            recs.append({
                "id":      "hevc",
                "codec":   "hevc",
                "encoder": "hevc_videotoolbox",
                "label":   "HEVC (H.265)",
                "tag":     "klein & schnell",
                "speed":   "fast",
                "note":    "Etwa 30-50 % kleinere Datei als H.264 bei vergleichbarer "
                           "Qualitaet. Auf deinem Mac wird HEVC in Hardware beschleunigt, "
                           "Render ist also ungefaehr so schnell wie bei H.264. "
                           "Wiedergabe ab iOS 11, macOS High Sierra, Windows 10 (mit "
                           "Codec) oder VLC problemlos; aeltere Geraete koennen HEVC "
                           "aber nicht abspielen.",
                "default": True,
            })
        if have_vt_h264:
            recs.append({
                "id":      "h264",
                "codec":   "h264",
                "encoder": "h264_videotoolbox",
                "label":   "H.264",
                "tag":     "weit kompatibel",
                "speed":   "fast",
                "note":    "H.264 ist ueberall abspielbar -- vom alten Smartphone bis "
                           "zum Fernseher. Auf deinem Mac wird der Render in Hardware "
                           "beschleunigt und ist sehr schnell. Dateien werden nur "
                           "etwas groesser als bei HEVC.",
                "default": not have_vt_hevc,
            })

    elif env == "raspberry-pi":
        if have_x264:
            recs.append({
                "id":      "h264",
                "codec":   "h264",
                "encoder": "libx264",
                "label":   "H.264",
                "tag":     "weit kompatibel",
                "speed":   "medium",
                "note":    "Ueberall abspielbar. Auf dem Pi wird H.264 per Software "
                           "berechnet (optional auch ueber den V4L2-Hardware-Encoder, "
                           "dann mit etwas weniger Qualitaet). Render-Zeit merklich "
                           "laenger als auf einem Mac, aber noch alltagstauglich.",
                "default": True,
            })
        if have_x265:
            recs.append({
                "id":      "hevc",
                "codec":   "hevc",
                "encoder": "libx265",
                "label":   "HEVC (H.265)",
                "tag":     "kleiner, aber langsam",
                "speed":   "slow",
                "note":    "Kleinere Dateien als H.264. Auf dem Pi wird HEVC nur per "
                           "Software berechnet, der Render ist deshalb deutlich langsamer. "
                           "Fuer kurze Clips in Ordnung, fuer lange Videos eher nicht "
                           "praktikabel.",
            })

    else:  # software
        if have_x264:
            recs.append({
                "id":      "h264",
                "codec":   "h264",
                "encoder": "libx264",
                "label":   "H.264",
                "tag":     "weit kompatibel",
                "speed":   "medium",
                "note":    "Ueberall abspielbar. Render wird per Software berechnet, "
                           "Geschwindigkeit haengt von der CPU ab.",
                "default": True,
            })
        if have_x265:
            recs.append({
                "id":      "hevc",
                "codec":   "hevc",
                "encoder": "libx265",
                "label":   "HEVC (H.265)",
                "tag":     "kleiner, aber langsam",
                "speed":   "slow",
                "note":    "Kleinere Dateien als H.264, dafuer deutlich laengere "
                           "Render-Zeit. Nur sinnvoll, wenn Dateigroesse wichtiger "
                           "als Geschwindigkeit ist.",
            })

    _cache = {
        "platform": {
            "env": env,
            "env_label": env_label,
            "system": sys,
            "machine": mach,
        },
        "encoders_available": {
            "h264_videotoolbox": have_vt_h264,
            "hevc_videotoolbox": have_vt_hevc,
            "h264_v4l2m2m":      have_v4l2,
            "libx264":           have_x264,
            "libx265":           have_x265,
        },
        "recommendations": recs,
    }
    return _cache
