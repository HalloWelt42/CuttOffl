"""
CuttOffl Backend - Tour-Recorder (einmaliger Helfer).

Nicht Teil des Produkts, sondern ein minimaler Helfer: waehrend der
Tour-Aufzeichnung (Bildschirmaufnahme parallel zur geklickten Tour)
schreibt das Frontend bei jedem Audio-Start einen Event mit Timestamp
und Text. Daraus baut tools/build_tour_audio.py spaeter die passende
Audio-Spur, die man in die Bildschirmaufnahme legen kann.

Aktiviert wird der Recorder Frontend-seitig per URL-Param
?tour_record=1 -- sonst postet das Frontend keine Events und diese
Routes sind inaktiv.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import DATA_DIR

router = APIRouter(prefix="/api/_recorder", tags=["recorder"])

# Eine einzige Aufnahme-Datei; kein Session-Konzept noetig fuer den
# einmaligen Use-Case. Das Frontend ueberschreibt sie beim tour_start.
LOG_PATH = DATA_DIR / "tmp" / "tour-recording.json"


class RecorderEvent(BaseModel):
    t_ms: float
    kind: str                    # 'tour_start' | 'audio_start' | 'tour_end'
    text: Optional[str] = None   # nur bei audio_start


def _read_all() -> list[dict]:
    if not LOG_PATH.exists():
        return []
    try:
        return json.loads(LOG_PATH.read_text("utf-8"))
    except Exception:
        return []


def _write_all(events: list[dict]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(events, ensure_ascii=False, indent=2), "utf-8")


@router.post("/event")
async def push_event(event: RecorderEvent) -> dict:
    """Haengt ein Event an die Aufzeichnung an. Bei kind='tour_start'
    wird die Datei geleert und neu begonnen (letzte Aufnahme fliegt)."""
    if event.kind == "tour_start":
        _write_all([event.model_dump()])
    else:
        events = _read_all()
        events.append(event.model_dump())
        _write_all(events)
    return {"ok": True, "count": len(_read_all()), "path": str(LOG_PATH)}


@router.get("/events")
async def list_events() -> list[dict]:
    """Gibt die aktuelle Event-Liste zurueck. Zur Kontrolle, bevor man
    das Audio-Build-Tool drueberlaufen laesst."""
    return _read_all()
