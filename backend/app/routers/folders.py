"""
CuttOffl Backend - Ordner-Router.

Ordner sind rein virtuell (Spalte files.folder_path). Dieser Router
liefert Navigationshilfen für die UI:

  GET    /api/folders            flache Übersicht aller belegten Pfade
  GET    /api/folders/tree       rekursiver Ordnerbaum mit Dateizählern
  GET    /api/folders/children   direkte Unterordner + Dateizahl einer Ebene
  GET    /api/folders/download   alle Original-Dateien als ZIP (Stream)
  POST   /api/folders/rename     Ordner (und alle darunter) umbenennen
  DELETE /api/folders            nur leere Ordner -- per Design
                                 (Verschieben vor dem Löschen nötig)
"""

from __future__ import annotations

import logging
import re
import zipfile
from pathlib import Path
from typing import Iterable, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.db import db
from app.services.folder_service import (
    FolderError, is_descendant, normalize, parent_of, rename_prefix,
)

logger = logging.getLogger(__name__)

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
            # Wurzel nur zurückgeben, wenn es Dateien direkt drin gibt
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


_BAD_ZIP_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')


def _slug_filename(s: str, maxlen: int = 80) -> str:
    s = (s or "").strip()
    s = _BAD_ZIP_CHARS.sub("_", s)
    s = re.sub(r"\s+", " ", s)
    return (s[:maxlen].strip(" ._")) or "Ordner"


def _safe_zip_member(folder_base: str, folder_path: str, original_name: str) -> str:
    """Baut den Pfad innerhalb des ZIPs.
    - folder_base ist der Wurzel-Ordner des Downloads (wird weggeschnitten)
    - folder_path ist der aktuelle Ordner der Datei
    - original_name ist der Anzeigename
    """
    rel = folder_path or ""
    if folder_base:
        if rel == folder_base:
            rel = ""
        elif rel.startswith(folder_base + "/"):
            rel = rel[len(folder_base) + 1:]
    # Sichere einzelne Namen
    rel_parts = [re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", p) for p in rel.split("/") if p]
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", original_name or "datei")
    return "/".join([*rel_parts, name]) if rel_parts else name


@router.get("/download")
async def download_folder_zip(
    folder: str = "",
    recursive: bool = True,
):
    """Liefert alle Originaldateien des Ordners (optional rekursiv) als
    ZIP-Stream aus. Bei `folder='' & recursive=False` wird die Wurzel
    ausgeliefert (nur direkte Dateien). Bei `folder='' & recursive=True`
    werden alle Dateien der Bibliothek verpackt.

    Hinweis: Videos sind in der Regel bereits komprimiert -- das ZIP
    nutzt daher `ZIP_STORED` (keine erneute Kompression) und streamt
    mit konstanter Speicherlast.
    """
    try:
        base = normalize(folder)
    except FolderError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if recursive and base:
        rows = await db.fetch_all(
            """SELECT original_name, path, folder_path, size_bytes, transcript_path
               FROM files WHERE folder_path = ? OR folder_path LIKE ?
               ORDER BY folder_path, original_name""",
            (base, base + "/%"),
        )
    elif recursive:
        rows = await db.fetch_all(
            """SELECT original_name, path, folder_path, size_bytes, transcript_path
               FROM files ORDER BY folder_path, original_name"""
        )
    else:
        rows = await db.fetch_all(
            """SELECT original_name, path, folder_path, size_bytes, transcript_path
               FROM files WHERE folder_path = ?
               ORDER BY original_name""",
            (base,),
        )
    if not rows:
        raise HTTPException(status_code=404, detail="Keine Dateien im Ordner")

    # Auf existierende Dateien reduzieren. Transcript-Pfade (SRT) werden
    # zusaetzlich als eigene Eintraege im ZIP gefuehrt -- im selben
    # Ordner wie das Video, mit passendem Dateinamen.
    items: list[tuple[str, Path]] = []
    transcripts: list[tuple[str, str]] = []   # (member_name, srt_text)
    missing: list[str] = []
    for r in rows:
        p = Path(r["path"])
        if not p.exists():
            missing.append(r["original_name"])
            continue
        member = _safe_zip_member(base, r["folder_path"] or "", r["original_name"])
        items.append((member, p))
        # SRT + VTT pro Video mit rein, wenn Transkript da
        tp = r["transcript_path"] if "transcript_path" in r.keys() else None
        if tp and Path(tp).exists():
            try:
                srt_text = Path(tp).read_text(encoding="utf-8")
                stem_member = member.rsplit(".", 1)[0]
                transcripts.append((f"{stem_member}.srt", srt_text))
                # VTT lokal erzeugen
                from app.services import transcribe_service as _tx
                vtt_text = _tx.segments_to_vtt(_tx.parse_srt(srt_text))
                transcripts.append((f"{stem_member}.vtt", vtt_text))
            except OSError:
                pass
    if missing:
        logger.info(f"ZIP-Download: {len(missing)} fehlende Datei(en) übersprungen")
    if not items:
        raise HTTPException(status_code=410, detail="Alle Dateien im Ordner fehlen auf der Platte")

    def _generate() -> Iterable[bytes]:
        # Streaming: wir schreiben das ZIP in einen einfachen In-Memory-
        # Puffer und yielden chunk-weise. Durch ZIP_STORED und fester
        # Reihenfolge bleibt der Speicherbedarf klein (Header + ein
        # Chunk), auch bei großen Dateien -- Central Directory wird am
        # Ende angehängt.
        class _Buffer:
            def __init__(self):
                self.data = bytearray()
                self.pos = 0

            def write(self, b):
                self.data.extend(b)
                self.pos += len(b)
                return len(b)

            def tell(self):
                return self.pos

            def flush(self):
                pass

            def take(self):
                out = bytes(self.data)
                self.data = bytearray()
                return out

        buf = _Buffer()
        # allowZip64 ist ab Py 3.4 Default True, aber explizit zur Klarheit
        with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_STORED,
                             allowZip64=True) as zf:
            for member, path in items:
                # Einzelne Datei chunked in den ZIP-Eintrag schreiben
                zinfo = zipfile.ZipInfo(member)
                zinfo.compress_type = zipfile.ZIP_STORED
                with path.open("rb") as src, zf.open(zinfo, mode="w", force_zip64=True) as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
                        if len(buf.data) >= 512 * 1024:
                            yield buf.take()
                if len(buf.data) > 0:
                    yield buf.take()
            # Transkripte (SRT + VTT) nach allen Videos einpacken
            for (t_member, t_text) in transcripts:
                zf.writestr(t_member, t_text)
                if len(buf.data) > 0:
                    yield buf.take()
        # Central directory wurde beim Close geschrieben -- letzten Puffer leeren
        if len(buf.data) > 0:
            yield buf.take()

    name = _slug_filename(base or "Bibliothek")
    filename = f"CuttOffl - {name}.zip"
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(_generate(), media_type="application/zip", headers=headers)


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
    """Löscht einen leeren Ordner (faktisch: entfernt die Ebene aus der
    Baum-Anzeige -- da Ordner rein virtuell sind, genügt es zu prüfen,
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
