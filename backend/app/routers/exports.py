"""
CuttOffl Backend - Exports-Router.

Listet fertige Render-Ergebnisse (jobs.kind='render' + result_path existiert)
und liefert die Dateien per HTTP-Download aus.

Dateiname auf Platte bleibt die Job-UUID (kollisionsfrei); der Download-Header
liefert einen lesbaren Namen aus Projekt + Zeitstempel.
"""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.db import db

router = APIRouter(prefix="/api/exports", tags=["exports"])


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _slug(s: str, maxlen: int = 80) -> str:
    s = (s or "").strip()
    s = _BAD_CHARS.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen].strip(" .")


def _display_name_for(project_name: str | None,
                      source_name: str | None,
                      updated_at: str | None,
                      suffix: str) -> str:
    """Baut einen lesbaren Download-Namen: "<Projekt> - <YYYY-MM-DD HHMM>.<ext>"."""
    base = _slug(project_name) or _slug(source_name and Path(source_name).stem)
    if not base:
        base = "CuttOffl-Schnitt"
    ts = ""
    if updated_at:
        # "2026-04-17 00:32:23" → "2026-04-17 0032"
        m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", updated_at)
        if m:
            ts = f" {m.group(1)} {m.group(2)}{m.group(3)}"
    return f"{base}{ts}{suffix}"


@router.get("")
async def list_exports() -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT j.id            AS job_id,
               j.status         AS status,
               j.project_id     AS project_id,
               j.file_id        AS file_id,
               j.result_path    AS result_path,
               j.created_at     AS created_at,
               j.updated_at     AS updated_at,
               p.name           AS project_name,
               f.original_name  AS source_name
        FROM jobs j
        LEFT JOIN projects p ON p.id = j.project_id
        LEFT JOIN files    f ON f.id = j.file_id
        WHERE j.kind = 'render'
          AND j.status = 'completed'
          AND j.result_path IS NOT NULL
        ORDER BY j.updated_at DESC
        """
    )
    result = []
    for r in rows:
        p = r["result_path"]
        exists = bool(p and Path(p).exists())
        size = Path(p).stat().st_size if exists else 0
        suffix = Path(p).suffix if p else ".mp4"
        display_name = _display_name_for(
            r["project_name"], r["source_name"], r["updated_at"], suffix,
        )
        result.append({
            "job_id": r["job_id"],
            "project_id": r["project_id"],
            "project_name": r["project_name"],
            "source_file_id": r["file_id"],
            "source_name": r["source_name"],
            "status": r["status"],
            "display_name": display_name,
            "result_path": p,
            "exists": exists,
            "size_bytes": size,
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
        })
    return result


@router.get("/{job_id}/download")
async def download_export(job_id: str):
    row = await db.fetch_one(
        """SELECT j.result_path, j.updated_at, p.name AS project_name,
                  f.original_name AS source_name
           FROM jobs j
           LEFT JOIN projects p ON p.id = j.project_id
           LEFT JOIN files    f ON f.id = j.file_id
           WHERE j.id = ? AND j.kind = 'render'""",
        (job_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Render-Job nicht gefunden")
    p = row["result_path"]
    if not p or not Path(p).exists():
        raise HTTPException(status_code=410, detail="Datei nicht mehr vorhanden")
    path = Path(p)
    media = "video/mp4" if path.suffix.lower() == ".mp4" else "application/octet-stream"
    display = _display_name_for(
        row["project_name"], row["source_name"], row["updated_at"], path.suffix,
    )
    return FileResponse(path, media_type=media, filename=display)


@router.delete("/{job_id}")
async def delete_export(job_id: str) -> dict:
    row = await db.fetch_one(
        "SELECT result_path FROM jobs WHERE id = ? AND kind = 'render'", (job_id,)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Render-Job nicht gefunden")
    p = row["result_path"]
    if p:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
    await db.execute(
        "UPDATE jobs SET result_path=NULL, updated_at=datetime('now') WHERE id = ?",
        (job_id,),
    )
    return {"deleted": job_id}
