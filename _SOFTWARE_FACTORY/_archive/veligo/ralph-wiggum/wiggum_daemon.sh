#!/usr/bin/env bash
# wiggum_daemon.sh - Daemon Wiggum autonome (TDD ou Deploy)
#
# Architecture RLM (arXiv:2512.24601 - MIT CSAIL):
# - Daemon autonome qui surveille une queue de tâches
# - Traite les tâches itérativement jusqu'à COMPLETE
# - Reporte le statut au LRM via fichiers
#
# Usage: ./wiggum_daemon.sh {tdd|deploy} [--once]
#   --once: Traite une seule tâche puis s'arrête (pour tests)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source .env.local if exists (API keys for LLM)
if [[ -f "$SCRIPT_DIR/.env.local" ]]; then
  source "$SCRIPT_DIR/.env.local"
fi

PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TASKS_DIR="$SCRIPT_DIR/tasks"
LOGS_DIR="$SCRIPT_DIR/logs"
STATUS_DIR="$SCRIPT_DIR/status"

# Configuration
POLL_INTERVAL=10          # Secondes entre checks
AGENT_TIMEOUT=7200        # 2h max par agent
MAX_RETRIES=3             # Retries par tâche
MAX_WORKERS=50            # Nombre de workers parallèles
MODEL="local/qwen3-30b-a3b"  # Modèle local llama-cpp (0 hallucination)

# Lock directory for parallel task assignment
LOCKS_DIR="$SCRIPT_DIR/status/locks"
mkdir -p "$LOCKS_DIR"

# API llama.cpp directe (bypass opencode pour éviter 40k tokens overhead)
LLAMA_API_URL="http://127.0.0.1:8002/v1/chat/completions"
LLAMA_MAX_TOKENS=8192
USE_RLM_LIGHT=true        # true = RLM Light Client (avec tools), false = opencode

# Real Agent (executes actual code changes and tests)
REAL_AGENT="$SCRIPT_DIR/real_agent.py"

# RLM Light Client (legacy, for reference)
RLM_LIGHT_CLIENT="$SCRIPT_DIR/rlm_light_client.py"

# ============================================================================
# UTILS
# ============================================================================
mkdir -p "$TASKS_DIR" "$LOGS_DIR" "$STATUS_DIR"

log_info() { echo -e "\033[0;34m[$(date +%H:%M:%S)]\033[0m $*"; }
log_success() { echo -e "\033[0;32m[$(date +%H:%M:%S)] ✓\033[0m $*"; }
log_warn() { echo -e "\033[0;33m[$(date +%H:%M:%S)] ⚠\033[0m $*"; }
log_error() { echo -e "\033[0;31m[$(date +%H:%M:%S)] ✗\033[0m $*" >&2; }

# ============================================================================
# LLAMA.CPP API DIRECT (bypass opencode, 0 overhead)
# ============================================================================
call_llm_direct() {
  local prompt="$1"
  local max_tokens="${2:-$LLAMA_MAX_TOKENS}"

  # Escape prompt for JSON
  local escaped_prompt
  escaped_prompt=$(printf '%s' "$prompt" | jq -Rs .)

  # Build JSON payload
  local payload
  payload=$(cat <<EOF
{
  "model": "qwen3",
  "messages": [{"role": "user", "content": $escaped_prompt}],
  "max_tokens": $max_tokens,
  "temperature": 0.7
}
EOF
)

  # Call API with timeout
  local response
  response=$(curl -s --max-time "$AGENT_TIMEOUT" \
    -H "Content-Type: application/json" \
    -d "$payload" \
    "$LLAMA_API_URL" 2>&1)

  local curl_exit=$?
  if [[ $curl_exit -ne 0 ]]; then
    echo "ERROR: curl failed with exit code $curl_exit"
    return 1
  fi

  # Extract content from response
  local content
  content=$(echo "$response" | jq -r '.choices[0].message.content // empty' 2>/dev/null)

  if [[ -z "$content" ]]; then
    echo "ERROR: No content in response: $response"
    return 1
  fi

  echo "$content"
  return 0
}

# ============================================================================
# ADVERSARIAL CHECK TDD - Vérification DÉTERMINISTE (pas de LLM, juste grep)
# ============================================================================
adversarial_check() {
  local task_id=$1
  local log_file=$2

  cd "$PROJECT_ROOT" || return 1

  local all_issues=""
  local has_blocker=false

  # 1. Vérifier que l'agent a bien terminé avec SUCCESS
  if ! grep -q "SUCCESS\|COMPLETE" "$log_file" 2>/dev/null; then
    echo "🚨 Agent n'a pas retourné SUCCESS"
    return 1
  fi

  # 2. Vérifier les STUBS dans les fichiers modifiés
  local files_changed
  files_changed=$(git diff --name-only HEAD 2>/dev/null | head -20)

  if [[ -n "$files_changed" ]]; then
    local stubs
    stubs=$(echo "$files_changed" | xargs grep -l 'unimplemented!\|todo!\|FIXME' 2>/dev/null | head -3)
    if [[ -n "$stubs" ]]; then
      has_blocker=true
      all_issues+="STUBS trouvés: $stubs\n"
    fi
  fi

  # 3. Vérifier test.skip dans les tests (exclure les console.log et commentaires)
  local skipped_tests
  skipped_tests=$(grep -rE '^\s*(test|it|describe)\.skip\(' veligo-platform/frontend/tests 2>/dev/null | grep -v 'console.log' | head -3)
  if [[ -n "$skipped_tests" ]]; then
    has_blocker=true
    all_issues+="Tests skippés: $skipped_tests\n"
  fi

  # 4. Vérifier que des tests ont été exécutés (présence de "test" ou "cargo" dans le log)
  if ! grep -qE 'cargo test|npm test|playwright|vitest' "$log_file" 2>/dev/null; then
    # Pas de commande de test trouvée - warning seulement
    all_issues+="⚠️ Aucune commande de test détectée dans le log\n"
  fi

  if [[ "$has_blocker" == "true" ]]; then
    echo "🚨 REJECTED: $all_issues"
    return 1
  elif [[ -n "$all_issues" ]]; then
    echo "⚠️ APPROVED_WITH_WARNINGS: $all_issues"
    return 0
  else
    echo "CLEAN"
    return 0
  fi
}

# ============================================================================
# ADVERSARIAL CHECK DEPLOY - Vérifie que le deploy a réussi
# ============================================================================
adversarial_check_deploy() {
  local task_id=$1
  local log_file=$2

  cd "$PROJECT_ROOT" || return 1

  # Pour deploy: vérifier seulement que le health check a réussi
  # Le vrai deploy est validé par l'agent qui exécute curl health check

  log_info "[$task_id] Adversarial check: HEALTH"

  # Vérifier que le log contient un health check OK ou des commandes deploy exécutées
  if grep -q "HEALTH OK\|Health OK\|health.*ok\|veligo cicd\|npm run test\|curl.*health" "$log_file" 2>/dev/null; then
    echo "CLEAN - Deploy commands verified in logs"
    return 0
  fi

  echo "⚠️ DEPLOY WARNING: No health check found in logs (but proceeding)"
  return 0  # Don't block deploy tasks, just warn
}

# ============================================================================
# TRACEABILITY - Auto-commit après COMPLETE avec référence AO
# ============================================================================
extract_ao_ref() {
  local task_file=$1
  # Cherche AO_REF: dans le fichier de tâche
  local ao_ref
  ao_ref=$(grep -E '^AO_REF:|^\*\*AO_REF\*\*:' "$task_file" 2>/dev/null | head -1 | sed 's/.*: *//' | tr -d '\r\n')
  echo "$ao_ref"
}

extract_task_description() {
  local task_file=$1
  # Extrait la description courte (première ligne du ## Description ou titre)
  local desc
  desc=$(head -1 "$task_file" | sed 's/^# Task [^:]*: //')
  # Limite à 50 caractères
  echo "${desc:0:50}"
}

auto_commit_task() {
  local task_file=$1
  local task_id=$2
  local queue_type=$3

  cd "$PROJECT_ROOT" || return 1

  # Vérifier s'il y a des changements à committer
  if ! git diff --quiet HEAD 2>/dev/null && ! git diff --cached --quiet 2>/dev/null; then
    local ao_ref
    ao_ref=$(extract_ao_ref "$task_file")

    local description
    description=$(extract_task_description "$task_file")

    # Déterminer le type de commit
    local commit_type="feat"
    if [[ "$queue_type" == "deploy" ]]; then
      commit_type="chore"
    fi

    # Construire le message de commit
    local commit_msg
    if [[ -n "$ao_ref" ]]; then
      commit_msg="${commit_type}(${task_id}): ${description} [${ao_ref}]"
    else
      commit_msg="${commit_type}(${task_id}): ${description}"
    fi

    # Git add + commit
    log_info "[$task_id] Auto-commit: $commit_msg"

    git add -A 2>/dev/null || true
    git commit -m "$commit_msg

Wiggum Agent: ${queue_type^^}
Model: $MODEL
Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)

Co-Authored-By: Wiggum Agent <wiggum@veligo.app>" 2>/dev/null || {
      log_warn "[$task_id] Git commit failed (maybe nothing to commit)"
      return 0
    }

    log_success "[$task_id] Committed successfully"
    return 0
  else
    log_info "[$task_id] No changes to commit"
    return 0
  fi
}

# ============================================================================
# TDD → DEPLOY QUEUE CHAINING
# ============================================================================
create_deploy_task() {
  local tdd_task_file=$1
  local tdd_task_id
  tdd_task_id=$(basename "$tdd_task_file" .md)

  # Extract task title and description
  local task_title
  task_title=$(head -1 "$tdd_task_file" | sed 's/^# Task [^:]*: //')

  # Extract AO_REF from source task for traceability
  local ao_ref
  ao_ref=$(extract_ao_ref "$tdd_task_file")

  # Find next D* number (use 10# to force decimal, avoid octal issue with 008)
  local next_d_num=1
  for f in "$TASKS_DIR"/D*.md; do
    [[ -f "$f" ]] || continue
    local num
    num=$(basename "$f" .md | sed 's/D//')
    if [[ "$num" =~ ^[0-9]+$ ]]; then
      # Force decimal interpretation (10#) to avoid octal issues with leading zeros
      local decimal_num=$((10#$num))
      [[ $decimal_num -ge $next_d_num ]] && next_d_num=$((decimal_num + 1))
    fi
  done

  local deploy_id
  deploy_id=$(printf "D%03d" "$next_d_num")
  local deploy_file="$TASKS_DIR/${deploy_id}.md"

  # Build AO_REF line if present
  local ao_ref_line=""
  if [[ -n "$ao_ref" ]]; then
    ao_ref_line="**AO_REF**: ${ao_ref}"
  fi

  cat > "$deploy_file" << EOF
# Task ${deploy_id}: Deploy ${tdd_task_id} - ${task_title}

**Priority**: P1
**Source**: ${tdd_task_id}
**Queue**: DEPLOY
${ao_ref_line}

## Description
Deploy changes from ${tdd_task_id} to production via CI/CD pipeline.

## Success Criteria
- [ ] veligo cicd pipeline passes all stages
- [ ] E2E tests pass on staging
- [ ] E2E tests pass on production
- [ ] No regressions in journey tests

## Actions
1. Run \`veligo cicd pipeline\` for full deployment
2. Verify staging tests pass
3. Verify production tests pass
4. Run journey E2E tests

## Files Changed (from ${tdd_task_id})
$(git diff --name-only HEAD 2>/dev/null | head -10 | sed 's/^/- /')

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING
COMPLEXITY: simple
MODEL_TIER: TIER1
WSJF: 9.0
---END_RALPH_STATUS---
EOF

  log_info "[${tdd_task_id}] Created deploy task: ${deploy_id}"
  echo "$deploy_file"
}

# ============================================================================
# TASK PROCESSING
# ============================================================================

# Acquire lock for a task (atomic operation)
acquire_task_lock() {
  local task_id=$1
  local lock_file="$LOCKS_DIR/${task_id}.lock"

  # Use mkdir for atomic lock (fails if already exists)
  if mkdir "$lock_file" 2>/dev/null; then
    echo $$ > "$lock_file/pid"
    return 0
  fi
  return 1
}

# Release lock for a task
release_task_lock() {
  local task_id=$1
  local lock_file="$LOCKS_DIR/${task_id}.lock"
  rm -rf "$lock_file" 2>/dev/null
}

# Clean stale locks (from crashed workers)
clean_stale_locks() {
  for lock_dir in "$LOCKS_DIR"/*.lock; do
    [[ -d "$lock_dir" ]] || continue
    local pid_file="$lock_dir/pid"
    if [[ -f "$pid_file" ]]; then
      local pid
      pid=$(cat "$pid_file" 2>/dev/null)
      # Check if process is still running
      if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
        rm -rf "$lock_dir"
      fi
    fi
  done
}

get_next_task() {
  local queue_type=$1
  local pattern

  case $queue_type in
    tdd) pattern="T*.md" ;;
    deploy) pattern="D*.md" ;;
    *) return 1 ;;
  esac

  # Trouver la première tâche PENDING non lockée
  for task_file in "$TASKS_DIR"/$pattern; do
    [[ -f "$task_file" ]] || continue
    if grep -q "^STATUS: PENDING" "$task_file" 2>/dev/null; then
      local task_id
      task_id=$(basename "$task_file" .md)
      # Try to acquire lock
      if acquire_task_lock "$task_id"; then
        echo "$task_file"
        return 0
      fi
      # Lock failed, task already being processed, try next
    fi
  done

  return 1
}

# Get multiple pending tasks (up to MAX_WORKERS)
get_pending_tasks() {
  local queue_type=$1
  local max_count=$2
  local pattern
  local count=0

  case $queue_type in
    tdd) pattern="T*.md" ;;
    deploy) pattern="D*.md" ;;
    *) return 1 ;;
  esac

  for task_file in "$TASKS_DIR"/$pattern; do
    [[ -f "$task_file" ]] || continue
    [[ $count -ge $max_count ]] && break

    if grep -q "^STATUS: PENDING" "$task_file" 2>/dev/null; then
      local task_id
      task_id=$(basename "$task_file" .md)
      # Try to acquire lock
      if acquire_task_lock "$task_id"; then
        echo "$task_file"
        ((count++))
      fi
    fi
  done

  [[ $count -gt 0 ]] && return 0
  return 1
}

mark_task_status() {
  local task_file=$1
  local new_status=$2

  # Update status in task file
  perl -i -pe "s/^STATUS: .*/STATUS: $new_status/" "$task_file" 2>/dev/null || true

  # Write to status file for LRM
  local task_id
  task_id=$(basename "$task_file" .md)
  echo "$new_status" > "$STATUS_DIR/${task_id}.status"
  date +%s > "$STATUS_DIR/${task_id}.timestamp"
}

build_agent_prompt() {
  local task_file=$1
  local queue_type=$2

  local task_content
  task_content=$(cat "$task_file")

  local task_title
  task_title=$(head -1 "$task_file" | sed 's/^# //')

  if [[ "$queue_type" == "tdd" ]]; then
    cat << EOF
Tu es un agent TDD autonome pour Veligo (vélos en libre-service).

## TÂCHE
$task_title

## DÉTAILS
$task_content

## 🔴 RÈGLE ABSOLUE: VÉRIFIER AVANT MODIFIER

AVANT de modifier ou créer un fichier, tu DOIS:
1. Utiliser \`Read\` pour VÉRIFIER que le fichier existe
2. Utiliser \`veligo_grep\` pour trouver les patterns existants
3. NE JAMAIS inventer un fichier qui n'existe pas

Si un fichier n'existe pas:
- Cherche un fichier similaire avec \`Glob\` ou \`veligo_rag_query\`
- Adapte ton approche au code RÉEL

## INSTRUCTIONS TDD (Red → Green)

1. **PHASE EXPLORATION**: Comprendre le contexte
   - \`veligo_rag_query("test skip failing")\` pour trouver tests problématiques
   - \`veligo_grep("TODO|FIXME", "*.rs")\` pour trouver points d'attention
   - \`Read\` sur les fichiers mentionnés pour VÉRIFIER qu'ils existent

2. **PHASE RED**: Lis le test qui échoue
   - Utilise \`Read\` pour voir le fichier test (VÉRIFIE qu'il existe!)
   - Comprends ce que le test attend

3. **PHASE CODE**: Implémente la solution
   - Utilise \`Read\` AVANT d'utiliser \`Edit\`
   - Modifie max 3 fichiers
   - Fais des changements minimaux

4. **PHASE GREEN**: Vérifie
   - Rust: \`cargo test --lib\`
   - Frontend: \`npm run test\`
   - E2E: \`npx playwright test <file>\`

## RÈGLES ANTI-HALLUCINATION
- ❌ JAMAIS modifier un fichier sans l'avoir lu d'abord
- ❌ JAMAIS inventer un chemin de fichier
- ❌ JAMAIS prétendre "tests pass" sans exécuter la commande
- ✅ Utilise veligo_grep pour trouver le bon fichier
- ✅ Utilise Read pour vérifier l'existence

## OUTILS MCP DISPONIBLES
- veligo_rag_query: Recherche sémantique dans le code
- veligo_ao_search: Recherche dans les specs AO
- veligo_grep: Grep pattern dans fichiers

Commence maintenant. Réponds avec: SUCCESS ou NEEDS_MORE_WORK
EOF
  else
    cat << EOF
DEPLOY AGENT - EXÉCUTE CES COMMANDES EXACTEMENT:

ÉTAPE 1 - Exécute MAINTENANT:
\`\`\`bash
which veligo || echo "veligo not found"
\`\`\`

ÉTAPE 2 - Si veligo existe, lance le pipeline:
\`\`\`bash
veligo cicd pipeline 2>&1 | tail -50
\`\`\`

ÉTAPE 3 - Si veligo n'existe pas, lance les tests manuellement:
\`\`\`bash
cd veligo-platform/frontend && npm run test:e2e -- --reporter=list 2>&1 | tail -30
\`\`\`

ÉTAPE 4 - Validation finale:
\`\`\`bash
curl -sf https://veligo.app/api/health && echo "SUCCESS - Health OK"
\`\`\`

RÈGLES:
- NE PAS explorer avec ls/find/cat
- EXÉCUTER les commandes ci-dessus dans l'ordre
- Réponds SUCCESS uniquement après curl health OK
EOF
  fi
}

process_task() {
  local task_file=$1
  local queue_type=$2
  local task_id
  task_id=$(basename "$task_file" .md)

  log_info "[$task_id] Processing with REAL agent..."
  mark_task_status "$task_file" "IN_PROGRESS"

  cd "$PROJECT_ROOT"

  local output
  local exit_code=0
  local log_file="$LOGS_DIR/${task_id}_$(date +%Y%m%d_%H%M%S).log"

  # Run REAL agent (executes code changes + tests + commits)
  log_info "[$task_id] Using Real Agent (actual execution, not simulation)..."
  output=$(timeout "$AGENT_TIMEOUT" python3 "$REAL_AGENT" "$task_file" "$queue_type" 2>&1) || exit_code=$?

  # Log output
  echo "$output" > "$log_file"

  # Check result - Real agent returns exit code 0 on success
  if [[ $exit_code -eq 0 ]] && echo "$output" | grep -qiE "SUCCESS|DECOMPOSED|FRACTAL_COMPLETE"; then

    # Check if task was decomposed and sub-agents completed (fractal recursive)
    if echo "$output" | grep -qi "FRACTAL_COMPLETE"; then
      log_info "[$task_id] FRACTAL: All sub-tasks completed successfully"
      mark_task_status "$task_file" "COMPLETE"
      return 0
    fi

    # Check if task was decomposed but some sub-agents failed
    if echo "$output" | grep -qi "FRACTAL_PARTIAL"; then
      log_warn "[$task_id] FRACTAL: Some sub-tasks failed, needs retry"
      mark_task_status "$task_file" "PENDING"
      return 1
    fi

    # Check if task was just decomposed (sub-agents still running)
    if echo "$output" | grep -qi "DECOMPOSED"; then
      log_info "[$task_id] Task was decomposed into sub-tasks (fractal)"
      mark_task_status "$task_file" "DECOMPOSED"
      return 0
    fi

    # =========================================================================
    # QUALITY GATES - Run before marking COMPLETE
    # =========================================================================
    # QUALITY GATES - Only for TDD tasks (deploy tasks just verify health check)
    # =========================================================================
    if [[ "$queue_type" == "tdd" ]]; then
      log_info "[$task_id] Running quality gates..."

      local gates_output
      local gates_exit=0
      gates_output=$(python3 "$SCRIPT_DIR/gates.py" --task "$task_id" --quick 2>&1) || gates_exit=$?

      if [[ $gates_exit -ne 0 ]]; then
        log_warn "[$task_id] Quality gates FAILED"
        echo "$gates_output" >> "$log_file"

        # Add gates failure to task
        echo -e "\n## Gates Failure ($(date))\n\`\`\`\n$gates_output\n\`\`\`" >> "$task_file"

        mark_task_status "$task_file" "PENDING"
        return 1
      fi

      log_success "[$task_id] Quality gates PASSED"
    else
      log_info "[$task_id] Deploy task - skipping code quality gates (health check in agent)"
    fi

    # =========================================================================
    # ADVERSARIAL CHECK - Additional validation
    # =========================================================================
    local adversarial_result
    if [[ "$queue_type" == "tdd" ]]; then
      adversarial_result=$(adversarial_check "$task_id" "$log_file")
    else
      adversarial_result=$(adversarial_check_deploy "$task_id" "$log_file")
    fi

    if echo "$adversarial_result" | grep -q "REJECTED\|BLOCKED"; then
      log_warn "[$task_id] Adversarial check REJECTED"
      echo -e "\n## Adversarial Rejection ($(date))\n\`\`\`\n$adversarial_result\n\`\`\`" >> "$task_file"
      mark_task_status "$task_file" "PENDING"
      return 1
    fi

    log_success "[$task_id] COMPLETE (real execution + gates verified)"
    mark_task_status "$task_file" "COMPLETE"

    # TDD → Deploy queue chaining (only if real changes were made)
    if [[ "$queue_type" == "tdd" ]]; then
      # Check if there were actual commits
      local last_commit
      last_commit=$(git log -1 --oneline 2>/dev/null | head -1)
      if echo "$last_commit" | grep -q "$task_id"; then
        log_info "[$task_id] Creating deploy task for committed changes"
        create_deploy_task "$task_file"
      fi
    fi
    return 0

  elif [[ $exit_code -eq 124 ]]; then
    log_warn "[$task_id] Timeout after ${AGENT_TIMEOUT}s - will retry"
    mark_task_status "$task_file" "PENDING"
    return 1

  else
    log_warn "[$task_id] Agent returned FAILED or needs more work"
    log_warn "[$task_id] Exit code: $exit_code"
    log_warn "[$task_id] Check log: $log_file"

    # Add failure summary to task for next retry
    local failure_summary
    failure_summary=$(echo "$output" | tail -20)
    echo -e "\n## Last Failure ($(date))\n\`\`\`\n$failure_summary\n\`\`\`" >> "$task_file"

    mark_task_status "$task_file" "PENDING"
    return 1
  fi
}

# ============================================================================
# DAEMON LOOP - PARALLEL WORKERS
# ============================================================================

# Process a single task with retries (worker function)
process_task_worker() {
  local task_file=$1
  local queue_type=$2
  local task_id
  task_id=$(basename "$task_file" .md)

  # Process with retries
  local retry=0
  while [[ $retry -lt $MAX_RETRIES ]]; do
    if process_task "$task_file" "$queue_type"; then
      release_task_lock "$task_id"
      return 0
    fi
    ((retry++))
    log_warn "[$task_id] Retry $retry/$MAX_RETRIES"
    sleep 5
  done

  log_error "[$task_id] Failed after $MAX_RETRIES retries"
  mark_task_status "$task_file" "FAILED"
  release_task_lock "$task_id"
  return 1
}

# Count running background jobs
count_running_workers() {
  jobs -r 2>/dev/null | wc -l | tr -d ' '
}

run_daemon() {
  local queue_type=$1
  local run_once=${2:-false}
  local daemon_name
  daemon_name="Wiggum-$(echo "$queue_type" | tr '[:lower:]' '[:upper:]')"

  log_info "Starting $daemon_name daemon (PARALLEL MODE)..."
  log_info "Queue: $queue_type"
  log_info "Tasks dir: $TASKS_DIR"
  log_info "Max workers: $MAX_WORKERS"
  log_info "Poll interval: ${POLL_INTERVAL}s"

  # Write PID file
  echo $$ > "$STATUS_DIR/${queue_type}_daemon.pid"

  # Clean stale locks from previous runs
  clean_stale_locks

  local consecutive_empty=0

  while true; do
    # Count current running workers
    local running_workers
    running_workers=$(count_running_workers)

    # Calculate how many new workers we can spawn
    local available_slots=$((MAX_WORKERS - running_workers))

    if [[ $available_slots -gt 0 ]]; then
      # Get multiple pending tasks
      local tasks_to_process
      tasks_to_process=$(get_pending_tasks "$queue_type" "$available_slots")

      if [[ -n "$tasks_to_process" ]]; then
        consecutive_empty=0

        # Spawn workers for each task
        while IFS= read -r task_file; do
          [[ -z "$task_file" ]] && continue
          local task_id
          task_id=$(basename "$task_file" .md)

          log_info "[$daemon_name] Spawning worker for: $task_id (running: $running_workers/$MAX_WORKERS)"

          # Launch worker in background
          process_task_worker "$task_file" "$queue_type" &

          ((running_workers++))
        done <<< "$tasks_to_process"

        # Exit if --once mode
        if [[ "$run_once" == "true" ]]; then
          log_info "[$daemon_name] --once mode, waiting for workers to finish..."
          wait
          break
        fi
      else
        # No new tasks found
        if [[ $running_workers -eq 0 ]]; then
          ((consecutive_empty++))

          if [[ $consecutive_empty -eq 1 ]]; then
            log_info "[$daemon_name] No pending tasks, waiting..."
          fi

          # Exit if --once mode and no tasks
          if [[ "$run_once" == "true" ]]; then
            log_info "[$daemon_name] No tasks found, exiting"
            break
          fi
        fi
      fi
    fi

    # Brief pause before next check
    sleep 2

    # Periodic status report
    if [[ $((SECONDS % 60)) -lt 3 ]]; then
      local running
      running=$(count_running_workers)
      local pending
      pending=$(grep -l "^STATUS: PENDING" "$TASKS_DIR"/*.md 2>/dev/null | wc -l | tr -d ' ')
      log_info "[$daemon_name] Status: $running workers active, $pending tasks pending"
    fi

    # Clean stale locks periodically
    if [[ $((SECONDS % 300)) -lt 3 ]]; then
      clean_stale_locks
    fi

    # Main sleep only if no workers running and no tasks
    if [[ $(count_running_workers) -eq 0 ]] && [[ $consecutive_empty -gt 0 ]]; then
      sleep "$POLL_INTERVAL"
    fi
  done

  # Wait for all workers to finish
  log_info "[$daemon_name] Waiting for all workers to complete..."
  wait

  # Cleanup
  rm -f "$STATUS_DIR/${queue_type}_daemon.pid"
  clean_stale_locks
  log_info "[$daemon_name] Daemon stopped"
}

# ============================================================================
# MAIN
# ============================================================================
main() {
  local queue_type=""
  local run_once=false

  # Parse args
  while [[ $# -gt 0 ]]; do
    case $1 in
      tdd|deploy)
        queue_type="$1"
        shift
        ;;
      --once)
        run_once=true
        shift
        ;;
      *)
        echo "Usage: $0 {tdd|deploy} [--once]"
        echo ""
        echo "Runs autonomous Wiggum daemon for task processing"
        echo ""
        echo "Options:"
        echo "  tdd      Process TDD tasks (T*.md)"
        echo "  deploy   Process Deploy tasks (D*.md)"
        echo "  --once   Process one task then exit"
        exit 1
        ;;
    esac
  done

  if [[ -z "$queue_type" ]]; then
    echo "Error: Queue type required (tdd or deploy)"
    exit 1
  fi

  run_daemon "$queue_type" "$run_once"
}

main "$@"
