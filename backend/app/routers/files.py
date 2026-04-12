"""
CuttOffl Backend - Files-Router.

Liste, Detail, Download, Löschen der hochgeladenen Originale.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import db
from app.models.schemas import (
    FileBulkDeleteBody, FileBulkMoveBody, FileMoveBody, FileOut,
    FileRenameBody, FileTagsBody,
)
from app.services.folder_service import FolderError, normalize


TAG_MAX_LEN = 24
TAG_ALLOWED = re.compile(r"^[\w äöüÄÖÜß\-]{1,24}$")


def _normalize_tags(raw: list[str]) -> list[str]:
    """Trimmt, dedupliziert und validiert Tags. Reihenfolge bleibt erhalten.
    Leere und zu lange Tags werden verworfen."""
    out: list[str] = []
    seen: set[str] = set()
    for t in raw or []:
        if not isinstance(t, str):
            continue
        s = " ".join(t.strip().split())
        if not s or len(s) > TAG_MAX_LEN:
            continue
        if not TAG_ALLOWED.match(s):
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
        if len(out) >= 32:
            break
    return out


def _tags_from_row(row) -> list[str]:
    if "tags_json" not in row.keys():
        return []
    raw = row["tags_json"] or "[]"
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(t) for t in data if isinstance(t, str)]
    except Exception:
        pass
    return []

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
        folder_path=row["folder_path"] if "folder_path" in row.keys() else "",
        tags=_tags_from_row(row),
        created_at=row["created_at"],
    )


@router.get("", response_model=list[FileOut])
async def list_files(
    folder: str | None = None,
    recursive: bool = False,
) -> list[FileOut]:
    """Listet Dateien.
    - Ohne folder: alle Dateien
    - Mit folder='A/B': nur Dateien in A/B (exakt)
    - recursive=true: auch alle Unterordner von folder
    """
    if folder is None:
        rows = await db.fetch_all(
            "SELECT * FROM files ORDER BY created_at DESC"
        )
    else:
        try:
            f = normalize(folder)
        except FolderError as e:
            raise HTTPException(status_code=400, detail=f"Ungueltiger Ordner: {e}")
        if recursive and f:
            rows = await db.fetch_all(
                "SELECT * FROM files WHERE folder_path = ? OR folder_path LIKE ? "
                "ORDER BY created_at DESC",
                (f, f + "/%"),
            )
        elif recursive:
            rows = await db.fetch_all(
                "SELECT * FROM files ORDER BY created_at DESC"
            )
        else:
            rows = await db.fetch_all(
                "SELECT * FROM files WHERE folder_path = ? ORDER BY created_at DESC",
                (f,),
            )
    return [_row_to_fileout(r) for r in rows]


@router.get("/{file_id}", response_model=FileOut)
async def get_file(file_id: str) -> FileOut:
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return _row_to_fileout(row)


@router.post("/bulk-delete", response_model=dict)
async def bulk_delete(body: FileBulkDeleteBody) -> dict:
    """Loescht mehrere Dateien samt aller Ableitungen. Gibt die Anzahl der
    erfolgreich entfernten Eintraege zurueck (und Liste der fehlgeschlagenen
    IDs). Nicht gefundene IDs werden ignoriert."""
    ids = list({fid for fid in body.file_ids if fid})
    if not ids:
        return {"deleted": 0, "missing": [], "errors": []}
    placeholders = ",".join("?" * len(ids))
    rows = await db.fetch_all(
        f"""SELECT id, path, proxy_path, thumb_path, sprite_path, waveform_path
            FROM files WHERE id IN ({placeholders})""",
        tuple(ids),
    )
    found_ids = {r["id"] for r in rows}
    missing = [i for i in ids if i not in found_ids]

    errors: list[str] = []
    for r in rows:
        for key in ("path", "proxy_path", "thumb_path", "sprite_path", "waveform_path"):
            p = r[key]
            if p:
                try:
                    Path(p).unlink(missing_ok=True)
                except OSError as e:
                    errors.append(f"{r['id']}:{key}:{e}")

    if found_ids:
        found_list = list(found_ids)
        ph = ",".join("?" * len(found_list))
        await db.execute(
            f"DELETE FROM files WHERE id IN ({ph})", tuple(found_list)
        )
    return {
        "deleted": len(found_ids),
        "missing": missing,
        "errors": errors,
    }


@router.post("/move", response_model=dict)
async def bulk_move(body: FileBulkMoveBody) -> dict:
    """Verschiebt mehrere Dateien in einen Ordner."""
    try:
        target = normalize(body.folder_path)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=f"Ungueltiger Zielordner: {e}")
    ids = list({fid for fid in body.file_ids if fid})
    if not ids:
        return {"moved": 0}
    placeholders = ",".join("?" * len(ids))
    await db.execute(
        f"UPDATE files SET folder_path = ?, updated_at=datetime('now') "
        f"WHERE id IN ({placeholders})",
        (target, *ids),
    )
    return {"moved": len(ids), "folder_path": target}


@router.patch("/{file_id}/move", response_model=FileOut)
async def move_file(file_id: str, body: FileMoveBody) -> FileOut:
    """Verschiebt eine einzelne Datei in einen Ordner."""
    try:
        target = normalize(body.folder_path)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=f"Ungueltiger Zielordner: {e}")
    row = await db.fetch_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    await db.execute(
        "UPDATE files SET folder_path = ?, updated_at=datetime('now') WHERE id = ?",
        (target, file_id),
    )
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    return _row_to_fileout(row)


@router.put("/{file_id}/tags", response_model=FileOut)
async def set_tags(file_id: str, body: FileTagsBody) -> FileOut:
    """Setzt die Tag-Liste einer Datei (ersetzt vollstaendig)."""
    row = await db.fetch_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    tags = _normalize_tags(body.tags)
    await db.execute(
        "UPDATE files SET tags_json = ?, updated_at=datetime('now') WHERE id = ?",
        (json.dumps(tags, ensure_ascii=False), file_id),
    )
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
    return _row_to_fileout(row)


@router.patch("/{file_id}", response_model=FileOut)
async def rename_file(file_id: str, body: FileRenameBody) -> FileOut:
    """Aendert nur den angezeigten Dateinamen (original_name).
    Der physische Pfad auf der Platte bleibt unveraendert (UUID-basiert).
    """
    row = await db.fetch_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    new_name = body.original_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="Name darf nicht leer sein")
    # Zeichen die im Download-Content-Disposition kaputtgehen koennten, filtern
    if any(ch in new_name for ch in ("\x00", "\r", "\n")):
        raise HTTPException(status_code=400, detail="Unerlaubte Zeichen im Namen")
    await db.execute(
        "UPDATE files SET original_name=?, updated_at=datetime('now') WHERE id = ?",
        (new_name, file_id),
    )
    row = await db.fetch_one("SELECT * FROM files WHERE id = ?", (file_id,))
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
