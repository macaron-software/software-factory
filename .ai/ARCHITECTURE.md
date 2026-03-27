# Architecture — Software Factory

## STACK
- Python 3.11 + FastAPI + Jinja2 + HTMX + SSE
- PostgreSQL 16 (62 tables, WAL mode)
- Redis 7 (rate limiting)
- Infisical (secrets vault)

## AGENTS: 324
- Roles: dev(35+) · qa(18+) · security(14+) · product(10+) · architect(7+) · devops(8+) · safe(6+) · doc(3)
- 55 tools: code, git, deploy, build, web, sec, mem, mcp, ast, lint, lsp
- Skills: 2389 (YAML + GH cache)

## PATTERNS: 26
- solo · seq · par · hier · loop · network · router · aggregator · wave · hitl
- mr · bb · comp · tournament · escalation · voting · speculative · red-blue · relay · mob
- fractal_qa · fractal_stories · fractal_tests · fractal_worktree · backprop_merge

## DB SCHEMA (62 tbl)
- agents · missions · epic_runs · sprints · features · user_stories · acceptance_criteria
- trace_links · persona · team_fitness · ac_cycles · ac_project_state
- integrations · modules · sessions · phase_outcomes

## ADVERSARIAL
- L0: 25 deterministic checks (0ms)
- L1: LLM semantic review
- VETO if critical dim <60

## AUTH
- JWT+bcrypt · access=15min · refresh=7d
- RBAC: admin · cto · pm · lead_dev · developer · qa · devops · security · viewer · auditor

## INVARIANTS
- `import platform` forbidden (shadows stdlib)
- `--reload` flag forbidden
- `*_API_KEY=dummy` forbidden
- Emoji/gradient/Feather SVG variants forbidden
- Fake/mock data forbidden; LIVE PG only
- `test.skip` / `@ts-ignore` / silent fallback forbidden
- TODO stub / `return {}` / `pass` forbidden
- WebSocket forbidden (SSE only)
- NodeStatus: PENDING · RUNNING · COMPLETED · VETOED · FAILED (no DONE)
- PG advisory lock conn-scoped; dedicated conn per mission
