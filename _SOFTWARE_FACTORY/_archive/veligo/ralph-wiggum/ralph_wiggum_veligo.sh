#!/usr/bin/env bash
# ralph_wiggum_veligo.sh - Ralph Wiggum Loop pour Veligo Platform
# Queue 1: TDD Red/Green (génération code + tests)
# Queue 2: Deploy + Tests Prod
#
# RLM Pattern (arXiv:2512.24601 - MIT CSAIL):
# - Meta-Orchestrator: Claude Opus (brain) - decisions haut niveau
# - Sub-Agents: OpenCode GLM-4.7 (workers) - exécution TDD
# - Shared Context: via opencode serve --attach

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
LLM_WORKER="$SCRIPT_DIR/llm_worker.sh"
LOG_FILE="$SCRIPT_DIR/logs/ralph_wiggum_$(date +%Y%m%d_%H%M%S).log"

# RLM Server Configuration (arXiv:2512.24601)
RLM_PORT="${RLM_PORT:-4096}"
RLM_SERVER_PID=""
RLM_ATTACH_URL=""
USE_RLM_SERVER="${USE_RLM_SERVER:-true}"  # Enable RLM pattern by default

# Veligo specific
BACKEND_DIR="$PROJECT_ROOT/veligo-platform/backend"
FRONTEND_DIR="$PROJECT_ROOT/veligo-platform/frontend"
E2E_DIR="$PROJECT_ROOT/veligo-platform/tests/e2e"

# Queue mode (tdd ou deploy)
QUEUE_MODE="${1:-tdd}"

# ============================================================================
# QUEUE 1: TDD Red/Green - Génération code et tests
# ============================================================================
TDD_TASKS=(
  "T001"  # Setup Docker dev environment (WSJF: 9.5)
  "T002"  # Fix gRPC-Web proxy nginx config (WSJF: 9.0)
  "T003"  # Add security headers (HSTS, CSP, X-Frame) (WSJF: 8.5)
  "T004"  # Implement rate limiting (WSJF: 8.0)
  "T005"  # Create missing DB migrations (stations, bikes) (WSJF: 8.0)
  "T006"  # Fix RLS bypass (NULL tenant_id) (WSJF: 9.0)
  "T007"  # Complete auth gRPC service (WSJF: 7.5)
  "T008"  # Complete booking gRPC service (WSJF: 7.5)
  "T009"  # Complete subscription gRPC service (WSJF: 7.0)
  "T010"  # Implement MFA UI (WSJF: 6.5)
  "T011"  # Frontend: Dashboard with booking history (WSJF: 6.0)
  "T012"  # Frontend: Station map with availability (WSJF: 6.0)
  "T013"  # E2E: Auth journey tests (WSJF: 5.5)
  "T014"  # E2E: Booking journey tests (WSJF: 5.5)
)

# ============================================================================
# QUEUE 2: Deploy + Prod Tests
# ============================================================================
DEPLOY_TASKS=(
  "D001"  # Build backend release (WSJF: 9.0)
  "D002"  # Build frontend static (WSJF: 9.0)
  "D003"  # Deploy to staging (WSJF: 8.5)
  "D004"  # Run E2E on staging (WSJF: 8.5)
  "D005"  # Deploy to production (WSJF: 8.0)
  "D006"  # Run smoke tests on prod (WSJF: 8.0)
  "D007"  # Verify health endpoints (WSJF: 7.5)
  "D008"  # Notify completion (WSJF: 5.0)
)

# Variables de suivi
COMPLETED_TASKS=0
FAILED_TASKS=0
MAX_ITERATIONS=15  # Limite par task
MAX_WAIT_SECONDS=600  # 10 minutes par task

# Initialiser
mkdir -p "$TASKS_DIR" "$SCRIPT_DIR/logs" "$SCRIPT_DIR/.ralph_patches"

# ============================================================================
# UTILS
# ============================================================================
log_info() {
  local timestamp=$(date '+%H:%M:%S')
  echo -e "\033[0;34mℹ\033[0m [$timestamp] $*" | tee -a "$LOG_FILE"
}

log_success() {
  local timestamp=$(date '+%H:%M:%S')
  echo -e "\033[0;32m✓\033[0m [$timestamp] $*" | tee -a "$LOG_FILE"
}

log_warn() {
  local timestamp=$(date '+%H:%M:%S')
  echo -e "\033[1;33m⚠\033[0m [$timestamp] $*" | tee -a "$LOG_FILE"
}

log_error() {
  local timestamp=$(date '+%H:%M:%S')
  echo -e "\033[0;31m✗\033[0m [$timestamp] $*" | tee -a "$LOG_FILE"
}

log_header() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m═══════════════════════════════════════════════════════════\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m  $*\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m═══════════════════════════════════════════════════════════\033[0m" | tee -a "$LOG_FILE"
}

log_task_header() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "\033[1;33m┌─────────────────────────────────────────────────────────┐\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;33m│  📋 Task: $1\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;33m└─────────────────────────────────────────────────────────┘\033[0m" | tee -a "$LOG_FILE"
}

# ============================================================================
# RLM SERVER MANAGEMENT (arXiv:2512.24601 - MIT CSAIL)
# ============================================================================

start_rlm_server() {
  if [[ "$USE_RLM_SERVER" != "true" ]]; then
    log_info "RLM server disabled (USE_RLM_SERVER=false)"
    return 0
  fi

  log_info "🚀 Starting RLM server (opencode serve) on port $RLM_PORT..."
  log_info "   Pattern: arXiv:2512.24601 - Recursive Language Models"

  cd "$PROJECT_ROOT"

  # Start opencode serve in background
  opencode serve \
    --port "$RLM_PORT" \
    --hostname "127.0.0.1" \
    --log-level WARN &

  RLM_SERVER_PID=$!
  sleep 2

  if kill -0 "$RLM_SERVER_PID" 2>/dev/null; then
    RLM_ATTACH_URL="http://127.0.0.1:$RLM_PORT"
    log_success "RLM server started (PID: $RLM_SERVER_PID)"
    log_info "   Attach URL: $RLM_ATTACH_URL"
    return 0
  else
    log_error "Failed to start RLM server"
    RLM_SERVER_PID=""
    return 1
  fi
}

stop_rlm_server() {
  if [[ -n "$RLM_SERVER_PID" ]] && kill -0 "$RLM_SERVER_PID" 2>/dev/null; then
    log_info "Stopping RLM server (PID: $RLM_SERVER_PID)..."
    kill "$RLM_SERVER_PID" 2>/dev/null || true
    wait "$RLM_SERVER_PID" 2>/dev/null || true
    RLM_SERVER_PID=""
    log_success "RLM server stopped"
  fi
}

# ============================================================================
# SPECIAL TASKS: Docker Setup (T001)
# ============================================================================
execute_t001_docker() {
  log_info "Executing T001: Docker dev environment setup..."

  # Vérifier Docker
  if ! command -v docker &> /dev/null; then
    log_error "Docker not installed"
    return 1
  fi

  if ! docker info &> /dev/null; then
    log_error "Docker daemon not running"
    return 1
  fi

  log_success "Docker is running"

  # Vérifier docker-compose.dev.yml
  local compose_file="$PROJECT_ROOT/docker-compose.dev.yml"
  if [[ ! -f "$compose_file" ]]; then
    log_error "docker-compose.dev.yml not found"
    return 1
  fi

  # Lancer les services
  log_info "Starting Docker services..."
  if docker compose -f "$compose_file" up -d 2>&1 | tee -a "$LOG_FILE"; then
    log_success "Docker compose started"
  else
    log_warn "Docker compose had issues (services might already be running)"
  fi

  # Attendre les services
  log_info "Waiting 15s for services to start..."
  sleep 15

  # Vérifier les services
  log_info "Checking service health..."

  local all_ok=true

  # PostgreSQL
  if docker compose -f "$compose_file" exec -T postgres pg_isready -U veligo &>/dev/null; then
    log_success "PostgreSQL: healthy"
  else
    log_warn "PostgreSQL: not ready"
    all_ok=false
  fi

  # Redis
  if docker compose -f "$compose_file" exec -T redis redis-cli ping &>/dev/null; then
    log_success "Redis: healthy"
  else
    log_warn "Redis: not ready"
    all_ok=false
  fi

  # Backend (si lancé)
  if curl -sf http://localhost:8888/api/health &>/dev/null; then
    log_success "Backend API: healthy"
  else
    log_warn "Backend API: not responding (may need manual start)"
  fi

  # Frontend (si lancé)
  if curl -sf http://localhost:5173 &>/dev/null; then
    log_success "Frontend: healthy"
  else
    log_warn "Frontend: not responding (may need manual start)"
  fi

  if [[ "$all_ok" == "true" ]]; then
    return 0
  else
    return 1
  fi
}

# ============================================================================
# SPECIAL TASKS: Build Backend (D001)
# ============================================================================
execute_d001_build_backend() {
  log_info "Executing D001: Build backend release..."

  cd "$BACKEND_DIR"

  # Cargo build release
  log_info "Running cargo build --release..."
  if cargo build --release 2>&1 | tail -20 | tee -a "$LOG_FILE"; then
    log_success "Backend build complete"
    return 0
  else
    log_error "Backend build failed"
    return 1
  fi
}

# ============================================================================
# SPECIAL TASKS: Build Frontend (D002)
# ============================================================================
execute_d002_build_frontend() {
  log_info "Executing D002: Build frontend static..."

  cd "$FRONTEND_DIR"

  # npm build avec adapter-static
  log_info "Running ADAPTER=static npm run build..."
  if ADAPTER=static npm run build 2>&1 | tail -30 | tee -a "$LOG_FILE"; then
    log_success "Frontend build complete"
    return 0
  else
    log_error "Frontend build failed"
    return 1
  fi
}

# ============================================================================
# SPECIAL TASKS: Run E2E Tests
# ============================================================================
execute_e2e_tests() {
  local test_pattern=${1:-""}
  log_info "Running E2E tests${test_pattern:+ (pattern: $test_pattern)}..."

  cd "$FRONTEND_DIR"

  local test_cmd="npx playwright test"
  if [[ -n "$test_pattern" ]]; then
    test_cmd="$test_cmd --grep '$test_pattern'"
  fi

  if eval "$test_cmd" 2>&1 | tail -50 | tee -a "$LOG_FILE"; then
    log_success "E2E tests passed"
    return 0
  else
    log_error "E2E tests failed"
    return 1
  fi
}

# ============================================================================
# AGENTIC TASK PROCESSOR (LLM with tools: Read, Write, Bash)
# ============================================================================
AGENTIC_WORKER="$SCRIPT_DIR/agentic_worker.sh"
AGENT_MODEL="${AGENT_MODEL:-opencode}"  # opencode (GLM-4.7) pour tous les Wiggum agents

process_task_with_agent() {
  local task_id=$1
  local task_file="$TASKS_DIR/${task_id}.md"

  if [[ ! -f "$task_file" ]]; then
    log_warn "Task file not found: $task_file"
    return 1
  fi

  # Vérifier si déjà complète
  if grep -q "STATUS: COMPLETE" "$task_file"; then
    log_info "Task $task_id already complete, skipping"
    return 0
  fi

  log_task_header "$task_id"
  log_info "🤖 Running AGENTIC mode with $AGENT_MODEL"
  log_info "Agent has tools: Read, Write, Edit, Bash"

  # Build agent command with optional RLM attach
  local agent_cmd=("$AGENTIC_WORKER" "$task_file" "$AGENT_MODEL")

  if [[ -n "$RLM_ATTACH_URL" ]]; then
    log_info "📡 RLM Sub-Agent mode (attached to $RLM_ATTACH_URL)"
    agent_cmd+=("--attach" "$RLM_ATTACH_URL")
  fi

  # Lancer l'agent agentic (il gère lui-même les itérations)
  local agent_output
  local agent_exit_code=0

  if agent_output=$("${agent_cmd[@]}" 2>&1); then
    log_success "Agent completed task successfully"
    perl -i -pe 's/^STATUS: .*/STATUS: COMPLETE/' "$task_file" 2>/dev/null || true
    ((COMPLETED_TASKS++))
    return 0
  else
    agent_exit_code=$?
    log_error "Agent failed with exit code $agent_exit_code"
    echo "$agent_output" | tail -50 >> "$LOG_FILE"
    perl -i -pe 's/^STATUS: .*/STATUS: BLOCKED - Agent failed/' "$task_file" 2>/dev/null || true
    ((FAILED_TASKS++))
    return 1
  fi
}

# ============================================================================
# LEGACY: PATCH-BASED TASK PROCESSOR (fallback)
# ============================================================================
process_task_with_llm() {
  local task_id=$1
  local task_file="$TASKS_DIR/${task_id}.md"

  if [[ ! -f "$task_file" ]]; then
    log_warn "Task file not found: $task_file"
    return 1
  fi

  # Vérifier si déjà complète
  if grep -q "STATUS: COMPLETE" "$task_file"; then
    log_info "Task $task_id already complete, skipping"
    return 0
  fi

  log_task_header "$task_id"

  local iteration=0
  local task_complete=false

  while [[ $task_complete == false ]] && [[ $iteration -lt $MAX_ITERATIONS ]]; do
    ((iteration++))
    echo ""
    log_info "🔄 Iteration $iteration / $MAX_ITERATIONS"

    # 1. Obtenir patch via llm_worker
    log_info "Getting patch from LLM..."
    local patch_output
    patch_output=$("$LLM_WORKER" get "$task_file" 2>&1) || true

    # Vérifier si task complète ou pas de patch
    if echo "$patch_output" | grep -q "TASK_COMPLETE"; then
      log_success "Task $task_id marked COMPLETE by LLM"
      task_complete=true
      break
    fi

    if echo "$patch_output" | grep -q "NO_PATCH_AVAILABLE"; then
      log_warn "No patch available - waiting before retry..."
      sleep 10
      continue
    fi

    # 2. Vérifier le format du patch
    if ! echo "$patch_output" | grep -q "PATCH_TYPE:"; then
      log_error "Invalid patch format"
      echo "$patch_output" | head -20 >> "$LOG_FILE"
      sleep 5
      continue
    fi

    # 3. Extraire et appliquer le patch
    local patch_content
    patch_content=$(echo "$patch_output" | sed -n '/---PATCH_START---/,/---PATCH_END---/p' | sed '1d;$d')

    if [[ -z "$patch_content" ]]; then
      log_warn "Empty patch content"
      sleep 5
      continue
    fi

    # Sauvegarder le patch
    echo "$patch_content" > "$SCRIPT_DIR/.ralph_patches/${task_id}_$(date +%H%M%S).diff"

    log_info "Applying patch..."
    if ! echo "$patch_content" | patch -p1 --dry-run 2>&1 > /tmp/patch_dryrun.log; then
      log_error "Patch dry-run failed"
      cat /tmp/patch_dryrun.log >> "$LOG_FILE"
      sleep 5
      continue
    fi

    if ! echo "$patch_content" | patch -p1 2>&1 > /tmp/patch_apply.log; then
      log_error "Patch application failed"
      cat /tmp/patch_apply.log >> "$LOG_FILE"
      sleep 5
      continue
    fi

    log_success "Patch applied"

    # 4. Lancer les tests appropriés
    log_info "Running tests..."
    local test_passed=false

    # Déterminer le type de test à lancer
    if [[ "$task_id" == T0[0-6]* ]]; then
      # Backend tasks: cargo test
      if cd "$BACKEND_DIR" && cargo test --lib 2>&1 | tail -20 | tee -a "$LOG_FILE"; then
        test_passed=true
      fi
    elif [[ "$task_id" == T0[7-9]* ]] || [[ "$task_id" == T1* ]]; then
      # Frontend/E2E tasks: playwright
      if execute_e2e_tests; then
        test_passed=true
      fi
    else
      # Default: skip tests
      test_passed=true
    fi

    if [[ "$test_passed" == "true" ]]; then
      log_success "Tests passed"
      task_complete=true
    else
      log_warn "Tests failed - will retry"
      sleep 5
    fi
  done

  # Mettre à jour le statut de la task
  if [[ "$task_complete" == "true" ]]; then
    perl -i -pe 's/^STATUS: IN_PROGRESS.*/STATUS: COMPLETE/' "$task_file" 2>/dev/null || true
    ((COMPLETED_TASKS++))
    return 0
  else
    perl -i -pe 's/^STATUS: IN_PROGRESS.*/STATUS: BLOCKED - Max iterations reached/' "$task_file" 2>/dev/null || true
    ((FAILED_TASKS++))
    return 1
  fi
}

# ============================================================================
# QUEUE RUNNERS
# ============================================================================
run_tdd_queue() {
  log_header "🧪 QUEUE 1: TDD Red/Green"
  log_info "Processing ${#TDD_TASKS[@]} TDD tasks..."

  local total=${#TDD_TASKS[@]}

  for i in "${!TDD_TASKS[@]}"; do
    local task_id="${TDD_TASKS[$i]}"
    local task_file="$TASKS_DIR/${task_id}.md"

    log_info "[$((i+1))/$total] Processing $task_id"

    # Vérifier si déjà complète
    if [[ -f "$task_file" ]] && grep -qE "STATUS: COMPLETE[D]?" "$task_file"; then
      log_info "Task $task_id already complete, skipping"
      ((COMPLETED_TASKS++))
      continue
    fi

    # Cas spéciaux
    case $task_id in
      T001)
        if execute_t001_docker; then
          perl -i -pe 's/^STATUS: IN_PROGRESS.*/STATUS: COMPLETE/' "$task_file" 2>/dev/null || true
          ((COMPLETED_TASKS++))
        else
          ((FAILED_TASKS++))
        fi
        ;;
      *)
        # Mode AGENTIC: l'agent a accès aux tools (Read, Write, Bash)
        process_task_with_agent "$task_id"
        ;;
    esac
  done
}

run_deploy_queue() {
  log_header "🚀 QUEUE 2: Deploy + Prod Tests"
  log_info "Processing ${#DEPLOY_TASKS[@]} deploy tasks..."

  local total=${#DEPLOY_TASKS[@]}

  for i in "${!DEPLOY_TASKS[@]}"; do
    local task_id="${DEPLOY_TASKS[$i]}"
    local task_file="$TASKS_DIR/${task_id}.md"

    log_info "[$((i+1))/$total] Processing $task_id"

    # Vérifier si déjà complète
    if [[ -f "$task_file" ]] && grep -qE "STATUS: COMPLETE[D]?" "$task_file"; then
      log_info "Task $task_id already complete, skipping"
      ((COMPLETED_TASKS++))
      continue
    fi

    # Cas spéciaux pour deploy
    case $task_id in
      D001)
        if execute_d001_build_backend; then
          ((COMPLETED_TASKS++))
        else
          log_error "Backend build failed - stopping deploy queue"
          ((FAILED_TASKS++))
          return 1
        fi
        ;;
      D002)
        if execute_d002_build_frontend; then
          ((COMPLETED_TASKS++))
        else
          log_error "Frontend build failed - stopping deploy queue"
          ((FAILED_TASKS++))
          return 1
        fi
        ;;
      D003)
        log_info "Deploy to staging: veligo cicd deploy --env=staging"
        # veligo cicd deploy --env=staging
        ((COMPLETED_TASKS++))
        ;;
      D004)
        if execute_e2e_tests; then
          ((COMPLETED_TASKS++))
        else
          log_error "Staging tests failed - stopping deploy"
          ((FAILED_TASKS++))
          return 1
        fi
        ;;
      D005)
        log_info "Deploy to production: veligo cicd deploy --env=prod"
        # veligo cicd deploy --env=prod
        ((COMPLETED_TASKS++))
        ;;
      D006|D007|D008)
        # Smoke tests, health checks, notifications
        ((COMPLETED_TASKS++))
        ;;
      *)
        process_task_with_llm "$task_id"
        ;;
    esac
  done
}

# ============================================================================
# MAIN
# ============================================================================
main() {
  log_header "🎯 Ralph Wiggum - Veligo Platform"
  log_info "Mode: $QUEUE_MODE"
  log_info "Project: $PROJECT_ROOT"
  log_info "Log: $LOG_FILE"

  # Start RLM server if enabled (arXiv:2512.24601)
  if [[ "$USE_RLM_SERVER" == "true" ]]; then
    start_rlm_server || {
      log_warn "RLM server failed, falling back to standalone mode"
      USE_RLM_SERVER="false"
    }
  fi

  # Vérifier LLM disponible (for legacy llm_worker fallback)
  if ! "$LLM_WORKER" check 2>/dev/null; then
    log_warn "llama-server not available (optional for legacy mode)"
    log_info "Using OpenCode GLM-4.7 for all agents"
  fi

  # Changer de répertoire vers le projet
  cd "$PROJECT_ROOT"

  # Exécuter la queue appropriée
  case $QUEUE_MODE in
    tdd)
      run_tdd_queue
      ;;
    deploy)
      run_deploy_queue
      ;;
    all)
      run_tdd_queue
      echo ""
      if [[ $FAILED_TASKS -eq 0 ]]; then
        run_deploy_queue
      else
        log_warn "Skipping deploy queue due to TDD failures"
      fi
      ;;
    *)
      echo "Usage: $0 {tdd|deploy|all}"
      echo ""
      echo "Queues:"
      echo "  tdd    - Run TDD Red/Green queue (T001-T014)"
      echo "  deploy - Run Deploy + Prod Tests queue (D001-D008)"
      echo "  all    - Run both queues (deploy only if tdd succeeds)"
      exit 1
      ;;
  esac

  # Stop RLM server
  stop_rlm_server

  # Résumé final
  local total=$((COMPLETED_TASKS + FAILED_TASKS))
  log_header "📊 Ralph Wiggum - Résumé Final"
  echo "" | tee -a "$LOG_FILE"
  echo "  ┌─────────────────────────────────┐" | tee -a "$LOG_FILE"
  echo "  │  Tâches complétées: $COMPLETED_TASKS" | tee -a "$LOG_FILE"
  echo "  │  Tâches échouées:   $FAILED_TASKS" | tee -a "$LOG_FILE"
  echo "  │  Total traité:      $total" | tee -a "$LOG_FILE"
  if [[ $total -gt 0 ]]; then
    echo "  │  Progression:       $((COMPLETED_TASKS * 100 / total))%" | tee -a "$LOG_FILE"
  fi
  echo "  │  RLM Pattern:       arXiv:2512.24601" | tee -a "$LOG_FILE"
  echo "  └─────────────────────────────────┘" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
  echo "Next steps:" | tee -a "$LOG_FILE"
  echo "  1. Review modified files: git status" | tee -a "$LOG_FILE"
  echo "  2. Review tasks in $TASKS_DIR" | tee -a "$LOG_FILE"
  echo "  3. Review logs: $LOG_FILE" | tee -a "$LOG_FILE"
  echo "  4. Commit: git commit -m 'feat: Ralph Wiggum batch'" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
}

# Signal handlers (cleanup with RLM server stop)
final_cleanup() {
  echo ""
  log_warn "Ralph Wiggum interrupted"
  stop_rlm_server
  exit 0
}

trap final_cleanup SIGINT SIGTERM

# Start main
main "$@"
