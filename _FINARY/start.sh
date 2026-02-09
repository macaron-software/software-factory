#!/bin/bash
# start.sh — Lance tout le stack Finary en une commande
# Usage: ./start.sh [--stop]
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

API_PORT=8000
WEB_PORT=3000
PID_DIR="$DIR/.pids"
mkdir -p "$PID_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[FINARY]${NC} $1"; }
warn() { echo -e "${YELLOW}[FINARY]${NC} $1"; }
err() { echo -e "${RED}[FINARY]${NC} $1"; }

stop_all() {
    log "Stopping all services..."
    for pidfile in "$PID_DIR"/*.pid; do
        [ -f "$pidfile" ] || continue
        pid=$(cat "$pidfile")
        name=$(basename "$pidfile" .pid)
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            log "  Stopped $name (PID $pid)"
        fi
        rm -f "$pidfile"
    done
    # Also kill by port
    lsof -ti:$API_PORT 2>/dev/null | xargs kill 2>/dev/null || true
    lsof -ti:$WEB_PORT 2>/dev/null | xargs kill 2>/dev/null || true
    log "All stopped."
}

if [ "$1" = "--stop" ]; then
    stop_all
    exit 0
fi

log "━━━ Finary Stack ━━━"

# 0. Ensure browser is running on :18800
if ! curl -s http://127.0.0.1:18800/json > /dev/null 2>&1; then
    warn "No browser on :18800 — launching Chrome..."
    bash "$DIR/scrapers/launch_browser.sh"
    sleep 3
fi

# 1. Kill existing processes on our ports
for port in $API_PORT $WEB_PORT; do
    pid=$(lsof -ti:$port 2>/dev/null | head -1)
    if [ -n "$pid" ]; then
        warn "Port $port busy (PID $pid), killing..."
        kill "$pid" 2>/dev/null || true
        sleep 1
    fi
done

# 2. Start API server
log "Starting API server on :$API_PORT..."
source "$DIR/scrapers/.venv/bin/activate"
PYTHONPATH="$DIR" python3 "$DIR/backend/api_server.py" > /tmp/finary-api.log 2>&1 &
API_PID=$!
echo $API_PID > "$PID_DIR/api.pid"

# 3. Start Frontend
log "Starting Frontend on :$WEB_PORT..."
cd "$DIR/frontend/web"
npx next start -p $WEB_PORT > /tmp/finary-web.log 2>&1 &
WEB_PID=$!
echo $WEB_PID > "$PID_DIR/web.pid"
cd "$DIR"

# 4. Start keep-alive (if browser is running)
if curl -s http://127.0.0.1:18800/json > /dev/null 2>&1; then
    log "Starting keep-alive (browser detected on :18800)..."
    python3 "$DIR/scrapers/session_keepalive.py" --daemon
else
    warn "No browser on :18800, skipping keep-alive"
fi

# 5. Wait for API to be ready
log "Waiting for API..."
for i in $(seq 1 30); do
    if curl -s http://localhost:$API_PORT/api/v1/status > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

# 6. Status check
if curl -s http://localhost:$API_PORT/api/v1/status > /dev/null 2>&1; then
    STATUS=$(curl -s http://localhost:$API_PORT/api/v1/status)
    log "✅ API ready"
    echo "$STATUS" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'   Net worth: {d.get(\"net_worth\",0):,.2f}€')
print(f'   Positions: {d.get(\"positions\",0)} ({d.get(\"live_prices\",0)} live)')
print(f'   Data date: {d.get(\"data_date\",\"?\")}')
print(f'   EUR/USD:   {d.get(\"eur_usd\",0):.4f}')
" 2>/dev/null
else
    err "API failed to start — check /tmp/finary-api.log"
fi

if curl -s http://localhost:$WEB_PORT > /dev/null 2>&1; then
    log "✅ Frontend ready at http://localhost:$WEB_PORT"
else
    warn "Frontend still starting — check /tmp/finary-web.log"
fi

log "━━━━━━━━━━━━━━━━━━━━"
log "Logs: /tmp/finary-api.log, /tmp/finary-web.log"
log "Stop: ./start.sh --stop"
