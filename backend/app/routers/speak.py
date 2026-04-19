"""
CuttOffl Backend - Speak-Proxy.

Leichter Proxy zu txt2voice (http://127.0.0.1:10031), damit Frontend-
Buttons kurze Text-Abschnitte vorlesen können, ohne selbst auf das
TTS-Backend zugreifen zu müssen.

Flow:
  Frontend -> POST /api/speak {text}
           -> Backend sanitizet, hashed, schaut in data/tts-cache
              - Cache-Hit: MP3 direkt ausliefern
              - Cache-Miss: txt2voice /api/synthesize/clone aufrufen
                            mit TTS_VOICE_ID, Audio herunterladen,
                            in den Cache legen, ausliefern

Läuft txt2voice nicht: 503. Das Frontend blendet die Buttons dann
still aus -- die App bleibt voll funktionsfähig, nur eben ohne
Vorleser.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import (
    TTS_BASE_URL, TTS_CACHE_DIR, TTS_MAX_CHARS, TTS_VOICE_ID,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["speak"])


class SpeakRequest(BaseModel):
    text: str


# Zeichen, die der TTS-Engine eher schaden als helfen: Emojis,
# Pfeile, typografische Deko. Wir entfernen sie vor dem Senden.
_CLEAN_RE = re.compile(
    r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF"
    r"\u2190-\u21FF\u2700-\u27BF\u2B00-\u2BFF]+"
)
# Mehrfache Whitespace-Sequenzen -> ein Leerzeichen
_WS_RE = re.compile(r"\s+")


def sanitize_for_speech(text: str) -> str:
    """Bereinigt User-Text für die TTS-Synthese.

    - HTML-Tags, Emojis, Pfeile, typografische Deko raus
    - Zeilenumbrüche zu Satz-Trennzeichen
    - Mehrfache Leerzeichen komprimiert
    - Auf TTS_MAX_CHARS begrenzt (Rest wird freundlich abgeschnitten)
    """
    if not text:
        return ""
    # Einfaches Strippen von HTML-Tags (die App schickt keine HTML,
    # aber sicher ist sicher).
    s = re.sub(r"<[^>]+>", " ", text)
    s = _CLEAN_RE.sub(" ", s)
    # Zeilenumbrüche zu Punkten, damit die Sprachausgabe pausiert.
    s = s.replace("\r", " ").replace("\n", ". ")
    # Mehrfache Punkte / Leerzeichen aufräumen
    s = re.sub(r"\.{2,}", ".", s)
    s = _WS_RE.sub(" ", s).strip()
    if len(s) > TTS_MAX_CHARS:
        # An letztem Satzende kürzen, wenn möglich -- sonst hart cut.
        head = s[:TTS_MAX_CHARS]
        last = max(head.rfind(". "), head.rfind("! "), head.rfind("? "))
        s = head[:last + 1] if last > 100 else head
    return s


def cache_path_for(text: str) -> Path:
    """Deterministischer Cache-Pfad per SHA256 über (Voice-ID, Text).
    Die Voice-ID steckt im Hash, damit ein Voice-Wechsel zu einem
    frischen Cache-Eintrag führt."""
    h = hashlib.sha256()
    h.update(TTS_VOICE_ID.encode("utf-8"))
    h.update(b"|")
    h.update(text.encode("utf-8"))
    return TTS_CACHE_DIR / f"{h.hexdigest()[:32]}.mp3"


@router.post("/speak")
async def speak(body: SpeakRequest):
    """Lässt einen kurzen Text vorlesen. Antwort ist direkt das MP3
    (audio/mpeg), damit das Frontend mit einem <audio src>-Element
    arbeiten kann."""
    text = sanitize_for_speech(body.text)
    if not text:
        raise HTTPException(status_code=400, detail="Text ist leer")
    if len(text) < 2:
        raise HTTPException(status_code=400, detail="Text zu kurz")

    TTS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = cache_path_for(text)
    if path.exists() and path.stat().st_size > 0:
        return FileResponse(
            path,
            media_type="audio/mpeg",
            headers={"Cache-Control": "public, max-age=604800"},
        )

    # Cache-Miss -> txt2voice ansprechen
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            form = {
                "text": text,
                "voice_id": TTS_VOICE_ID,
                "language": "german",
                "speed": "1.0",
                "persist": "false",
            }
            r = await client.post(
                f"{TTS_BASE_URL}/api/synthesize/clone", data=form,
            )
            r.raise_for_status()
            result = r.json()
            audio_url = result.get("audio_url") or ""
            if not audio_url:
                raise HTTPException(
                    status_code=502,
                    detail="txt2voice ohne audio_url",
                )
            full = audio_url if audio_url.startswith("http") \
                   else f"{TTS_BASE_URL}{audio_url}"
            r2 = await client.get(full)
            r2.raise_for_status()
            audio = r2.content
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Vorlese-Dienst nicht erreichbar ({TTS_BASE_URL}). "
                   f"Starte txt2voice, damit der Button funktioniert.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Vorlesen fehlgeschlagen: {e}",
        )

    try:
        path.write_bytes(audio)
    except OSError as e:
        logger.warning(f"Cache schreiben fehlgeschlagen: {e}")
    return FileResponse(
        path if path.exists() else None,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=604800"},
    ) if path.exists() else HTTPException(status_code=500, detail="Audio verloren")
