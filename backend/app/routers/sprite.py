"""
CuttOffl Backend - Sprite + Waveform-Router.

  - GET  /api/sprite/{id}           JPEG ausliefern
  - GET  /api/sprite/{id}/meta      Tile-Raster + Intervall (zum Positionieren im Frontend)
  - POST /api/sprite/{id}/generate  Job manuell anstoßen
  - GET  /api/waveform/{id}         JSON mit Peaks
  - POST /api/waveform/{id}/generate
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.db import db
from app.services.job_service import job_service

router = APIRouter(prefix="/api", tags=["visualisation"])


async def _file_row(file_id: str):
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return row


# --- Sprite ---------------------------------------------------------------

@router.get("/sprite/{file_id}")
async def get_sprite(file_id: str):
    row = await _file_row(file_id)
    p = row["sprite_path"]
    if not p or not Path(p).exists():
        raise HTTPException(status_code=425, detail="Sprite noch nicht fertig")
    return FileResponse(p, media_type="image/jpeg")


@router.get("/sprite/{file_id}/meta")
async def get_sprite_meta(file_id: str) -> dict:
    row = await _file_row(file_id)
    if not row["sprite_path"]:
        raise HTTPException(status_code=425, detail="Sprite noch nicht fertig")
    return {
        "file_id": file_id,
        "interval": row["sprite_interval"],
        "tile_w": row["sprite_tile_w"],
        "tile_h": row["sprite_tile_h"],
        "cols": row["sprite_cols"],
        "rows": row["sprite_rows"],
        "count": row["sprite_count"],
    }


@router.post("/sprite/{file_id}/generate")
async def generate_sprite(file_id: str) -> dict:
    await _file_row(file_id)
    job_id = await job_service.enqueue("sprite", file_id=file_id)
    return {"job_id": job_id, "status": "queued"}


# --- Waveform -------------------------------------------------------------

@router.get("/waveform/{file_id}")
async def get_waveform(file_id: str):
    row = await _file_row(file_id)
    p = row["waveform_path"]
    if not p or not Path(p).exists():
        raise HTTPException(status_code=425, detail="Waveform noch nicht fertig")
    try:
        data = json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Waveform unlesbar: {e}")
    return JSONResponse(data)


@router.post("/waveform/{file_id}/generate")
async def generate_waveform(file_id: str) -> dict:
    await _file_row(file_id)
    job_id = await job_service.enqueue("waveform", file_id=file_id)
    return {"job_id": job_id, "status": "queued"}
