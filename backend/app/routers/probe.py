"""
CuttOffl Backend - Probe-Router.

Liefert vollständige ffprobe-Ausgabe einer bekannten Datei.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.db import db
from app.models.schemas import ProbeResponse
from app.services.error_helper import sanitize_error
from app.services.probe_service import probe_file, summarize

router = APIRouter(prefix="/api/probe", tags=["probe"])


@router.get("/{file_id}", response_model=ProbeResponse)
async def probe(file_id: str, refresh: bool = False) -> ProbeResponse:
    row = await db.fetch_one(
        "SELECT path, probe_json FROM files WHERE id = ?", (file_id,)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    if not refresh and row["probe_json"]:
        raw = json.loads(row["probe_json"])
    else:
        path = Path(row["path"])
        if not path.exists():
            raise HTTPException(status_code=410, detail="Originaldatei fehlt auf Platte")
        try:
            raw = await probe_file(path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"ffprobe-Fehler: {sanitize_error(str(e))}",
            )
        summary = summarize(raw)
        await db.execute(
            """UPDATE files SET duration_s=?, width=?, height=?, fps=?,
                video_codec=?, audio_codec=?, probe_json=?, updated_at=datetime('now')
               WHERE id = ?""",
            (
                summary.get("duration_s"),
                summary.get("width"),
                summary.get("height"),
                summary.get("fps"),
                summary.get("video_codec"),
                summary.get("audio_codec"),
                json.dumps(raw),
                file_id,
            ),
        )

    summary = summarize(raw)
    return ProbeResponse(file_id=file_id, raw=raw, **summary)
