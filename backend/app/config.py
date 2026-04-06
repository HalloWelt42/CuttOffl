"""
CuttOffl Backend - Konfiguration

Paths, Ports und Umgebungsvariablen.
"""

import os
from pathlib import Path


APP_NAME = "CuttOffl"
VERSION = "0.5.0"

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("CUTTOFFL_DATA_DIR", str(BASE_DIR.parent / "data"))).resolve()

ORIGINALS_DIR = DATA_DIR / "originals"
PROXIES_DIR = DATA_DIR / "proxies"
EXPORTS_DIR = DATA_DIR / "exports"
THUMBS_DIR = DATA_DIR / "thumbs"
SPRITES_DIR = DATA_DIR / "sprites"
WAVEFORMS_DIR = DATA_DIR / "waveforms"
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

CORS_ORIGINS = ["*"]

MAX_UPLOAD_MB = int(os.getenv("CUTTOFFL_MAX_UPLOAD_MB", "10240"))
ALLOWED_EXTENSIONS = {
    ".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v",
    ".mts", ".ts", ".mpg", ".mpeg", ".flv", ".wmv",
}


def ensure_directories() -> None:
    for d in (ORIGINALS_DIR, PROXIES_DIR, EXPORTS_DIR, THUMBS_DIR,
              SPRITES_DIR, WAVEFORMS_DIR, TMP_DIR, DB_DIR):
        d.mkdir(parents=True, exist_ok=True)
