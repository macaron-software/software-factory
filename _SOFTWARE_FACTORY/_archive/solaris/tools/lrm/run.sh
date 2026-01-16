#!/bin/bash
# ============================================================
# SOLARIS LRM ORCHESTRATOR
# ============================================================
# Lance et surveille le système LRM complet:
# - Brain (Claude Opus 4.5)
# - Wiggum (MiniMax)
# - Adversarial (intégré)
#
# Usage:
#   ./tools/lrm/run.sh start    # Lance tout
#   ./tools/lrm/run.sh stop     # Arrête tout
#   ./tools/lrm/run.sh status   # Affiche le statut
#   ./tools/lrm/run.sh brain    # Lance le Brain seul
#   ./tools/lrm/run.sh wiggum   # Lance Wiggum seul
# ============================================================

set -e

PROJECT_ROOT="/Users/sylvain/_LAPOSTE/_SD3"
LRM_DIR="$PROJECT_ROOT/tools/lrm"
LOGS_DIR="$PROJECT_ROOT/logs/lrm"
PID_FILE="$LRM_DIR/.lrm.pid"

mkdir -p "$LOGS_DIR"

log() {
    echo "[$(date '+%H:%M:%S')] $1"
}

start_brain() {
    log "🧠 Starting LRM Brain..."
    cd "$PROJECT_ROOT"
    python3 "$LRM_DIR/lrm_brain_solaris.py" 2>&1 | tee "$LOGS_DIR/brain_$(date +%Y%m%d_%H%M%S).log"
}

start_wiggum() {
    local daemon=$1
    log "🔧 Starting Wiggum..."
    cd "$PROJECT_ROOT"
    
    if [ "$daemon" = "daemon" ]; then
        nohup python3 "$LRM_DIR/wiggum_solaris.py" --daemon > "$LOGS_DIR/wiggum_$(date +%Y%m%d_%H%M%S).log" 2>&1 &
        echo $! > "$PID_FILE"
        log "   Wiggum started as daemon (PID: $!)"
    else
        python3 "$LRM_DIR/wiggum_solaris.py" 2>&1 | tee "$LOGS_DIR/wiggum_$(date +%Y%m%d_%H%M%S).log"
    fi
}

start_all() {
    log "=" | tr '=' '='
    log "🚀 SOLARIS LRM - Full Pipeline"
    log "=" | tr '=' '='
    
    # Step 1: Run Brain
    start_brain
    
    # Step 2: Run Wiggum
    start_wiggum
    
    log "=" | tr '=' '='
    log "✅ Pipeline complete"
    log "=" | tr '=' '='
}

stop_all() {
    log "🛑 Stopping LRM..."
    
    if [ -f "$PID_FILE" ]; then
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid"
            log "   Killed Wiggum (PID: $pid)"
        fi
        rm -f "$PID_FILE"
    fi
    
    # Kill any remaining Python processes
    pkill -f "lrm_brain_solaris.py" 2>/dev/null || true
    pkill -f "wiggum_solaris.py" 2>/dev/null || true
    
    log "✅ All LRM processes stopped"
}

show_status() {
    log "=" | tr '=' '='
    log "📊 SOLARIS LRM STATUS"
    log "=" | tr '=' '='
    
    # Check Brain
    if pgrep -f "lrm_brain_solaris.py" > /dev/null; then
        log "🧠 Brain: RUNNING"
    else
        log "🧠 Brain: STOPPED"
    fi
    
    # Check Wiggum
    if pgrep -f "wiggum_solaris.py" > /dev/null; then
        log "🔧 Wiggum: RUNNING (PID: $(pgrep -f 'wiggum_solaris.py'))"
    else
        log "🔧 Wiggum: STOPPED"
    fi
    
    # Show backlog status
    if [ -f "$LRM_DIR/backlog_solaris.json" ]; then
        tasks=$(python3 -c "import json; d=json.load(open('$LRM_DIR/backlog_solaris.json')); print(len(d.get('tasks', [])))")
        log "📋 Backlog: $tasks tasks"
    else
        log "📋 Backlog: No backlog"
    fi
    
    # Show completed status
    if [ -f "$LRM_DIR/completed_solaris.json" ]; then
        completed=$(python3 -c "import json; d=json.load(open('$LRM_DIR/completed_solaris.json')); print(len(d.get('completed', [])))")
        failed=$(python3 -c "import json; d=json.load(open('$LRM_DIR/completed_solaris.json')); print(len(d.get('failed', [])))")
        log "✅ Completed: $completed | ❌ Failed: $failed"
    fi
    
    # Show latest logs
    log ""
    log "📄 Latest logs:"
    ls -lt "$LOGS_DIR"/*.log 2>/dev/null | head -5 | while read line; do
        log "   $line"
    done
    
    log "=" | tr '=' '='
}

# Main
case "${1:-start}" in
    start)
        start_all
        ;;
    stop)
        stop_all
        ;;
    status)
        show_status
        ;;
    brain)
        start_brain
        ;;
    wiggum)
        start_wiggum "${2:-}"
        ;;
    daemon)
        start_brain
        start_wiggum daemon
        ;;
    *)
        echo "Usage: $0 {start|stop|status|brain|wiggum|daemon}"
        exit 1
        ;;
esac
