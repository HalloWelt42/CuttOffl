"""
CuttOffl Backend - Files-Router.

Liste, Detail, Download, Löschen der hochgeladenen Originale.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import db
from app.models.schemas import FileOut

router = APIRouter(prefix="/api/files", tags=["files"])


def _row_to_fileout(row) -> FileOut:
    return FileOut(
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
        proxy_status=row["proxy_status"] if "proxy_status" in row.keys() else "none",
        has_thumb=bool(row["thumb_path"]) if "thumb_path" in row.keys() else False,
        has_sprite=bool(row["sprite_path"]) if "sprite_path" in row.keys() else False,
        has_waveform=bool(row["waveform_path"]) if "waveform_path" in row.keys() else False,
        keyframe_count=row["keyframe_count"] if "keyframe_count" in row.keys() else None,
        created_at=row["created_at"],
    )


@router.get("", response_model=list[FileOut])
async def list_files() -> list[FileOut]:
    rows = await db.fetch_all("SELECT * FROM files ORDER BY created_at DESC")
    return [_row_to_fileout(r) for r in rows]


@router.get("/{file_id}", response_model=FileOut)
async def get_file(file_id: str) -> FileOut:
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return _row_to_fileout(row)


@router.get("/{file_id}/download")
async def download_file(file_id: str):
    """Liefert die Original-Datei zum Herunterladen aus.
    Der Download-Header traegt den urspruenglichen Dateinamen.
    """
    row = await db.fetch_one(
        "SELECT path, original_name FROM files WHERE id = ?", (file_id,)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    path = Path(row["path"])
    if not path.exists():
        raise HTTPException(status_code=410, detail="Originaldatei fehlt auf Platte")

    suffix = path.suffix.lower()
    media = {
        ".mp4": "video/mp4", ".mov": "video/quicktime",
        ".mkv": "video/x-matroska", ".webm": "video/webm",
        ".avi": "video/x-msvideo", ".m4v": "video/x-m4v",
    }.get(suffix, "application/octet-stream")

    return FileResponse(
        path,
        media_type=media,
        filename=row["original_name"] or path.name,
    )


@router.delete("/{file_id}")
async def delete_file(file_id: str) -> dict:
    row = await db.fetch_one(
        """SELECT path, proxy_path, thumb_path, sprite_path, waveform_path
           FROM files WHERE id = ?""",
        (file_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    for key in ("path", "proxy_path", "thumb_path", "sprite_path", "waveform_path"):
        p = row[key]
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass

    await db.execute("DELETE FROM files WHERE id = ?", (file_id,))
    return {"deleted": file_id}
