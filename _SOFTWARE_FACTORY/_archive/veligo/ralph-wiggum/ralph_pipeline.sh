#!/usr/bin/env bash
# ralph_pipeline.sh - Pipeline RLM → TDD → Deploy avec isolation
#
# Architecture (arXiv:2512.24601 - MIT CSAIL):
# ┌─────────────────────────────────────────────────────────────────┐
# │  QUEUE 1: LRM (Meta-Orchestrator)                               │
# │  - Analyse codebase + AO                                        │
# │  - Génère tâches TDD et Deploy                                  │
# │  - opencode serve isolé (port 4096)                             │
# └─────────────────────────┬───────────────────────────────────────┘
#                           ▼
# ┌─────────────────────────────────────────────────────────────────┐
# │  QUEUE 2: TDD (Wiggum Agents)                                   │
# │  - Boucle itérative: test → code → compile → fix                │
# │  - Jusqu'à GREEN complet                                        │
# │  - opencode serve isolé (port 4097)                             │
# └─────────────────────────┬───────────────────────────────────────┘
#                           ▼
# ┌─────────────────────────────────────────────────────────────────┐
# │  QUEUE 3: Deploy (Wiggum Agents)                                │
# │  - Build → staging → E2E → prod → journeys                      │
# │  - Boucle itérative jusqu'à succès                              │
# │  - opencode serve isolé (port 4098)                             │
# └─────────────────────────────────────────────────────────────────┘

set -euo pipefail

# ============================================================================
# CONFIGURATION
# ============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
LOGS_DIR="$SCRIPT_DIR/logs"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOGS_DIR/ralph_pipeline_${TIMESTAMP}.log"

# Ports isolés par queue (dynamiques pour éviter conflits)
find_free_port() {
  local port
  for port in $(seq $1 $2); do
    if ! lsof -i :$port >/dev/null 2>&1; then
      echo $port
      return 0
    fi
  done
  echo "0"
}

LRM_PORT=$(find_free_port 5000 5100)
TDD_PORT=$(find_free_port 5101 5200)
DEPLOY_PORT=$(find_free_port 5201 5300)

# PIDs des serveurs
LRM_SERVER_PID=""
TDD_SERVER_PID=""
DEPLOY_SERVER_PID=""

# Limites
MAX_TDD_ITERATIONS=50      # Max iterations pour queue TDD
MAX_DEPLOY_ITERATIONS=20   # Max iterations pour queue Deploy
AGENT_TIMEOUT=300          # 5 min par agent

# Stats
TDD_COMPLETED=0
TDD_FAILED=0
DEPLOY_COMPLETED=0
DEPLOY_FAILED=0

# ============================================================================
# UTILS
# ============================================================================
mkdir -p "$TASKS_DIR" "$LOGS_DIR"

log_info() { echo -e "\033[0;34mℹ\033[0m [$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
log_success() { echo -e "\033[0;32m✓\033[0m [$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
log_warn() { echo -e "\033[1;33m⚠\033[0m [$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
log_error() { echo -e "\033[0;31m✗\033[0m [$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }

log_header() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m╔══════════════════════════════════════════════════════════════════╗\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m║  $*\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;36m╚══════════════════════════════════════════════════════════════════╝\033[0m" | tee -a "$LOG_FILE"
}

log_queue() {
  echo "" | tee -a "$LOG_FILE"
  echo -e "\033[1;35m┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;35m┃  $*\033[0m" | tee -a "$LOG_FILE"
  echo -e "\033[1;35m┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛\033[0m" | tee -a "$LOG_FILE"
}

# ============================================================================
# SERVEUR RLM ISOLÉ
# ============================================================================
start_isolated_server() {
  local name=$1
  local port=$2

  log_info "Starting isolated server: $name on port $port"

  cd "$PROJECT_ROOT"
  opencode serve --port "$port" --hostname "127.0.0.1" --log-level WARN &
  local pid=$!
  sleep 2

  if kill -0 "$pid" 2>/dev/null; then
    log_success "$name server ready (PID: $pid, URL: http://127.0.0.1:$port)"
    echo "$pid"
    return 0
  else
    log_error "Failed to start $name server"
    return 1
  fi
}

stop_server() {
  local pid=$1
  local name=${2:-"server"}

  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    log_info "Stopping $name server (PID: $pid)"
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
  fi
}

cleanup_all() {
  log_warn "Pipeline interrupted - cleaning up..."
  stop_server "$LRM_SERVER_PID" "LRM"
  stop_server "$TDD_SERVER_PID" "TDD"
  stop_server "$DEPLOY_SERVER_PID" "Deploy"
  exit 1
}

trap cleanup_all SIGINT SIGTERM

# ============================================================================
# QUEUE 1: LRM (Meta-Orchestrator)
# ============================================================================
run_lrm_queue() {
  log_queue "QUEUE 1: LRM Meta-Orchestrator (arXiv:2512.24601)"

  # Démarrer serveur isolé pour LRM
  LRM_SERVER_PID=$(start_isolated_server "LRM" "$LRM_PORT")
  local attach_url="http://127.0.0.1:$LRM_PORT"

  log_info "Running meta-orchestrator analysis..."
  log_info "This generates TDD and Deploy task queues"

  # Exécuter le meta-orchestrator Python
  cd "$PROJECT_ROOT"
  if python3 "$SCRIPT_DIR/ralph_meta_orchestrator.py" \
      --project "$PROJECT_ROOT" \
      --output "$TASKS_DIR" 2>&1 | tee -a "$LOG_FILE"; then
    log_success "LRM analysis complete - tasks generated"
  else
    log_warn "LRM analysis had issues, checking existing tasks..."
  fi

  # Compter les tâches générées
  local tdd_count=$(find "$TASKS_DIR" -name "T*.md" 2>/dev/null | wc -l | tr -d ' ')
  local deploy_count=$(find "$TASKS_DIR" -name "D*.md" 2>/dev/null | wc -l | tr -d ' ')

  log_info "Tasks generated: $tdd_count TDD, $deploy_count Deploy"

  # Arrêter serveur LRM
  stop_server "$LRM_SERVER_PID" "LRM"
  LRM_SERVER_PID=""

  return 0
}

# ============================================================================
# QUEUE 2: TDD Red/Green (Wiggum Agents itératifs)
# ============================================================================
run_tdd_queue() {
  log_queue "QUEUE 2: TDD Red/Green (Wiggum Agents)"

  # Démarrer serveur isolé pour TDD
  TDD_SERVER_PID=$(start_isolated_server "TDD" "$TDD_PORT")
  local attach_url="http://127.0.0.1:$TDD_PORT"

  # Collecter toutes les tâches TDD
  local tdd_tasks=()
  while IFS= read -r task_file; do
    tdd_tasks+=("$task_file")
  done < <(find "$TASKS_DIR" -name "T*.md" -type f | sort)

  if [[ ${#tdd_tasks[@]} -eq 0 ]]; then
    log_warn "No TDD tasks found"
    stop_server "$TDD_SERVER_PID" "TDD"
    return 0
  fi

  log_info "Found ${#tdd_tasks[@]} TDD tasks"

  # Boucle itérative jusqu'à tout GREEN
  local iteration=0
  local all_green=false

  while [[ $all_green == false ]] && [[ $iteration -lt $MAX_TDD_ITERATIONS ]]; do
    ((iteration++))
    log_info "━━━ TDD Iteration $iteration / $MAX_TDD_ITERATIONS ━━━"

    all_green=true
    local pending_count=0

    for task_file in "${tdd_tasks[@]}"; do
      local task_id=$(basename "$task_file" .md)

      # Vérifier status
      if grep -qE "STATUS: COMPLETE[D]?" "$task_file" 2>/dev/null; then
        continue  # Déjà complète
      fi

      all_green=false
      ((pending_count++))

      log_info "[$task_id] Running Wiggum agent..."

      # Lancer agent avec attach au serveur TDD
      if run_wiggum_agent "$task_file" "$attach_url" "tdd"; then
        log_success "[$task_id] Agent completed successfully"
        perl -i -pe 's/^STATUS: .*/STATUS: COMPLETE/' "$task_file" 2>/dev/null || true
        ((TDD_COMPLETED++))
      else
        log_warn "[$task_id] Agent needs more iterations"
        ((TDD_FAILED++))
      fi
    done

    if [[ $pending_count -eq 0 ]]; then
      all_green=true
    fi

    log_info "Iteration $iteration: $pending_count tasks remaining"
  done

  # Arrêter serveur TDD
  stop_server "$TDD_SERVER_PID" "TDD"
  TDD_SERVER_PID=""

  if [[ $all_green == true ]]; then
    log_success "🎉 All TDD tasks GREEN!"
    return 0
  else
    log_error "TDD queue incomplete after $MAX_TDD_ITERATIONS iterations"
    return 1
  fi
}

# ============================================================================
# QUEUE 3: Deploy (Wiggum Agents itératifs)
# ============================================================================
run_deploy_queue() {
  log_queue "QUEUE 3: Deploy + E2E Journeys (Wiggum Agents)"

  # Démarrer serveur isolé pour Deploy
  DEPLOY_SERVER_PID=$(start_isolated_server "Deploy" "$DEPLOY_PORT")
  local attach_url="http://127.0.0.1:$DEPLOY_PORT"

  # Collecter toutes les tâches Deploy
  local deploy_tasks=()
  while IFS= read -r task_file; do
    deploy_tasks+=("$task_file")
  done < <(find "$TASKS_DIR" -name "D*.md" -type f | sort)

  if [[ ${#deploy_tasks[@]} -eq 0 ]]; then
    log_warn "No Deploy tasks found"
    stop_server "$DEPLOY_SERVER_PID" "Deploy"
    return 0
  fi

  log_info "Found ${#deploy_tasks[@]} Deploy tasks"

  # Boucle itérative jusqu'à succès complet
  local iteration=0
  local all_deployed=false

  while [[ $all_deployed == false ]] && [[ $iteration -lt $MAX_DEPLOY_ITERATIONS ]]; do
    ((iteration++))
    log_info "━━━ Deploy Iteration $iteration / $MAX_DEPLOY_ITERATIONS ━━━"

    all_deployed=true
    local pending_count=0

    for task_file in "${deploy_tasks[@]}"; do
      local task_id=$(basename "$task_file" .md)

      # Vérifier status
      if grep -qE "STATUS: COMPLETE[D]?" "$task_file" 2>/dev/null; then
        continue  # Déjà complète
      fi

      all_deployed=false
      ((pending_count++))

      log_info "[$task_id] Running Wiggum deploy agent..."

      # Lancer agent avec attach au serveur Deploy
      if run_wiggum_agent "$task_file" "$attach_url" "deploy"; then
        log_success "[$task_id] Deploy agent completed"
        perl -i -pe 's/^STATUS: .*/STATUS: COMPLETE/' "$task_file" 2>/dev/null || true
        ((DEPLOY_COMPLETED++))
      else
        log_warn "[$task_id] Deploy agent needs more iterations"
        ((DEPLOY_FAILED++))
      fi
    done

    if [[ $pending_count -eq 0 ]]; then
      all_deployed=true
    fi

    log_info "Iteration $iteration: $pending_count tasks remaining"
  done

  # Arrêter serveur Deploy
  stop_server "$DEPLOY_SERVER_PID" "Deploy"
  DEPLOY_SERVER_PID=""

  if [[ $all_deployed == true ]]; then
    log_success "🚀 All Deploy tasks complete!"
    return 0
  else
    log_error "Deploy queue incomplete after $MAX_DEPLOY_ITERATIONS iterations"
    return 1
  fi
}

# ============================================================================
# WIGGUM AGENT (exécute une tâche avec opencode)
# ============================================================================
build_tdd_prompt() {
  local task_title="$1"
  local task_content="$2"

  cat << PROMPT_END
Tu es un agent Wiggum TDD pour Veligo. Exécute cette tâche en mode itératif.

## TÂCHE
${task_title}

## DÉTAILS
${task_content}

## OUTILS MCP DISPONIBLES (pour contexte)
Tu as accès au MCP RAG Veligo. Utilise ces outils si tu as besoin de contexte:
- veligo_rag_query: Recherche code par similarité (ex: "auth login gRPC")
- veligo_ao_search: Recherche dans les docs AO/requirements
- veligo_grep: Grep rapide dans le codebase
- veligo_modules: Liste des modules Veligo

## PROCESSUS TDD ITÉRATIF
1. CONTEXT: Si besoin, utilise MCP RAG pour comprendre le code existant
2. READ: Lis le test qui doit passer (fichier .spec.ts ou test Rust)
3. CODE: Écris le code minimal pour faire passer le test
4. COMPILE: Vérifie la compilation (cargo build ou npm run build)
5. TEST: Lance le test spécifique
6. FIX: Si erreur, corrige et recommence

## COMMANDES
- cargo test --lib           # Tests Rust
- cargo build               # Compilation Rust
- npm run build             # Build frontend
- npx playwright test       # Test E2E

## RÈGLES
- Code minimal, pas d'over-engineering
- STOP quand le test passe

Commence par lire le test, puis implémente.
PROMPT_END
}

build_deploy_prompt() {
  local task_title="$1"
  local task_content="$2"

  cat << PROMPT_END
Tu es un agent Wiggum Deploy pour Veligo. Exécute cette tâche de déploiement.

## TÂCHE
${task_title}

## DÉTAILS
${task_content}

## OUTILS MCP DISPONIBLES (pour contexte)
Tu as accès au MCP RAG Veligo:
- veligo_rag_query: Recherche code par similarité
- veligo_ao_search: Recherche dans les docs AO (SLA, requirements)
- veligo_grep: Grep rapide dans le codebase
- veligo_modules: Liste des modules Veligo

## PROCESSUS DEPLOY ITÉRATIF
1. CONTEXT: Vérifie les requirements AO si besoin (SLA, uptime)
2. BUILD: Compile le code (cargo build --release, npm run build)
3. DEPLOY: Déploie sur l'environnement cible
4. HEALTH: Vérifie les health checks
5. E2E: Lance les tests E2E / journeys
6. FIX: Si erreur, corrige et recommence

## COMMANDES
- cargo build --release      # Build release Rust
- npm run build              # Build frontend static
- veligo deploy staging      # Deploy staging
- veligo deploy prod         # Deploy prod
- npx playwright test        # Tests E2E complets

## RÈGLES
- Vérifier les health checks après deploy
- Rollback si erreur critique

Commence par le build, puis déploie.
PROMPT_END
}

run_wiggum_agent() {
  local task_file=$1
  local attach_url=$2
  local mode=${3:-"tdd"}

  local task_id
  task_id=$(basename "$task_file" .md)

  local task_content
  task_content=$(cat "$task_file")

  local task_title
  task_title=$(head -1 "$task_file" | sed 's/^# //')

  # Construire le prompt selon le mode
  local prompt
  if [[ "$mode" == "tdd" ]]; then
    prompt=$(build_tdd_prompt "$task_title" "$task_content")
  else
    prompt=$(build_deploy_prompt "$task_title" "$task_content")
  fi

  # Exécuter l'agent OpenCode
  cd "$PROJECT_ROOT"

  local output
  local cmd_args=(
    "opencode" "run"
    "--agent" "build"
    "-m" "opencode/minimax-m2.1-free"
  )

  # Ajouter --attach si URL fournie et serveur actif
  if [[ -n "$attach_url" ]] && curl -s "$attach_url" >/dev/null 2>&1; then
    cmd_args+=("--attach" "$attach_url")
    log_info "  ↳ Mode RLM (attached)"
  else
    log_info "  ↳ Mode standalone"
  fi

  cmd_args+=("$prompt")

  if output=$(timeout "$AGENT_TIMEOUT" "${cmd_args[@]}" 2>&1); then
    echo "$output" >> "$LOG_FILE"
    # Vérifier si l'agent a vraiment fait quelque chose
    if [[ ${#output} -gt 100 ]]; then
      return 0
    else
      log_warn "Agent output too short, may have failed"
      return 1
    fi
  else
    local exit_code=$?
    echo "$output" >> "$LOG_FILE"

    if [[ $exit_code -eq 124 ]]; then
      log_warn "Agent timeout after ${AGENT_TIMEOUT}s"
    fi
    return 1
  fi
}

# ============================================================================
# MAIN
# ============================================================================
main() {
  log_header "🎯 Ralph Pipeline - RLM → TDD → Deploy"
  log_info "Project: $PROJECT_ROOT"
  log_info "Log: $LOG_FILE"
  log_info "Pattern: arXiv:2512.24601 (MIT CSAIL)"

  local mode=${1:-"all"}

  case $mode in
    lrm)
      run_lrm_queue
      ;;
    tdd)
      run_tdd_queue
      ;;
    deploy)
      run_deploy_queue
      ;;
    all)
      # Pipeline complet avec gates
      log_info "Running full pipeline: LRM → TDD → Deploy"

      # Queue 1: LRM
      if ! run_lrm_queue; then
        log_error "LRM queue failed"
        exit 1
      fi

      # Queue 2: TDD (bloquant)
      if ! run_tdd_queue; then
        log_error "TDD queue failed - stopping before deploy"
        exit 1
      fi

      # Queue 3: Deploy (seulement si TDD OK)
      if ! run_deploy_queue; then
        log_error "Deploy queue failed"
        exit 1
      fi

      log_success "🎉 Full pipeline complete!"
      ;;
    *)
      echo "Usage: $0 {lrm|tdd|deploy|all}"
      echo ""
      echo "Queues:"
      echo "  lrm    - Run LRM meta-orchestrator (generate tasks)"
      echo "  tdd    - Run TDD queue (iterative until GREEN)"
      echo "  deploy - Run Deploy queue (iterative until success)"
      echo "  all    - Run full pipeline (LRM → TDD → Deploy)"
      exit 1
      ;;
  esac

  # Résumé final
  log_header "📊 Pipeline Summary"
  echo "" | tee -a "$LOG_FILE"
  echo "  ┌─────────────────────────────────────┐" | tee -a "$LOG_FILE"
  echo "  │  TDD Completed:    $TDD_COMPLETED" | tee -a "$LOG_FILE"
  echo "  │  TDD Failed:       $TDD_FAILED" | tee -a "$LOG_FILE"
  echo "  │  Deploy Completed: $DEPLOY_COMPLETED" | tee -a "$LOG_FILE"
  echo "  │  Deploy Failed:    $DEPLOY_FAILED" | tee -a "$LOG_FILE"
  echo "  │  Pattern:          arXiv:2512.24601" | tee -a "$LOG_FILE"
  echo "  └─────────────────────────────────────┘" | tee -a "$LOG_FILE"
  echo "" | tee -a "$LOG_FILE"
}

main "$@"
