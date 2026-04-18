"""
CuttOffl Backend - EDL-Schemas (Edit Decision List).

Eine EDL ist die serialisierbare Beschreibung eines Schnitts:
Quelle + Liste von Clips + Output-Profil. Das Backend baut daraus
die FFmpeg-Befehle für den Render.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


ClipMode = Literal["copy", "reencode"]
# 'source' heißt: Quell-Codec beim Rendern übernehmen. Wird im
# Render-Service aufgeloest, sobald die Quell-Metadaten bekannt sind.
Codec = Literal["h264", "hevc", "source"]
Container = Literal["mp4", "mkv", "mov"]

# Erlaubte Bitrate-Formate: 500k, 2M, 8M, 800K, 1500000
# Mindestens eine Ziffer (nicht zwei!) -- "8M" ist ein gebräuchlicher
# Wert und muss durchgehen.
_RE_BITRATE = re.compile(r"^\d{1,9}[KkMm]?$")
# Erlaubte Resolution-Formate: 'source', '1080p', '1280x720'
_RE_RES_P   = re.compile(r"^\d{3,4}p$")
_RE_RES_WH  = re.compile(r"^\d{3,5}x\d{3,5}$")


class Clip(BaseModel):
    id: str
    src_start: float = Field(ge=0.0)
    src_end: float = Field(gt=0.0)
    mode: ClipMode = "copy"
    # reserviert für künftige Effekte (Fade, Speed, Overlay etc.)
    effects: list[str] = Field(default_factory=list)

    @field_validator("src_end")
    @classmethod
    def _end_after_start(cls, v, info):
        start = (info.data or {}).get("src_start", 0.0)
        if v <= start:
            raise ValueError("src_end muss größer als src_start sein")
        return v

    @property
    def duration(self) -> float:
        return self.src_end - self.src_start


class OutputProfile(BaseModel):
    codec: Codec = "h264"
    # "source" = Auflösung vom Original übernehmen
    resolution: str = "source"   # z. B. "1080p", "720p", "source"
    bitrate: Optional[str] = None  # z. B. "8M"; None = CRF
    crf: Optional[int] = Field(default=23, ge=0, le=51)
    container: Container = "mp4"
    audio_codec: Literal["aac", "mp3", "opus", "copy"] = "aac"
    audio_bitrate: str = "160k"
    # Audio-Filter. Greifen nur bei reencode -- wenn mindestens einer
    # davon aktiv ist, zwingen wir den Clip auf reencode (copy kann
    # keine Filter anwenden).
    audio_normalize: bool = False   # EBU R128 loudnorm
    audio_mono: bool = False        # Stereo -> Mono mischen
    audio_mute: bool = False        # Tonspur komplett stumm

    @field_validator("resolution")
    @classmethod
    def _validate_resolution(cls, v: str) -> str:
        v = (v or "source").strip().lower()
        if v == "source":
            return v
        if _RE_RES_P.fullmatch(v) or _RE_RES_WH.fullmatch(v):
            return v
        raise ValueError(
            "resolution muss 'source', z. B. '1080p' oder 'BREITExHOEHE' sein"
        )

    @field_validator("bitrate")
    @classmethod
    def _validate_bitrate(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v == "":
            return None
        v = v.strip()
        if not _RE_BITRATE.fullmatch(v):
            raise ValueError(
                "bitrate muss numerisch sein, optional mit K oder M als Suffix "
                "(z. B. '500k', '8M', '1500000')"
            )
        return v

    @field_validator("audio_bitrate")
    @classmethod
    def _validate_audio_bitrate(cls, v: str) -> str:
        v = (v or "160k").strip()
        if not _RE_BITRATE.fullmatch(v):
            raise ValueError("audio_bitrate hat ungültiges Format")
        return v


class EDL(BaseModel):
    source_file_id: str
    timeline: list[Clip] = Field(default_factory=list)
    output: OutputProfile = Field(default_factory=OutputProfile)

    @field_validator("timeline", mode="before")
    @classmethod
    def _sanitize_timeline(cls, v):
        """Filtert degenerierte Clips heraus (src_end <= src_start,
        negative src_start, NaN), bevor die Einzel-Clip-Validierung
        greift. Rundet Zeit-Werte auf 3 Nachkommastellen.

        Grund: das Frontend erzeugt waehrend Drag-Operationen oder
        Animationen kurzfristig degenerate Clips. Frueher hat ein
        Frontend-Sanitize das abgefangen -- jetzt macht das Backend
        das zentral, sonst muessten beide Seiten die Regel kennen.
        """
        if not isinstance(v, list):
            return v
        cleaned = []
        for item in v:
            if not isinstance(item, dict):
                cleaned.append(item)
                continue
            try:
                s = float(item.get("src_start"))
                e = float(item.get("src_end"))
            except (TypeError, ValueError):
                continue
            if not (s >= 0 and e > s):
                continue
            # Flache Kopie, damit der Aufrufer-Dict nicht mutiert wird
            patched = dict(item)
            patched["src_start"] = round(s, 3)
            patched["src_end"] = round(e, 3)
            cleaned.append(patched)
        return cleaned


class ProjectCreate(BaseModel):
    name: str
    source_file_id: str
    edl: Optional[EDL] = None


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    edl: Optional[EDL] = None


class ProjectOut(BaseModel):
    id: str
    name: str
    source_file_id: Optional[str] = None
    edl: EDL
    created_at: str
    updated_at: str


class RenderStartResponse(BaseModel):
    job_id: str
    status: str = "queued"


class SnapResponse(BaseModel):
    file_id: str
    t_input: float
    t_snap: float
    delta: float
    snapped: bool
