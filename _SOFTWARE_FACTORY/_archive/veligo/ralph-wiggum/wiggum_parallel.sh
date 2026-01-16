#!/usr/bin/env bash
# wiggum_parallel.sh - Lance plusieurs Wiggum en parallèle avec Minimax M2
#
# Usage: ./wiggum_parallel.sh [num_workers] [queue_type]
#   num_workers: Nombre de workers parallèles (default: 4)
#   queue_type: tdd ou deploy (default: tdd)
#
# Exemple:
#   MINIMAX_API_KEY=xxx ./wiggum_parallel.sh 8 tdd
#
# Rate limiting: 200 calls/hour (1000 calls/5h) partagé entre tous les workers

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source .env.local if exists (API keys)
if [[ -f "$SCRIPT_DIR/.env.local" ]]; then
  source "$SCRIPT_DIR/.env.local"
fi
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
LOGS_DIR="$SCRIPT_DIR/logs"
STATUS_DIR="$SCRIPT_DIR/status"
LOCK_DIR="$STATUS_DIR/locks"

# Configuration
NUM_WORKERS=${1:-4}
QUEUE_TYPE=${2:-tdd}
POLL_INTERVAL=5

# LLM Backend - auto = Minimax avec fallback local
export LLM_BACKEND=${LLM_BACKEND:-"auto"}

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================================================
# UTILS
# ============================================================================
mkdir -p "$TASKS_DIR" "$LOGS_DIR" "$STATUS_DIR" "$LOCK_DIR"

log_info() { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $*"; }
log_success() { echo -e "${GREEN}[$(date +%H:%M:%S)] ✓${NC} $*"; }
log_warn() { echo -e "${YELLOW}[$(date +%H:%M:%S)] ⚠${NC} $*"; }
log_error() { echo -e "${RED}[$(date +%H:%M:%S)] ✗${NC} $*" >&2; }

# ============================================================================
# TASK LOCKING - Avoid race conditions between workers
# ============================================================================
acquire_task_lock() {
  local task_id=$1
  local worker_id=$2
  local lock_file="$LOCK_DIR/${task_id}.lock"

  # Try to create lock file atomically
  if ( set -o noclobber; echo "$worker_id" > "$lock_file" ) 2>/dev/null; then
    return 0  # Lock acquired
  else
    return 1  # Already locked
  fi
}

release_task_lock() {
  local task_id=$1
  local lock_file="$LOCK_DIR/${task_id}.lock"
  rm -f "$lock_file"
}

is_task_locked() {
  local task_id=$1
  local lock_file="$LOCK_DIR/${task_id}.lock"
  [[ -f "$lock_file" ]]
}

# ============================================================================
# TASK MANAGEMENT
# ============================================================================
get_pending_tasks() {
  local queue_type=$1
  local pattern

  case "$queue_type" in
    tdd) pattern="T*.md" ;;
    deploy) pattern="D*.md" ;;
    *) pattern="*.md" ;;
  esac

  # Find pending tasks, sorted by WSJF score (highest first)
  for f in "$TASKS_DIR"/$pattern; do
    [[ -f "$f" ]] || continue
    local task_id
    task_id=$(basename "$f" .md)

    # Skip if already locked
    if is_task_locked "$task_id"; then
      continue
    fi

    # Check status file first (authoritative)
    local status_file="$STATUS_DIR/${task_id}.status"
    if [[ -f "$status_file" ]]; then
      local file_status
      file_status=$(cat "$status_file" 2>/dev/null)
      # Skip if COMPLETE or FAILED
      if [[ "$file_status" == "COMPLETE" || "$file_status" == "DONE" ]]; then
        continue
      fi
    fi

    # Check status in .md file
    if grep -q "STATUS: PENDING\|STATUS: IN_PROGRESS" "$f" 2>/dev/null; then
      local wsjf
      wsjf=$(grep "WSJF:" "$f" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '\r\n')
      wsjf=${wsjf:-0}
      echo "$wsjf $f"
    fi
  done | sort -rn | cut -d' ' -f2-
}

# ============================================================================
# WORKER PROCESS
# ============================================================================
run_worker() {
  local worker_id=$1
  local queue_type=$2

  log_info "[Worker-$worker_id] Starting..."

  while true; do
    # Get next available task
    local task_file
    task_file=$(get_pending_tasks "$queue_type" | head -1)

    if [[ -z "$task_file" ]]; then
      # No tasks available, wait
      sleep $POLL_INTERVAL
      continue
    fi

    local task_id
    task_id=$(basename "$task_file" .md)

    # Try to acquire lock
    if ! acquire_task_lock "$task_id" "$worker_id"; then
      # Another worker got it first
      sleep 1
      continue
    fi

    log_info "[Worker-$worker_id] Processing $task_id"

    # Mark as IN_PROGRESS
    sed -i '' "s/STATUS: PENDING/STATUS: IN_PROGRESS/" "$task_file" 2>/dev/null || true

    # Run the single daemon in --once mode
    local log_file="$LOGS_DIR/${task_id}_worker${worker_id}_$(date +%Y%m%d_%H%M%S).log"

    if "$SCRIPT_DIR/wiggum_daemon.sh" "$queue_type" --once > "$log_file" 2>&1; then
      # Mark as COMPLETED in task file
      sed -i '' "s/STATUS: IN_PROGRESS/STATUS: COMPLETED/" "$task_file" 2>/dev/null || true
      # Also write status file
      echo "COMPLETE" > "$STATUS_DIR/${task_id}.status"
      log_success "[Worker-$worker_id] $task_id COMPLETE"
    else
      # Mark as FAILED for retry
      sed -i '' "s/STATUS: IN_PROGRESS/STATUS: FAILED/" "$task_file" 2>/dev/null || true
      echo "FAILED" > "$STATUS_DIR/${task_id}.status"
      log_warn "[Worker-$worker_id] $task_id FAILED - needs retry"
    fi

    # Release lock
    release_task_lock "$task_id"

    # Small delay to avoid hammering
    sleep 1
  done
}

# ============================================================================
# MAIN - Spawn parallel workers
# ============================================================================
main() {
  log_info "╔════════════════════════════════════════════════════════════╗"
  log_info "║  WIGGUM PARALLEL - $NUM_WORKERS workers                    ║"
  log_info "╠════════════════════════════════════════════════════════════╣"
  log_info "║  Queue: $QUEUE_TYPE                                        ║"
  log_info "║  Backend: $LLM_BACKEND                                     ║"
  log_info "║  Rate Limit: 200 calls/hour (shared)                       ║"
  log_info "╚════════════════════════════════════════════════════════════╝"

  # Check rate limit status
  if [[ -f "$SCRIPT_DIR/rate_limiter.py" ]]; then
    python3 "$SCRIPT_DIR/rate_limiter.py" stats 2>/dev/null || true
  fi

  # Check Cloud API key (Minimax Coding Plan)
  if [[ -z "${CLOUD_API_KEY:-}" ]]; then
    log_warn "CLOUD_API_KEY not set - using local Qwen only"
    export LLM_BACKEND="local"
  else
    log_success "Cloud API key configured (MiniMax M2.1)"
  fi

  # Clean old locks
  rm -f "$LOCK_DIR"/*.lock 2>/dev/null || true

  # Spawn workers in background (bash 3 compatible)
  local pids=""
  for i in $(seq 1 $NUM_WORKERS); do
    run_worker "$i" "$QUEUE_TYPE" &
    local pid=$!
    pids="$pids $pid"
    log_info "Spawned Worker-$i (PID: $pid)"
    sleep 0.5  # Stagger startup
  done

  # Save PIDs
  echo "$pids" > "$STATUS_DIR/parallel_pids.txt"
  log_info "PIDs saved to $STATUS_DIR/parallel_pids.txt"

  # Wait for Ctrl+C
  log_info "Press Ctrl+C to stop all workers"

  trap 'log_warn "Stopping workers..."; kill $pids 2>/dev/null; rm -f "$LOCK_DIR"/*.lock 2>/dev/null; exit 0' INT TERM

  # Monitor loop
  while true; do
    sleep 30
    # Show status
    local running=0
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        running=$((running + 1))
      fi
    done
    log_info "Workers running: $running/$NUM_WORKERS"

    # Show rate limit
    if [[ -f "$SCRIPT_DIR/rate_limiter.py" ]]; then
      python3 "$SCRIPT_DIR/rate_limiter.py" 2>/dev/null || true
    fi
  done
}

# Handle --stop
if [[ "${1:-}" == "--stop" ]]; then
  if [[ -f "$STATUS_DIR/parallel_pids.txt" ]]; then
    pids=$(cat "$STATUS_DIR/parallel_pids.txt")
    log_info "Stopping workers: $pids"
    kill $pids 2>/dev/null || true
    rm -f "$STATUS_DIR/parallel_pids.txt"
    rm -f "$LOCK_DIR"/*.lock
    log_success "All workers stopped"
  else
    log_warn "No workers running"
  fi
  exit 0
fi

# Handle --status
if [[ "${1:-}" == "--status" ]]; then
  if [[ -f "$STATUS_DIR/parallel_pids.txt" ]]; then
    pids=$(cat "$STATUS_DIR/parallel_pids.txt")
    running=0
    for pid in $pids; do
      if kill -0 "$pid" 2>/dev/null; then
        ((running++))
      fi
    done
    log_info "Workers running: $running"
  else
    log_info "No parallel session active"
  fi

  # Show locks
  locks=$(ls -1 "$LOCK_DIR"/*.lock 2>/dev/null | wc -l | tr -d ' ' || echo 0)
  log_info "Active task locks: $locks"

  # Show rate limit
  if [[ -f "$SCRIPT_DIR/rate_limiter.py" ]]; then
    python3 "$SCRIPT_DIR/rate_limiter.py" stats 2>/dev/null || true
  fi
  exit 0
fi

main "$@"
