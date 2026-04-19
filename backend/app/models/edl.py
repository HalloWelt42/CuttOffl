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


class AudioClip(BaseModel):
    """Ein Audio-Stueck auf der Audio-Spur der EDL.

    - file_id verweist auf eine Audio- oder Video-Datei in der Library;
      der Audio-Stream wird beim Render extrahiert.
    - src_start/src_end schneiden den Clip aus der Quelldatei (in s).
    - timeline_start legt fest, an welcher Stelle der Video-Timeline
      der Clip einsetzt (in s, >= 0). Ist der Clip laenger als das
      Video, wird er beim Render per -shortest abgeschnitten.
    - gain_db (-30..+12), fade_in_s / fade_out_s (0..10) als Effekte.
    - Ein laengerer Audio-Block wird per Split (im UI) in zwei Clips
      mit passenden src_*- und timeline_start-Werten aufgeteilt. Dadurch
      lassen sich Drift-Korrekturen durch Verschieben des rechten Teils
      erledigen, ohne die Quell-Datei zu veraendern.
    """
    id: str
    file_id: str
    src_start: float = Field(ge=0.0)
    src_end: float = Field(gt=0.0)
    timeline_start: float = Field(ge=0.0, default=0.0)
    gain_db: float = Field(default=0.0, ge=-30.0, le=12.0)
    fade_in_s: float = Field(default=0.0, ge=0.0, le=10.0)
    fade_out_s: float = Field(default=0.0, ge=0.0, le=10.0)

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


class EDL(BaseModel):
    source_file_id: str
    timeline: list[Clip] = Field(default_factory=list)
    # Audio-Override-Spur: 0..N Clips, moeglicherweise aus verschiedenen
    # Dateien. Ueberlappen sich Clips zeitlich, werden sie im Render
    # gemischt; Luecken liefern Stille (oder das Original, falls
    # mute_original=False).
    audio_track: list[AudioClip] = Field(default_factory=list)
    # Original-Video-Audio beim Render komplett stummschalten (nur die
    # audio_track-Clips bleiben hoerbar). Default aus, damit bestehende
    # Projekte ohne Audio-Override unveraendert funktionieren.
    mute_original: bool = False
    output: OutputProfile = Field(default_factory=OutputProfile)

    @field_validator("timeline", mode="before")
    @classmethod
    def _sanitize_timeline(cls, v):
        """Filtert degenerierte Clips heraus (src_end <= src_start,
        negative src_start, NaN), bevor die Einzel-Clip-Validierung
        greift. Rundet Zeit-Werte auf 3 Nachkommastellen."""
        return _sanitize_clip_list(v, ("src_start", "src_end"))

    @field_validator("audio_track", mode="before")
    @classmethod
    def _sanitize_audio_track(cls, v):
        """Gleiches Prinzip wie bei timeline: degenerate AudioClips raus
        (src_end <= src_start, negative Werte) und Zeiten runden.
        timeline_start wird ebenfalls gerundet und negativ abgelehnt."""
        return _sanitize_clip_list(
            v, ("src_start", "src_end", "timeline_start"),
        )


def _sanitize_clip_list(v, numeric_fields: tuple[str, ...]) -> list:
    """Shared Helper: filtert ungueltige Clip-Dicts und rundet die
    genannten Felder auf 3 Nachkommastellen. Felder, die in den
    Einzelfeldern required=True mit ge=0.0 sind, duerfen hier nicht
    negativ sein -- wir filtern statt zu werfen, damit eine EDL mit
    einem kaputten Clip nicht die ganze Timeline ablehnt."""
    if not isinstance(v, list):
        return v
    cleaned = []
    for item in v:
        if not isinstance(item, dict):
            cleaned.append(item)
            continue
        try:
            vals = {k: float(item.get(k)) for k in numeric_fields
                    if item.get(k) is not None}
        except (TypeError, ValueError):
            continue
        s = vals.get("src_start")
        e = vals.get("src_end")
        if s is None or e is None:
            continue
        if not (s >= 0 and e > s):
            continue
        tl = vals.get("timeline_start", 0.0)
        if tl < 0:
            continue
        patched = dict(item)
        for k, val in vals.items():
            patched[k] = round(val, 3)
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
