#!/usr/bin/env bash
# adversarial_agent.sh - Agent Adversarial (Red Team)
#
# Vérifie la qualité du travail des Wiggum:
# - Détecte le slop (code bâclé)
# - Vérifie les hallucinations
# - Détecte les contournements (test.skip, etc.)
#
# Usage: ./adversarial_agent.sh {review|audit|challenge|watch} [task_id]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
STATUS_DIR="$SCRIPT_DIR/status"
LOGS_DIR="$SCRIPT_DIR/logs"
AUDIT_DIR="$SCRIPT_DIR/audits"

MODEL="opencode/minimax-m2.1-free"

mkdir -p "$AUDIT_DIR"

# ============================================================================
# UTILS
# ============================================================================
log_red() { echo -e "\033[0;31m[ADVERSARIAL $(date +%H:%M:%S)] $*\033[0m"; }
log_warn() { echo -e "\033[0;33m[ADVERSARIAL $(date +%H:%M:%S)] ⚠ $*\033[0m"; }
log_ok() { echo -e "\033[0;32m[ADVERSARIAL $(date +%H:%M:%S)] ✓ $*\033[0m"; }

safe_count() {
  # Safely count and return integer
  local result
  result=$(cat 2>/dev/null | wc -l | tr -d '[:space:]')
  if [[ -z "$result" ]] || ! [[ "$result" =~ ^[0-9]+$ ]]; then
    echo "0"
  else
    echo "$result"
  fi
}

# ============================================================================
# CHECKS
# ============================================================================
check_slop() {
  local task_id=$1
  log_red "[$task_id] Checking for SLOP..."

  cd "$PROJECT_ROOT" || return 1

  local issues=0

  # TODO/FIXME files
  local todos
  todos=$(git diff HEAD~5 --name-only 2>/dev/null | head -100 | xargs grep -l "TODO\|FIXME" 2>/dev/null | safe_count)
  if [[ $todos -gt 0 ]]; then
    log_warn "[$task_id] Found $todos files with TODO/FIXME"
    issues=$((issues + 1))
  fi

  # Debug statements
  local debugs
  debugs=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c "console\.log\|println!\|dbg!" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$debugs" || ! "$debugs" =~ ^[0-9]+$ ]] && debugs=0
  if [[ $debugs -gt 10 ]]; then
    log_warn "[$task_id] Found $debugs debug statements"
    issues=$((issues + 1))
  fi

  # Any types
  local anys
  anys=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c ": any\|as any" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$anys" || ! "$anys" =~ ^[0-9]+$ ]] && anys=0
  if [[ $anys -gt 0 ]]; then
    log_warn "[$task_id] Found $anys 'any' types (TS slop)"
    issues=$((issues + 1))
  fi

  # Unwrap abuse
  local unwraps
  unwraps=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c "\.unwrap()" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$unwraps" || ! "$unwraps" =~ ^[0-9]+$ ]] && unwraps=0
  if [[ $unwraps -gt 5 ]]; then
    log_warn "[$task_id] Found $unwraps unwrap() calls"
    issues=$((issues + 1))
  fi

  return $issues
}

check_bypass() {
  local task_id=$1
  log_red "[$task_id] Checking for BYPASS..."

  cd "$PROJECT_ROOT" || return 1

  local issues=0

  # test.skip
  local skips
  skips=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c "test\.skip\|it\.skip" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$skips" || ! "$skips" =~ ^[0-9]+$ ]] && skips=0
  if [[ $skips -gt 0 ]]; then
    log_warn "[$task_id] CRITICAL: $skips test.skip() added!"
    issues=$((issues + 5))
  fi

  # @ts-ignore
  local ignores
  ignores=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c "@ts-ignore\|@ts-nocheck" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$ignores" || ! "$ignores" =~ ^[0-9]+$ ]] && ignores=0
  if [[ $ignores -gt 0 ]]; then
    log_warn "[$task_id] Found $ignores @ts-ignore"
    issues=$((issues + 2))
  fi

  # eslint-disable
  local eslint
  eslint=$(git diff HEAD~5 2>/dev/null | grep "^\+" | grep -c "eslint-disable" 2>/dev/null | tr -d '[:space:]' || true)
  [[ -z "$eslint" || ! "$eslint" =~ ^[0-9]+$ ]] && eslint=0
  if [[ $eslint -gt 0 ]]; then
    log_warn "[$task_id] Found $eslint eslint-disable"
    issues=$((issues + 1))
  fi

  return $issues
}

check_hallucination() {
  local task_id=$1
  log_red "[$task_id] Checking for HALLUCINATION..."

  local log_file
  log_file=$(ls -t "$LOGS_DIR/${task_id}_"*.log 2>/dev/null | head -1 || echo "")

  if [[ -z "$log_file" ]] || [[ ! -f "$log_file" ]]; then
    log_warn "[$task_id] No log file found"
    return 1
  fi

  local issues=0

  # Check for suspicious claims
  if grep -qi "100% coverage\|zero bugs\|perfect\|flawless" "$log_file" 2>/dev/null; then
    log_warn "[$task_id] Suspicious claim detected"
    issues=$((issues + 2))
  fi

  # Check SUCCESS claim
  if grep -qi "SUCCESS" "$log_file" 2>/dev/null; then
    log_ok "[$task_id] Agent claimed SUCCESS"
  fi

  return $issues
}

# ============================================================================
# REVIEW TASK
# ============================================================================
review_task() {
  local task_id=$1

  local slop_issues=0 bypass_issues=0 halluc_issues=0

  check_slop "$task_id" || slop_issues=$?
  check_bypass "$task_id" || bypass_issues=$?
  check_hallucination "$task_id" || halluc_issues=$?

  local total=$((slop_issues + bypass_issues + halluc_issues))

  echo ""
  echo "┌─ Review: $task_id ─────────────────────────────────────────────────┐"
  echo "│  Slop issues:         $slop_issues"
  echo "│  Bypass issues:       $bypass_issues"
  echo "│  Hallucination issues: $halluc_issues"
  echo "│  TOTAL:               $total"

  if [[ $total -gt 5 ]]; then
    echo "│  VERDICT:             REJECTED"
  elif [[ $total -gt 0 ]]; then
    echo "│  VERDICT:             SUSPICIOUS"
  else
    echo "│  VERDICT:             APPROVED"
  fi
  echo "└───────────────────────────────────────────────────────────────────┘"

  return $total
}

# ============================================================================
# CHALLENGE WITH AI
# ============================================================================
challenge_task() {
  local task_id=$1
  local task_file="$TASKS_DIR/${task_id}.md"

  log_red "Challenging $task_id with adversarial AI..."

  if [[ ! -f "$task_file" ]]; then
    log_red "Task file not found"
    return 1
  fi

  local task_content
  task_content=$(cat "$task_file")

  local log_content=""
  local log_file
  log_file=$(ls -t "$LOGS_DIR/${task_id}_"*.log 2>/dev/null | head -1 || echo "")
  if [[ -f "$log_file" ]]; then
    log_content=$(head -80 "$log_file")
  fi

  local prompt="Tu es un auditeur ADVERSARIAL. Cherche les PROBLÈMES.

TÂCHE:
$task_content

LOG AGENT:
$log_content

QUESTIONS:
1. L'agent a-t-il VRAIMENT résolu le problème?
2. Y a-t-il des HALLUCINATIONS?
3. Code SLOP (TODO, any, unwrap)?
4. BYPASS (test.skip, @ts-ignore)?
5. MENSONGES sur les résultats?

Réponds:
VERDICT: APPROVED / REJECTED / SUSPICIOUS
ISSUES: [liste]
SCORE: 0-100

Sois SÉVÈRE."

  local result
  result=$(timeout 180 opencode run --agent build -m "$MODEL" "$prompt" 2>&1)

  # Save audit
  local audit_file="$AUDIT_DIR/${task_id}_$(date +%Y%m%d_%H%M%S).md"
  echo "# Audit: $task_id" > "$audit_file"
  echo "Date: $(date)" >> "$audit_file"
  echo "" >> "$audit_file"
  echo "## Result" >> "$audit_file"
  echo "$result" >> "$audit_file"

  echo "$result"
  log_red "Audit saved: $audit_file"
}

# ============================================================================
# FULL AUDIT
# ============================================================================
full_audit() {
  log_red "=== FULL ADVERSARIAL AUDIT ==="

  local audited=0
  local rejected=0
  local approved=0

  for f in "$TASKS_DIR"/*.md; do
    [[ -f "$f" ]] || continue

    local task_id
    task_id=$(basename "$f" .md)

    # Only audit completed tasks
    if ! grep -q "^STATUS: COMPLETE" "$f" 2>/dev/null; then
      continue
    fi

    ((audited++))

    local issues=0
    review_task "$task_id" || issues=$?

    if [[ $issues -gt 5 ]]; then
      ((rejected++))
      # Mark as rejected
      perl -i -pe 's/^STATUS: COMPLETE/STATUS: REJECTED_AUDIT/' "$f" 2>/dev/null || true
    else
      ((approved++))
    fi
  done

  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  AUDIT SUMMARY                                                   ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo "  Audited:  $audited"
  echo "  Approved: $approved"
  echo "  Rejected: $rejected"

  return $rejected
}

# ============================================================================
# WATCH MODE
# ============================================================================
watch_mode() {
  log_red "Starting ADVERSARIAL WATCH MODE..."

  local seen=""

  while true; do
    for f in "$TASKS_DIR"/*.md; do
      [[ -f "$f" ]] || continue

      local task_id
      task_id=$(basename "$f" .md)

      # Skip seen
      if echo "$seen" | grep -q "$task_id"; then
        continue
      fi

      # Only check completed
      if grep -q "^STATUS: COMPLETE" "$f" 2>/dev/null; then
        log_red "New completed: $task_id"
        review_task "$task_id" || true
        seen="$seen $task_id"
      fi
    done

    sleep 30
  done
}

# ============================================================================
# MAIN
# ============================================================================
main() {
  echo ""
  echo "╔══════════════════════════════════════════════════════════════════╗"
  echo "║  🔴 ADVERSARIAL AGENT - Red Team Quality Control                 ║"
  echo "╚══════════════════════════════════════════════════════════════════╝"
  echo ""

  local command=${1:-"help"}
  local task_id=${2:-""}

  case $command in
    review)
      [[ -n "$task_id" ]] || { log_red "Usage: $0 review <task_id>"; exit 1; }
      review_task "$task_id"
      ;;
    challenge)
      [[ -n "$task_id" ]] || { log_red "Usage: $0 challenge <task_id>"; exit 1; }
      challenge_task "$task_id"
      ;;
    audit)
      full_audit
      ;;
    watch)
      watch_mode
      ;;
    *)
      echo "Usage: $0 {review|audit|challenge|watch} [task_id]"
      echo ""
      echo "  review <task>  - Quick review (slop/bypass/hallucination)"
      echo "  challenge <task> - AI adversarial challenge"
      echo "  audit          - Full audit of completed tasks"
      echo "  watch          - Continuous monitoring"
      ;;
  esac
}

main "$@"
