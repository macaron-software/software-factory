#!/usr/bin/env bash
# lrm_brain.sh - LRM Brain (Meta-Orchestrator actif)
#
# ╔═══════════════════════════════════════════════════════════════════════════╗
# ║  ARCHITECTURE RLM (arXiv:2512.24601 - MIT CSAIL)                          ║
# ╠═══════════════════════════════════════════════════════════════════════════╣
# ║                                                                           ║
# ║  Ce script orchestre le LRM Brain qui:                                    ║
# ║  1. Analyse le projet via Recursive Language Model (Python)               ║
# ║  2. Génère des tâches T* pour le backlog TDD                             ║
# ║  3. Surveille les Wiggum daemons (indépendants)                          ║
# ║                                                                           ║
# ║  IMPORTANT: Les Wiggum dépilent leurs backlogs INDÉPENDAMMENT            ║
# ║  Le LRM alimente les backlogs, il ne les traite pas!                     ║
# ║                                                                           ║
# ║  Récursion RLM (dans lrm_brain.py):                                      ║
# ║  - Root LM (depth=0) reçoit la query                                     ║
# ║  - Spawne Sub-LMs (depth=1+) pour sous-tâches                            ║
# ║  - Contexte accessible via REPL, pas dans le prompt                      ║
# ║  - Termine avec FINAL(answer)                                            ║
# ║                                                                           ║
# ╚═══════════════════════════════════════════════════════════════════════════╝
#
# Usage: ./lrm_brain.sh [--generate|--monitor|--once]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
STATUS_DIR="$SCRIPT_DIR/status"
LOGS_DIR="$SCRIPT_DIR/logs"

# LRM Configuration
LRM_POLL_INTERVAL=30      # Secondes entre analyses
LRM_MODEL="opencode/minimax-m2.1-free"  # Pour analyses rapides
DECISION_THRESHOLD=3      # Tâches failed avant escalade

mkdir -p "$TASKS_DIR" "$STATUS_DIR" "$LOGS_DIR"

LOG_FILE="$LOGS_DIR/lrm_brain_$(date +%Y%m%d_%H%M%S).log"

# ============================================================================
# UTILS
# ============================================================================
log() {
  local msg="[LRM $(date +%H:%M:%S)] $*"
  echo -e "\033[0;36m$msg\033[0m" | tee -a "$LOG_FILE"
}
log_decision() {
  local msg="[LRM DECISION $(date +%H:%M:%S)] $*"
  echo -e "\033[1;35m$msg\033[0m" | tee -a "$LOG_FILE"
}
log_action() {
  local msg="[LRM ACTION $(date +%H:%M:%S)] $*"
  echo -e "\033[1;32m$msg\033[0m" | tee -a "$LOG_FILE"
}

# ============================================================================
# SITUATION ANALYSIS
# ============================================================================
analyze_situation() {
  local tdd_pending=0 tdd_complete=0 tdd_failed=0 tdd_progress=0
  local deploy_pending=0 deploy_complete=0 deploy_failed=0 deploy_progress=0

  # Count TDD tasks
  for f in "$TASKS_DIR"/T*.md; do
    [[ -f "$f" ]] || continue
    local status
    status=$(grep "^STATUS:" "$f" 2>/dev/null | head -1 | sed 's/STATUS: //' || echo "UNKNOWN")
    case "$status" in
      PENDING*) ((tdd_pending++)) ;;
      COMPLETE*) ((tdd_complete++)) ;;
      FAILED*) ((tdd_failed++)) ;;
      IN_PROGRESS*) ((tdd_progress++)) ;;
      ANALYZED*) ((tdd_complete++)) ;;  # Analyzed = done for now
    esac
  done

  # Count Deploy tasks
  for f in "$TASKS_DIR"/D*.md; do
    [[ -f "$f" ]] || continue
    local status
    status=$(grep "^STATUS:" "$f" 2>/dev/null | head -1 | sed 's/STATUS: //' || echo "UNKNOWN")
    case "$status" in
      PENDING*) ((deploy_pending++)) ;;
      COMPLETE*) ((deploy_complete++)) ;;
      FAILED*) ((deploy_failed++)) ;;
      IN_PROGRESS*) ((deploy_progress++)) ;;
    esac
  done

  # Check daemon status
  local tdd_daemon_running=false
  local deploy_daemon_running=false

  if [[ -f "$STATUS_DIR/tdd_daemon.pid" ]]; then
    local pid
    pid=$(cat "$STATUS_DIR/tdd_daemon.pid")
    kill -0 "$pid" 2>/dev/null && tdd_daemon_running=true
  fi

  if [[ -f "$STATUS_DIR/deploy_daemon.pid" ]]; then
    local pid
    pid=$(cat "$STATUS_DIR/deploy_daemon.pid")
    kill -0 "$pid" 2>/dev/null && deploy_daemon_running=true
  fi

  # Export for decision making
  export TDD_PENDING=$tdd_pending
  export TDD_COMPLETE=$tdd_complete
  export TDD_FAILED=$tdd_failed
  export TDD_PROGRESS=$tdd_progress
  export DEPLOY_PENDING=$deploy_pending
  export DEPLOY_COMPLETE=$deploy_complete
  export DEPLOY_FAILED=$deploy_failed
  export DEPLOY_PROGRESS=$deploy_progress
  export TDD_DAEMON=$tdd_daemon_running
  export DEPLOY_DAEMON=$deploy_daemon_running

  # Calculate totals
  export TDD_TOTAL=$((tdd_pending + tdd_complete + tdd_failed + tdd_progress))
  export DEPLOY_TOTAL=$((deploy_pending + deploy_complete + deploy_failed + deploy_progress))
}

print_situation() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  LRM Brain - Situation Analysis                                  ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo ""
  echo "┌─ TDD Queue ───────────────────────────────────────────────────────┐"
  printf "│  Daemon: %s | Progress: %d | Pending: %d | Complete: %d | Failed: %d\n" \
    "$([[ $TDD_DAEMON == true ]] && echo 'ON' || echo 'OFF')" \
    "$TDD_PROGRESS" "$TDD_PENDING" "$TDD_COMPLETE" "$TDD_FAILED"
  echo "└───────────────────────────────────────────────────────────────────┘"
  echo ""
  echo "┌─ Deploy Queue ────────────────────────────────────────────────────┐"
  printf "│  Daemon: %s | Progress: %d | Pending: %d | Complete: %d | Failed: %d\n" \
    "$([[ $DEPLOY_DAEMON == true ]] && echo 'ON' || echo 'OFF')" \
    "$DEPLOY_PROGRESS" "$DEPLOY_PENDING" "$DEPLOY_COMPLETE" "$DEPLOY_FAILED"
  echo "└───────────────────────────────────────────────────────────────────┘"
  echo ""
}

# ============================================================================
# DECISION MAKING
# ============================================================================
make_decision() {
  analyze_situation
  print_situation

  # Decision tree

  # 1. Si pas de tâches du tout -> générer
  if [[ $TDD_TOTAL -eq 0 ]] && [[ $DEPLOY_TOTAL -eq 0 ]]; then
    log_decision "No tasks found -> GENERATE NEW TASKS"
    return 1  # Need to generate tasks
  fi

  # 2. Si trop de failures -> escalade
  if [[ $TDD_FAILED -ge $DECISION_THRESHOLD ]]; then
    log_decision "Too many TDD failures ($TDD_FAILED) -> ANALYZE FAILURES"
    return 2  # Need to analyze failures
  fi

  # 3. Si TDD daemon off et tâches pending -> start daemon
  if [[ $TDD_DAEMON == false ]] && [[ $TDD_PENDING -gt 0 ]]; then
    log_decision "TDD daemon off with pending tasks -> START TDD DAEMON"
    return 3  # Start TDD daemon
  fi

  # 4. Si Deploy daemon off et tâches pending -> start daemon
  if [[ $DEPLOY_DAEMON == false ]] && [[ $DEPLOY_PENDING -gt 0 ]]; then
    log_decision "Deploy daemon off with pending tasks -> START DEPLOY DAEMON"
    return 4  # Start Deploy daemon
  fi

  # 5. Si TDD all complete et Deploy pending -> focus deploy
  if [[ $TDD_PENDING -eq 0 ]] && [[ $TDD_PROGRESS -eq 0 ]] && [[ $DEPLOY_PENDING -gt 0 ]]; then
    log_decision "TDD complete, Deploy pending -> FOCUS ON DEPLOY"
    return 5  # Focus on deploy
  fi

  # 6. Si tout complete -> SUCCESS
  if [[ $TDD_PENDING -eq 0 ]] && [[ $TDD_PROGRESS -eq 0 ]] && \
     [[ $DEPLOY_PENDING -eq 0 ]] && [[ $DEPLOY_PROGRESS -eq 0 ]]; then
    log_decision "ALL TASKS COMPLETE -> SUCCESS"
    return 0  # All done
  fi

  # 7. Default: work in progress, continue monitoring
  log_decision "Work in progress -> CONTINUE MONITORING"
  return 6  # Continue monitoring
}

# ============================================================================
# ACTIONS
# ============================================================================
# Note: L'analyse LEAN est maintenant dans lrm_brain.py (REPLEnvironment)
# Le RLM Python gère la récursion et l'accès au contexte via REPL
# ============================================================================
action_generate_tasks() {
  # ═══════════════════════════════════════════════════════════════════════════
  # GÉNÉRATION DE TÂCHES VIA RLM (Recursive Language Model)
  # AUCUN FALLBACK - Si ça échoue, ça échoue explicitement
  # ═══════════════════════════════════════════════════════════════════════════

  log_action "Generating tasks via RLM (Recursive Language Model)..."

  cd "$SCRIPT_DIR"

  # Le fichier DOIT exister - pas de fallback
  [[ ! -f "$SCRIPT_DIR/lrm_brain.py" ]] && {
    log "FATAL: lrm_brain.py not found"
    exit 1
  }

  log "Invoking RLM with recursive sub-agents..."
  python3 "$SCRIPT_DIR/lrm_brain.py" --generate-backlog 2>&1 | tee -a "$LOG_FILE"

  local exit_code=$?
  [[ $exit_code -ne 0 ]] && {
    log "FATAL: RLM failed with exit code $exit_code"
    exit 1
  }

  local task_count
  task_count=$(ls -1 "$TASKS_DIR"/T*.md 2>/dev/null | wc -l | tr -d ' ')
  log "Total tasks in backlog: $task_count"
}

action_analyze_failures() {
  log_action "Analyzing failed tasks..."

  local failed_tasks=""
  for f in "$TASKS_DIR"/T*.md; do
    [[ -f "$f" ]] || continue
    if grep -q "^STATUS: FAILED" "$f" 2>/dev/null; then
      failed_tasks+="$(basename "$f" .md) "
    fi
  done

  if [[ -n "$failed_tasks" ]]; then
    local prompt="Ces tâches TDD ont échoué: $failed_tasks

Analyse les logs dans $LOGS_DIR pour ces tâches.
Identifie le problème commun et propose une solution.
MAX 15 lignes."

    timeout 120 opencode run --agent build -m "$LRM_MODEL" "$prompt" 2>&1 | tee -a "$LOG_FILE"
  fi
}

action_start_tdd_daemon() {
  log_action "Starting TDD daemon..."
  nohup "$SCRIPT_DIR/wiggum_daemon.sh" tdd >> "$LOGS_DIR/wiggum_tdd_daemon.log" 2>&1 &
  sleep 2
  log "TDD daemon started"
}

action_start_deploy_daemon() {
  log_action "Starting Deploy daemon..."
  nohup "$SCRIPT_DIR/wiggum_daemon.sh" deploy >> "$LOGS_DIR/wiggum_deploy_daemon.log" 2>&1 &
  sleep 2
  log "Deploy daemon started"
}

action_focus_deploy() {
  log_action "Focusing on deploy - TDD complete"
  # Could stop TDD daemon to free resources
  # For now, just log the transition
  log "Transition: TDD -> Deploy phase"
}

# ============================================================================
# MAIN LOOP
# ============================================================================
main() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  LRM Brain - Active Meta-Orchestrator                            ║"
  echo "║  Pattern: arXiv:2512.24601 (MIT CSAIL)                          ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo ""
  log "Starting LRM Brain..."
  log "Log file: $LOG_FILE"
  log "Poll interval: ${LRM_POLL_INTERVAL}s"
  echo ""

  local iteration=0

  while true; do
    ((iteration++))
    log "━━━ Iteration $iteration ━━━"

    make_decision
    local decision=$?

    case $decision in
      0)
        log "🎉 All tasks complete! LRM Brain shutting down."
        break
        ;;
      1)
        action_generate_tasks
        ;;
      2)
        action_analyze_failures
        ;;
      3)
        action_start_tdd_daemon
        ;;
      4)
        action_start_deploy_daemon
        ;;
      5)
        action_focus_deploy
        ;;
      6)
        log "Monitoring... next check in ${LRM_POLL_INTERVAL}s"
        ;;
    esac

    sleep "$LRM_POLL_INTERVAL"
  done

  # Final summary
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  LRM Brain - Final Summary                                       ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  analyze_situation
  print_situation
  log "LRM Brain completed after $iteration iterations"
}

main "$@"
