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
    has_proxy: bool = False
    proxy_status: str = "none"
    has_thumb: bool = False
    has_sprite: bool = False
    has_waveform: bool = False
    keyframe_count: Optional[int] = None
    folder_path: str = ""
    created_at: str


class UploadStartResponse(BaseModel):
    file: "FileOut"
    proxy_job_id: str
    thumb_job_id: str


class FileRenameBody(BaseModel):
    original_name: str = Field(min_length=1, max_length=255)


class FileMoveBody(BaseModel):
    folder_path: str = Field(default="", max_length=512)


class FileBulkMoveBody(BaseModel):
    file_ids: list[str] = Field(min_length=1, max_length=500)
    folder_path: str = Field(default="", max_length=512)


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
