"""
CuttOffl Backend - Upload-Router.

Standard-Multipart-Upload. Nach erfolgreichem Upload wird sofort ffprobe auf
die Datei angewendet, die Metadaten in der files-Tabelle persistiert und die
Folgearbeiten angestossen: Thumbnail-Job (schnell) und Proxy-Job (laenger,
triggert seinerseits Sprite- und Waveform-Extraktion).
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.config import ALLOWED_EXTENSIONS, MAX_UPLOAD_MB, ORIGINALS_DIR
from app.db import db
from app.models.schemas import FileOut, UploadStartResponse
from app.services.folder_service import FolderError, normalize as normalize_folder
from app.services.job_service import job_service
from app.services.probe_service import probe_file, summarize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/upload", tags=["upload"])


@router.post("", response_model=UploadStartResponse)
async def upload(
    file: UploadFile = File(...),
    folder: str = Form(default=""),
) -> UploadStartResponse:
    filename = file.filename or "upload.bin"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Dateiendung {suffix!r} nicht erlaubt. Erlaubt: {sorted(ALLOWED_EXTENSIONS)}",
        )
    try:
        folder_path = normalize_folder(folder)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=f"Ungueltiger Ordner: {e}")

    file_id = uuid.uuid4().hex
    stored_name = f"{file_id}{suffix}"
    dest = ORIGINALS_DIR / stored_name

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    async with aiofiles.open(dest, "wb") as out:
        while True:
            chunk = await file.read(1024 * 1024)
            if not chunk:
                break
            written += len(chunk)
            if written > max_bytes:
                await out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(
                    status_code=413,
                    detail=f"Datei zu groß (> {MAX_UPLOAD_MB} MB).",
                )
            await out.write(chunk)

    probe_summary: dict = {}
    probe_raw: dict = {}
    try:
        probe_raw = await probe_file(dest)
        probe_summary = summarize(probe_raw)
    except Exception as e:
        logger.warning(f"ffprobe nach Upload fehlgeschlagen: {e}")

    await db.execute(
        """
        INSERT INTO files (
            id, original_name, stored_name, path, size_bytes,
            mime_type, duration_s, width, height, fps,
            video_codec, audio_codec, folder_path, probe_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            file_id,
            filename,
            stored_name,
            str(dest),
            written,
            file.content_type,
            probe_summary.get("duration_s"),
            probe_summary.get("width"),
            probe_summary.get("height"),
            probe_summary.get("fps"),
            probe_summary.get("video_codec"),
            probe_summary.get("audio_codec"),
            folder_path,
            json.dumps(probe_raw) if probe_raw else None,
        ),
    )

    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    assert row is not None

    thumb_job_id = await job_service.enqueue("thumbnail", file_id=file_id)
    proxy_job_id = await job_service.enqueue("proxy", file_id=file_id)

    return UploadStartResponse(
        file=FileOut(
            id=row["id"],
            original_name=row["original_name"],
            stored_name=row["stored_name"],
            size_bytes=row["size_bytes"],
            mime_type=row["mime_type"],
            duration_s=row["duration_s"],
            width=row["width"],
            height=row["height"],
            fps=row["fps"],
            video_codec=row["video_codec"],
            audio_codec=row["audio_codec"],
            has_proxy=bool(row["has_proxy"]),
            proxy_status=row["proxy_status"],
            has_thumb=bool(row["thumb_path"]),
            has_sprite=bool(row["sprite_path"]),
            has_waveform=bool(row["waveform_path"]),
            keyframe_count=row["keyframe_count"],
            folder_path=row["folder_path"] if "folder_path" in row.keys() else "",
            created_at=row["created_at"],
        ),
        proxy_job_id=proxy_job_id,
        thumb_job_id=thumb_job_id,
    )
