"""
CuttOffl Backend - Job-Service.

In-Process async Queue für Hintergrund-Jobs.
Persistiert Status in der jobs-Tabelle und broadcastet Fortschritt über WebSocket.

Job-Typen:
  - proxy      → Proxy-Generierung + anschließende Keyframe-Extraktion,
                 stößt danach automatisch sprite + waveform an
  - thumbnail  → Einzelbild-Thumbnail aus dem Original
  - sprite     → Tile-JPEG mit Frame-Streifen aus dem Proxy
  - waveform   → Audio-Peak-JSON aus dem Proxy
  - keyframes  → manuelle Neu-Extraktion der Keyframe-Liste
  - render     → EDL → FFmpeg-Plan → fertiges Video in data/exports/
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

import json as _json

from app.config import PROXIES_DIR, SPRITES_DIR, THUMBS_DIR, WAVEFORMS_DIR
from app.db import db
from app.models.edl import EDL
from app.services.error_helper import sanitize_error
from app.services.keyframe_service import extract_keyframes
from app.services.proxy_service import generate_proxy
from app.services.render_service import render_edl
from app.services.sprite_service import generate_sprite
from app.services.thumbnail_service import generate_thumbnail
from app.services.waveform_service import generate_waveform

logger = logging.getLogger(__name__)


Broadcaster = Callable[[dict], Awaitable[None]]


@dataclass
class Job:
    id: str
    kind: str
    file_id: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "pending"
    progress: float = 0.0
    message: Optional[str] = None
    result_path: Optional[str] = None
    error: Optional[str] = None
    payload: dict = field(default_factory=dict)


class JobService:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[Job] = asyncio.Queue()
        self._worker_task: Optional[asyncio.Task] = None
        self._broadcaster: Optional[Broadcaster] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._active: Optional[Job] = None

    def set_broadcaster(self, broadcaster: Broadcaster) -> None:
        self._broadcaster = broadcaster

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._run_worker(), name="job-worker")
            logger.info("Job-Worker gestartet")

    async def stop(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            logger.info("Job-Worker gestoppt")

    async def enqueue(self, kind: str, file_id: Optional[str] = None,
                      project_id: Optional[str] = None, payload: Optional[dict] = None) -> str:
        job_id = uuid.uuid4().hex
        await db.execute(
            """INSERT INTO jobs (id, kind, status, file_id, project_id)
               VALUES (?, ?, 'pending', ?, ?)""",
            (job_id, kind, file_id, project_id),
        )
        job = Job(id=job_id, kind=kind, file_id=file_id, project_id=project_id,
                  payload=payload or {})
        await self._queue.put(job)
        await self._broadcast_job_event(job, "queued")
        return job_id

    async def active(self) -> Optional[dict]:
        if self._active is None:
            return None
        return self._job_to_dict(self._active)

    async def _run_worker(self) -> None:
        while True:
            job = await self._queue.get()
            self._active = job
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.exception(f"Job-Fehler ({job.kind} {job.id}): {e}")
                job.status = "failed"
                job.error = sanitize_error(str(e), fallback="Job-Fehler")
                await self._persist(job)
                if job.kind == "proxy" and job.file_id:
                    await db.execute(
                        "UPDATE files SET proxy_status='failed' WHERE id = ?",
                        (job.file_id,),
                    )
                await self._broadcast_job_event(job, "failed")
            finally:
                self._active = None
                self._queue.task_done()

    async def _process(self, job: Job) -> None:
        job.status = "running"
        await self._persist(job)
        await self._broadcast_job_event(job, "running")

        if job.kind == "proxy":
            await self._process_proxy(job)
        elif job.kind == "thumbnail":
            await self._process_thumbnail(job)
        elif job.kind == "keyframes":
            await self._process_keyframes(job)
        elif job.kind == "sprite":
            await self._process_sprite(job)
        elif job.kind == "waveform":
            await self._process_waveform(job)
        elif job.kind == "render":
            await self._process_render(job)
        else:
            raise RuntimeError(f"Unbekannter Job-Typ: {job.kind}")

        job.status = "completed"
        job.progress = 1.0
        await self._persist(job)
        await self._broadcast_job_event(job, "completed")

    async def _process_proxy(self, job: Job) -> None:
        assert job.file_id, "proxy-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT path, duration_s, fps FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["path"])
        dest = PROXIES_DIR / f"{job.file_id}.mp4"

        await db.execute(
            "UPDATE files SET proxy_status='running' WHERE id = ?", (job.file_id,)
        )
        await self._broadcast_file_event(job.file_id, "proxy_started")

        last_sent = -1.0

        def on_progress(pct: float, info: dict) -> None:
            nonlocal last_sent
            job.progress = pct
            if pct - last_sent >= 0.02 or info.get("progress") == "end":
                last_sent = pct
                self._schedule_broadcast({
                    "type": "job_progress",
                    "job_id": job.id,
                    "kind": job.kind,
                    "file_id": job.file_id,
                    "progress": pct,
                })

        await generate_proxy(
            source=src,
            dest=dest,
            duration_s=row["duration_s"],
            fps=row["fps"],
            progress_cb=on_progress,
        )
        job.result_path = str(dest)

        keyframes = await extract_keyframes(dest, duration_s=row["duration_s"])
        await db.execute(
            """UPDATE files
               SET has_proxy=1, proxy_status='ready', proxy_path=?,
                   keyframes_json=?, keyframe_count=?, updated_at=datetime('now')
               WHERE id = ?""",
            (str(dest), json.dumps(keyframes), len(keyframes), job.file_id),
        )
        await self._broadcast_file_event(job.file_id, "proxy_ready")

        # Folge-Jobs: Sprite + Waveform aus dem Proxy
        await self.enqueue("sprite",   file_id=job.file_id)
        await self.enqueue("waveform", file_id=job.file_id)

    async def _process_thumbnail(self, job: Job) -> None:
        assert job.file_id, "thumbnail-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT path, duration_s FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["path"])
        dest = THUMBS_DIR / f"{job.file_id}.jpg"
        await generate_thumbnail(src, dest, duration_s=row["duration_s"])
        await db.execute(
            "UPDATE files SET thumb_path=?, updated_at=datetime('now') WHERE id = ?",
            (str(dest), job.file_id),
        )
        job.result_path = str(dest)
        await self._broadcast_file_event(job.file_id, "thumb_ready")

    async def _process_render(self, job: Job) -> None:
        assert job.project_id, "render-Job benötigt project_id"
        prow = await db.fetch_one(
            "SELECT source_file_id, edl_json FROM projects WHERE id = ?", (job.project_id,)
        )
        if prow is None:
            raise RuntimeError("Projekt nicht gefunden")
        frow = await db.fetch_one(
            "SELECT path FROM files WHERE id = ?", (prow["source_file_id"],)
        )
        if frow is None:
            raise RuntimeError("Quelldatei nicht gefunden")
        # Falls der Job einen EDL-Override mitbringt (z. B. Einzel-Clip-Export),
        # hat dieser Vorrang vor der gespeicherten Projekt-EDL.
        override = (job.payload or {}).get("edl_override")
        if override:
            edl = EDL.model_validate(override)
        else:
            edl = EDL.model_validate(_json.loads(prow["edl_json"] or "{}"))

        last_sent = -1.0

        def on_progress(pct: float, phase: str) -> None:
            nonlocal last_sent
            job.progress = pct
            if pct - last_sent >= 0.02 or phase in ("merging", "done"):
                last_sent = pct
                self._schedule_broadcast({
                    "type": "job_progress",
                    "job_id": job.id,
                    "kind": job.kind,
                    "project_id": job.project_id,
                    "file_id": job.file_id,
                    "progress": pct,
                    "phase": phase,
                })

        final = await render_edl(
            source=Path(frow["path"]),
            edl=edl,
            job_id=job.id,
            progress_cb=on_progress,
        )
        job.result_path = str(final)

    async def _process_sprite(self, job: Job) -> None:
        assert job.file_id, "sprite-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT proxy_path, path, duration_s FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["proxy_path"] or row["path"])
        if not src.exists():
            raise RuntimeError("Quelle fuer Sprite fehlt")
        dest = SPRITES_DIR / f"{job.file_id}.jpg"
        meta = await generate_sprite(src, dest, duration_s=row["duration_s"])
        await db.execute(
            """UPDATE files
               SET sprite_path=?, sprite_interval=?, sprite_tile_w=?, sprite_tile_h=?,
                   sprite_cols=?, sprite_rows=?, sprite_count=?, updated_at=datetime('now')
               WHERE id = ?""",
            (str(dest), meta["interval"], meta["tile_w"], meta["tile_h"],
             meta["cols"], meta["rows"], meta["count"], job.file_id),
        )
        job.result_path = str(dest)
        await self._broadcast_file_event(job.file_id, "sprite_ready")

    async def _process_waveform(self, job: Job) -> None:
        assert job.file_id, "waveform-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT proxy_path, path, duration_s FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["proxy_path"] or row["path"])
        if not src.exists():
            raise RuntimeError("Quelle fuer Waveform fehlt")
        dest = WAVEFORMS_DIR / f"{job.file_id}.json"
        meta = await generate_waveform(src, dest, duration_s=row["duration_s"])
        await db.execute(
            """UPDATE files
               SET waveform_path=?, waveform_samples=?, waveform_rate=?, updated_at=datetime('now')
               WHERE id = ?""",
            (str(dest), meta["samples"], meta["rate"], job.file_id),
        )
        job.result_path = str(dest)
        await self._broadcast_file_event(job.file_id, "waveform_ready")

    async def _process_keyframes(self, job: Job) -> None:
        assert job.file_id, "keyframes-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT proxy_path, path, duration_s FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["proxy_path"] or row["path"])
        kf = await extract_keyframes(src, duration_s=row["duration_s"])
        await db.execute(
            """UPDATE files SET keyframes_json=?, keyframe_count=?, updated_at=datetime('now')
               WHERE id = ?""",
            (json.dumps(kf), len(kf), job.file_id),
        )

    async def _persist(self, job: Job) -> None:
        await db.execute(
            """UPDATE jobs
               SET status=?, progress=?, message=?, result_path=?, error=?,
                   updated_at=datetime('now')
               WHERE id=?""",
            (job.status, job.progress, job.message, job.result_path, job.error, job.id),
        )

    async def _broadcast_job_event(self, job: Job, event: str) -> None:
        if self._broadcaster is None:
            return
        await self._broadcaster({
            "type": "job_event",
            "event": event,
            "job": self._job_to_dict(job),
        })

    async def _broadcast_file_event(self, file_id: str, event: str) -> None:
        if self._broadcaster is None:
            return
        await self._broadcaster({
            "type": "file_event",
            "event": event,
            "file_id": file_id,
        })

    def _schedule_broadcast(self, message: dict) -> None:
        """Sync-Wrapper für Callbacks aus ffmpeg-Progress (derselbe Loop)."""
        if self._broadcaster is None or self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self._broadcaster(message), self._loop)

    @staticmethod
    def _job_to_dict(job: Job) -> dict[str, Any]:
        return {
            "id": job.id,
            "kind": job.kind,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "file_id": job.file_id,
            "project_id": job.project_id,
            "result_path": job.result_path,
            "error": job.error,
        }


job_service = JobService()
