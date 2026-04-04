"""
CuttOffl Backend - EDL-Schemas (Edit Decision List).

Eine EDL ist die serialisierbare Beschreibung eines Schnitts:
Quelle + Liste von Clips + Output-Profil. Das Backend baut daraus
die FFmpeg-Befehle fuer den Render.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


ClipMode = Literal["copy", "reencode"]
Codec = Literal["h264", "hevc"]
Container = Literal["mp4", "mkv", "mov"]


class Clip(BaseModel):
    id: str
    src_start: float = Field(ge=0.0)
    src_end: float = Field(gt=0.0)
    mode: ClipMode = "copy"
    # reserviert fuer kuenftige Effekte (Fade, Speed, Overlay etc.)
    effects: list[str] = Field(default_factory=list)

    @field_validator("src_end")
    @classmethod
    def _end_after_start(cls, v, info):
        start = (info.data or {}).get("src_start", 0.0)
        if v <= start:
            raise ValueError("src_end muss groesser als src_start sein")
        return v

    @property
    def duration(self) -> float:
        return self.src_end - self.src_start


class OutputProfile(BaseModel):
    codec: Codec = "h264"
    # "source" = Aufloesung vom Original uebernehmen
    resolution: str = "source"   # z. B. "1080p", "720p", "source"
    bitrate: Optional[str] = None  # z. B. "8M"; None = CRF
    crf: Optional[int] = Field(default=23, ge=0, le=51)
    container: Container = "mp4"
    audio_codec: str = "aac"
    audio_bitrate: str = "160k"


class EDL(BaseModel):
    source_file_id: str
    timeline: list[Clip] = Field(default_factory=list)
    output: OutputProfile = Field(default_factory=OutputProfile)


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
