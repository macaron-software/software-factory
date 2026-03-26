# Copilot Instructions — Software Factory

## Project
SAFe multi-agent orch platform. 324 agents · 26 patterns · 69 wf · 32 tpl · 55 tools.
Platform: macaron-software/software-factory (AGPL-3.0)
Port: dev :8099 · prod :8090 · baby :8093.
Native: sf-macos (Rust/AppKit, SQLite local, SSE remote).

## Stack
- Python 3.11 · FastAPI · Jinja2 · HTMX · SSE
- PostgreSQL 16 (62 tbl WAL) · Redis 7 · Infisical vault
- LLM: MiniMax M2.7 (93%) · Mistral devstral (87%) · azure-openai · local-mlx · ollama · opencode

## Architecture
```
platform/ (375py 148KLOC)
  server.py          lifespan · GZipMiddleware · auth mw · 8 bg tasks
  agents/            exec · store(324) · adversarial(L0+L1+L2) · tool_runner(134)
  patterns/          engine(26 topo) · fractal_{qa,stories,tests,worktree}
  workflows/         store(32-tpl) · definitions/(69 YAML)
  services/          epic_orch · auto_resume · pm_checkpoint · notif
  llm/               client(6 prov) · context tiers L0/L1/L2 · observability
  db/                adapter(PG) · schema(62tbl) · migrations
  tools/             55 tools: code·git·deploy·build·web·sec·mem·mcp·ast·lint·lsp
  auth/              JWT+bcrypt · RBAC mw · OAuth(GH/Azure)
  a2a/               bus · veto · jarvis_mcp · azure_bridge
  web/routes/        missions · wf · auth · tpl(124)
skills/              2389 (139 YAML) — Thompson Sampling Beta(a=wins, b=losses)
projects/            per-proj config + git_url
```

DB: `postgresql://macaron:macaron@localhost:5432/macaron_platform`
PG advisory locks conn-scoped → dedicated conn/mission

## Commands
```sh
uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
ruff check platform/ --select E9
pytest tests/ -v
psql: PGPASSWORD=macaron /opt/homebrew/bin/psql -h localhost -U macaron -d macaron_platform
```

## LLM Providers (6) — Fallback Chain
```
1. minimax/MiniMax-M2.7      93% TC-15 · free · primary
2. mistral/devstral-latest   87% TC-15 · free experiment · fallback #1
3. azure-openai/gpt-5-mini   paid · fallback #2
4. local-mlx/Qwen3.5-35B     local Mac
5. ollama/qwen3:14b           local
6. opencode                   self-hosted Go
```
- MiniMax: no temp · strip `<think>` · parallel_tool_calls=False
- Mistral: tool_call_id sanitized → 9-char alphanumeric hash (no underscores)
- GPT-5.x: max_completion_tokens · reasoning budget>=16K
- Timeouts: connect=30s read=300s stream=600s idle=120s

## Invariants
- `import platform` forbidden → use `from platform.X import Y`
- `--reload` banned · `*_API_KEY=dummy` banned
- SSE only (`--ws none`) · no WebSocket
- No emoji/gradient/inline/hardcoded hex · Feather SVG only
- No fake/mock data · LIVE PG only
- No test.skip · `@ts-ignore` · silent fallback
- No TODO stub · `return {}` · `pass`
- NodeStatus: PENDING · RUNNING · COMPLETED · VETOED · FAILED (no DONE)
- PG advisory lock conn-scoped · dedicated conn per mission

## Quality Gates (17)
HARD: guardrails · veto · prompt_inject · tool_acl · adv-L0(25-det) · AC-reward · RBAC · CI
SOFT: adv-L1(LLM) · L2-visual(Playwright screenshots) · convergence · complexity

## Adversarial (Swiss Cheese)
L0: deterministic (25 rules, 0ms) → VETO ABSOLU
L1: LLM semantic (SLOP, hallucination, logic) → VETO ABSOLU
L2: visual screenshot eval (Playwright, UI phases only, non-blocking)
"Code writers cannot declare their own success"

## Harness Patterns (Anthropic 2026)
- context_reset: true → clean context per phase (prevents context anxiety)
- max_iterations auto-boost 5→12 for design/UI phases
- Sprint contract negotiation (adversarial-pair) before TDD
- compare_models() for upgrade/rollback decisions

## ToolCall-15 Bench
- 15 scenarios · 5 categories · deterministic scoring · per-provider
- API: /api/toolcall-bench/{list,run,job,key}
- Watchdog: daily auto-bench + regression alerts

## Key Decisions
| Decision | Rationale |
|----------|-----------|
| HTMX over SPA | SSE + Jinja2, no React/Vue bundling |
| PostgreSQL only | SQLite deprecated, advisory locks per mission |
| Feather SVG | no emoji, no FontAwesome |
| JWT+bcrypt auth | 15min access, 7d refresh, rate 5/min/IP |
| Infisical vault | .env = bootstrap only |
| Thompson Sampling | skill selection Beta per skill |
| Darwin GA | team fitness evolution nightly |
| MiniMax primary | 93% TC-15, free, fast |
| Mistral fallback | 87% TC-15, free experiment, tool_call_id quirk handled |

## Deployments
```
OVH Demo  :8090  MiniMax-M2.7 → Mistral devstral  blue-green Docker
OVH Baby  :8093  MiniMax-M2.7 → Mistral devstral  simple mode
Local dev :8099  local-mlx or minimax              direct uvicorn
sf-macos  native Ollama local or SSE remote        Rust/AppKit
```
