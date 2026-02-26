# LLM Configuration

## Multi-Model Routing (v2.2.0+)

Software Factory automatically routes agents to the **right model** based on their role:

| Category | Heavy Model | Light Model | Agent Tags |
|----------|-------------|-------------|------------|
| Reasoning | gpt-5.2 | gpt-5-mini | `reasoner`, `architect`, `strategist`, `planner` |
| Production / Code | gpt-5.1-codex | gpt-5-mini | `developer`, `tester`, `security`, `refactoring` |
| Tasks | gpt-5-mini | gpt-5-mini | Generic agents |
| Redaction | gpt-5.1-codex | gpt-5-mini | `doc_writer`, `tech_writer` |

Configure live in **Settings → LLM** (no restart required).

## Darwin LLM Thompson Sampling

Same team (agent + pattern) **A/B tests across LLM models** automatically:

```
Beta(wins+1, losses+1) per (agent_id, pattern_id, technology, phase_type, llm_model)
```

- **Warmup**: random exploration for first 5 runs per context
- **After warmup**: Thompson Sampling picks the model with best Beta distribution
- View results in **Teams → LLM A/B** tab

## Providers (multi-provider with fallback)

| Provider | Models | Use Case |
|----------|--------|----------|
| MiniMax | MiniMax-M2.5 | Default (local dev) |
| Azure OpenAI | gpt-5-mini | Production lightweight |
| Azure AI Foundry | gpt-5.2, gpt-5.1-codex, gpt-5.1-mini | Production advanced |
| Demo | Mock | Testing (no API key) |

## Fallback Chain

```
minimax → azure-openai → azure-ai
Cooldown: 90s on HTTP 429 (rate limit)
```

## Environment Variables

```bash
PLATFORM_LLM_PROVIDER=minimax          # or azure-openai, azure-ai, demo
PLATFORM_LLM_MODEL=MiniMax-M2.5       # or gpt-5-mini
LLM_RATE_LIMIT_RPM=50                 # requests per minute

# Azure AI Foundry (for gpt-5.2 / gpt-5.1-codex)
AZURE_AI_API_KEY=...
AZURE_DEPLOY=your-deployment-endpoint

# Azure OpenAI (for gpt-5-mini)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=...
```

## API Keys

Keys stored in `~/.config/factory/*.key` (chmod 600).  
⚠️ **NEVER** set `*_API_KEY=dummy` — use `PLATFORM_LLM_PROVIDER=demo` instead.

## Routing Config API

```bash
# Get current routing matrix
GET /api/llm/routing

# Update routing matrix (flushes 60s cache instantly)
POST /api/llm/routing
Content-Type: application/json
{
  "routing": {
    "reasoning_heavy": {"provider": "azure-ai", "model": "gpt-5.2"},
    "reasoning_light": {"provider": "azure-openai", "model": "gpt-5-mini"},
    "production_heavy": {"provider": "azure-ai", "model": "gpt-5.1-codex"},
    "production_light": {"provider": "azure-openai", "model": "gpt-5-mini"}
  }
}
```

## LLM A/B APIs

```bash
# Model fitness leaderboard
GET /api/teams/llm-leaderboard?technology=generic&phase_type=generic

# Recent A/B test results
GET /api/teams/llm-ab-tests?limit=20
```

## Provider Notes

| Provider | Notes |
|----------|-------|
| MiniMax | `<think>` tags consume tokens (min 16K context) |
| gpt-5-mini | NO `temperature` param; `max_completion_tokens` ≥ 8K |
| gpt-5.1-codex | Optimized for code; use `max_completion_tokens` |
| Demo | Returns mock responses, no external calls |

## Observability

Each LLM call is traced with: provider, model, tokens (in/out), cost, latency.  
View: `/api/llm/stats`, `/api/llm/traces`, and **Monitoring → MCP Tool Calls** in the dashboard.

## 🇫🇷 [Configuration LLM (FR)](LLM-Configuration‐FR) · 🇪🇸 [ES](LLM-Configuration‐ES)
