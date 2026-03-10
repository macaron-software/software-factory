#!/bin/bash
# Factory Monitor - Run every hour to check progress and detect blockers

LOG_DIR="/Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY/data/logs"
DB="/Users/sylvain/_MACARON-SOFTWARE/_SOFTWARE_FACTORY/data/factory.db"
MONITOR_LOG="$LOG_DIR/monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$MONITOR_LOG"
}

log "═══════════════════════════════════════════════════════════════"
log "FACTORY MONITOR - Hourly Check"
log "═══════════════════════════════════════════════════════════════"

# 1. Task Stats
log ""
log "📊 TASK STATS BY PROJECT:"
sqlite3 -header -column "$DB" "
SELECT
    project_id as Project,
    SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as Pending,
    SUM(CASE WHEN status='tdd_in_progress' THEN 1 ELSE 0 END) as TDD,
    SUM(CASE WHEN status IN ('code_written','commit_queued') THEN 1 ELSE 0 END) as Deploy_Q,
    SUM(CASE WHEN status='deployed' THEN 1 ELSE 0 END) as Deployed,
    SUM(CASE WHEN status LIKE '%failed' THEN 1 ELSE 0 END) as Failed
FROM tasks
GROUP BY project_id
ORDER BY Deployed DESC
" 2>/dev/null | tee -a "$MONITOR_LOG"

# 2. Deploy Queue Status
log ""
log "🚀 DEPLOY QUEUE:"
DEPLOY_PID=$(cat /tmp/factory/wiggum-deploy-global.pid 2>/dev/null)
if [ -n "$DEPLOY_PID" ] && ps -p "$DEPLOY_PID" > /dev/null 2>&1; then
    log "  Deploy daemon: RUNNING (PID $DEPLOY_PID)"
    LAST_DEPLOY=$(tail -100 "$LOG_DIR/wiggum-deploy-global.log" 2>/dev/null | grep "BATCH DEPLOYED" | tail -1)
    if [ -n "$LAST_DEPLOY" ]; then
        log "  Last deploy: $LAST_DEPLOY"
    fi
else
    log "  ⚠️  Deploy daemon: NOT RUNNING - needs restart!"
fi

# 3. Cycle Workers Status
log ""
log "🔄 CYCLE WORKERS:"
for project in ppz psy fervenza veligo yolonow; do
    PID_FILE="/tmp/factory/cycle-$project.pid"
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            # Check for stale streams (no progress in 10+ minutes)
            LAST_LINE=$(tail -1 "$LOG_DIR/cycle-$project.log" 2>/dev/null)
            if echo "$LAST_LINE" | grep -q "stale [4-9][0-9][0-9]s\|stale [0-9][0-9][0-9][0-9]"; then
                log "  $project: ⚠️  STALE (blocked >400s)"
            else
                log "  $project: RUNNING (PID $PID)"
            fi
        else
            log "  $project: ⚠️  DEAD (PID $PID not found)"
        fi
    else
        log "  $project: NOT STARTED"
    fi
done

# 4. MCP Server Status
log ""
log "🔌 MCP SERVER:"
MCP_PID=$(cat /tmp/factory/mcp-lrm.pid 2>/dev/null)
if [ -n "$MCP_PID" ] && ps -p "$MCP_PID" > /dev/null 2>&1; then
    log "  MCP LRM: RUNNING (PID $MCP_PID)"
else
    log "  ⚠️  MCP LRM: NOT RUNNING"
fi

# 5. Recent Errors
log ""
log "❌ RECENT ERRORS (last hour):"
ERROR_COUNT=$(grep -h "ERROR\|FAILED\|REJECTED" $LOG_DIR/*.log 2>/dev/null | grep "$(date '+%Y-%m-%d %H:')" | wc -l | tr -d ' ')
log "  $ERROR_COUNT errors in the last hour"

# 6. Hourly Progress (compare with previous run)
PROGRESS_FILE="/tmp/factory/last_deployed.txt"
CURRENT_DEPLOYED=$(sqlite3 "$DB" "SELECT SUM(CASE WHEN status='deployed' THEN 1 ELSE 0 END) FROM tasks" 2>/dev/null)
if [ -f "$PROGRESS_FILE" ]; then
    LAST_DEPLOYED=$(cat "$PROGRESS_FILE")
    DIFF=$((CURRENT_DEPLOYED - LAST_DEPLOYED))
    log ""
    log "📈 HOURLY PROGRESS: +$DIFF deployed (total: $CURRENT_DEPLOYED)"
else
    log ""
    log "📈 TOTAL DEPLOYED: $CURRENT_DEPLOYED"
fi
echo "$CURRENT_DEPLOYED" > "$PROGRESS_FILE"

log ""
log "═══════════════════════════════════════════════════════════════"
