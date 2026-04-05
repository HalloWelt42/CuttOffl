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
                "id":      "small",
                "codec":   "hevc",
                "encoder": "hevc_videotoolbox",
                "label":   "HEVC (H.265) mit VideoToolbox",
                "tag":     "klein",
                "note":    "Rund 30-50 % kleinere Datei als H.264 bei vergleichbarer "
                           "Qualitaet. Wiedergabe ab iOS 11, macOS High Sierra, Windows 10 "
                           "(mit Codec) oder VLC problemlos. Nicht optimal fuer aeltere Geraete.",
                "default": True,
            })
        if have_vt_h264:
            recs.append({
                "id":      "fast",
                "codec":   "h264",
                "encoder": "h264_videotoolbox",
                "label":   "H.264 mit VideoToolbox",
                "tag":     "kompatibel",
                "note":    "Ueberall abspielbar. Auf Apple Silicon sehr schnell und "
                           "in guter Qualitaet. Etwas groessere Dateien als HEVC.",
                "default": not have_vt_hevc,
            })
        if have_x264:
            recs.append({
                "id":      "software",
                "codec":   "h264",
                "encoder": "libx264",
                "label":   "H.264 Software (libx264)",
                "tag":     "vorsichtig",
                "note":    "Reiner Software-Encoder, etwas besser konfigurierbar. Deutlich "
                           "langsamer als VideoToolbox, hier selten noetig.",
            })

    elif env == "raspberry-pi":
        if have_x264:
            recs.append({
                "id":      "fast",
                "codec":   "h264",
                "encoder": "libx264",
                "label":   "H.264 Software (libx264 fast)",
                "tag":     "empfohlen",
                "note":    "Auf dem Pi 5 liefert libx264 meist bessere Qualitaet als der "
                           "V4L2-Hardware-Encoder. Preset 'fast' ist ein guter Kompromiss.",
                "default": True,
            })
        if have_v4l2:
            recs.append({
                "id":      "turbo",
                "codec":   "h264",
                "encoder": "h264_v4l2m2m",
                "label":   "H.264 Hardware (V4L2)",
                "tag":     "schnell, grob",
                "note":    "Hardware-Encoder auf dem Pi. Spart CPU, Qualitaet teils "
                           "merklich schlechter als libx264. Nur wenn Geschwindigkeit klar "
                           "Prioritaet hat.",
            })
        if have_x265:
            recs.append({
                "id":      "small",
                "codec":   "hevc",
                "encoder": "libx265",
                "label":   "HEVC Software (libx265)",
                "tag":     "langsam, klein",
                "note":    "Kleinere Dateien, aber auf dem Pi sehr langsam. Fuer lange "
                           "Videos oft nicht praxistauglich.",
            })

    else:  # software
        if have_x264:
            recs.append({
                "id":      "fast",
                "codec":   "h264",
                "encoder": "libx264",
                "label":   "H.264 Software (libx264)",
                "tag":     "empfohlen",
                "note":    "Allround-Codec. Ueberall abspielbar, solide Qualitaet.",
                "default": True,
            })
        if have_x265:
            recs.append({
                "id":      "small",
                "codec":   "hevc",
                "encoder": "libx265",
                "label":   "HEVC Software (libx265)",
                "tag":     "langsam, klein",
                "note":    "Kleinere Dateien, aber deutlich langsamer. Nur wenn "
                           "Dateigroesse wichtiger als Render-Zeit ist.",
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
