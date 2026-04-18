#!/usr/bin/env bash
# Lädt einmalig ein Demo-Video in data/demo/, damit die Touren im
# Editor etwas zu zeigen haben. Quelle: Big Buck Bunny von der
# Blender Foundation (CC BY 3.0), die 1080p-Version vom offiziellen
# download.blender.org-Mirror.
#
# Aufruf:
#   ./tools/fetch_demo_video.sh            -- nur laden wenn nicht da
#   ./tools/fetch_demo_video.sh --force    -- neu laden auch wenn da
#
# Läuft idempotent: existiert die Zieldatei bereits und ist sie
# plausibel groß, passiert nichts. Bei Download-Abbruch bleibt nur
# eine Teil-Datei liegen -- die wird beim nächsten Lauf entsorgt
# und neu geholt.

set -e
cd "$(dirname "$0")/.."

SOURCE_URL="https://download.blender.org/peach/bigbuckbunny_movies/big_buck_bunny_1080p_h264.mov"
# Quicktime-MOV von Blender. MP4-Varianten existieren ebenfalls, die
# MOV-Version ist aber die stabilste, bestdokumentierte Quelle.
TARGET_DIR="data/demo"
TARGET_FILE="$TARGET_DIR/cuttoffl-demo.mov"
MIN_SIZE_MB=200   # plausibel minimal (die 1080p-Variante ist ~700 MB)

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[0;33m'; NC='\033[0m'
log() { echo -e "${2:-$NC}$1${NC}"; }

force=0
for arg in "$@"; do
  case "$arg" in
    --force|-f) force=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
  esac
done

mkdir -p "$TARGET_DIR"

if [ -f "$TARGET_FILE" ] && [ "$force" -ne 1 ]; then
  size_mb=$(( $(stat -f%z "$TARGET_FILE" 2>/dev/null || stat -c%s "$TARGET_FILE") / 1024 / 1024 ))
  if [ "$size_mb" -ge "$MIN_SIZE_MB" ]; then
    log "[demo] bereits vorhanden: $TARGET_FILE (${size_mb} MB)" "$GREEN"
    exit 0
  fi
  log "[demo] vorhandene Datei ist nur ${size_mb} MB -- lade neu" "$YELLOW"
  rm -f "$TARGET_FILE"
fi

log "[demo] lade Big Buck Bunny 1080p von $SOURCE_URL" "$YELLOW"
log "       das sind etwa 690 MB -- einmalig, danach liegt der Film lokal" "$YELLOW"

tmp="$TARGET_FILE.part"
# curl mit Fortschrittsanzeige, bei Unterbrechung Resume über -C -
if command -v curl >/dev/null 2>&1; then
  curl -L --fail -C - --progress-bar -o "$tmp" "$SOURCE_URL"
elif command -v wget >/dev/null 2>&1; then
  wget -c -O "$tmp" "$SOURCE_URL"
else
  log "[demo] weder curl noch wget gefunden -- Download nicht möglich" "$RED"
  exit 1
fi

# Größe plausibilisieren -- macOS nutzt stat -f, Linux stat -c
size_mb=$(( $(stat -f%z "$tmp" 2>/dev/null || stat -c%s "$tmp") / 1024 / 1024 ))
if [ "$size_mb" -lt "$MIN_SIZE_MB" ]; then
  log "[demo] Download unplausibel klein (${size_mb} MB) -- Abbruch" "$RED"
  rm -f "$tmp"
  exit 1
fi

mv "$tmp" "$TARGET_FILE"
log "[demo] fertig: $TARGET_FILE (${size_mb} MB)" "$GREEN"
log "       Lizenz: Big Buck Bunny (c) Blender Foundation, CC BY 3.0" "$NC"
log "       https://peach.blender.org" "$NC"
