# SF Platform — Copilot Instructions

## RUN
```bash
cd _SOFTWARE_FACTORY
pip install -r requirements.txt
python -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
# ⚠ NO --reload (shadows stdlib `platform`) · --ws none (SSE only)
# DB: data/platform.db (SQLite) or PG_DSN (PostgreSQL) — auto-created
```

## ENV
```
AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT  # primary LLM
MINIMAX_API_KEY                                # fb MiniMax-M2.5
PLATFORM_LLM_PROVIDER / PLATFORM_LLM_MODEL    # override default
```

## ARCH — FastAPI + Jinja2 + HTMX + SSE (no WS, zero build step)
```
Web (routes, templates/117)  → HTMX endpoints, Jinja2 HTML
Sessions (runner.py)         → User↔Agent bridge, SSE events
Agents (executor.py)         → Tool-call loop (max 15 rds)
Orchestrator (engine.py)     → 26 pattern impls (solo→fractal→mob)
Epic Orch (epic_orch.py)     → Mission phases, sprint loop, platform-aware prompts
A2A (bus.py, veto.py)        → Inter-agent msg + veto hierarchy
LLM (client.py)              → Multi-provider auto-fallback (azure→minimax→local)
Memory (manager.py)          → 4-layer: project/global/vector/short-term
Bricks (bricks/)             → Modular infra: docker, github, sonarqube, rag
DB (adapter.py)              → PG16 WAL+FTS5 (~35 tables) | SQLite fb
Security (security/)         → prompt_guard, output_validator, audit, sanitize
AC (ac/)                     → reward(14-dim), convergence, experiments, skill_thompson
```

## EXECUTOR — agents/executor.py
Loop: sys_prompt → LLM(tools) → tool_calls? exec → feed back → repeat (max 15 rds)
Dev agents keep tools penultimate rd (non-dev → synthesis at rd N-2)
Tools: code_read/write/edit/search, build, test, git_*, memory_*, deep_search, list_files
`_TOOL_SCHEMAS` cached global — restart to refresh

## RLM — agents/rlm.py (arXiv:2512.24601)
WRITE-EXECUTE-OBSERVE-DECIDE loop, 10 iter max, 8K findings cap
Triggered by `deep_search` — deterministic sub-agents (no LLM)

## LLM — llm/client.py
Fallback: azure → azure-ai → minimax → nvidia → local-mlx
Azure: `max_completion_tokens` (not max_tokens) · MiniMax: auto-strips `<think>`
GPT-5.x: reasoning models, budget ≥16K (reasoning eats from budget)
Singleton: `get_llm_client()` · Rate: 15rpm (Redis or in-mem)

## ADVERSARIAL GUARD — agents/adversarial.py (Swiss Cheese)
**L0 det (0ms):** SLOP · MOCK · FAKE_BUILD(+7) · HALLUCINATION · LIE ·
  STACK_MISMATCH(+7) · CODE_SLOP · ECHO · REPETITION · HARDCODED_SECRET ·
  FILE_TOO_LARGE(>200L,+4) · GOD_FILE(>3types,+3) · COGNITIVE_COMPLEXITY(>25,+4) ·
  DEEP_NESTING(>4lvl,+3) · HIGH_COUPLING(>12imp,+2) · LOC_REGRESSION(+6) ·
  MISSING_UUID_REF · MISSING_TRACEABILITY · FAKE_TESTS · NO_TESTS ·
  SECURITY_VULN · PII_LEAK · PROMPT_INJECTION · IDENTITY_CLAIM · RESOURCE_ABUSE
**L1 LLM semantic:** semi-formal reasoning (arXiv:2603.01896) — premises→trace→verdict
**Score:** <5=pass · 5-6=soft · ≥7=reject · HALLUCINATION/SLOP/FAKE_BUILD/STACK_MISMATCH → force reject
MAX_ADVERSARIAL_RETRIES=1 (2 attempts total) — exhausted → FAILED, output discarded

## STACK ENFORCEMENT — epic orch + adversarial
`_detect_project_platform(ws, brief)` → rust-native | macos-native | ios-native | android-native | web-node | web-docker | web-static
Priority: brief keywords → .stack file → filesystem (Cargo.toml, package.json, etc.)
Platform-specific prompts injected: build cmd, file structure, QA/deploy/CICD instructions
STACK_MISMATCH L0 rejects wrong-lang code (e.g. .ts in Rust project) → score +7

## PATTERNS — patterns/engine.py + impls/ (26)
solo · sequential · parallel · hierarchical · loop · network/debate · router ·
aggregator · wave · fractal_{worktree,qa,stories,tests} · backprop_merge ·
human_in_the_loop · tournament · escalation · voting · speculative · red_blue ·
relay · mob · map_reduce · blackboard · composite
Protocols: DECOMPOSE(lead) · EXEC(dev) · QA · REVIEW · RESEARCH · CICD
Role match: "dev","lead","veloppeur","engineer","coder","tdd","worker","fullstack"

## QUALITY — metrics/quality.py (KISS)
QualityScanner.scan_architecture: LOC(>200) · GOD_FILE(>3types) ·
COGNITIVE_COMPLEXITY(>25) · DEEP_NESTING(>5lvl) · HIGH_COUPLING(>12imp)
Det only, no ext deps — indent-tracking + regex

## BRICKS — bricks/ (modular infra)
docker.py · github.py · sonarqube.py · rag.py — self-contained, wirable as tools

## CONVENTIONS
- `@dataclass` + Store singletons (not Pydantic) — `get_agent_store()`, `get_llm_client()`
- Relative imports: `from ..db.migrations import get_db`
- NEVER `import platform` top-level (shadows stdlib)
- Templates: `base.html` → `{% block content %}` · HTMX hx-get/post/swap
- CSS vars: `--bg-primary:#0f0a1a` `--purple:#a855f7` · JetBrains Mono
- Views: card/card-simple/list/list-compact via `partials/view_switcher.html`
- `from __future__ import annotations` for fwd refs

## STATS
207 agents · 26 pattern impls · 49 workflows · 139 skills · 53 tool files · 4 bricks · 117 templates
