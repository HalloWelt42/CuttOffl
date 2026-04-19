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

from app.config import (
    ORIGINALS_DIR,
    PROXIES_DIR, SPRITES_DIR, THUMBS_DIR, TMP_DIR, TRANSCRIPTS_DIR, WAVEFORMS_DIR,
)
from app.db import db
from app.models.edl import EDL
from app.services.error_helper import sanitize_error
from app.services.keyframe_service import extract_keyframes
from app.services.proxy_service import generate_proxy
from app.services.audio_mix_service import build_audio_mix_wav
from app.services.render_service import render_edl
from app.services.sprite_service import generate_sprite
from app.services.thumbnail_service import generate_thumbnail
from app.services import transcribe_service
from app.services.waveform_service import generate_waveform

logger = logging.getLogger(__name__)


Broadcaster = Callable[[dict], Awaitable[None]]


class CancelledByUser(Exception):
    """Signal, das Worker-Handler werfen können, wenn der Job vom
    Nutzer per cancel-Event abgebrochen wurde. Unterscheidet den Fall
    sauber von echten Fehlern."""
    pass


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
    # cancel_event wird beim Anlegen erzeugt und kann vom Worker
    # überprüft werden (event.is_set()). Der Cancel-Endpunkt setzt es.
    cancel_event: Optional[asyncio.Event] = None


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
        await self._cleanup_zombie_jobs()
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._run_worker(), name="job-worker")
            logger.info("Job-Worker gestartet")

    async def _cleanup_zombie_jobs(self) -> None:
        """Alle Jobs, die laut DB noch 'running', 'queued' oder 'pending'
        sind, beim Start auf 'failed' setzen. Nach einem Backend-Neustart
        können diese Jobs nicht mehr weiterlaufen -- sie würden die
        JobsBar-Anzeige sonst dauerhaft rotieren lassen."""
        rows = await db.fetch_all(
            "SELECT id, kind, status FROM jobs "
            "WHERE status IN ('running', 'queued', 'pending')"
        )
        if not rows:
            return
        ids = [r["id"] for r in rows]
        kinds = [f"{r['kind']}({r['id'][:8]})" for r in rows]
        placeholders = ",".join("?" * len(ids))
        await db.execute(
            f"UPDATE jobs SET status='failed', "
            f"error='Backend-Neustart -- Job wurde unterbrochen', "
            f"updated_at=datetime('now') WHERE id IN ({placeholders})",
            tuple(ids),
        )
        # Proxy-Status der betroffenen Dateien mit zurücksetzen, damit
        # sie nicht "in Bearbeitung" hängen.
        proxy_rows = await db.fetch_all(
            f"SELECT file_id FROM jobs WHERE id IN ({placeholders}) "
            f"AND kind = 'proxy' AND file_id IS NOT NULL",
            tuple(ids),
        )
        if proxy_rows:
            file_ids = [r["file_id"] for r in proxy_rows]
            fph = ",".join("?" * len(file_ids))
            await db.execute(
                f"UPDATE files SET proxy_status='failed' "
                f"WHERE id IN ({fph}) AND proxy_status='processing'",
                tuple(file_ids),
            )
        logger.info(
            f"Zombie-Jobs beim Start aufgeräumt: {len(rows)} ({', '.join(kinds)})"
        )

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
                  payload=payload or {}, cancel_event=asyncio.Event())
        await self._queue.put(job)
        await self._broadcast_job_event(job, "queued")
        return job_id

    async def active(self) -> Optional[dict]:
        if self._active is None:
            return None
        return self._job_to_dict(self._active)

    async def cancel(self, job_id: str) -> bool:
        """Markiert einen Job zum Abbrechen. Laufende Jobs beachten das
        Event an definierten Prüfpunkten (aktuell: Transkriptions-Chunks).
        Queue-Jobs, die noch nicht gestartet sind, werden beim Aufruf
        direkt als cancelled markiert."""
        # Wenn der aktive Job das ist: Event setzen, Worker prüft selber
        if self._active and self._active.id == job_id:
            if self._active.cancel_event is not None:
                self._active.cancel_event.set()
            return True
        # Wenn in der Queue: Status auf cancelled setzen. Der Worker
        # überspringt Jobs mit status=cancelled.
        await db.execute(
            "UPDATE jobs SET status='cancelled', updated_at=datetime('now') "
            "WHERE id = ? AND status IN ('pending','queued')",
            (job_id,),
        )
        return True

    async def _run_worker(self) -> None:
        while True:
            job = await self._queue.get()
            # Vor-Cancel prüfen (Job wurde in der Queue schon gecancelt)
            pre = await db.fetch_one("SELECT status FROM jobs WHERE id = ?", (job.id,))
            if pre and pre["status"] == "cancelled":
                self._queue.task_done()
                await self._broadcast_job_event(job, "cancelled")
                continue
            self._active = job
            try:
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except CancelledByUser:
                logger.info(f"Job {job.id} vom Nutzer abgebrochen")
                job.status = "cancelled"
                job.message = "Vom Nutzer abgebrochen"
                await self._persist(job)
                await self._broadcast_job_event(job, "cancelled")
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
        elif job.kind == "audio_mix":
            await self._process_audio_mix(job)
        elif job.kind == "transcribe":
            await self._process_transcribe(job)
        elif job.kind == "download_model":
            await self._process_download_model(job)
        else:
            raise RuntimeError(f"Unbekannter Job-Typ: {job.kind}")

        job.status = "completed"
        job.progress = 1.0
        await self._persist(job)
        await self._broadcast_job_event(job, "completed")

    async def _process_proxy(self, job: Job) -> None:
        assert job.file_id, "proxy-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT path, duration_s, fps, video_codec FROM files WHERE id = ?",
            (job.file_id,),
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
            source_codec=row["video_codec"],
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
            """SELECT path, video_codec, audio_codec, width, height, fps
               FROM files WHERE id = ?""",
            (prow["source_file_id"],),
        )
        if frow is None:
            raise RuntimeError("Quelldatei nicht gefunden")
        source_meta = {
            "video_codec": frow["video_codec"],
            "audio_codec": frow["audio_codec"],
            "width": frow["width"],
            "height": frow["height"],
            "fps": frow["fps"],
        }
        # Falls der Job einen EDL-Override mitbringt (z. B. Einzel-Clip-Export),
        # hat dieser Vorrang vor der gespeicherten Projekt-EDL.
        override = (job.payload or {}).get("edl_override")
        if override:
            edl = EDL.model_validate(override)
        else:
            edl = EDL.model_validate(_json.loads(prow["edl_json"] or "{}"))

        last_sent = -1.0
        last_step: str | None = None

        def on_progress(pct: float, phase: str, info: dict | None = None) -> None:
            nonlocal last_sent, last_step
            job.progress = pct
            step = (info or {}).get("step")
            # Broadcast, wenn:
            #  - >= 2 % Fortschritt seit letztem Event ODER
            #  - der Pipeline-Schritt wechselt (preparing -> encoding_clip
            #    -> clip_done -> merging -> done) ODER
            #  - wir in einer Finalisierungs-Phase sind
            should = (
                pct - last_sent >= 0.02
                or phase in ("merging", "done")
                or (step is not None and step != last_step)
            )
            if should:
                last_sent = pct
                if step is not None:
                    last_step = step
                msg = {
                    "type": "job_progress",
                    "job_id": job.id,
                    "kind": job.kind,
                    "project_id": job.project_id,
                    "file_id": job.file_id,
                    "progress": pct,
                    "phase": phase,
                }
                if info:
                    msg["info"] = info
                self._schedule_broadcast(msg)

        clip_tag = (job.payload or {}).get("clip_id")

        # Audio-Override: Pfade aller beteiligten Quelldateien aus der
        # DB holen. Der Render-Service mischt sie in Phase 2 ueber das
        # fertige Video.
        audio_sources: dict[str, str] = {}
        for ac in edl.audio_track:
            if ac.file_id in audio_sources:
                continue
            row = await db.fetch_one(
                "SELECT path FROM files WHERE id = ?", (ac.file_id,),
            )
            if row and row["path"]:
                audio_sources[ac.file_id] = Path(row["path"])

        final = await render_edl(
            source=Path(frow["path"]),
            edl=edl,
            job_id=job.id,
            progress_cb=on_progress,
            filename_suffix=f"clip-{clip_tag}" if clip_tag else "",
            source_meta=source_meta,
            audio_sources=audio_sources,
        )
        job.result_path = str(final)

    async def _process_audio_mix(self, job: Job) -> None:
        """Mischt die AudioClips aus job.payload['audio_track'] zu einer
        einzelnen WAV und registriert sie als Library-Datei. Das
        Ergebnis ist damit als audio-only-File im Editor weiter nutzbar
        und kann jederzeit heruntergeladen werden.

        payload:
          - audio_track: list[AudioClip-dict]
          - normalize: bool
          - mono: bool
          - name: str         (optional, Anzeige-Name)
          - folder_path: str  (optional, in welcher Library-Kategorie)
        """
        from app.models.edl import AudioClip
        from app.services.probe_service import probe_file, summarize

        payload = job.payload or {}
        raw_clips = payload.get("audio_track") or []
        if not raw_clips:
            raise RuntimeError("audio_mix: keine Audio-Clips im Payload")

        # AudioClip-Objekte wieder aufbauen (Sanitize + Validierung
        # ueber das Pydantic-Schema, dann haben wir die gleiche
        # Rundung wie im Backend-EDL).
        clips = [AudioClip.model_validate(c) for c in raw_clips]

        # Quelldateien pro file_id ermitteln
        audio_sources: dict[str, Path] = {}
        for c in clips:
            if c.file_id in audio_sources:
                continue
            row = await db.fetch_one(
                "SELECT path FROM files WHERE id = ?", (c.file_id,),
            )
            if row and row["path"]:
                audio_sources[c.file_id] = Path(row["path"])

        if not audio_sources:
            raise RuntimeError("audio_mix: keine Quelldateien auffindbar")

        # Ziel-Datei in originals/ ablegen, damit sie automatisch
        # Teil der Library wird. UUID = job_id, Endung .wav.
        new_file_id = uuid.uuid4().hex
        dest = ORIGINALS_DIR / f"{new_file_id}.wav"

        normalize = bool(payload.get("normalize", False))
        mono = bool(payload.get("mono", False))
        name_hint = payload.get("name") or "Audio-Mix"
        folder_path = payload.get("folder_path") or ""

        duration_s = await build_audio_mix_wav(
            audio_clips=clips,
            audio_sources=audio_sources,
            dest=dest,
            normalize=normalize,
            mono=mono,
        )

        # Library-Eintrag fuer die neue WAV
        original_name = f"{name_hint}.wav"
        probe_raw: dict = {}
        probe_summary: dict = {}
        try:
            probe_raw = await probe_file(dest)
            probe_summary = summarize(probe_raw)
        except Exception as e:
            logger.warning(f"ffprobe nach audio_mix fehlgeschlagen: {e}")
            probe_summary = {"duration_s": duration_s, "audio_codec": "pcm_s16le"}

        stored_name = dest.name
        size_bytes = dest.stat().st_size

        await db.execute(
            """
            INSERT INTO files (
                id, original_name, stored_name, path, size_bytes,
                mime_type, duration_s, width, height, fps,
                video_codec, audio_codec, folder_path, sha256, probe_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                new_file_id, original_name, stored_name, str(dest),
                size_bytes, "audio/wav",
                probe_summary.get("duration_s") or duration_s,
                None, None, None,          # keine Video-Dimensions
                None,                      # kein video_codec
                probe_summary.get("audio_codec") or "pcm_s16le",
                folder_path, None,
                json.dumps(probe_raw) if probe_raw else None,
            ),
        )

        # Waveform-Job anstossen, damit die Kachel in der Bibliothek
        # direkt eine Waveform zeigt.
        await self.enqueue("waveform", file_id=new_file_id)

        job.result_path = str(dest)
        job.payload["result_file_id"] = new_file_id
        await self._broadcast_file_event(new_file_id, "created")

    async def _process_sprite(self, job: Job) -> None:
        assert job.file_id, "sprite-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT proxy_path, path, duration_s FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["proxy_path"] or row["path"])
        if not src.exists():
            raise RuntimeError("Quelle für Sprite fehlt")
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
            raise RuntimeError("Quelle für Waveform fehlt")
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

    async def _process_transcribe(self, job: Job) -> None:
        """KI-Transkription: Audio aus dem Original extrahieren, Whisper
        darüber laufen lassen, Segmente als SRT schreiben. Payload kann
        `engine` und `model` enthalten -- fehlen sie, nimmt der Service
        die Empfehlung aus capabilities()."""
        assert job.file_id, "transcribe-Job benötigt file_id"
        row = await db.fetch_one(
            "SELECT path, original_name FROM files WHERE id = ?", (job.file_id,)
        )
        if row is None:
            raise RuntimeError("Datei nicht gefunden")
        src = Path(row["path"])
        if not src.exists():
            raise RuntimeError("Quelldatei fehlt auf der Platte")

        caps = transcribe_service.capabilities(scan=True)
        payload = job.payload or {}
        # Prioritaet: explizit im Payload > persistierte Nutzer-Wahl > Vorschlag
        engine = payload.get("engine") or caps.active_engine or caps.suggested_engine
        model = payload.get("model") or caps.active_model or caps.suggested_model
        if not engine or not caps.available:
            raise RuntimeError(
                "Transkription nicht verfügbar. Bitte in den Einstellungen "
                "ein Modell einrichten."
            )

        job.message = f"Audio extrahieren ({src.name})"
        await self._persist(job)
        await self._broadcast_job_event(job, "running")

        audio_path = TMP_DIR / f"tx-{job.file_id}.wav"
        try:
            await transcribe_service.extract_audio(src, audio_path)

            job.progress = 0.15
            job.message = f"Transkribiere mit {engine} / {model}"
            await self._persist(job)
            self._schedule_broadcast({
                "type": "job_progress",
                "job_id": job.id,
                "kind": job.kind,
                "file_id": job.file_id,
                "progress": job.progress,
                "phase": "transcribing",
            })

            last_sent = 0.15

            def on_prog(frac: float) -> None:
                nonlocal last_sent
                # frac ist 0..1 des Audio-Durchlaufs; wir mappen auf 0.15..0.95
                pct = 0.15 + max(0.0, min(1.0, frac)) * 0.80
                job.progress = pct
                if pct - last_sent >= 0.02:
                    last_sent = pct
                    self._schedule_broadcast({
                        "type": "job_progress",
                        "job_id": job.id,
                        "kind": job.kind,
                        "file_id": job.file_id,
                        "progress": pct,
                        "phase": "transcribing",
                    })

            # Segmente live pushen, sobald sie fertig sind -- das Frontend
            # ergänzt die Panel-Liste und zeigt Text mit, während der
            # Rest noch läuft.
            def on_segment(seg: dict) -> None:
                self._schedule_broadcast({
                    "type": "transcript_segment",
                    "job_id": job.id,
                    "file_id": job.file_id,
                    "segment": seg,
                })

            result = await transcribe_service.run_transcription(
                audio_path=audio_path,
                engine=engine,
                model=model,
                progress_cb=on_prog,
                segment_cb=on_segment,
                cancel_event=job.cancel_event,
            )

            # SRT schreiben
            srt = transcribe_service.segments_to_srt(result.segments)
            dest = TRANSCRIPTS_DIR / f"{job.file_id}.srt"
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(srt, encoding="utf-8")

            await db.execute(
                """UPDATE files
                   SET transcript_path=?, transcript_lang=?, transcript_model=?,
                       updated_at=datetime('now')
                   WHERE id = ?""",
                (str(dest), result.language, f"{result.engine}:{result.model}",
                 job.file_id),
            )
            job.result_path = str(dest)
            job.message = f"Fertig ({len(result.segments)} Segmente, {result.language or '?'})"
            await self._broadcast_file_event(job.file_id, "transcript_ready")
        finally:
            # Temp-WAV wegraeumen -- unabhängig davon ob erfolgreich
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass

    async def _process_download_model(self, job: Job) -> None:
        """Lädt ein Whisper-Modell in den Standard-Cache der jeweiligen
        Engine. payload = { engine, model }."""
        payload = job.payload or {}
        engine = payload.get("engine")
        model = payload.get("model")
        if not engine or not model:
            raise RuntimeError("download_model-Job braucht engine + model")
        job.message = f"Lade {engine} / {model}"
        await self._persist(job)
        await self._broadcast_job_event(job, "running")

        last_sent = 0.0

        def on_prog(frac: float) -> None:
            nonlocal last_sent
            job.progress = max(0.0, min(1.0, float(frac)))
            if job.progress - last_sent >= 0.01:
                last_sent = job.progress
                self._schedule_broadcast({
                    "type": "job_progress",
                    "job_id": job.id,
                    "kind": job.kind,
                    "progress": job.progress,
                    "phase": "downloading",
                })

        target = await transcribe_service.download_model(
            engine=engine, model=model,
            progress_cb=on_prog,
            cancel_event=job.cancel_event,
        )
        job.result_path = target
        job.message = f"{engine} / {model} bereit"

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
