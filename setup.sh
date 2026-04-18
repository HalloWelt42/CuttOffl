#!/usr/bin/env bash
# CuttOffl -- Setup fuer Backend (Python-venv) und Frontend (npm).
# Erkennt das Host-System und schlaegt die passende Installation vor.
#
# Unterstuetzte Plattformen:
#   - macOS (Apple Silicon / Intel) mit Homebrew
#   - Linux (Debian/Ubuntu/Raspberry Pi OS) mit apt
#
# Andere Systeme: Skript zeigt, was gebraucht wird, installiert aber nicht.

set -euo pipefail

# Optionale Flags:
#   --with-transcription   installiert zusaetzlich die Whisper-Pakete
#                          fuer KI-Untertitel (requirements-transcription.txt)
WITH_TRANSCRIPTION=false
for arg in "$@"; do
  case "$arg" in
    --with-transcription) WITH_TRANSCRIPTION=true ;;
    -h|--help)
      echo "CuttOffl setup"
      echo "Optionen:"
      echo "  --with-transcription  Installiere zusaetzlich Whisper fuer KI-Untertitel"
      exit 0
      ;;
  esac
done

cd "$(dirname "$0")"
ROOT="$(pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

OS="$(uname -s)"
ARCH="$(uname -m)"
PLATFORM="unknown"
case "$OS" in
  Darwin) PLATFORM="mac" ;;
  Linux)
    if [ -f /etc/debian_version ]; then PLATFORM="debian"; fi
    if [ -f /etc/raspberrypi-release ] || grep -qi raspberry /proc/cpuinfo 2>/dev/null; then
      PLATFORM="raspberrypi"
    fi
    ;;
esac

echo "========================================"
echo " CuttOffl Setup"
echo " Host:     $OS $ARCH"
echo " Plattform: $PLATFORM"
echo "========================================"

# ------------------------------------------------------------------
# 1. System-Abhaengigkeiten (ffmpeg, python3-venv, node)
# ------------------------------------------------------------------

need_install=false
check_cmd() {
  if command -v "$1" >/dev/null 2>&1; then
    echo "  [ok]   $1 ($(command -v "$1"))"
  else
    echo "  [MISS] $1"
    need_install=true
  fi
}

echo
echo "[1/4] System-Abhaengigkeiten pruefen"
check_cmd ffmpeg
check_cmd ffprobe
check_cmd python3
check_cmd node
check_cmd npm

if $need_install; then
  echo
  case "$PLATFORM" in
    mac)
      echo "Fehlende Pakete bitte per Homebrew installieren:"
      echo "  brew install ffmpeg python@3.13 node"
      ;;
    debian|raspberrypi)
      echo "Fehlende Pakete bitte per apt installieren:"
      echo "  sudo apt update"
      echo "  sudo apt install -y ffmpeg python3 python3-venv python3-pip nodejs npm"
      if [ "$PLATFORM" = "raspberrypi" ]; then
        echo
        echo "Fuer V4L2-Hardware-Encoder sollte der User in der 'video'-Gruppe sein:"
        echo "  sudo usermod -aG video \$USER  # danach neu einloggen"
      fi
      ;;
    *)
      echo "Bitte per Paketmanager deines Systems nachinstallieren:"
      echo "  ffmpeg, python3 (>=3.11), python3-venv, nodejs (>=20), npm"
      ;;
  esac
  exit 1
fi

# ------------------------------------------------------------------
# 2. Backend: venv + requirements
# ------------------------------------------------------------------

echo
echo "[2/4] Python-venv im Backend"
if [ ! -d "$BACKEND/.venv" ]; then
  python3 -m venv "$BACKEND/.venv"
  echo "  venv angelegt: $BACKEND/.venv"
else
  echo "  venv vorhanden"
fi

# shellcheck disable=SC1091
source "$BACKEND/.venv/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$BACKEND/requirements.txt"

if $WITH_TRANSCRIPTION; then
  echo
  echo "  zusaetzlich: Transkriptions-Pakete (Whisper)"
  python -m pip install -r "$BACKEND/requirements-transcription.txt"
fi

# ------------------------------------------------------------------
# 3. Frontend: npm install
# ------------------------------------------------------------------

echo
echo "[3/4] Frontend-Dependencies (npm install)"
if [ -d "$FRONTEND/node_modules" ]; then
  echo "  node_modules vorhanden -- pruefe auf Updates"
fi
( cd "$FRONTEND" && npm install --no-audit --no-fund )

# ------------------------------------------------------------------
# 3.5 Demo-Video fuer Touren und erste Schritte
# ------------------------------------------------------------------

echo
echo "[3.5/4] Demo-Video (Big Buck Bunny, CC BY 3.0)"
echo "  Laedt einmalig ein hochaufloesendes Beispielvideo nach data/demo/,"
echo "  damit die Touren im Editor echtes Material zum Zeigen haben."
if [ -f "$ROOT/tools/fetch_demo_video.sh" ]; then
  bash "$ROOT/tools/fetch_demo_video.sh" || \
    echo "  [warn] Demo-Download uebersprungen -- Tour im Editor bleibt leer"
fi

# ------------------------------------------------------------------
# 4. Hinweise fuer den Start
# ------------------------------------------------------------------

echo
echo "[4/4] Fertig. Ueberpruefte HW-Encoder laut ffmpeg:"
ffmpeg -hide_banner -encoders 2>/dev/null | \
  grep -E "h264_videotoolbox|hevc_videotoolbox|h264_v4l2m2m|libx264|libx265" | \
  awk '{print "  "$0}'

echo
echo "Starten mit:"
echo "  ./start.sh           # beide Prozesse"
echo "  ./start.sh status"
echo "  ./start.sh stop"

if ! $WITH_TRANSCRIPTION; then
  echo
  echo "Optional (KI-Untertitel/SRT per Whisper):"
  echo "  ./setup.sh --with-transcription"
  echo "  oder in der Backend-venv:"
  echo "    cd backend && source .venv/bin/activate"
  echo "    pip install -r requirements-transcription.txt"
fi
