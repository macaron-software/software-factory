---
description: LLM client and provider configuration — frozen, do not change models
globs: platform/llm/**/*.py, platform/config.py
---

- LLM models and deployments are FROZEN. Never change model names or provider config.
- If LLM error: check network/auth, NOT model names.
- MiniMax: no temperature param, `<think>` tokens stripped, `parallel_tool_calls=False`.
- MiniMax M2.7: supports native `role=tool` messages. No mangling.
- GPT-5.x: use `max_completion_tokens` (not `max_tokens`), reasoning budget >= 16K.
- Fallback chain: defined by `PLATFORM_LLM_PROVIDER` env var. Never hardcode.
- `_disable_thinking`: opt-in via `LLM_DISABLE_THINKING=1` env var.
- Cache key: model + messages + temperature + tools. `tool_choice` is NOT cached.
