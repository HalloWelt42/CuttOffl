"""
CuttOffl Backend - Hauptanwendung.

Phase 4 (v0.4.0):
  - Phase 3: EDL-CRUD, Render-Pipeline, Snap, Exports
  - Thumbnail-Sprite (Tile-JPEG) aus dem Proxy
  - Audio-Wellenform (Peak-JSON) aus dem Proxy
  - Timeline-Visualisierung mit Frame-Strip und Waveform
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import APP_NAME, CORS_ORIGINS, HOST, LOG_LEVEL, PORT, VERSION, ensure_directories
from app.db import db
from app.routers import (
    exports, files, jobs, probe, projects, proxy, sprite,
    system, thumbnail, upload, ws,
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
    logger.info(f"[OK] API: http://{HOST}:{PORT}  Docs: http://{HOST}:{PORT}/docs  HW: {hw}")
    yield
    logger.info(f"[STOP] {APP_NAME} fährt herunter...")
    await job_service.stop()
    await db.disconnect()
    logger.info(f"[BYE] {APP_NAME} gestoppt")


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
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Range", "Accept-Ranges", "Content-Length"],
)

app.include_router(system.router)
app.include_router(upload.router)
app.include_router(files.router)
app.include_router(probe.router)
app.include_router(proxy.router)
app.include_router(thumbnail.router)
app.include_router(sprite.router)
app.include_router(projects.router)
app.include_router(exports.router)
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
