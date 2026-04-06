"""
CuttOffl Backend - Projects-Router (EDL-CRUD + Render-Trigger).
"""

from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, HTTPException

from app.db import db
from app.models.edl import (
    EDL, OutputProfile, ProjectCreate, ProjectOut, ProjectUpdate,
    RenderStartResponse,
)
from app.services.error_helper import sanitize_error
from app.services.job_service import job_service

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _empty_edl(source_file_id: str) -> EDL:
    return EDL(source_file_id=source_file_id, timeline=[], output=OutputProfile())


def _row_to_project(row) -> ProjectOut:
    raw = row["edl_json"] or "{}"
    try:
        data = json.loads(raw)
        edl = EDL.model_validate(data)
    except Exception:
        edl = _empty_edl(row["source_file_id"] or "")
    return ProjectOut(
        id=row["id"],
        name=row["name"],
        source_file_id=row["source_file_id"],
        edl=edl,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("", response_model=list[ProjectOut])
async def list_projects() -> list[ProjectOut]:
    rows = await db.fetch_all("SELECT * FROM projects ORDER BY updated_at DESC")
    return [_row_to_project(r) for r in rows]


@router.post("", response_model=ProjectOut, status_code=201)
async def create_project(body: ProjectCreate) -> ProjectOut:
    src = await db.fetch_one("SELECT id FROM files WHERE id = ?", (body.source_file_id,))
    if src is None:
        raise HTTPException(status_code=404, detail="Quelldatei nicht gefunden")

    edl = body.edl or _empty_edl(body.source_file_id)
    if edl.source_file_id != body.source_file_id:
        edl = EDL(source_file_id=body.source_file_id,
                  timeline=edl.timeline, output=edl.output)

    pid = uuid.uuid4().hex
    await db.execute(
        """INSERT INTO projects (id, name, source_file_id, edl_json)
           VALUES (?, ?, ?, ?)""",
        (pid, body.name, body.source_file_id, edl.model_dump_json()),
    )
    row = await db.fetch_one("SELECT * FROM projects WHERE id = ?", (pid,))
    return _row_to_project(row)


@router.get("/{project_id}", response_model=ProjectOut)
async def get_project(project_id: str) -> ProjectOut:
    row = await db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    return _row_to_project(row)


@router.put("/{project_id}", response_model=ProjectOut)
async def update_project(project_id: str, body: ProjectUpdate) -> ProjectOut:
    row = await db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")

    name = body.name if body.name is not None else row["name"]
    if body.edl is not None:
        # Konsistenz: EDL-source muss zum Projekt passen
        if body.edl.source_file_id != row["source_file_id"]:
            raise HTTPException(
                status_code=400,
                detail="EDL.source_file_id weicht vom Projekt ab",
            )
        edl_json = body.edl.model_dump_json()
    else:
        edl_json = row["edl_json"]

    await db.execute(
        """UPDATE projects SET name=?, edl_json=?, updated_at=datetime('now')
           WHERE id = ?""",
        (name, edl_json, project_id),
    )
    row = await db.fetch_one("SELECT * FROM projects WHERE id = ?", (project_id,))
    return _row_to_project(row)


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> dict:
    row = await db.fetch_one("SELECT id FROM projects WHERE id = ?", (project_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    await db.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    return {"deleted": project_id}


@router.post("/{project_id}/render", response_model=RenderStartResponse)
async def render_project(project_id: str) -> RenderStartResponse:
    row = await db.fetch_one("SELECT id, source_file_id, edl_json FROM projects WHERE id = ?",
                             (project_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="Projekt nicht gefunden")
    try:
        edl = EDL.model_validate(json.loads(row["edl_json"] or "{}"))
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"EDL unlesbar: {sanitize_error(str(e))}",
        )
    if not edl.timeline:
        raise HTTPException(status_code=400, detail="EDL-Timeline ist leer")

    job_id = await job_service.enqueue(
        "render",
        file_id=row["source_file_id"],
        project_id=project_id,
    )
    return RenderStartResponse(job_id=job_id)
