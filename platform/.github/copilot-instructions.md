# SF Platform — Copilot Instructions

## RUN
```bash
cd _SOFTWARE_FACTORY
pip install -r requirements.txt
python -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
# ⚠ NO --reload (shadows stdlib `platform`) · --ws none mandatory (SSE only)
# DB auto-created: data/platform.db (SQLite) or PG_DSN (PostgreSQL)
```

## ENV
```
AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT  # primary LLM
MINIMAX_API_KEY                                # fallback MiniMax-M2.5
PLATFORM_LLM_PROVIDER / PLATFORM_LLM_MODEL    # override default provider/model
```

## ARCH — FastAPI + Jinja2 + HTMX + SSE (no WS, no build step)
```
Web (routes, templates/116)  → HTMX endpoints, Jinja2 HTML
Sessions (runner.py)         → User↔Agent bridge, SSE events
Agents (executor.py)         → Tool-calling loop (max 15 rounds)
Orchestrator (engine.py)     → 26 pattern impls (solo→fractal→mob)
A2A (bus.py, veto.py)        → Inter-agent msg + veto hierarchy
LLM (client.py)              → Multi-provider auto-fallback
Memory (manager.py)          → 4-layer: project/global/vector/short-term
Bricks (bricks/)             → Modular infra: docker, github, sonarqube, rag
DB (adapter.py)              → PG 16 + FTS5 (~35 tables) | SQLite fallback
```

## EXECUTOR — agents/executor.py
Loop: sys_prompt → LLM(tools) → tool_calls? exec → feed back → repeat (max 15 rds)
Dev agents keep tools on penultimate rd (non-dev → synthesis mode at rd N-2)
Tools: code_read/write/edit/search, build, test, git_*, memory_*, deep_search, list_files
`_TOOL_SCHEMAS` cached globally — restart to refresh after tool changes

## RLM — agents/rlm.py (arXiv:2512.24601)
WRITE-EXECUTE-OBSERVE-DECIDE loop, 10 iter max, 8K findings cap
Triggered by `deep_search` tool call — deterministic sub-agents (no LLM)

## LLM — llm/client.py
Fallback: azure → azure-ai → minimax → nvidia → local
Azure: `max_completion_tokens` (not max_tokens) · MiniMax: auto-strips `<think>`
Singleton: `get_llm_client()` · Rate: 15 rpm (Redis or in-memory)

## ADVERSARIAL GUARD — agents/adversarial.py (Swiss Cheese 2-layer)
**L0 deterministic (0ms):** SLOP · MOCK · FAKE_BUILD · HALLUCINATION · LIE ·
  STACK_MISMATCH · CODE_SLOP · ECHO · REPETITION · HARDCODED_SECRET ·
  FILE_TOO_LARGE(>200L,+4) · GOD_FILE(>3types,+3) · COGNITIVE_COMPLEXITY(>25,+4) ·
  DEEP_NESTING(>4lvl,+3) · HIGH_COUPLING(>12imports,+2) · MISSING_UUID_REF ·
  MISSING_TRACEABILITY · FAKE_TESTS · SECURITY_VULN · PII_LEAK
**L1 LLM semantic:** semi-formal reasoning (arXiv:2603.01896) — premises→trace→verdict
**Score:** <5=pass · 5-6=soft · ≥7=reject · HALLUCINATION/SLOP/FAKE_BUILD → force reject

## PATTERNS — patterns/engine.py + impls/ (26 impls)
solo · sequential · parallel · hierarchical · loop · network/debate · router ·
aggregator · wave · fractal_{worktree,qa,stories,tests} · backprop_merge ·
human_in_the_loop · tournament · escalation · voting · speculative · red_blue ·
relay · mob · map_reduce · blackboard · composite
Protocols: DECOMPOSE(lead) · EXEC(dev) · QA · REVIEW · RESEARCH · CICD

## QUALITY — metrics/quality.py (KISS enforcement)
QualityScanner.scan_architecture walks workspace:
LOC(>200L) · GOD_FILE(>3types) · COGNITIVE_COMPLEXITY(>25) ·
DEEP_NESTING(>5lvl) · HIGH_COUPLING(>12imports)
All deterministic, no ext deps — indent-tracking + regex

## BRICKS — bricks/ (modular infra)
docker.py · github.py · sonarqube.py · rag.py
Each brick = self-contained infra capability, wirable as agent tools

## CONVENTIONS
- `@dataclass` + Store singletons (not Pydantic) — `get_agent_store()`, `get_llm_client()`
- Relative imports only: `from ..db.migrations import get_db`
- NEVER `import platform` top-level (shadows stdlib)
- Templates: `base.html` → `{% block content %}` · HTMX hx-get/post/swap
- CSS vars: `--bg-primary:#0f0a1a` `--purple:#a855f7` · JetBrains Mono
- View modes: card/card-simple/list/list-compact via `partials/view_switcher.html`
- `from __future__ import annotations` for forward refs

## STATS
207 agents · 33 patterns · 68 workflows · 132 skills · 164 tools · 12 roles · 4 bricks
