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


@router.get("/{job_id}")
async def get_job(job_id: str) -> dict:
    row = await db.fetch_one("SELECT * FROM jobs WHERE id = ?", (job_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    return dict(row)
