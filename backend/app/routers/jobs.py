"""
CuttOffl Backend - Jobs-Router.

Aktuelle Job-Liste, Einzel-Status, aktiver Job.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import db
from app.services.job_service import job_service

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(limit: int = 50) -> list[dict]:
    rows = await db.fetch_all(
        "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    return [dict(r) for r in rows]


@router.get("/active")
async def active_job() -> dict:
    active = await job_service.active()
    return {"active": active}


@router.delete("/failed")
async def clear_failed_jobs() -> dict:
    """Loescht alle fehlgeschlagenen Jobs aus der Historie."""
    row = await db.fetch_one(
        "SELECT COUNT(*) c FROM jobs WHERE status = 'failed'"
    )
    count = row["c"] if row else 0
    await db.execute("DELETE FROM jobs WHERE status = 'failed'")
    return {"deleted": count}


@router.delete("/completed")
async def clear_completed_jobs(keep_renders: bool = True) -> dict:
    """Loescht abgeschlossene Hintergrund-Jobs (Proxy/Thumbnail/Sprite/Waveform).
    Render-Jobs werden standardmaessig behalten, weil sie die Referenz auf das
    fertige Export-Video sind; kann per keep_renders=false umgeschaltet werden.
    """
    if keep_renders:
        where = ("status = 'completed' "
                 "AND kind IN ('proxy','thumbnail','sprite','waveform','keyframes')")
    else:
        where = "status = 'completed'"
    row = await db.fetch_one(f"SELECT COUNT(*) c FROM jobs WHERE {where}")
    count = row["c"] if row else 0
    await db.execute(f"DELETE FROM jobs WHERE {where}")
    return {"deleted": count}


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    row = await db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return dict(row)
