"""
CuttOffl Backend - Exports-Router.

Listet fertige Render-Ergebnisse (jobs.kind='render' + result_path existiert)
und liefert die Dateien per HTTP-Download aus.

Dateiname auf Platte bleibt die Job-UUID (kollisionsfrei); der Download-Header
liefert einen lesbaren Namen aus Projekt + Zeitstempel.

Zusätzlich: "In Bibliothek übernehmen" kopiert das fertige Video als neue
Quelle in data/originals/, legt einen files-Eintrag an und startet Thumbnail-
und Proxy-Job -- damit ist das Resultat sofort wieder schnittbar.
"""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from app.config import ORIGINALS_DIR
from app.db import db
from app.routers.ws import broadcaster as ws_broadcaster
from app.services import transcribe_service as tx
from app.services.folder_service import FolderError, normalize as normalize_folder
from app.services.job_service import job_service
from app.services.probe_service import probe_file, summarize

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/exports", tags=["exports"])


class ImportToLibraryRequest(BaseModel):
    folder_path: str = ""
    rename: str | None = None


_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _slug(s: str, maxlen: int = 80) -> str:
    s = (s or "").strip()
    s = _BAD_CHARS.sub("", s)
    s = re.sub(r"\s+", " ", s)
    return s[:maxlen].strip(" .")


def _display_name_for(project_name: str | None,
                      source_name: str | None,
                      updated_at: str | None,
                      suffix: str,
                      clip_id: str | None = None) -> str:
    """Baut einen lesbaren Download-Namen:
    "<Projekt> - <YYYY-MM-DD HHMM>.<ext>"
    bzw. bei Einzel-Clip-Export:
    "<Projekt> - Clip <id> - <YYYY-MM-DD HHMM>.<ext>"
    """
    base = _slug(project_name) or _slug(source_name and Path(source_name).stem)
    if not base:
        base = "CuttOffl-Schnitt"
    clip_part = f" - Clip {clip_id}" if clip_id else ""
    ts = ""
    if updated_at:
        m = re.match(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2})", updated_at)
        if m:
            ts = f" {m.group(1)} {m.group(2)}{m.group(3)}"
    return f"{base}{clip_part}{ts}{suffix}"


@router.get("")
async def list_exports() -> list[dict]:
    rows = await db.fetch_all(
        """
        SELECT j.id              AS job_id,
               j.status           AS status,
               j.project_id       AS project_id,
               j.file_id          AS file_id,
               j.result_path      AS result_path,
               j.created_at       AS created_at,
               j.updated_at       AS updated_at,
               p.name             AS project_name,
               f.original_name    AS source_name,
               f.transcript_path  AS source_transcript_path
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
        stem = Path(p).stem if p else ""
        clip_id = None
        # Datei-Stem "<job-id>-clip-<id>" => Clip-Export-Erkennung
        m = re.match(r"^[0-9a-f]{32}-clip-(.+)$", stem)
        if m:
            clip_id = m.group(1)
        display_name = _display_name_for(
            r["project_name"], r["source_name"], r["updated_at"], suffix,
            clip_id=clip_id,
        )
        stp = r["source_transcript_path"]
        has_transcript = bool(stp and Path(stp).exists())
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
            # Bundle / CC-Download ist möglich, wenn die Quelldatei
            # ein Transkript hat -- die Export-SRT wird on-the-fly
            # aus der EDL des Projekts umgerechnet.
            "has_transcript": has_transcript,
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
    stem = path.stem
    clip_id = None
    m = re.match(r"^[0-9a-f]{32}-clip-(.+)$", stem)
    if m:
        clip_id = m.group(1)
    display = _display_name_for(
        row["project_name"], row["source_name"], row["updated_at"], path.suffix,
        clip_id=clip_id,
    )
    return FileResponse(path, media_type=media, filename=display)


async def _build_export_segments(job_id: str) -> tuple[list[dict], str]:
    """Holt Original-Transkript, Projekt-EDL und Clip-ID aus dem Job,
    bildet das Ergebnis auf die Export-Zeitachse ab. Gibt (segments,
    stem) zurück -- stem ist der lesbare Dateiname ohne Endung.

    Wirft HTTPException mit klarer Meldung, wenn das Quelltranskript
    fehlt oder das Projekt nicht auflösbar ist.
    """
    row = await db.fetch_one(
        """SELECT j.result_path, j.updated_at, j.project_id,
                  p.edl_json, p.name AS project_name,
                  f.original_name AS source_name,
                  f.transcript_path AS source_transcript
           FROM jobs j
           LEFT JOIN projects p ON p.id = j.project_id
           LEFT JOIN files    f ON f.id = p.source_file_id
           WHERE j.id = ? AND j.kind = 'render'""",
        (job_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Render-Job nicht gefunden")
    stp = row["source_transcript"]
    if not stp or not Path(stp).exists():
        raise HTTPException(
            status_code=404,
            detail="Keine Untertitel verfügbar (Quelldatei hat kein Transkript)",
        )
    try:
        srt_text = Path(stp).read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Transkript nicht lesbar: {e}")
    original_segments = tx.parse_srt(srt_text)

    # EDL aus dem Projekt
    try:
        edl_data = json.loads(row["edl_json"] or "{}")
    except Exception:
        edl_data = {}
    clips = edl_data.get("timeline") or []

    # Einzel-Clip-Export? Dateiname-Stem "<jobhex>-clip-<id>"
    rp = row["result_path"] or ""
    stem_on_disk = Path(rp).stem if rp else ""
    m = re.match(r"^[0-9a-f]{32}-clip-(.+)$", stem_on_disk)
    clip_id = m.group(1) if m else None

    segs = tx.remap_segments_for_edl(
        original_segments, clips, clip_id=clip_id,
    )
    # Lesbarer Stem für Download-Dateinamen
    suffix = Path(rp).suffix if rp else ".mp4"
    display = _display_name_for(
        row["project_name"], row["source_name"], row["updated_at"], suffix,
        clip_id=clip_id,
    )
    stem = display.rsplit(".", 1)[0]
    return segs, stem


@router.get("/{job_id}/transcript.srt")
async def export_transcript_srt(job_id: str):
    segs, stem = await _build_export_segments(job_id)
    content = tx.segments_to_srt(segs)
    return Response(
        content=content,
        media_type="application/x-subrip",
        headers={"Content-Disposition": f'attachment; filename="{stem}.srt"'},
    )


@router.get("/{job_id}/transcript.vtt")
async def export_transcript_vtt(job_id: str):
    segs, stem = await _build_export_segments(job_id)
    content = tx.segments_to_vtt(segs)
    return Response(
        content=content,
        media_type="text/vtt; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{stem}.vtt"'},
    )


@router.get("/{job_id}/bundle.zip")
async def export_bundle(job_id: str):
    """ZIP mit Export-Video + SRT + VTT, falls die Quelle ein Transkript
    hat. Ohne Transkript: nur das Video im ZIP."""
    row = await db.fetch_one(
        """SELECT j.result_path, j.updated_at, j.project_id,
                  p.edl_json, p.name AS project_name,
                  f.original_name AS source_name,
                  f.transcript_path AS source_transcript
           FROM jobs j
           LEFT JOIN projects p ON p.id = j.project_id
           LEFT JOIN files    f ON f.id = p.source_file_id
           WHERE j.id = ? AND j.kind = 'render'""",
        (job_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Render-Job nicht gefunden")
    rp = row["result_path"]
    if not rp or not Path(rp).exists():
        raise HTTPException(status_code=410, detail="Datei nicht mehr vorhanden")
    video = Path(rp)
    stem_on_disk = video.stem
    m = re.match(r"^[0-9a-f]{32}-clip-(.+)$", stem_on_disk)
    clip_id = m.group(1) if m else None
    display = _display_name_for(
        row["project_name"], row["source_name"], row["updated_at"], video.suffix,
        clip_id=clip_id,
    )
    stem = display.rsplit(".", 1)[0]

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED, allowZip64=True) as zf:
        zf.write(video, arcname=display)
        stp = row["source_transcript"]
        if stp and Path(stp).exists():
            try:
                srt_text = Path(stp).read_text(encoding="utf-8")
                original_segments = tx.parse_srt(srt_text)
                try:
                    edl_data = json.loads(row["edl_json"] or "{}")
                except Exception:
                    edl_data = {}
                clips = edl_data.get("timeline") or []
                export_segs = tx.remap_segments_for_edl(
                    original_segments, clips, clip_id=clip_id,
                )
                zf.writestr(f"{stem}.srt", tx.segments_to_srt(export_segs))
                zf.writestr(f"{stem}.vtt", tx.segments_to_vtt(export_segs))
            except OSError:
                pass
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{stem}.zip"'},
    )


@router.post("/{job_id}/import-to-library")
async def import_export_to_library(job_id: str, body: ImportToLibraryRequest) -> dict:
    """Übernimmt ein fertiges Render-Ergebnis als neue Quelle in die
    Bibliothek. Datei wird nach data/originals/<new-id>.<ext> kopiert,
    ein files-Eintrag angelegt und Thumbnail + Proxy angestoßen."""
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
    src = row["result_path"]
    if not src or not Path(src).exists():
        raise HTTPException(status_code=410, detail="Datei nicht mehr vorhanden")

    src_path = Path(src)
    suffix = src_path.suffix or ".mp4"

    try:
        folder_path = normalize_folder(body.folder_path or "")
    except FolderError as e:
        raise HTTPException(status_code=400, detail=f"Ungültiger Ordner: {e}")

    # Lesbarer Name: Nutzer-Override, sonst aus Projekt + Zeitstempel,
    # sonst das Standard-Schema für den Download.
    clip_id = None
    m = re.match(r"^[0-9a-f]{32}-clip-(.+)$", src_path.stem)
    if m:
        clip_id = m.group(1)
    if body.rename and body.rename.strip():
        original_name = _slug(body.rename) or _display_name_for(
            row["project_name"], row["source_name"], row["updated_at"], suffix,
            clip_id=clip_id,
        )
        if not original_name.lower().endswith(suffix.lower()):
            original_name = f"{original_name}{suffix}"
    else:
        original_name = _display_name_for(
            row["project_name"], row["source_name"], row["updated_at"], suffix,
            clip_id=clip_id,
        )

    # Kopieren (kein Hardlink -- der Export soll unabhängig löschbar bleiben)
    new_id = uuid.uuid4().hex
    stored_name = f"{new_id}{suffix}"
    dest = ORIGINALS_DIR / stored_name
    try:
        shutil.copy2(src_path, dest)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Kopieren fehlgeschlagen: {e}")

    size_bytes = dest.stat().st_size
    probe_summary: dict = {}
    probe_raw: dict = {}
    try:
        probe_raw = await probe_file(dest)
        probe_summary = summarize(probe_raw)
    except Exception as e:
        logger.warning(f"ffprobe nach Import fehlgeschlagen: {e}")

    await db.execute(
        """
        INSERT INTO files (
            id, original_name, stored_name, path, size_bytes,
            mime_type, duration_s, width, height, fps,
            video_codec, audio_codec, folder_path, probe_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id,
            original_name,
            stored_name,
            str(dest),
            size_bytes,
            "video/mp4" if suffix.lower() == ".mp4" else None,
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

    thumb_job_id = await job_service.enqueue("thumbnail", file_id=new_id)
    proxy_job_id = await job_service.enqueue("proxy", file_id=new_id)

    # Bibliothek aktualisiert sich per file_event automatisch
    await ws_broadcaster.broadcast({
        "type": "file_event",
        "event": "imported",
        "file_id": new_id,
    })

    logger.info(
        f"Export {job_id} in Bibliothek übernommen als {new_id} "
        f"(Ordner={folder_path or '-'}, Name={original_name})"
    )
    return {
        "file_id": new_id,
        "original_name": original_name,
        "folder_path": folder_path,
        "size_bytes": size_bytes,
        "thumb_job_id": thumb_job_id,
        "proxy_job_id": proxy_job_id,
    }


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
