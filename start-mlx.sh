#!/bin/bash
# start-mlx.sh — Lance mlx_lm.server avec Qwen3.5-35B-A3B-4bit
# Usage: ./start-mlx.sh [model]
#
# Le serveur écoute sur http://localhost:8080/v1 (OpenAI-compatible)
# Thompson Sampling SF : minimax M2.5 ↔ local Qwen (via LOCAL_MLX_ENABLED=1)

MODEL="${1:-mlx-community/Qwen3.5-35B-A3B-4bit}"
PORT=8080
MAX_TOKENS=8192

echo "🧬 Starting MLX server — model: $MODEL"
echo "   Port : $PORT"
echo "   Max tokens : $MAX_TOKENS"
echo ""
echo "   API endpoint : http://localhost:$PORT/v1"
echo "   Logs below ↓"
echo ""

# Download model on first run (huggingface_hub cache)
python3 -m mlx_lm server \
  --model "$MODEL" \
  --port $PORT \
  --host 127.0.0.1 \
  --max-tokens $MAX_TOKENS \
  --log-level INFO
