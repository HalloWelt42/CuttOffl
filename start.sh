#!/usr/bin/env bash
# CuttOffl -- startet Backend und Frontend in diesem Ordner.
#
# Nutzung:
#   ./start.sh            -- beide Prozesse starten und Logs tailen
#   ./start.sh backend    -- nur Backend
#   ./start.sh frontend   -- nur Frontend
#   ./start.sh stop [backend|frontend]    -- Prozess(e) beenden (ohne Ziel: beide)
#   ./start.sh status                     -- laufende Prozesse anzeigen
#   ./start.sh logs                       -- Logs live verfolgen
#   ./start.sh restart [backend|frontend] -- stop + start (ohne Ziel: beide)

set -e
cd "$(dirname "$0")"
ROOT="$(pwd)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"

BACKEND_PORT=10036
FRONTEND_PORT=10037
HOST="${CUTTOFFL_HOST:-127.0.0.1}"

C_OK=$'\e[0;32m'; C_WARN=$'\e[0;33m'; C_ERR=$'\e[0;31m'; C_BOLD=$'\e[1m'; C_RST=$'\e[0m'
ok()   { printf '%s%s%s\n' "$C_OK"   "$1" "$C_RST"; }
warn() { printf '%s%s%s\n' "$C_WARN" "$1" "$C_RST"; }
err()  { printf '%s%s%s\n' "$C_ERR"  "$1" "$C_RST"; }

start_backend() {
  cd "$ROOT/backend"
  if [ ! -d .venv ]; then
    err "[backend] .venv fehlt -- einmalig ausführen:"
    echo "  cd $ROOT && ./setup.sh"
    exit 1
  fi
  if lsof -iTCP:$BACKEND_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    warn "[backend] läuft bereits auf Port $BACKEND_PORT -- übersprungen"
    cd "$ROOT"; return
  fi
  echo "[backend] starte auf $HOST:$BACKEND_PORT"
  if [ -f .env.dev ]; then set -a; . ./.env.dev; set +a; fi
  nohup .venv/bin/python -m uvicorn app.main:app \
      --host "$HOST" --port "$BACKEND_PORT" \
      > "$LOG_DIR/backend.log" 2>&1 &
  echo $! > "$LOG_DIR/backend.pid"
  cd "$ROOT"
}

start_frontend() {
  cd "$ROOT/frontend"
  if [ ! -d node_modules ]; then
    err "[frontend] node_modules fehlt -- einmalig ausführen:"
    echo "  cd $ROOT/frontend && npm install"
    exit 1
  fi
  if lsof -iTCP:$FRONTEND_PORT -sTCP:LISTEN >/dev/null 2>&1; then
    warn "[frontend] läuft bereits auf Port $FRONTEND_PORT -- übersprungen"
    cd "$ROOT"; return
  fi
  echo "[frontend] starte auf $HOST:$FRONTEND_PORT"
  nohup npm run dev -- --host "$HOST" --port "$FRONTEND_PORT" \
      > "$LOG_DIR/frontend.log" 2>&1 &
  echo $! > "$LOG_DIR/frontend.pid"
  cd "$ROOT"
}

stop_all() {
  local target="${1:-all}"
  local names ports
  case "$target" in
    backend)  names=(backend);           ports=($BACKEND_PORT) ;;
    frontend) names=(frontend);          ports=($FRONTEND_PORT) ;;
    all)      names=(backend frontend);  ports=($BACKEND_PORT $FRONTEND_PORT) ;;
    *) err "Unbekanntes Ziel: $target (erlaubt: backend | frontend | leer)"; exit 1 ;;
  esac
  for name in "${names[@]}"; do
    if [ -f "$LOG_DIR/$name.pid" ]; then
      pid=$(cat "$LOG_DIR/$name.pid")
      if kill -0 "$pid" 2>/dev/null; then
        echo "[$name] stoppe pid $pid"
        kill "$pid" 2>/dev/null || true
        # Kinder (Vite/uvicorn-Reload-Worker) mit killen
        pkill -P "$pid" 2>/dev/null || true
      fi
      rm -f "$LOG_DIR/$name.pid"
    fi
  done
  # Fallback: noch auf den Ports haengende Prozesse beenden
  for port in "${ports[@]}"; do
    pid=$(lsof -ti:$port 2>/dev/null || true)
    [ -n "$pid" ] && { echo "[port $port] kille pid $pid"; kill "$pid" 2>/dev/null || true; }
  done
}

show_status() {
  for name_port in "backend:$BACKEND_PORT" "frontend:$FRONTEND_PORT"; do
    name=${name_port%%:*}; port=${name_port##*:}
    if lsof -iTCP:$port -sTCP:LISTEN >/dev/null 2>&1; then
      ok "[$name] läuft auf Port $port"
    else
      warn "[$name] nicht aktiv auf Port $port"
    fi
  done
}

print_urls() {
  echo
  ok "Fertig. URLs:"
  echo "  Frontend:  http://$HOST:$FRONTEND_PORT"
  echo "  Backend:   http://$HOST:$BACKEND_PORT/docs"
  echo "  Health:    http://$HOST:$BACKEND_PORT/api/ping"
  echo "  WebSocket: ws://$HOST:$BACKEND_PORT/ws/jobs"
  echo
  echo "Logs:      $LOG_DIR/"
  echo "Tailen:    ./start.sh logs"
  echo "Stoppen:   ./start.sh stop"
}

tail_logs() {
  tail -n 30 -F "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log" 2>/dev/null
}

case "${1:-all}" in
  backend)  start_backend ;;
  frontend) start_frontend ;;
  stop)     stop_all "${2:-all}" ;;
  status)   show_status ;;
  logs)     tail_logs ;;
  restart)
    target="${2:-all}"
    stop_all "$target"
    sleep 1
    case "$target" in
      backend)  start_backend ;;
      frontend) start_frontend ;;
      all)      start_backend; sleep 1; start_frontend ;;
    esac
    print_urls
    ;;
  all|"")
    start_backend
    sleep 1
    start_frontend
    print_urls
    ;;
  *)
    echo "Unbekannter Befehl: $1"
    echo "Verfügbar: backend | frontend | stop [ziel] | status | logs | restart [ziel] | all"
    exit 1
    ;;
esac
