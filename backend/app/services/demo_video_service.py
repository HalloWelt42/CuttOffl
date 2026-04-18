"""
Demo-Video-Service -- sorgt dafür, dass das Big-Buck-Bunny-Demo-Video
in der Bibliothek liegt und mit allen Ableitungen (Proxy, Thumbnail,
Sprite, Wellenform) arbeitsfähig ist.

Wird beim Backend-Start (lifespan) aufgerufen und vom Reset-Tab aus
(POST /api/system/reset mit target='demo-video-reload').

Verantwortlich für:
  - Einmaliges Importieren der Datei unter data/demo/cuttoffl-demo.mov
    in die files-Tabelle mit dem protected=1-Flag
  - Triggern der Thumbnail-/Proxy-Jobs, damit das Demo sofort in der
    Bibliothek funktioniert
  - "Entfernen" des Demo-Videos aus der Bibliothek (DB-Eintrag +
    abgeleitete Dateien weg, Original bleibt, damit re-import
    sofort wieder möglich ist)
  - "Neu laden" = optional fetch_demo_video.sh anstoßen, dann
    importieren
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from app.config import DATA_DIR, ORIGINALS_DIR
from app.db import db

logger = logging.getLogger(__name__)

DEMO_DIR = DATA_DIR / "demo"
DEMO_SOURCE = DEMO_DIR / "cuttoffl-demo.mov"
DEMO_ORIGINAL_NAME = "CuttOffl-Demo (Big Buck Bunny).mov"
DEMO_FOLDER = "Demo"
DEMO_TAGS = ["demo"]


async def demo_video_source_exists() -> bool:
    return DEMO_SOURCE.exists() and DEMO_SOURCE.stat().st_size > 0


async def demo_db_entry() -> dict | None:
    """Aktueller DB-Eintrag des Demo-Videos, falls vorhanden."""
    row = await db.fetch_one(
        "SELECT * FROM files WHERE protected = 1 ORDER BY created_at ASC LIMIT 1"
    )
    return dict(row) if row else None


async def ensure_demo_imported() -> str | None:
    """Wenn das Demo-Video auf der Platte liegt, aber in der DB kein
    protected-Eintrag existiert, wird es importiert. Gibt die file_id
    zurück (oder None, wenn kein Demo auf der Platte liegt)."""
    if not await demo_video_source_exists():
        return None
    existing = await demo_db_entry()
    if existing is not None:
        # Schon importiert -- nichts zu tun.
        return existing["id"]
    return await _import_demo()


async def _import_demo() -> str:
    """Kopiert das Demo-Video als neue Datei in ORIGINALS_DIR, legt den
    DB-Eintrag an und stößt die Thumbnail- und Proxy-Jobs an. Die
    Quelle in data/demo/ bleibt unangetastet -- so kann das Video
    beim nächsten Reset sofort wieder importiert werden."""
    from shutil import copy2

    # Lokaler Import vermeidet Zirkularimport zwischen job_service
    # (importiert diesen Modul in _cleanup_zombie_jobs) und umgekehrt.
    from app.services.job_service import job_service
    from app.services.probe_service import probe_file, summarize

    ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4().hex
    suffix = DEMO_SOURCE.suffix or ".mov"
    stored_name = f"{file_id}{suffix}"
    dest = ORIGINALS_DIR / stored_name

    try:
        copy2(DEMO_SOURCE, dest)
    except OSError as e:
        logger.error(f"[demo] kopieren fehlgeschlagen: {e}")
        raise

    size_bytes = dest.stat().st_size
    probe_summary: dict = {}
    probe_raw: dict = {}
    try:
        probe_raw = await probe_file(dest)
        probe_summary = summarize(probe_raw)
    except Exception as e:
        logger.warning(f"[demo] ffprobe fehlgeschlagen: {e}")

    await db.execute(
        """
        INSERT INTO files (
            id, original_name, stored_name, path, size_bytes,
            mime_type, duration_s, width, height, fps,
            video_codec, audio_codec, folder_path, probe_json,
            tags_json, protected
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """,
        (
            file_id,
            DEMO_ORIGINAL_NAME,
            stored_name,
            str(dest),
            size_bytes,
            "video/quicktime" if suffix.lower() == ".mov" else None,
            probe_summary.get("duration_s"),
            probe_summary.get("width"),
            probe_summary.get("height"),
            probe_summary.get("fps"),
            probe_summary.get("video_codec"),
            probe_summary.get("audio_codec"),
            DEMO_FOLDER,
            json.dumps(probe_raw) if probe_raw else None,
            json.dumps(DEMO_TAGS, ensure_ascii=False),
        ),
    )

    await job_service.enqueue("thumbnail", file_id=file_id)
    await job_service.enqueue("proxy", file_id=file_id)
    logger.info(
        f"[demo] importiert als {file_id} ({size_bytes // (1024 * 1024)} MB)"
    )
    return file_id


async def remove_demo_from_library() -> bool:
    """Entfernt den DB-Eintrag + alle abgeleiteten Dateien des
    Demo-Videos. Die Quelle in data/demo/ bleibt liegen, damit der
    Nutzer es jederzeit wieder importieren kann.

    Gibt True zurück, wenn etwas gelöscht wurde."""
    row = await demo_db_entry()
    if row is None:
        return False
    # abgeleitete Dateien wegräumen
    for key in ("path", "proxy_path", "thumb_path", "sprite_path",
                "waveform_path", "transcript_path"):
        p = row.get(key)
        if p:
            try:
                Path(p).unlink(missing_ok=True)
            except OSError:
                pass
    # Projekte, die auf diese Datei verweisen, mit entfernen -- sonst
    # gibt es Waisen im Dashboard.
    await db.execute(
        "DELETE FROM projects WHERE source_file_id = ?", (row["id"],),
    )
    await db.execute("DELETE FROM files WHERE id = ?", (row["id"],))
    logger.info(f"[demo] aus Bibliothek entfernt ({row['id']})")
    return True


async def fetch_demo_source() -> bool:
    """Ruft tools/fetch_demo_video.sh auf -- relevant, wenn die Quelle
    in data/demo/ fehlt (z. B. weil der User sie gelöscht hat).
    Synchron wartend, weil der Download groß ist und der User das
    Ergebnis im UI erwartet."""
    script = Path(__file__).resolve().parent.parent.parent.parent / "tools" / "fetch_demo_video.sh"
    if not script.exists():
        logger.warning(f"[demo] fetch-Script nicht gefunden: {script}")
        return False
    proc = await asyncio.create_subprocess_exec(
        "bash", str(script),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        logger.error(
            f"[demo] Download fehlgeschlagen: {stderr.decode('utf-8', errors='replace')}"
        )
        return False
    logger.info(f"[demo] Download ok: {stdout.decode('utf-8', errors='replace').strip()}")
    return True
