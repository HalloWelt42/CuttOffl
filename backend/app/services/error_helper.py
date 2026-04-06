"""
CuttOffl Backend - Fehler-Text-Hilfen.

Verhindert, dass absolute Pfade (insbesondere das Daten-Verzeichnis des
Hosts) in API-Fehlermeldungen nach aussen durchsickern. Fehler aus ffmpeg
oder ffprobe enthalten regelmaessig volle Pfade -- die gehoeren ins Log,
nicht in die HTTP-Antwort.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.config import DATA_DIR


_DATA_STR = str(DATA_DIR)
_HOME_STR = str(Path.home())


def sanitize_error(msg: str | None, fallback: str = "Interner Fehler") -> str:
    """Entfernt absolute Pfade, kuerzt Text auf sinnvolle Laenge."""
    if not msg:
        return fallback
    text = str(msg)
    text = text.replace(_DATA_STR, "<data>")
    text = text.replace(_HOME_STR, "~")
    # Generisches Home-Muster (z. B. /Users/name/... oder /home/name/...)
    text = re.sub(r"/Users/[^/\s]+", "~", text)
    text = re.sub(r"/home/[^/\s]+",  "~", text)
    # Zeilenumbrueche normalisieren, auf 500 Zeichen kuerzen
    text = " ".join(text.split())
    if len(text) > 500:
        text = text[:497] + "..."
    return text
