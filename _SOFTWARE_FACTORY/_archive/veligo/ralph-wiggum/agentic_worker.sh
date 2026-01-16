#!/bin/bash
# agentic_worker.sh - Lance des agents LLM agentic (avec tools)
# Les agents peuvent: Read, Write, Edit, Bash (tests, build)
#
# Usage: ./agentic_worker.sh <task_file> [model] [--attach URL]
# Models: opencode (default), claude
#
# RLM Pattern (arXiv:2512.24601 - MIT CSAIL):
# - Sans --attach: Mode standalone (lance son propre contexte)
# - Avec --attach: Mode sub-agent (connecté au serveur RLM)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MAX_TURNS="${MAX_TURNS:-25}"
RLM_ATTACH_URL="${RLM_ATTACH_URL:-}"

# ============================================================================
# UTILS
# ============================================================================
log_info() { echo -e "\033[0;34mℹ\033[0m $*"; }
log_success() { echo -e "\033[0;32m✓\033[0m $*"; }
log_error() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

# ============================================================================
# BUILD AGENTIC PROMPT
# ============================================================================
build_agent_prompt() {
    local task_file=$1

    # Extraire infos de la tâche
    local task_title
    task_title=$(head -1 "$task_file" | sed 's/^# //')

    local task_content
    task_content=$(cat "$task_file")

    cat << EOF
Tu es un agent TDD pour le projet Veligo (vélos en libre-service).

## TÂCHE À ACCOMPLIR
$task_title

## DÉTAILS
$task_content

## INSTRUCTIONS TDD (Red → Green)

1. **PHASE RED**: Lis d'abord le test qui échoue (fichier .spec.ts ou test Rust)
   - Utilise Read pour voir le test
   - Comprends ce que le test attend

2. **PHASE CODE**: Implémente le code nécessaire
   - Utilise Read pour voir le code source actuel
   - Utilise Edit pour modifier le code
   - Fais des changements minimaux et ciblés

3. **PHASE GREEN**: Vérifie que les tests passent
   - Pour Rust: \`cargo test --lib\`
   - Pour Frontend: \`npm run test\` dans veligo-platform/frontend
   - Pour E2E: \`npx playwright test <fichier>\`

4. **ITÉRATION**: Si le test échoue, lis l'erreur et corrige

## RÈGLES
- Ne modifie PAS plus de 3 fichiers
- Pas de refactoring inutile
- Pas de code commenté
- Commit atomiques
- STOP quand les tests passent

## STRUCTURE DU PROJET
- Backend Rust: veligo-platform/backend/src/
- Frontend SvelteKit: veligo-platform/frontend/src/
- Tests E2E: veligo-platform/tests/e2e/
- Protos gRPC: veligo-platform/proto/

## COMMANDES UTILES
- cargo test --lib                    # Tests Rust
- cargo test <test_name>              # Test spécifique
- npm run test                        # Tests frontend
- npx playwright test <file>          # Test E2E spécifique
- cargo build                         # Vérifier compilation

Commence par lire le test puis implémente la solution.
EOF
}

# ============================================================================
# RUN CLAUDE AGENT (agentic mode with tools - headless)
# Note: Claude CLI doesn't support --attach, used only for Meta-Orchestrator brain
# ============================================================================
run_claude_agent() {
    local task_file=$1
    local prompt
    prompt=$(build_agent_prompt "$task_file")

    log_info "Launching Claude agent (headless agentic mode)..."
    log_info "Max turns: $MAX_TURNS"

    cd "$PROJECT_ROOT"

    # Claude CLI headless mode with -p flag
    # --dangerously-skip-permissions enables auto-accept for tools
    # --max-turns limits iterations
    claude -p "$prompt" \
        --dangerously-skip-permissions \
        --max-turns "$MAX_TURNS" \
        2>&1

    return $?
}

# ============================================================================
# RUN OPENCODE AGENT (agentic mode with tools)
# Supports RLM pattern via --attach for sub-agent mode
# ============================================================================
run_opencode_agent() {
    local task_file=$1
    local attach_url=${2:-""}
    local prompt
    prompt=$(build_agent_prompt "$task_file")

    cd "$PROJECT_ROOT"

    if [[ -n "$attach_url" ]]; then
        # RLM Sub-Agent Mode (arXiv:2512.24601)
        # Connect to existing opencode serve instance
        log_info "Launching OpenCode sub-agent (RLM attached mode)..."
        log_info "Attach URL: $attach_url"
        log_info "Agent has tools: bash, read, write, edit, grep, glob"

        opencode run \
            --attach "$attach_url" \
            --agent build \
            -m "opencode/minimax-m2.1-free" \
            "$prompt" \
            2>&1
    else
        # Standalone Mode
        log_info "Launching OpenCode agent (standalone mode)..."
        log_info "Agent has tools: bash, read, write, edit, grep, glob"

        # OpenCode avec l'agent 'build' qui a toutes les permissions
        # --agent build permet bash, read, write, edit
        # -m pour le modèle GLM-4.7 (gratuit)
        opencode run \
            --agent build \
            -m "opencode/minimax-m2.1-free" \
            "$prompt" \
            2>&1
    fi

    return $?
}

# ============================================================================
# START RLM SERVER (opencode serve)
# ============================================================================
start_rlm_server() {
    local port=${1:-4096}

    log_info "Starting RLM server (opencode serve) on port $port..."

    cd "$PROJECT_ROOT"

    # Start opencode serve in background
    opencode serve \
        --port "$port" \
        --hostname "127.0.0.1" \
        --log-level WARN &

    local pid=$!
    sleep 2

    if kill -0 "$pid" 2>/dev/null; then
        log_success "RLM server started (PID: $pid, Port: $port)"
        echo "$pid"
    else
        log_error "Failed to start RLM server"
        return 1
    fi
}

# ============================================================================
# MAIN
# ============================================================================
main() {
    local task_file=""
    local model="opencode"  # Default to opencode (GLM-4.7) for all Wiggum agents
    local attach_url=""

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --attach)
                attach_url="$2"
                shift 2
                ;;
            --model|-m)
                model="$2"
                shift 2
                ;;
            --start-server)
                start_rlm_server "${2:-4096}"
                exit $?
                ;;
            -*)
                log_error "Unknown option: $1"
                exit 1
                ;;
            *)
                if [[ -z "$task_file" ]]; then
                    task_file="$1"
                else
                    model="$1"
                fi
                shift
                ;;
        esac
    done

    # Also check environment variable for attach URL
    if [[ -z "$attach_url" && -n "$RLM_ATTACH_URL" ]]; then
        attach_url="$RLM_ATTACH_URL"
    fi

    if [[ -z "$task_file" ]]; then
        cat << 'USAGE'
Usage: ./agentic_worker.sh <task_file.md> [model] [--attach URL]

Runs an agentic LLM with tools (Read, Write, Bash) to complete TDD tasks

Models:
  opencode  - GLM-4.7 Free (default, recommended for Wiggum agents)
  claude    - Claude Opus (reserved for Meta-Orchestrator brain)

RLM Pattern (arXiv:2512.24601 - MIT CSAIL):
  --attach URL     Connect as sub-agent to RLM server
  --start-server   Start opencode serve (RLM server mode)

Environment:
  MAX_TURNS        Max agent iterations (default: 25)
  RLM_ATTACH_URL   Default attach URL for sub-agent mode

Examples:
  # Standalone mode
  ./agentic_worker.sh tasks/T001.md opencode

  # Start RLM server
  ./agentic_worker.sh --start-server 4096

  # Sub-agent connected to RLM server
  ./agentic_worker.sh tasks/T001.md --attach http://127.0.0.1:4096
USAGE
        exit 1
    fi

    if [[ ! -f "$task_file" ]]; then
        log_error "Task file not found: $task_file"
        exit 1
    fi

    log_info "Task: $task_file"
    log_info "Model: $model"
    log_info "Working directory: $PROJECT_ROOT"
    [[ -n "$attach_url" ]] && log_info "RLM Attach: $attach_url"

    case $model in
        claude)
            if [[ -n "$attach_url" ]]; then
                log_error "Claude CLI doesn't support --attach (RLM mode)"
                log_error "Use opencode for sub-agents per arXiv:2512.24601"
                exit 1
            fi
            run_claude_agent "$task_file"
            ;;
        opencode)
            run_opencode_agent "$task_file" "$attach_url"
            ;;
        *)
            log_error "Unknown model: $model (use opencode or claude)"
            exit 1
            ;;
    esac
}

main "$@"
