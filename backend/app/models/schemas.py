"""
CuttOffl Backend - Pydantic-Schemas (API-Modelle).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class PingResponse(BaseModel):
    app: str
    version: str
    status: str = "ok"
    host: str
    port: int
    hw_encoder: str
    ffmpeg_version: Optional[str] = None


class FileOut(BaseModel):
    id: str
    original_name: str
    stored_name: str
    size_bytes: int
    mime_type: Optional[str] = None
    duration_s: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    # Leitet sich aus den Streams ab: audio-only heisst kein Video-
    # Stream in der Quelldatei. Solche Dateien werden in der Library
    # als Waveform-Kachel statt Thumbnail dargestellt und sind als
    # Audio-Track-Override im Editor auswaehlbar.
    is_audio_only: bool = False
    has_proxy: bool = False
    proxy_status: str = "none"
    has_thumb: bool = False
    has_sprite: bool = False
    has_waveform: bool = False
    keyframe_count: Optional[int] = None
    folder_path: str = ""
    tags: list[str] = Field(default_factory=list)
    has_transcript: bool = False
    transcript_lang: Optional[str] = None
    transcript_model: Optional[str] = None
    protected: bool = False
    created_at: str


class UploadStartResponse(BaseModel):
    file: "FileOut"
    # Bei Audio-Only-Files gibt es weder proxy_job_id noch thumb_job_id
    # -- nur einen waveform_job_id. Die Felder sind deshalb optional.
    proxy_job_id: Optional[str] = None
    thumb_job_id: Optional[str] = None
    waveform_job_id: Optional[str] = None


class FileRenameBody(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)


class FileMoveBody(BaseModel):
    folder_path: str = Field(default="", max_length=512)


class FileBulkMoveBody(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=500)
    folder_path: str = Field(default="", max_length=512)


class FileBulkDeleteBody(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=500)


class FileTagsBody(BaseModel):
    tags: list[str] = Field(default_factory=list, max_length=32)


class UploadResponse(BaseModel):
    file: FileOut


class ProbeResponse(BaseModel):
    file_id: str
    duration_s: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    fps: Optional[float] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    raw: dict = Field(default_factory=dict)
