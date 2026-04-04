#!/usr/bin/env bash
# CuttOffl - nativer Mac-Setup (Phase 1, Backend).
# Legt venv an, installiert Backend-Dependencies, prüft ffmpeg.

set -euo pipefail

cd "$(dirname "$0")"
ROOT="$(pwd)"
BACKEND="$ROOT/backend"

echo "[1/4] Prüfe ffmpeg/ffprobe..."
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  echo "FEHLER: ffmpeg/ffprobe nicht gefunden. Installation: brew install ffmpeg"
  exit 1
fi
ffmpeg -version | head -1

echo "[2/4] Lege Python-venv an..."
if [ ! -d "$BACKEND/.venv" ]; then
  python3 -m venv "$BACKEND/.venv"
fi

echo "[3/4] Installiere Dependencies..."
# shellcheck disable=SC1091
source "$BACKEND/.venv/bin/activate"
pip install --upgrade pip >/dev/null
pip install -r "$BACKEND/requirements.txt"

echo "[4/4] Fertig. Starten mit: ./run.sh"
