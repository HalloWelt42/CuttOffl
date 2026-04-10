"""
CuttOffl Backend - Ordner-Router.

Ordner sind rein virtuell (Spalte files.folder_path). Dieser Router
liefert Navigationshilfen fuer die UI:

  GET    /api/folders            flache Uebersicht aller belegten Pfade
  GET    /api/folders/tree       rekursiver Ordnerbaum mit Dateizaehlern
  GET    /api/folders/children   direkte Unterordner + Dateizahl einer Ebene
  POST   /api/folders/rename     Ordner (und alle darunter) umbenennen
  DELETE /api/folders            nur leere Ordner -- per Design
                                 (Verschieben vor dem Loeschen noetig)
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.db import db
from app.services.folder_service import (
    FolderError, is_descendant, normalize, parent_of, rename_prefix,
)

router = APIRouter(prefix="/api/folders", tags=["folders"])


# --- Hilfen ---------------------------------------------------------------

async def _all_folder_paths() -> list[str]:
    """Alle belegten folder_path-Werte, Duplikate entfernt, sortiert."""
    rows = await db.fetch_all(
        "SELECT DISTINCT folder_path FROM files WHERE folder_path IS NOT NULL"
    )
    return sorted({(r["folder_path"] or "") for r in rows})


def _expand_with_parents(paths: list[str]) -> list[str]:
    """Fuegt alle Vorfahren-Pfade zur Liste hinzu, damit der Baum auch
    Zwischenebenen enthaelt, selbst wenn dort keine Dateien liegen."""
    full: set[str] = set()
    for p in paths:
        full.add(p)
        while p:
            p = parent_of(p)
            full.add(p)
    return sorted(full)


# --- Schemas --------------------------------------------------------------

class FolderRenameBody(BaseModel):
    source: str = Field(default="", max_length=512)
    target: str = Field(default="", max_length=512)


# --- Endpunkte ------------------------------------------------------------

@router.get("")
async def list_folders() -> list[dict]:
    """Flache Liste aller Ordner mit direkter Dateizahl und rekursiver Summe."""
    raw = await _all_folder_paths()
    all_paths = _expand_with_parents(raw)

    result: list[dict] = []
    for p in all_paths:
        if p == "":
            # Wurzel nur zurueckgeben, wenn es Dateien direkt drin gibt
            direct = await db.fetch_one(
                "SELECT COUNT(*) c FROM files WHERE folder_path = ''"
            )
            total = await db.fetch_one("SELECT COUNT(*) c FROM files")
            result.append({
                "path": "",
                "name": "",
                "parent": None,
                "direct_count": direct["c"] if direct else 0,
                "total_count":  total["c"]  if total  else 0,
            })
            continue
        direct = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ?", (p,)
        )
        total = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ? OR folder_path LIKE ?",
            (p, p + "/%"),
        )
        result.append({
            "path": p,
            "name": p.rsplit("/", 1)[-1],
            "parent": parent_of(p),
            "direct_count": direct["c"] if direct else 0,
            "total_count":  total["c"]  if total  else 0,
        })
    return result


@router.get("/children")
async def children(folder: str = "") -> dict:
    """Direkte Unterordner + Dateizahl der jeweiligen Ebene."""
    try:
        f = normalize(folder)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Alle Pfade, die genau eine Ebene unter f liegen
    all_paths = _expand_with_parents(await _all_folder_paths())
    prefix = f + "/" if f else ""

    kids: list[dict] = []
    seen: set[str] = set()
    for p in all_paths:
        if not p or p == f:
            continue
        if prefix and not p.startswith(prefix):
            continue
        if not prefix and "/" in p:
            # Wurzel-Kinder haben keinen Slash
            p = p.split("/")[0]
        rest = p[len(prefix):] if prefix else p
        first = rest.split("/")[0]
        full = (prefix + first) if prefix else first
        if full in seen:
            continue
        seen.add(full)
        direct = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ?", (full,)
        )
        total = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ? OR folder_path LIKE ?",
            (full, full + "/%"),
        )
        kids.append({
            "path": full,
            "name": first,
            "direct_count": direct["c"] if direct else 0,
            "total_count":  total["c"]  if total  else 0,
        })

    kids.sort(key=lambda x: x["name"].lower())

    # Dateien auf dieser Ebene direkt
    row = await db.fetch_one(
        "SELECT COUNT(*) c FROM files WHERE folder_path = ?", (f,)
    )
    file_count = row["c"] if row else 0

    return {
        "folder": f,
        "parent": parent_of(f) if f else None,
        "children": kids,
        "file_count": file_count,
    }


@router.get("/tree")
async def tree() -> dict:
    """Rekursiver Baum aller Ordner mit Dateizahlen. Fuer die Sidebar oder
    einen Tree-View."""
    all_paths = _expand_with_parents(await _all_folder_paths())

    # Map path -> node
    nodes: dict[str, dict] = {}
    for p in all_paths:
        nodes[p] = {
            "path": p,
            "name": p.rsplit("/", 1)[-1] if p else "",
            "children": [],
            "direct_count": 0,
            "total_count": 0,
        }
    for p in list(nodes.keys()):
        direct = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ?", (p,)
        )
        total = await db.fetch_one(
            "SELECT COUNT(*) c FROM files WHERE folder_path = ? OR folder_path LIKE ?",
            (p, p + "/%"),
        )
        nodes[p]["direct_count"] = direct["c"] if direct else 0
        nodes[p]["total_count"]  = total["c"]  if total  else 0

    # Eltern-Kind-Verknuepfung
    for p, node in nodes.items():
        if p == "":
            continue
        par = parent_of(p)
        if par in nodes:
            nodes[par]["children"].append(node)

    for node in nodes.values():
        node["children"].sort(key=lambda x: x["name"].lower())

    return nodes.get("", {
        "path": "", "name": "", "children": [],
        "direct_count": 0, "total_count": 0,
    })


@router.post("/rename")
async def rename_folder(body: FolderRenameBody) -> dict:
    """Benennt einen Ordner um und verschiebt alle darunter liegenden
    Dateien entsprechend. Zielpfad darf kein Nachfahre des Quellpfads sein.
    """
    try:
        src = normalize(body.source)
        dst = normalize(body.target)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if src == dst:
        return {"moved": 0, "source": src, "target": dst}
    if src == "":
        raise HTTPException(status_code=400, detail="Wurzel kann nicht umbenannt werden")
    if is_descendant(dst, src):
        raise HTTPException(
            status_code=400,
            detail="Zielpfad darf nicht im Quellpfad liegen",
        )

    rows = await db.fetch_all(
        "SELECT id, folder_path FROM files WHERE folder_path = ? OR folder_path LIKE ?",
        (src, src + "/%"),
    )
    if not rows:
        return {"moved": 0, "source": src, "target": dst}

    for r in rows:
        new_path = rename_prefix(r["folder_path"], src, dst)
        await db.execute(
            "UPDATE files SET folder_path = ?, updated_at=datetime('now') WHERE id = ?",
            (new_path, r["id"]),
        )
    return {"moved": len(rows), "source": src, "target": dst}


@router.delete("")
async def delete_folder(folder: str) -> dict:
    """Loescht einen leeren Ordner (faktisch: entfernt die Ebene aus der
    Baum-Anzeige -- da Ordner rein virtuell sind, genuegt es zu pruefen,
    dass keine Dateien mehr darunter liegen).
    """
    try:
        f = normalize(folder)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if f == "":
        raise HTTPException(status_code=400, detail="Wurzel kann nicht geloescht werden")

    row = await db.fetch_one(
        "SELECT COUNT(*) c FROM files WHERE folder_path = ? OR folder_path LIKE ?",
        (f, f + "/%"),
    )
    count = row["c"] if row else 0
    if count > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Ordner ist nicht leer ({count} Datei(en)). Bitte zuerst leeren oder verschieben.",
        )
    # Da Ordner rein virtuell sind und aus der Dateimenge abgeleitet werden,
    # verschwindet er automatisch, sobald keine Datei mehr darauf zeigt.
    return {"deleted": f, "empty": True}
