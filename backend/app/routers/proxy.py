"""
CuttOffl Backend - Proxy-Streaming & Keyframes.

  - GET /api/proxy/{id}           Stream des Low-Res-Proxies (Range-Requests)
  - GET /api/proxy/{id}/keyframes Liste der Keyframe-Zeitstempel
  - POST /api/proxy/{id}/generate Proxy-Job manuell anstoßen
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.db import db
from app.models.edl import SnapResponse
from app.services.job_service import job_service

router = APIRouter(prefix="/api/proxy", tags=["proxy"])


CHUNK = 1024 * 1024


async def _file_row(file_id: str):
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return row


@router.get("/{file_id}/keyframes")
async def keyframes(file_id: str) -> dict:
    row = await _file_row(file_id)
    raw = row["keyframes_json"]
    return {
        "file_id": file_id,
        "count": row["keyframe_count"] or 0,
        "keyframes": json.loads(raw) if raw else [],
    }


@router.post("/{file_id}/generate")
async def generate(file_id: str) -> dict:
    await _file_row(file_id)
    job_id = await job_service.enqueue("proxy", file_id=file_id)
    return {"job_id": job_id, "status": "queued"}


@router.get("/{file_id}/snap", response_model=SnapResponse)
async def snap(file_id: str, t: float, mode: str = "nearest") -> SnapResponse:
    """Gibt den nächsten Keyframe zum Zeitpunkt t zurück.

    mode: 'nearest' | 'prev' | 'next'
    """
    row = await _file_row(file_id)
    raw = row["keyframes_json"]
    if not raw:
        return SnapResponse(file_id=file_id, t_input=t, t_snap=t, delta=0.0, snapped=False)
    kf: list[float] = json.loads(raw)
    if not kf:
        return SnapResponse(file_id=file_id, t_input=t, t_snap=t, delta=0.0, snapped=False)

    # Binary-Search waere overkill; Liste ist sortiert
    prev_kf = max((k for k in kf if k <= t), default=kf[0])
    next_kf = min((k for k in kf if k >= t), default=kf[-1])
    if mode == "prev":
        pick = prev_kf
    elif mode == "next":
        pick = next_kf
    else:
        pick = prev_kf if (t - prev_kf) <= (next_kf - t) else next_kf
    return SnapResponse(
        file_id=file_id, t_input=t, t_snap=round(pick, 4),
        delta=round(pick - t, 4), snapped=True,
    )


@router.get("/{file_id}")
async def stream_proxy(file_id: str, request: Request):
    row = await _file_row(file_id)
    proxy_path = row["proxy_path"]
    if not proxy_path or not Path(proxy_path).exists():
        raise HTTPException(status_code=425, detail="Proxy noch nicht fertig")

    path = Path(proxy_path)
    size = path.stat().st_size
    range_header: Optional[str] = request.headers.get("range")

    if range_header is None:
        return FileResponse(
            path,
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes", "Content-Length": str(size)},
        )

    # "bytes=START-END"
    try:
        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError
        start_s, _, end_s = rng.partition("-")
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    except ValueError:
        raise HTTPException(status_code=416, detail="Ungültiger Range-Header")

    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(status_code=416, headers={"Content-Range": f"bytes */{size}"})

    length = end - start + 1

    def iterator():
        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                data = f.read(min(CHUNK, remaining))
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        iterator(),
        status_code=206,
        media_type="video/mp4",
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
        },
    )
