"""
CuttOffl Backend - Konfiguration

Paths, Ports und Umgebungsvariablen.
"""

import os
from pathlib import Path


APP_NAME = "CuttOffl"
VERSION = "0.23.1"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CUTTOFFL_DATA_DIR", str(BASE_DIR.parent / "data"))).resolve()


def _resolve_path(custom: str | None, default: Path) -> Path:
    """Nimmt den nutzerdefinierten Pfad, wenn er existiert und ein Verzeichnis
    ist, sonst den Default."""
    if custom:
        try:
            p = Path(custom).expanduser().resolve()
            if p.exists() and p.is_dir():
                return p
        except Exception:
            pass
    return default


# Nutzer-Overrides aus user_config.json (falls vorhanden) sind für die
# beiden großen Datenbereiche möglich, in denen echte Video-Dateien
# landen. DB, Proxy, Thumbs, Sprites und Waveforms bleiben bewusst beim
# Default im Daten-Verzeichnis -- das sind interne Caches.
try:
    from app.services.user_config import load as _load_user_config
    _uc = _load_user_config()
except Exception:
    _uc = {}

ORIGINALS_DIR = _resolve_path(_uc.get("originals_dir"), DATA_DIR / "originals")
EXPORTS_DIR   = _resolve_path(_uc.get("exports_dir"),   DATA_DIR / "exports")

PROXIES_DIR = DATA_DIR / "proxies"
THUMBS_DIR = DATA_DIR / "thumbs"
SPRITES_DIR = DATA_DIR / "sprites"
WAVEFORMS_DIR = DATA_DIR / "waveforms"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
TMP_DIR = DATA_DIR / "tmp"
DB_DIR = DATA_DIR / "db"
DB_PATH = DB_DIR / "cuttoffl.db"

PROXY_HEIGHT = int(os.getenv("CUTTOFFL_PROXY_HEIGHT", "480"))
PROXY_CRF = int(os.getenv("CUTTOFFL_PROXY_CRF", "28"))
PROXY_GOP_SECONDS = float(os.getenv("CUTTOFFL_PROXY_GOP_SECONDS", "1.0"))
THUMB_WIDTH = int(os.getenv("CUTTOFFL_THUMB_WIDTH", "320"))

HOST = os.getenv("CUTTOFFL_HOST", "127.0.0.1")
PORT = int(os.getenv("CUTTOFFL_PORT", "10036"))

LOG_LEVEL = os.getenv("CUTTOFFL_LOG_LEVEL", "INFO").upper()

# CORS: standardmaessig nur die erwarteten Dev-Origins. Erlaubte Werte
# können per CUTTOFFL_CORS_ORIGINS überschrieben werden (komma-separiert).
# "*" als Eintrag bleibt möglich für offene Umgebungen; in dem Fall
# wird allow_credentials in main.py bewusst auf False gezwungen, weil
# Browser "Origin: *" + Credentials sowieso ignorieren.
_DEFAULT_CORS = (
    "http://127.0.0.1:10037,http://localhost:10037,"
    "http://127.0.0.1:10036,http://localhost:10036"
)
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CUTTOFFL_CORS_ORIGINS", _DEFAULT_CORS).split(",")
    if o.strip()
]
CORS_ALLOW_ANY = "*" in CORS_ORIGINS
CORS_ALLOW_CREDENTIALS = not CORS_ALLOW_ANY

MAX_UPLOAD_MB = int(os.getenv("CUTTOFFL_MAX_UPLOAD_MB", "10240"))
ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".mts", ".ts", ".mpg", ".mpeg", ".flv", ".wmv",
}

# Vorlese-Proxy -- leitet /api/speak an das txt2voice-Schwesterprojekt
# weiter, damit Texte in der App per Klick vorgelesen werden können.
# Nur lokal, rein als Komfort-Feature. Wenn txt2voice nicht läuft,
# antwortet die Route mit 503 und das Frontend blendet die Buttons
# still aus.
TTS_BASE_URL = os.getenv("CUTTOFFL_TTS_URL", "http://127.0.0.1:10031")
TTS_VOICE_ID = os.getenv(
    "CUTTOFFL_TTS_VOICE_ID",
    "8d6cfa8841bb408d9da44520889deb54",  # "Zeit Stimme"
)
TTS_CACHE_DIR = DATA_DIR / "tts-cache"
# Max-Länge des vorzulesenden Textes (Zeichen), Schutz vor Missbrauch
# und langen Synthese-Laufzeiten.
TTS_MAX_CHARS = int(os.getenv("CUTTOFFL_TTS_MAX_CHARS", "2000"))


def ensure_directories() -> None:
    for d in (ORIGINALS_DIR, PROXIES_DIR, EXPORTS_DIR, THUMBS_DIR,
              SPRITES_DIR, WAVEFORMS_DIR, TRANSCRIPTS_DIR, TMP_DIR, DB_DIR,
              TTS_CACHE_DIR):
        d.mkdir(parents=True, exist_ok=True)
