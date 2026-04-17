"""
CuttOffl Backend - Transkription-Router.

Endpunkte:
  GET  /api/transcription/status                  Capabilities + Modelle
  POST /api/transcription/scan                    Neu scannen (optional extra Pfade)
  GET  /api/transcript/{file_id}                  geparste Segmente (aus SRT)
  GET  /api/transcript/{file_id}.srt              SRT-Datei zum Download
  DELETE /api/transcript/{file_id}                Transkript loeschen

Der Service ist defensiv geschrieben: Ist kein Whisper-Paket installiert
oder fehlt jedes Modell, liefert /status eine klare "nicht verfuegbar"-
Antwort. Das Frontend kann daraufhin die Transkriptions-UI ausblenden
bzw. dem Nutzer den Installations-/Download-Hinweis zeigen.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from app.db import db
from app.services import transcribe_service as tx
from app.services.job_service import job_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["transcription"])


class GenerateRequest(BaseModel):
    engine: str | None = None   # wenn None: suggested_engine
    model: str | None = None    # wenn None: suggested_model


# --- Capabilities / Scan -------------------------------------------------

class ScanRequest(BaseModel):
    extra_roots: list[str] = []


@router.get("/transcription/status")
async def transcription_status() -> dict:
    caps = tx.capabilities(scan=True)
    return {
        "available": caps.available,
        "engines": [asdict(e) for e in caps.engines],
        "models_found": [asdict(m) for m in caps.models_found],
        "suggested_engine": caps.suggested_engine,
        "suggested_model": caps.suggested_model,
        # Die tatsaechlich aktive Wahl -- Nutzer-Preference, sonst
        # suggested_*. Frontend markiert das entsprechende Modell.
        "active_engine": caps.active_engine,
        "active_model": caps.active_model,
        "notes": caps.notes,
        "default_model": tx.DEFAULT_MODEL,
        "supported_sizes": list(tx.WHISPER_SIZES),
    }


class PreferenceRequest(BaseModel):
    engine: str | None = None
    model: str | None = None


@router.put("/transcription/preference")
async def set_preference(body: PreferenceRequest) -> dict:
    """Persistiert die Nutzer-Wahl (Engine + Modell). Leerer Body
    (oder beide Felder None) setzt die Auswahl zurueck auf den
    automatischen Vorschlag."""
    tx.set_preference(body.engine, body.model)
    caps = tx.capabilities(scan=True)
    return {
        "active_engine": caps.active_engine,
        "active_model": caps.active_model,
    }


@router.post("/transcription/scan")
async def transcription_scan(body: ScanRequest) -> dict:
    try:
        models = tx.scan_models(extra_roots=body.extra_roots or None)
    except Exception as e:
        # Kein Crash -- wir geben einen sauberen Fehler raus
        logger.warning(f"Scan fehlgeschlagen: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scan fehlgeschlagen: {e}",
        )
    return {"models_found": [asdict(m) for m in models]}


# --- Transkript lesen / loeschen ----------------------------------------

async def _file_or_404(file_id: str):
    row = await db.fetch_one(
        "SELECT id, transcript_path, transcript_lang, transcript_model, "
        "original_name FROM files WHERE id = ?",
        (file_id,),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")
    return row


@router.post("/transcript/{file_id}/generate")
async def start_transcription(file_id: str, body: GenerateRequest) -> dict:
    """Startet einen Transkriptions-Job. Prüft vorab capabilities; wenn
    die Engine nicht verfuegbar ist oder kein Modell da ist, gibt es
    eine klare 409-Meldung -- kein Crash."""
    row = await db.fetch_one("SELECT id FROM files WHERE id = ?", (file_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    caps = tx.capabilities(scan=True)
    if not caps.available:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Transkription ist auf diesem System nicht verfügbar.",
                "notes": caps.notes,
                "engines": [asdict(e) for e in caps.engines],
            },
        )

    engine = body.engine or caps.suggested_engine
    model = body.model or caps.suggested_model
    job_id = await job_service.enqueue(
        "transcribe",
        file_id=file_id,
        payload={"engine": engine, "model": model},
    )
    return {"job_id": job_id, "engine": engine, "model": model}


@router.get("/transcript/{file_id}")
async def get_transcript(file_id: str) -> dict:
    """Liefert geparste Segmente + Metadaten. Gibt 204-ish (leere Liste)
    zurueck, wenn noch kein Transkript da ist -- damit das Frontend
    einfach reagieren kann ohne 404-Toast."""
    row = await _file_or_404(file_id)
    p = row["transcript_path"]
    if not p or not Path(p).exists():
        return {
            "file_id": file_id,
            "has_transcript": False,
            "lang": row["transcript_lang"],
            "model": row["transcript_model"],
            "segments": [],
        }
    try:
        content = Path(p).read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"SRT nicht lesbar: {e}")
    segs = tx.parse_srt(content)
    return {
        "file_id": file_id,
        "has_transcript": True,
        "lang": row["transcript_lang"],
        "model": row["transcript_model"],
        "segments": segs,
    }


@router.get("/transcript/{file_id}.srt")
async def get_transcript_srt(file_id: str):
    row = await _file_or_404(file_id)
    p = row["transcript_path"]
    if not p or not Path(p).exists():
        raise HTTPException(status_code=404, detail="Kein Transkript vorhanden")
    # Lesbarer Dateiname
    base = (row["original_name"] or file_id).rsplit(".", 1)[0]
    return FileResponse(p, media_type="application/x-subrip",
                        filename=f"{base}.srt")


@router.get("/transcript/{file_id}.vtt")
async def get_transcript_vtt(file_id: str):
    """Gleicher Inhalt wie SRT, aber als WebVTT -- praktisch fuer HTML5-
    Player mit <track kind='captions'>."""
    row = await _file_or_404(file_id)
    p = row["transcript_path"]
    if not p or not Path(p).exists():
        raise HTTPException(status_code=404, detail="Kein Transkript vorhanden")
    try:
        srt_text = Path(p).read_text(encoding="utf-8")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"SRT nicht lesbar: {e}")
    segs = tx.parse_srt(srt_text)
    vtt = tx.segments_to_vtt(segs)
    base = (row["original_name"] or file_id).rsplit(".", 1)[0]
    from fastapi.responses import Response
    return Response(
        content=vtt,
        media_type="text/vtt; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{base}.vtt"',
        },
    )


@router.delete("/transcript/{file_id}")
async def delete_transcript(file_id: str) -> dict:
    row = await _file_or_404(file_id)
    p = row["transcript_path"]
    if p:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
    await db.execute(
        "UPDATE files SET transcript_path=NULL, transcript_lang=NULL, "
        "transcript_model=NULL, updated_at=datetime('now') WHERE id = ?",
        (file_id,),
    )
    return {"deleted": file_id}
