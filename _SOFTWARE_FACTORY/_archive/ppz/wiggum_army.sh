#!/bin/bash
# =============================================================================
# WIGGUM ARMY - Parallel Task Executor with MiniMax m2.1
# =============================================================================
# Lance N wiggums en parallèle via MiniMax Coding Tools API
# Usage: ./wiggum_army.sh [--workers N] [--backlog FILE]
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKLOG_FILE="${SCRIPT_DIR}/backlog_tasks.json"
MAX_WORKERS=50
LOG_DIR="${SCRIPT_DIR}/wiggum_logs"
RESULTS_DIR="${SCRIPT_DIR}/wiggum_results"

# MiniMax API Config
export ANTHROPIC_BASE_URL="${MINIMAX_BASE_URL:-https://api.minimax.io/anthropic}"
export ANTHROPIC_MODEL="${MINIMAX_MODEL:-MiniMax-M2.1}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() { echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1"; }
success() { echo -e "${GREEN}[✓]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        --workers) MAX_WORKERS="$2"; shift 2 ;;
        --backlog) BACKLOG_FILE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        -h|--help)
            echo "Usage: $0 [--workers N] [--backlog FILE] [--dry-run]"
            exit 0
            ;;
        *) shift ;;
    esac
done

# Check dependencies
check_deps() {
    if ! command -v jq &>/dev/null; then
        error "jq required. Install with: brew install jq"
        exit 1
    fi

    if [[ -z "${MINIMAX_API_KEY:-}" ]]; then
        error "MINIMAX_API_KEY not set. Get from https://platform.minimax.io"
        exit 1
    fi
    export ANTHROPIC_API_KEY="$MINIMAX_API_KEY"

    if ! command -v opencode &>/dev/null && ! command -v claude &>/dev/null; then
        warn "Neither opencode nor claude CLI found. Using curl fallback."
        USE_CURL=1
    fi
}

# Load tasks from backlog
load_tasks() {
    if [[ ! -f "$BACKLOG_FILE" ]]; then
        error "Backlog not found: $BACKLOG_FILE"
        exit 1
    fi

    # Get pending tasks
    TASKS=$(jq -r '.tasks[] | select(.status == "pending") | @base64' "$BACKLOG_FILE")
    TASK_COUNT=$(echo "$TASKS" | grep -c . || echo 0)

    log "Found $TASK_COUNT pending tasks in backlog"
}

# Execute single task via MiniMax API
execute_task_curl() {
    local task_json="$1"
    local task_id="$2"
    local log_file="${LOG_DIR}/${task_id}.log"

    local task_desc=$(echo "$task_json" | jq -r '.description // .title // "unknown"')
    local task_file=$(echo "$task_json" | jq -r '.file // "N/A"')
    local task_type=$(echo "$task_json" | jq -r '.category // "general"')

    local prompt="You are a Wiggum TDD agent. Fix this issue:
Task: $task_desc
File: $task_file
Type: $task_type

Instructions:
1. Read the file if it exists
2. Analyze the issue
3. Fix the code
4. Return the diff or state 'NO_CHANGE_NEEDED' if false positive

Be concise. Output only the fix or analysis."

    curl -s -X POST "${ANTHROPIC_BASE_URL}/v1/messages" \
        -H "x-api-key: ${ANTHROPIC_API_KEY}" \
        -H "anthropic-version: 2023-06-01" \
        -H "Content-Type: application/json" \
        -d "$(jq -n \
            --arg model "$ANTHROPIC_MODEL" \
            --arg prompt "$prompt" \
            '{
                model: $model,
                max_tokens: 4096,
                messages: [{role: "user", content: $prompt}]
            }')" \
        > "$log_file" 2>&1

    local exit_code=$?
    if [[ $exit_code -eq 0 ]]; then
        success "Task $task_id completed"
    else
        error "Task $task_id failed (exit $exit_code)"
    fi

    return $exit_code
}

# Execute task via opencode CLI
execute_task_opencode() {
    local task_json="$1"
    local task_id="$2"
    local log_file="${LOG_DIR}/${task_id}.log"

    local task_desc=$(echo "$task_json" | jq -r '.description // .title // "unknown"')
    local task_file=$(echo "$task_json" | jq -r '.file // ""')

    local prompt="Fix this issue: $task_desc"
    [[ -n "$task_file" ]] && prompt="$prompt (file: $task_file)"

    # Use opencode with MiniMax backend
    timeout 300 opencode -m "$ANTHROPIC_MODEL" "$prompt" > "$log_file" 2>&1
    return $?
}

# Worker function for parallel execution
worker() {
    local task_b64="$1"
    local worker_id="$2"

    # Decode task
    local task_json=$(echo "$task_b64" | base64 -d)
    local task_id=$(echo "$task_json" | jq -r '.id // "task-'$worker_id'"')

    log "Worker $worker_id: Starting task $task_id"

    if [[ "${USE_CURL:-0}" -eq 1 ]]; then
        execute_task_curl "$task_json" "$task_id"
    else
        execute_task_opencode "$task_json" "$task_id"
    fi

    local result=$?

    # Save result
    echo "{\"task_id\": \"$task_id\", \"status\": \"$([[ $result -eq 0 ]] && echo 'completed' || echo 'failed')\", \"timestamp\": \"$(date -Iseconds)\"}" \
        > "${RESULTS_DIR}/${task_id}.json"

    return $result
}

# Main execution
main() {
    log "========================================="
    log "  WIGGUM ARMY - MiniMax m2.1 Parallel"
    log "========================================="

    check_deps

    mkdir -p "$LOG_DIR" "$RESULTS_DIR"

    load_tasks

    if [[ $TASK_COUNT -eq 0 ]]; then
        warn "No pending tasks found"
        exit 0
    fi

    local actual_workers=$((TASK_COUNT < MAX_WORKERS ? TASK_COUNT : MAX_WORKERS))
    log "Launching $actual_workers workers for $TASK_COUNT tasks"

    if [[ "${DRY_RUN:-0}" -eq 1 ]]; then
        warn "DRY RUN - Would execute $TASK_COUNT tasks with $actual_workers workers"
        exit 0
    fi

    # Launch workers in parallel using xargs
    local worker_id=0
    echo "$TASKS" | xargs -P "$actual_workers" -I {} bash -c '
        source "'$0'"
        worker "{}" "'$((++worker_id))'"
    ' 2>/dev/null || true

    # Alternative: use GNU parallel if available
    # echo "$TASKS" | parallel -j "$actual_workers" "worker {} {#}"

    # Summary
    local completed=$(find "$RESULTS_DIR" -name "*.json" -exec grep -l '"completed"' {} \; | wc -l)
    local failed=$(find "$RESULTS_DIR" -name "*.json" -exec grep -l '"failed"' {} \; | wc -l)

    log "========================================="
    log "  RESULTS"
    log "========================================="
    success "Completed: $completed"
    [[ $failed -gt 0 ]] && error "Failed: $failed"
    log "Logs: $LOG_DIR"
    log "Results: $RESULTS_DIR"
}

# Export worker function for xargs subshell
export -f worker execute_task_curl execute_task_opencode log success error warn

main "$@"
