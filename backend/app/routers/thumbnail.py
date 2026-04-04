"""
CuttOffl Backend - Thumbnail-Router.

  - GET  /api/thumbnail/{id}           JPEG ausliefern
  - POST /api/thumbnail/{id}/generate  Thumbnail-Job manuell anstoßen
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import db
from app.services.job_service import job_service

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])


@router.post("/{file_id}/generate")
async def generate(file_id: str) -> dict:
    row = await db.fetch_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    job_id = await job_service.enqueue("thumbnail", file_id=file_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/{file_id}")
async def get_thumbnail(file_id: str):
    row = await db.fetch_one("SELECT thumb_path FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    thumb = row["thumb_path"]
    if not thumb or not Path(thumb).exists():
        raise HTTPException(status_code=425, detail="Thumbnail noch nicht fertig")
    return FileResponse(thumb, media_type="image/jpeg")
