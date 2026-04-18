"""
CuttOffl Backend - Hauptanwendung.

Registriert alle Router, hängt den Job-Worker und die Lifespan-Hooks ein.

Aktueller Funktionsumfang (v0.4.0):
  - Multipart-Upload mit ffprobe-Metadatenextraktion
  - Auto-Proxy (480p H.264, GOP 1 s), Thumbnail, Sprite, Waveform
  - Keyframe-Liste + Snap-Endpunkt
  - In-Process Job-Queue mit WebSocket-Progress
  - EDL-CRUD (Projekte, Timeline, Output-Profil)
  - Hybrid-Render (copy + reencode) mit Concat-Demuxer
  - Proxy-Streaming mit HTTP-Range
  - Export-Liste und -Download mit lesbaren Dateinamen
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import (
    APP_NAME, CORS_ALLOW_CREDENTIALS, CORS_ORIGINS, HOST, LOG_LEVEL,
    PORT, VERSION, ensure_directories,
)
from app.db import db
from app.routers import (
    exports, files, folders, jobs, probe, projects, proxy, sprite,
    system, thumbnail, transcription, upload, ws,
)
from app.services.hwaccel_service import detect_hw_encoder
from app.services.job_service import job_service

logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"[START] {APP_NAME} v{VERSION}")
    ensure_directories()
    await db.connect()
    hw = await detect_hw_encoder()
    job_service.set_broadcaster(ws.broadcaster.broadcast)
    await job_service.start()
    await _auto_cleanup_jobs()
    # Demo-Video einmalig importieren, falls die Quelle in data/demo/
    # liegt (kam beim setup.sh über tools/fetch_demo_video.sh dort an).
    # Wenn der User das Demo später manuell in den Einstellungen
    # entfernt, bleibt der Import hier aus -- es passiert nur genau
    # dann etwas, wenn die Quelle da ist UND die Bibliothek noch
    # keinen protected-Eintrag hat.
    try:
        from app.services.demo_video_service import ensure_demo_imported
        await ensure_demo_imported()
    except Exception as e:
        logger.warning(f"Demo-Video-Import übersprungen: {e}")
    logger.info(f"[OK] API: http://{HOST}:{PORT}  Docs: http://{HOST}:{PORT}/docs  HW: {hw}")
    yield
    logger.info(f"[STOP] {APP_NAME} fährt herunter...")
    await job_service.stop()
    await db.disconnect()
    logger.info(f"[BYE] {APP_NAME} gestoppt")


async def _auto_cleanup_jobs() -> None:
    """Haelt die jobs-Tabelle klein: alte abgeschlossene Hintergrund-Jobs und
    alte fehlgeschlagene Jobs werden nach 14 Tagen entfernt. Render-Jobs
    bleiben erhalten (Referenz auf das Export-Video)."""
    try:
        await db.execute(
            """DELETE FROM jobs
               WHERE status = 'failed'
                 AND updated_at < datetime('now', '-14 days')"""
        )
        await db.execute(
            """DELETE FROM jobs
               WHERE status = 'completed'
                 AND kind IN ('proxy','thumbnail','sprite','waveform','keyframes')
                 AND updated_at < datetime('now', '-14 days')"""
        )
    except Exception as e:
        logger.warning(f"Auto-Cleanup Jobs fehlgeschlagen: {e}")


app = FastAPI(
    title=APP_NAME,
    description="Offline-first Video-Cutter mit EDL und Chunked Processing.",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept",
                   "Range", "X-Requested-With"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length",
                    "Content-Disposition"],
    max_age=600,
)

app.include_router(system.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(folders.router)
app.include_router(probe.router)
app.include_router(proxy.router)
app.include_router(thumbnail.router)
app.include_router(sprite.router)
app.include_router(projects.router)
app.include_router(exports.router)
app.include_router(transcription.router)
app.include_router(jobs.router)
app.include_router(ws.router)


@app.get("/")
async def root() -> dict:
    return {
        "app": APP_NAME,
        "version": VERSION,
        "status": "running",
        "docs": "/docs",
    }
