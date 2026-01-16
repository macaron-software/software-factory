#!/bin/bash
# ralph_full_pipeline.sh - Full Autonomous Pipeline
#
# 1. Meta-Orchestrator: Analyse LEAN + génère tâches
# 2. Ralph Wiggum TDD: Red/Green cycle sur toutes les tâches
# 3. Ralph Wiggum Deploy: Build + Deploy + E2E journeys
#
# Usage: ./ralph_full_pipeline.sh [--skip-meta] [--tdd-only] [--deploy-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$SCRIPT_DIR/logs/pipeline_$(date +%Y%m%d_%H%M%S).log"

cd "$SCRIPT_DIR"
mkdir -p logs

# ============================================================================
# UTILS
# ============================================================================
log() { echo -e "\033[0;34m[$(date +%H:%M:%S)]\033[0m $*" | tee -a "$LOG_FILE"; }
log_success() { echo -e "\033[0;32m✓\033[0m $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "\033[0;31m✗\033[0m $*" | tee -a "$LOG_FILE"; }
log_header() {
    echo "" | tee -a "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
    echo "  $*" | tee -a "$LOG_FILE"
    echo "═══════════════════════════════════════════════════════════════════" | tee -a "$LOG_FILE"
}

# ============================================================================
# PARSE ARGS
# ============================================================================
SKIP_META=false
TDD_ONLY=false
DEPLOY_ONLY=false

for arg in "$@"; do
    case $arg in
        --skip-meta) SKIP_META=true ;;
        --tdd-only) TDD_ONLY=true ;;
        --deploy-only) DEPLOY_ONLY=true ;;
    esac
done

# ============================================================================
# BANNER
# ============================================================================
cat << 'EOF'

╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   ██████╗  █████╗ ██╗     ██████╗ ██╗  ██╗    ██████╗ ██╗██████╗ ███████╗   ║
║   ██╔══██╗██╔══██╗██║     ██╔══██╗██║  ██║    ██╔══██╗██║██╔══██╗██╔════╝   ║
║   ██████╔╝███████║██║     ██████╔╝███████║    ██████╔╝██║██████╔╝█████╗     ║
║   ██╔══██╗██╔══██║██║     ██╔═══╝ ██╔══██║    ██╔═══╝ ██║██╔═══╝ ██╔══╝     ║
║   ██║  ██║██║  ██║███████╗██║     ██║  ██║    ██║     ██║██║     ███████╗   ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝    ╚═╝     ╚═╝╚═╝     ╚══════╝   ║
║                                                                              ║
║   VELIGO - Full Autonomous TDD Pipeline                                      ║
║   Based on MIT CSAIL Recursive Language Models (arXiv:2512.24601)           ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║   PHASE 1: Meta-Orchestrator (LEAN Analysis + Task Generation)               ║
║   PHASE 2: TDD Queue (Red → Code → Green cycle)                              ║
║   PHASE 3: Deploy Queue (Build → Deploy → E2E Journeys)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

EOF

log "Pipeline started at $(date)"
log "Log file: $LOG_FILE"

# ============================================================================
# PHASE 0: CHECK BACKENDS
# ============================================================================
log_header "PHASE 0: Checking LLM Backends"

./llm_worker.sh check || {
    log_error "No LLM backend available!"
    exit 1
}

# ============================================================================
# PHASE 1: META-ORCHESTRATOR
# ============================================================================
if [[ "$SKIP_META" == "false" ]] && [[ "$DEPLOY_ONLY" == "false" ]]; then
    log_header "PHASE 1: Meta-Orchestrator (LEAN Analysis)"

    log "Scanning project: $PROJECT_ROOT"
    log "Analyzing with LEAN methodology..."

    if python3 ralph_meta_orchestrator.py --project "$PROJECT_ROOT" --output tasks/ 2>&1 | tee -a "$LOG_FILE"; then
        log_success "Meta-analysis complete"

        # Count generated tasks
        TDD_COUNT=$(ls -1 tasks/T*.md 2>/dev/null | wc -l | tr -d ' ')
        DEPLOY_COUNT=$(ls -1 tasks/D*.md 2>/dev/null | wc -l | tr -d ' ')
        log "Generated: $TDD_COUNT TDD tasks, $DEPLOY_COUNT Deploy tasks"
    else
        log_error "Meta-orchestrator failed"
        # Continue with existing tasks
        log "Continuing with existing tasks..."
    fi
else
    log "Skipping meta-orchestrator (--skip-meta or --deploy-only)"
fi

# ============================================================================
# PHASE 2: TDD QUEUE
# ============================================================================
if [[ "$DEPLOY_ONLY" == "false" ]]; then
    log_header "PHASE 2: TDD Queue (Red/Green Cycle)"

    log "Starting TDD queue..."

    if ./ralph_wiggum_veligo.sh tdd 2>&1 | tee -a "$LOG_FILE"; then
        log_success "TDD queue complete"
    else
        TDD_EXIT=$?
        log_error "TDD queue failed with exit code $TDD_EXIT"

        # Check for blocked tasks
        BLOCKED=$(grep -l "STATUS: BLOCKED" tasks/T*.md 2>/dev/null | wc -l | tr -d ' ')
        if [[ $BLOCKED -gt 0 ]]; then
            log_error "$BLOCKED tasks are BLOCKED"
        fi

        if [[ "$TDD_ONLY" == "true" ]]; then
            exit $TDD_EXIT
        fi
    fi
fi

if [[ "$TDD_ONLY" == "true" ]]; then
    log_header "Pipeline Complete (TDD Only)"
    log "Log file: $LOG_FILE"
    exit 0
fi

# ============================================================================
# PHASE 3: DEPLOY QUEUE
# ============================================================================
log_header "PHASE 3: Deploy Queue (Build + Deploy + E2E)"

log "Starting deploy queue..."

if ./ralph_wiggum_veligo.sh deploy 2>&1 | tee -a "$LOG_FILE"; then
    log_success "Deploy queue complete"
else
    DEPLOY_EXIT=$?
    log_error "Deploy queue failed with exit code $DEPLOY_EXIT"
    exit $DEPLOY_EXIT
fi

# ============================================================================
# SUMMARY
# ============================================================================
log_header "Pipeline Complete"

# Count task statuses
COMPLETE=$(grep -l "STATUS: COMPLETE" tasks/*.md 2>/dev/null | wc -l | tr -d ' ')
BLOCKED=$(grep -l "STATUS: BLOCKED" tasks/*.md 2>/dev/null | wc -l | tr -d ' ')
PENDING=$(grep -l "STATUS: PENDING\|STATUS: IN_PROGRESS" tasks/*.md 2>/dev/null | wc -l | tr -d ' ')

cat << EOF

╔══════════════════════════════════════════════════════════════════════════════╗
║  PIPELINE SUMMARY                                                            ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Tasks Complete: $COMPLETE
║  Tasks Blocked:  $BLOCKED
║  Tasks Pending:  $PENDING
║
║  Log file: $LOG_FILE
╚══════════════════════════════════════════════════════════════════════════════╝

EOF

log "Pipeline finished at $(date)"
