"""
CuttOffl Backend - Audio-Streaming.

Liefert den Audio-Stream einer Library-Datei fuer das Frontend-
Live-Preview. Audio-Only-Dateien streamen wir 1:1 aus data/originals;
Videos streamen wir die Originaldatei (der Browser spielt daraus nur
den Audio-Stream im <audio>-Element). Range-Requests werden
unterstuetzt, damit der Browser bei grossen Videos nicht die komplette
Datei laedt.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response, StreamingResponse

from app.db import db

router = APIRouter(prefix="/api/audio", tags=["audio"])

CHUNK = 1024 * 1024  # 1 MB pro Range-Chunk


async def _file_row(file_id: str):
    row = await db.fetch_one(
        "SELECT path, mime_type FROM files WHERE id = ?", (file_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return row


def _media_type(path: Path, hint: Optional[str]) -> str:
    if hint:
        return hint
    guess, _ = mimetypes.guess_type(path.name)
    return guess or "application/octet-stream"


@router.get("/{file_id}")
async def stream_audio(file_id: str, request: Request):
    row = await _file_row(file_id)
    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Datei fehlt auf Disk")

    media_type = _media_type(path, row["mime_type"])
    size = path.stat().st_size
    range_header: Optional[str] = request.headers.get("range")

    if range_header is None:
        return FileResponse(
            path,
            media_type=media_type,
            headers={
                "Accept-Ranges": "bytes",
                "Content-Length": str(size),
            },
        )

    try:
        units, _, rng = range_header.partition("=")
        if units.strip().lower() != "bytes":
            raise ValueError
        start_s, _, end_s = rng.partition("-")
        start = int(start_s)
        end = int(end_s) if end_s else size - 1
    except ValueError:
        raise HTTPException(status_code=416, detail="Ungueltiger Range-Header")

    end = min(end, size - 1)
    if start > end or start >= size:
        return Response(
            status_code=416,
            headers={"Content-Range": f"bytes */{size}"},
        )

    length = end - start + 1

    async def iter_bytes():
        remaining = length
        with path.open("rb") as fh:
            fh.seek(start)
            while remaining > 0:
                chunk = fh.read(min(CHUNK, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        iter_bytes(),
        status_code=206,
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Content-Length": str(length),
        },
    )
