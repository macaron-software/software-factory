#!/bin/bash
# llm_worker.sh - Multi-Backend LLM Worker for Veligo Ralph Wiggum
# Supports: Claude CLI (headless), OpenCode, llama-server (local)

set -euo pipefail

TASKS_DIR="tasks"
PATCHES_DIR=".ralph_patches"
LOG_DIR="logs"
MAX_TOKENS="${MAX_TOKENS:-8000}"

mkdir -p "$TASKS_DIR" "$PATCHES_DIR" "$LOG_DIR"

# ============================================================================
# UTILS
# ============================================================================
log_info() { echo -e "\033[0;34mℹ\033[0m $*"; }
log_success() { echo -e "\033[0;32m✓\033[0m $*"; }
log_warn() { echo -e "\033[1;33m⚠\033[0m $*"; }
log_error() { echo -e "\033[0;31m✗\033[0m $*" >&2; }

# ============================================================================
# BACKEND DETECTION - Auto-select best available model
# Test actual generation, not just health check
# ============================================================================
test_llama_generation() {
    local url="$1"
    local response
    response=$(curl -s -X POST "$url" \
        -H "Content-Type: application/json" \
        -d '{"prompt":"Say hello","max_tokens":5,"temperature":0}' \
        --connect-timeout 2 --max-time 10 2>/dev/null)

    # Check if response contains valid choices
    if echo "$response" | grep -q '"choices"'; then
        return 0
    fi
    return 1
}

detect_backend() {
    # Priority (per user): opencode GLM-4.7 > opencode Minimax > local llama > claude (orchestrator only)
    # TDD/Code tasks use opencode models (FREE), NOT claude

    # 1. Check opencode CLI (GLM-4.7 for medium, Minimax for coding)
    if command -v opencode &>/dev/null; then
        echo "opencode"
        return 0
    fi

    # 2. Check llama-server :8000 (Qwen3-Coder local)
    if test_llama_generation "http://127.0.0.1:8000/v1/completions"; then
        echo "llama"
        return 0
    fi

    # 3. Check llama-server :8001 (DeepSeek local)
    if test_llama_generation "http://127.0.0.1:8001/v1/completions"; then
        echo "llama:8001"
        return 0
    fi

    # 4. Claude CLI only as last resort (orchestrator tier)
    if command -v claude &>/dev/null; then
        echo "claude"
        return 0
    fi

    echo "none"
    return 1
}

# ============================================================================
# CALL LLM - Route to appropriate backend
# ============================================================================
call_llm() {
    local prompt="$1"
    local backend=$(detect_backend)

    case "$backend" in
        llama)
            call_llama "http://127.0.0.1:8000/v1/completions" "$prompt"
            ;;
        llama:8001)
            call_llama "http://127.0.0.1:8001/v1/completions" "$prompt"
            ;;
        opencode)
            call_opencode "$prompt"
            ;;
        claude)
            call_claude "$prompt"
            ;;
        *)
            log_error "No LLM backend available"
            return 1
            ;;
    esac
}

call_llama() {
    local url="$1"
    local prompt="$2"

    local json_prompt
    json_prompt=$(echo "$prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

    local payload
    payload=$(cat <<EOF
{
    "prompt": "<|im_start|>user\n${json_prompt}\n<|im_end|>\n<|im_start|>assistant\n",
    "max_tokens": $MAX_TOKENS,
    "temperature": 0.2,
    "stop": ["<|im_end|>", "---END---"]
}
EOF
)

    local response
    response=$(curl -s -X POST "$url" -H "Content-Type: application/json" -d "$payload" 2>/dev/null)

    echo "$response" | python3 -c "
import json, sys, re
try:
    data = json.load(sys.stdin)
    if 'choices' in data and len(data['choices']) > 0:
        text = data['choices'][0].get('text', '')
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        print(text.strip())
except: pass
"
}

call_opencode() {
    local prompt="$1"

    # Use GLM-4.7 free model for better code generation
    # opencode uses local context (Glob, Grep, Read) automatically
    local result
    result=$(opencode run -m "opencode/glm-4.7-free" "$prompt" 2>&1 | grep -v "^\[" || echo "")

    echo "$result"
}

call_claude() {
    local prompt="$1"
    local tmpfile=$(mktemp)
    echo "$prompt" > "$tmpfile"

    # Use Claude CLI in headless mode
    local result
    result=$(cat "$tmpfile" | claude -p --output-format text --model opus --dangerously-skip-permissions 2>/dev/null || echo "")

    rm -f "$tmpfile"
    echo "$result"
}

# ============================================================================
# COMMAND: GET - Get patch from LLM (simplified prompt for opencode)
# ============================================================================
cmd_get() {
    local task_file=$1

    if [[ ! -f "$task_file" ]]; then
        echo "Error: Task file not found: $task_file"
        return 1
    fi

    local backend=$(detect_backend)
    log_info "Getting patch for: $task_file (backend: $backend)"

    # Check if task is already complete
    if grep -q "STATUS: COMPLETE" "$task_file"; then
        echo "TASK_COMPLETE"
        return 0
    fi

    # Extract key info from task file
    local task_title
    task_title=$(head -1 "$task_file" | sed 's/# //')

    local files_section
    files_section=$(sed -n '/## Files to/,/## /p' "$task_file" | grep -E "^\- \[" | head -5)

    local actions_section
    actions_section=$(sed -n '/## Actions/,/## /p' "$task_file" | grep -E "^[0-9]" | head -5)

    # Build SHORT prompt (opencode has its own context via tools)
    local prompt
    prompt="Task: $task_title

Actions:
$actions_section

Files to modify:
$files_section

Generate a unified diff patch for these changes. Use diff --git format.
Return ONLY the patch starting with 'diff --git'."

    # Call LLM
    local content
    content=$(call_llm "$prompt")

    if [[ -z "$content" ]]; then
        log_error "Empty response from LLM"
        echo "NO_PATCH_AVAILABLE"
        return 0
    fi

    # Check if task complete
    if echo "$content" | grep -q "TASK_COMPLETE\|already.*complete\|no.*changes"; then
        echo "TASK_COMPLETE"
        return 0
    fi

    # Extract patch - look for diff --git
    if echo "$content" | grep -q "^diff --git\|diff --git"; then
        local patch_content
        patch_content=$(echo "$content" | sed -n '/diff --git/,$p' | head -200)

        if [[ -n "$patch_content" ]]; then
            echo "$patch_content" > "$PATCHES_DIR/last_patch.diff"
            echo "PATCH_TYPE:diff"
            echo "---PATCH_START---"
            echo "$patch_content"
            echo "---PATCH_END---"
            return 0
        fi
    fi

    # Look for code blocks
    if echo "$content" | grep -q '```'; then
        local code_content
        code_content=$(echo "$content" | sed -n '/```/,/```/p' | sed '1d;$d')
        if [[ -n "$code_content" ]]; then
            log_info "Found code block (not a patch)"
            echo "CODE_BLOCK"
            echo "$code_content"
            return 0
        fi
    fi

    echo "NO_PATCH_AVAILABLE"
    return 0
}

# ============================================================================
# COMMAND: APPLY - Apply patch
# ============================================================================
cmd_apply() {
    local patch_file=${1:-"$PATCHES_DIR/last_patch.diff"}

    if [[ ! -f "$patch_file" ]]; then
        log_error "Patch file not found: $patch_file"
        return 1
    fi

    log_info "Applying patch from: $patch_file"

    if ! patch -p1 --dry-run < "$patch_file" &>/dev/null; then
        log_error "Patch dry-run failed"
        return 1
    fi

    if ! patch -p1 < "$patch_file" &>/dev/null; then
        log_error "Failed to apply patch"
        return 1
    fi

    log_success "Patch applied successfully"
}

# ============================================================================
# COMMAND: CHECK - Check available backends (test actual generation)
# ============================================================================
cmd_check() {
    log_info "Checking LLM backends (testing generation)..."

    local found=0

    if test_llama_generation "http://127.0.0.1:8000/v1/completions"; then
        log_success "llama-server :8000 (Qwen3-Coder) - generation OK"
        found=1
    else
        log_warn "llama-server :8000 - not working"
    fi

    if test_llama_generation "http://127.0.0.1:8001/v1/completions"; then
        log_success "llama-server :8001 (DeepSeek) - generation OK"
        found=1
    else
        log_warn "llama-server :8001 - not working"
    fi

    if command -v opencode &>/dev/null; then
        log_success "opencode CLI (GLM-4.7, Minimax)"
        found=1
    fi

    if command -v claude &>/dev/null; then
        log_success "claude CLI (Opus 4.5)"
        found=1
    fi

    if [[ $found -eq 0 ]]; then
        log_error "No LLM backend available"
        return 1
    fi

    local active=$(detect_backend)
    log_info "Active backend: $active"
}

# ============================================================================
# COMMAND: VALIDATE
# ============================================================================
cmd_validate() {
    local task_file=$1

    if [[ ! -f "$task_file" ]]; then
        log_error "Task file not found: $task_file"
        return 1
    fi

    local success_section
    success_section=$(sed -n '/## Success Criteria/,/## /p' "$task_file" | head -n -1)

    local total=$(echo "$success_section" | grep -c "^\- \[" || echo "0")
    local completed=$(echo "$success_section" | grep -c "\[x\]" || echo "0")

    echo "TOTAL:$total"
    echo "COMPLETED:$completed"

    [[ "$completed" -eq "$total" ]] && [[ "$total" -gt 0 ]]
}

# ============================================================================
# MAIN
# ============================================================================
case ${1:-help} in
    get) shift; cmd_get "$@" ;;
    apply) shift; cmd_apply "$@" ;;
    validate) shift; cmd_validate "$@" ;;
    check) cmd_check ;;
    reset) rm -rf "$PATCHES_DIR"/* && log_success "History reset" ;;
    *)
        echo "llm_worker.sh - Multi-Backend LLM Worker"
        echo ""
        echo "Usage: $0 {get|apply|validate|check|reset}"
        echo ""
        echo "Backends (auto-detected):"
        echo "  1. llama-server :8000 (Qwen3-Coder)"
        echo "  2. llama-server :8001 (DeepSeek)"
        echo "  3. opencode CLI (GLM-4.7 free)"
        echo "  4. claude CLI (Opus 4.5)"
        ;;
esac
