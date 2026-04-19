"""
CuttOffl Backend - Tour-Recorder.

Einmaliger Helfer fuer die Demo-Bildschirmaufnahme: das Backend merkt
sich waehrend einer Aufnahme-Session, wann welche Audio- und Video-
Ressource geladen wurde. Daraus baut tools/build_tour_audio.py die
Audio-Spur fuer das Screencast-Video.

Architektur:
  - Das Backend ist die einzige Wahrheit. Jeder Audio-/Video-Call
    landet ohnehin hier (Tour-MP3, TTS, Proxy-Video). Die
    record_middleware loggt diese Requests automatisch, sobald eine
    Session laeuft.
  - Das Frontend muss nur zwei Endpoints rufen: start und stop.
  - Eigene Event-Typen (audio/video/tts) werden anhand des URL-
    Pfades klassifiziert, nicht vom Frontend geschickt.

Das Frontend in tourRecorder.js ruft:
  - POST /api/_recorder/start  -- beim Tour-Start
  - POST /api/_recorder/stop   -- beim Tour-Ende

Nicht mehr:
  - POST /api/_recorder/event  -- deprecated; bleibt als Kompat-
    Endpoint erhalten, macht aber nichts Neues mehr.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import DATA_DIR

router = APIRouter(prefix="/api/_recorder", tags=["recorder"])

LOG_PATH = DATA_DIR / "tmp" / "tour-recording.json"


# ---------------------------------------------------------------------------
# Session-State (einfach: eine globale Session, ausreicht fuer den
# einmaligen Use-Case).
# ---------------------------------------------------------------------------

class _Session:
    active: bool = False
    t0: float = 0.0           # monotonic-Referenz beim Start
    events: list[dict] = []

    @classmethod
    def start(cls) -> None:
        cls.active = True
        cls.t0 = time.monotonic()
        cls.events = [{"t_ms": 0.0, "kind": "tour_start"}]
        cls._flush()

    @classmethod
    def stop(cls) -> None:
        if cls.active:
            cls.events.append({"t_ms": cls._now_ms(), "kind": "tour_end"})
            cls._flush()
        cls.active = False

    @classmethod
    def append(cls, event: dict) -> None:
        if not cls.active:
            return
        event = {"t_ms": cls._now_ms(), **event}
        cls.events.append(event)
        cls._flush()

    @classmethod
    def _now_ms(cls) -> float:
        return (time.monotonic() - cls.t0) * 1000.0

    @classmethod
    def _flush(cls) -> None:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text(
            json.dumps(cls.events, ensure_ascii=False, indent=2),
            "utf-8",
        )


# ---------------------------------------------------------------------------
# Middleware-Helfer: eingehende Requests automatisch klassifizieren.
# ---------------------------------------------------------------------------

_TOUR_AUDIO = re.compile(r"^/tour-audio/([^/]+)\.mp3$")
_PROXY_VIDEO = re.compile(r"^/api/proxy/([^/]+)$")


def classify_request(method: str, path: str) -> Optional[dict]:
    """Leitet aus Methode + Pfad einen Recorder-Event-Typ ab.

    - GET /tour-audio/<id>.mp3         -> kind=tour_audio, id=...
    - GET /api/proxy/<file_id>         -> kind=video_play, file_id=...
      (Range-Requests oder erneute GETs loggen wir einzeln; das
      Build-Tool fasst bei Bedarf benachbarte zusammen.)
    - POST /api/speak                  -> kind=tts (Text kommt vom
      Request-Body, das wird im Router gezielt geloggt, nicht hier.)
    """
    if method != "GET":
        return None
    m = _TOUR_AUDIO.match(path)
    if m:
        return {"kind": "tour_audio", "tour_audio_id": m.group(1)}
    m = _PROXY_VIDEO.match(path)
    if m:
        return {"kind": "video_play", "file_id": m.group(1)}
    return None


async def record_middleware(request: Request, call_next):
    """FastAPI-Middleware: wenn Session aktiv, jede GET-Audio/Video-
    Anforderung loggen. Der eigentliche Response-Ablauf wird nicht
    beeinflusst -- auch wenn das Logging fehlschlagen wuerde."""
    if _Session.active:
        try:
            info = classify_request(request.method, request.url.path)
            if info is not None:
                _Session.append(info)
        except Exception:
            pass  # Recorder darf niemals den Request-Flow kaputt machen
    return await call_next(request)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

class TtsEvent(BaseModel):
    text: str


@router.post("/start")
async def start() -> dict:
    _Session.start()
    return {"ok": True, "t0": _Session.t0, "path": str(LOG_PATH)}


@router.post("/stop")
async def stop() -> dict:
    was_active = _Session.active
    _Session.stop()
    return {"ok": True, "was_active": was_active, "count": len(_Session.events)}


@router.get("/events")
async def list_events() -> list[dict]:
    """Aktuelle Event-Liste zur Kontrolle."""
    return _Session.events


@router.get("/status")
async def status() -> dict:
    return {
        "active": _Session.active,
        "count": len(_Session.events),
        "path": str(LOG_PATH),
    }


@router.post("/tts")
async def record_tts(event: TtsEvent) -> dict:
    """Speak-Calls werden mit Text geloggt (nicht nur ueber den URL-
    Pfad, weil der TTS-Text im POST-Body steckt und die Middleware ihn
    sonst nicht kennt). Der /api/speak-Router ruft diesen Endpoint
    selbst, wenn eine Recorder-Session aktiv ist."""
    _Session.append({"kind": "tts", "text": event.text})
    return {"ok": True}


def session_is_active() -> bool:
    """Modulweiter Export, damit der Speak-Router in seiner eigenen
    Logik pruefen kann, ob er den TTS-Text loggen soll."""
    return _Session.active
