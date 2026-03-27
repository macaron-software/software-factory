#!/usr/bin/env bash
# bench_local_models.sh — Run ToolCall-15 on local models via llama.cpp + TurboQuant
# Sequential execution (one model at a time) to avoid RAM exhaustion on 32GB Mac.
#
# Usage: bash scripts/bench_local_models.sh

set -euo pipefail

LLAMA_SERVER="${LLAMA_TURBO:-/tmp/llama-turbo/build/bin/llama-server}"
MODELS_DIR="${MODELS_DIR:-$HOME/Models}"
SF_PORT="${SF_PORT:-8099}"
LLAMA_PORT=8181
API_KEY="${MACARON_API_KEY:-local-dev-skip}"

# Check prerequisites
if [ ! -x "$LLAMA_SERVER" ]; then
    echo "ERROR: llama-server not found at $LLAMA_SERVER"
    echo "Build with: cd /tmp/llama-turbo && cmake -B build -DGGML_METAL=ON && cmake --build build -j -- llama-server"
    exit 1
fi

# Models to bench (sequential)
declare -A MODELS
MODELS["qwen3-32b"]="${MODELS_DIR}/qwen3-32b-q4_k_m.gguf"
MODELS["qwen3.5-35b-a3b"]="${MODELS_DIR}/qwen3.5-35b-a3b-q4_k_m.gguf"

# TurboQuant cache types to test
CACHE_TYPES=("turbo3" "q8_0")

bench_model() {
    local name="$1"
    local model_path="$2"
    local cache_type="$3"

    if [ ! -f "$model_path" ]; then
        echo "SKIP: $model_path not found"
        return
    fi

    echo "================================================"
    echo "BENCH: $name (cache=$cache_type)"
    echo "================================================"

    # Start llama-server
    echo "Starting llama-server on :$LLAMA_PORT..."
    $LLAMA_SERVER \
        -m "$model_path" \
        --port $LLAMA_PORT \
        --host 127.0.0.1 \
        -ngl 999 \
        --flash-attn on \
        --cache-type-k "$cache_type" \
        --cache-type-v "$cache_type" \
        -c 32768 \
        --threads $(sysctl -n hw.ncpu) \
        > /tmp/llama-bench-${name}.log 2>&1 &
    LLAMA_PID=$!

    # Wait for server to be ready
    echo "Waiting for server..."
    for i in $(seq 1 60); do
        if curl -sf "http://127.0.0.1:$LLAMA_PORT/health" > /dev/null 2>&1; then
            echo "Server ready (${i}s)"
            break
        fi
        if ! kill -0 $LLAMA_PID 2>/dev/null; then
            echo "ERROR: llama-server died. Check /tmp/llama-bench-${name}.log"
            return
        fi
        sleep 1
    done

    # Run ToolCall-15 via SF API
    echo "Running ToolCall-15..."
    local provider_name="llamacpp"
    local model_name="${name}-${cache_type}"

    # Configure SF to use local llama.cpp
    export OLLAMA_ENABLED=1
    export OLLAMA_URL="http://127.0.0.1:$LLAMA_PORT/v1"
    export OLLAMA_MODEL="$name"

    python3 -c "
import asyncio
from platform.tools.toolcall_bench import run_toolcall_bench

async def main():
    result = await run_toolcall_bench(
        model='${name}',
        provider='ollama',
        tool_choice='auto',
    )
    print(f'Score: {result.final_score}% ({result.rating})')
    print(f'Points: {result.total_points}/{result.max_points} | Duration: {result.duration_s}s')
    for cs in result.category_scores:
        bar = '#' * (cs.percent // 10) + '.' * (10 - cs.percent // 10)
        print(f'  {cs.category}: {cs.label:25s} {cs.earned}/6 [{bar}] {cs.percent}%')
    print()
    for sr in result.scenario_results:
        icon = {'pass': 'OK', 'partial': '~~', 'fail': 'XX'}.get(sr.status, '??')
        print(f'  [{icon}] {sr.scenario_id}: {sr.title:30s} {sr.points}pts  {sr.summary[:70]}')

asyncio.run(main())
" 2>&1 | tee /tmp/toolcall15-${name}-${cache_type}.txt

    # Stop llama-server
    echo "Stopping llama-server (PID=$LLAMA_PID)..."
    kill $LLAMA_PID 2>/dev/null
    wait $LLAMA_PID 2>/dev/null || true
    sleep 3  # Let RAM free up

    echo ""
    echo "Results saved: /tmp/toolcall15-${name}-${cache_type}.txt"
    echo ""
}

# ── Run benchmarks sequentially ──────────────────────────────────────────────

echo "Local Model Bench — ToolCall-15 via llama.cpp + TurboQuant"
echo "RAM: $(sysctl -n hw.memsize | awk '{printf "%.0f GB", $1/1024/1024/1024}')"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
echo ""

# Test 1: Qwen3-32B (dense) — the reliable one
for ct in "${CACHE_TYPES[@]}"; do
    bench_model "qwen3-32b" "${MODELS[qwen3-32b]}" "$ct"
done

# Test 2: Qwen3.5-35B-A3B (MoE) — the fast one
for ct in "${CACHE_TYPES[@]}"; do
    bench_model "qwen3.5-35b-a3b" "${MODELS[qwen3.5-35b-a3b]}" "$ct"
done

echo "================================================"
echo "ALL DONE — Compare results:"
echo "  cat /tmp/toolcall15-qwen3-32b-turbo3.txt"
echo "  cat /tmp/toolcall15-qwen3-32b-q8_0.txt"
echo "  cat /tmp/toolcall15-qwen3.5-35b-a3b-turbo3.txt"
echo "  cat /tmp/toolcall15-qwen3.5-35b-a3b-q8_0.txt"
echo "================================================"
