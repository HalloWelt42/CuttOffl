"""
CuttOffl Backend - System-Router.

Health-Check, Version, HW-Info, Disk-Nutzung, Codec-Empfehlungen.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter

from app.config import (
    APP_NAME, DATA_DIR, EXPORTS_DIR, HOST, ORIGINALS_DIR,
    PORT, PROXIES_DIR, SPRITES_DIR, THUMBS_DIR, TMP_DIR, VERSION, WAVEFORMS_DIR,
)
from pydantic import BaseModel

from app.db import db
from app.models.schemas import PingResponse
from app.services.codec_service import get_recommendations
from app.services.ffmpeg_service import get_ffmpeg_version
from app.services.hwaccel_service import detect_hw_encoder
from app.services import user_config as uc

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    hw = await detect_hw_encoder()
    ff_version = await get_ffmpeg_version()
    return PingResponse(
        app=APP_NAME,
        version=VERSION,
        status="ok",
        host=HOST,
        port=PORT,
        hw_encoder=hw,
        ffmpeg_version=ff_version,
    )


def _dir_bytes(p: Path) -> int:
    if not p.exists():
        return 0
    total = 0
    for f in p.rglob("*"):
        try:
            if f.is_file():
                total += f.stat().st_size
        except OSError:
            pass
    return total


@router.get("/system/storage")
async def system_storage() -> dict:
    """Belegter Platz je Datenbereich und freier Platz auf dem Host-Volume."""
    try:
        usage = shutil.disk_usage(str(DATA_DIR))
        disk = {
            "total_bytes": usage.total,
            "used_bytes":  usage.used,
            "free_bytes":  usage.free,
        }
    except Exception:
        disk = None

    buckets = {
        "originals":  _dir_bytes(ORIGINALS_DIR),
        "proxies":    _dir_bytes(PROXIES_DIR),
        "exports":    _dir_bytes(EXPORTS_DIR),
        "thumbs":     _dir_bytes(THUMBS_DIR),
        "sprites":    _dir_bytes(SPRITES_DIR),
        "waveforms":  _dir_bytes(WAVEFORMS_DIR),
        "tmp":        _dir_bytes(TMP_DIR),
    }
    buckets["total"] = sum(buckets.values())
    return {
        "disk": disk,
        "buckets": buckets,
        "data_dir": str(DATA_DIR),
    }


@router.get("/system/overview")
async def system_overview() -> dict:
    """Kompakte Startseite-Statistik: Counts + HW + Codec-Empfehlungen."""
    hw = await detect_hw_encoder()
    codecs = await get_recommendations()

    row_files    = await db.fetch_one("SELECT COUNT(*) c FROM files")
    row_projects = await db.fetch_one("SELECT COUNT(*) c FROM projects")
    row_exports  = await db.fetch_one(
        "SELECT COUNT(*) c FROM jobs WHERE kind='render' AND status='completed' "
        "AND result_path IS NOT NULL"
    )
    row_jobs_active = await db.fetch_one(
        "SELECT COUNT(*) c FROM jobs WHERE status IN ('pending','running')"
    )
    row_jobs_failed = await db.fetch_one(
        "SELECT COUNT(*) c FROM jobs WHERE status='failed'"
    )
    row_total_dur = await db.fetch_one(
        "SELECT COALESCE(SUM(duration_s), 0) s FROM files"
    )

    return {
        "counts": {
            "files":           row_files["c"]    if row_files    else 0,
            "projects":        row_projects["c"] if row_projects else 0,
            "exports":         row_exports["c"]  if row_exports  else 0,
            "active_jobs":     row_jobs_active["c"] if row_jobs_active else 0,
            "failed_jobs":     row_jobs_failed["c"] if row_jobs_failed else 0,
        },
        "total_duration_s": float(row_total_dur["s"]) if row_total_dur else 0.0,
        "hw_encoder": hw,
        "codecs": codecs,
    }


@router.get("/system/codecs")
async def system_codecs() -> dict:
    return await get_recommendations()


# --- Nutzer-Pfade ---------------------------------------------------------

class PathsBody(BaseModel):
    originals_dir: str | None = None
    exports_dir:   str | None = None


@router.get("/system/paths")
async def system_paths() -> dict:
    """Gibt aktuell aktive und persistierte Pfade zurück."""
    data = uc.load()
    return {
        "active": {
            "originals_dir": str(ORIGINALS_DIR),
            "exports_dir":   str(EXPORTS_DIR),
        },
        "saved": {
            "originals_dir": data.get("originals_dir"),
            "exports_dir":   data.get("exports_dir"),
        },
        "default": {
            "originals_dir": str(DATA_DIR / "originals"),
            "exports_dir":   str(DATA_DIR / "exports"),
        },
        "note": (
            "Aenderungen werden persistiert, aber erst nach einem Neustart "
            "des Backends wirksam. Bereits vorhandene Dateien bleiben am "
            "alten Ort -- sie müssen bei Bedarf manuell übertragen werden."
        ),
    }


@router.put("/system/paths")
async def set_system_paths(body: PathsBody) -> dict:
    """Speichert neue Pfade. Validiert jeden gegen Existenz, is_dir und
    Schreibrecht. Ein leerer String setzt den jeweiligen Override zurück
    auf den Default.
    """
    current = uc.load()

    def _apply(key: str, value: str | None):
        if value is None:
            return None  # nichts tun
        v = value.strip()
        if v == "":
            current.pop(key, None)
            return None
        err = uc.validate_directory(v)
        if err:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"{key}: {err}")
        # resolve -> speichere expandierten, absoluten Pfad
        from pathlib import Path as _P
        current[key] = str(_P(v).expanduser().resolve())
        return None

    _apply("originals_dir", body.originals_dir)
    _apply("exports_dir",   body.exports_dir)
    uc.save(current)
    return {
        "saved": current,
        "restart_required": True,
    }
