#!/usr/bin/env bash
# lrm_orchestrator.sh - LRM Meta-Orchestrator (arXiv:2512.24601)
#
# Orchestre les 2 daemons Wiggum:
# - Génère les tâches TDD et Deploy
# - Lance les daemons en background
# - Surveille la progression
# - Alimente en nouvelles tâches si nécessaire
#
# Usage: ./lrm_orchestrator.sh {start|stop|status|feed}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
STATUS_DIR="$SCRIPT_DIR/status"
LOGS_DIR="$SCRIPT_DIR/logs"

mkdir -p "$TASKS_DIR" "$STATUS_DIR" "$LOGS_DIR"

# ============================================================================
# UTILS
# ============================================================================
log_info() { echo -e "\033[0;34m[LRM $(date +%H:%M:%S)]\033[0m $*"; }
log_success() { echo -e "\033[0;32m[LRM $(date +%H:%M:%S)] ✓\033[0m $*"; }
log_warn() { echo -e "\033[0;33m[LRM $(date +%H:%M:%S)] ⚠\033[0m $*"; }
log_error() { echo -e "\033[0;31m[LRM $(date +%H:%M:%S)] ✗\033[0m $*" >&2; }

is_daemon_running() {
  local queue_type=$1
  local pid_file="$STATUS_DIR/${queue_type}_daemon.pid"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

get_daemon_pid() {
  local queue_type=$1
  local pid_file="$STATUS_DIR/${queue_type}_daemon.pid"

  if [[ -f "$pid_file" ]]; then
    cat "$pid_file"
  else
    echo "0"
  fi
}

# ============================================================================
# DAEMON MANAGEMENT
# ============================================================================
start_daemons() {
  log_info "Starting Wiggum daemons..."

  # Start TDD daemon
  if is_daemon_running "tdd"; then
    log_warn "TDD daemon already running (PID: $(get_daemon_pid tdd))"
  else
    log_info "Starting TDD daemon..."
    nohup "$SCRIPT_DIR/wiggum_daemon.sh" tdd \
      >> "$LOGS_DIR/wiggum_tdd_daemon.log" 2>&1 &
    sleep 2
    if is_daemon_running "tdd"; then
      log_success "TDD daemon started (PID: $(get_daemon_pid tdd))"
    else
      log_error "Failed to start TDD daemon"
    fi
  fi

  # Start Deploy daemon
  if is_daemon_running "deploy"; then
    log_warn "Deploy daemon already running (PID: $(get_daemon_pid deploy))"
  else
    log_info "Starting Deploy daemon..."
    nohup "$SCRIPT_DIR/wiggum_daemon.sh" deploy \
      >> "$LOGS_DIR/wiggum_deploy_daemon.log" 2>&1 &
    sleep 2
    if is_daemon_running "deploy"; then
      log_success "Deploy daemon started (PID: $(get_daemon_pid deploy))"
    else
      log_error "Failed to start Deploy daemon"
    fi
  fi
}

stop_daemons() {
  log_info "Stopping Wiggum daemons..."

  for queue_type in tdd deploy; do
    if is_daemon_running "$queue_type"; then
      local pid
      pid=$(get_daemon_pid "$queue_type")
      log_info "Stopping $queue_type daemon (PID: $pid)..."
      kill "$pid" 2>/dev/null || true
      sleep 1
      # Force kill if still running
      kill -9 "$pid" 2>/dev/null || true
      rm -f "$STATUS_DIR/${queue_type}_daemon.pid"
      log_success "$queue_type daemon stopped"
    else
      log_info "$queue_type daemon not running"
    fi
  done
}

show_status() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  LRM Orchestrator Status                                         ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo ""

  # Daemon status
  echo "┌─ Daemons ─────────────────────────────────────────────────────────┐"
  for queue_type in tdd deploy; do
    if is_daemon_running "$queue_type"; then
      local pid
      pid=$(get_daemon_pid "$queue_type")
      local upper_type
      upper_type=$(echo "$queue_type" | tr '[:lower:]' '[:upper:]')
      printf "│  %s Daemon: [OK] Running (PID: %s)\n" "$upper_type" "$pid"
    else
      local upper_type
      upper_type=$(echo "$queue_type" | tr '[:lower:]' '[:upper:]')
      printf "│  %s Daemon: [--] Stopped\n" "$upper_type"
    fi
  done
  echo "└───────────────────────────────────────────────────────────────────┘"
  echo ""

  # Task counts
  local tdd_pending=0 tdd_complete=0 tdd_failed=0
  local deploy_pending=0 deploy_complete=0 deploy_failed=0

  for f in "$TASKS_DIR"/T*.md; do
    [[ -f "$f" ]] || continue
    local status
    status=$(grep "^STATUS:" "$f" 2>/dev/null | head -1 | sed 's/STATUS: //')
    case "$status" in
      PENDING*) ((tdd_pending++)) ;;
      COMPLETE*) ((tdd_complete++)) ;;
      FAILED*) ((tdd_failed++)) ;;
    esac
  done

  for f in "$TASKS_DIR"/D*.md; do
    [[ -f "$f" ]] || continue
    local status
    status=$(grep "^STATUS:" "$f" 2>/dev/null | head -1 | sed 's/STATUS: //')
    case "$status" in
      PENDING*) ((deploy_pending++)) ;;
      COMPLETE*) ((deploy_complete++)) ;;
      FAILED*) ((deploy_failed++)) ;;
    esac
  done

  echo "┌─ Task Queues ─────────────────────────────────────────────────────┐"
  printf "│  TDD Queue:    %d pending | %d complete | %d failed\n" "$tdd_pending" "$tdd_complete" "$tdd_failed"
  printf "│  Deploy Queue: %d pending | %d complete | %d failed\n" "$deploy_pending" "$deploy_complete" "$deploy_failed"
  echo "└───────────────────────────────────────────────────────────────────┘"
  echo ""

  # Recent activity
  echo "┌─ Recent Logs ─────────────────────────────────────────────────────┐"
  if [[ -f "$LOGS_DIR/wiggum_tdd_daemon.log" ]]; then
    echo "│  TDD: $(tail -1 "$LOGS_DIR/wiggum_tdd_daemon.log" 2>/dev/null | head -c 60)..."
  fi
  if [[ -f "$LOGS_DIR/wiggum_deploy_daemon.log" ]]; then
    echo "│  Deploy: $(tail -1 "$LOGS_DIR/wiggum_deploy_daemon.log" 2>/dev/null | head -c 60)..."
  fi
  echo "└───────────────────────────────────────────────────────────────────┘"
  echo ""
}

# ============================================================================
# TASK FEEDING (from Meta-Orchestrator)
# ============================================================================
feed_tasks() {
  log_info "Running Meta-Orchestrator to generate tasks..."

  cd "$PROJECT_ROOT"

  # Run Python meta-orchestrator if exists
  if [[ -f "$SCRIPT_DIR/ralph_meta_orchestrator.py" ]]; then
    python3 "$SCRIPT_DIR/ralph_meta_orchestrator.py" \
      --project "$PROJECT_ROOT" \
      --output "$TASKS_DIR" 2>&1 | tee -a "$LOGS_DIR/lrm_feed.log"
  else
    log_warn "Meta-orchestrator not found, using existing tasks"
  fi

  # Count new tasks
  local tdd_count deploy_count
  tdd_count=$(find "$TASKS_DIR" -name "T*.md" 2>/dev/null | wc -l | tr -d ' ')
  deploy_count=$(find "$TASKS_DIR" -name "D*.md" 2>/dev/null | wc -l | tr -d ' ')

  log_success "Tasks available: $tdd_count TDD, $deploy_count Deploy"
}

# ============================================================================
# WATCH MODE (continuous monitoring)
# ============================================================================
watch_progress() {
  log_info "Watching progress (Ctrl+C to stop)..."

  while true; do
    clear
    show_status

    echo "Refreshing in 10s... (Ctrl+C to stop)"
    sleep 10
  done
}

# ============================================================================
# MAIN
# ============================================================================
main() {
  local command=${1:-""}

  case $command in
    start)
      feed_tasks
      start_daemons
      show_status
      ;;
    stop)
      stop_daemons
      ;;
    status)
      show_status
      ;;
    feed)
      feed_tasks
      ;;
    watch)
      watch_progress
      ;;
    restart)
      stop_daemons
      sleep 2
      start_daemons
      show_status
      ;;
    *)
      echo "╔══════════════════════════════════════════════════════════════════╗"
      echo "║  LRM Orchestrator - Ralph Wiggum Pipeline                        ║"
      echo "║  Pattern: arXiv:2512.24601 (MIT CSAIL)                          ║"
      echo "╚══════════════════════════════════════════════════════════════════╝"
      echo ""
      echo "Usage: $0 {start|stop|status|feed|watch|restart}"
      echo ""
      echo "Commands:"
      echo "  start   - Generate tasks and start both Wiggum daemons"
      echo "  stop    - Stop both Wiggum daemons"
      echo "  status  - Show current status"
      echo "  feed    - Run meta-orchestrator to generate new tasks"
      echo "  watch   - Continuous monitoring (auto-refresh)"
      echo "  restart - Stop then start daemons"
      echo ""
      echo "Architecture:"
      echo "  ┌─────────────────────────────────────────┐"
      echo "  │  LRM (this script)                      │"
      echo "  │  - Generates tasks                      │"
      echo "  │  - Monitors progress                    │"
      echo "  └─────────────────┬───────────────────────┘"
      echo "                    │"
      echo "          ┌─────────┴─────────┐"
      echo "          ▼                   ▼"
      echo "  ┌───────────────┐   ┌───────────────┐"
      echo "  │ Wiggum TDD    │   │ Wiggum Deploy │"
      echo "  │ (daemon)      │   │ (daemon)      │"
      echo "  └───────────────┘   └───────────────┘"
      echo ""
      exit 1
      ;;
  esac
}

main "$@"
