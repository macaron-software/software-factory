# LLM Configuration

## Providers (multi-provider with fallback)

| Provider | Model | Use Case |
|----------|-------|----------|
| MiniMax | MiniMax-M2.5 | Default (local dev) |
| Azure OpenAI | gpt-5-mini | Production (Azure VM) |
| Azure AI | Various | Fallback |
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
```

## API Keys

Keys stored in `~/.config/factory/*.key` (chmod 600).  
⚠️ **NEVER** set `*_API_KEY=dummy` — use `PLATFORM_LLM_PROVIDER=demo` instead.

## Provider Notes

| Provider | Notes |
|----------|-------|
| MiniMax | `<think>` tags consume tokens (min 16K context) |
| GPT-5-mini | NO `temperature` param; `max_completion_tokens` ≥ 8K |
| Demo | Returns mock responses, no external calls |

## Observability

Each LLM call is traced with: provider, model, tokens (in/out), cost, latency.  
View: `/api/llm/stats` and `/api/llm/traces`.

## 🇫🇷 [Configuration LLM (FR)](LLM-Configuration‐FR) · 🇪🇸 [ES](LLM-Configuration‐ES)
