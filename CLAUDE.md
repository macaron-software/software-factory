# Software Factory — Context

## STRUCTURE

```
_SOFTWARE_FACTORY/     # Agent Platform + Dashboard
  cli/sf.py            # CLI: sf <command> (platform client, SSE streaming)
  cli/_api.py          # httpx REST + SSE streaming client
  cli/_db.py           # SQLite direct (offline mode)
  cli/_output.py       # ANSI tables, colors, JSON output
  cli/_stream.py       # SSE consumer, agent colorizer
  dashboard/           # Lightweight monitoring dashboard (port 8080)
  platform/            # Agent Platform — FastAPI web app
    server.py          # Port 8090 (prod) / 8099 (dev)
    web/routes/        # 10 sub-modules (helpers.py: _parse_body dual JSON/form)
    a2a/               # Agent-to-Agent: bus, negotiation, veto
    agents/            # Loop, executor, store (192 agents)
    patterns/          # 15 orchestration patterns (12 DB + 3 engine-only)
    missions/          # SAFe lifecycle + ProductBacklog
    workflows/         # 36 builtin workflows
    llm/               # Multi-provider client + observability
    tools/             # code, git, deploy, memory, security, browser, infisical, MCP bridge
    ops/               # Auto-heal, chaos, endurance, backup/restore
    services/          # Notification (Slack/Email/Webhook)
    mcps/              # MCP server manager (fetch, memory, playwright)
    modules/           # registry.yaml — 25 optional modules (knowledge + CLI tools)
    deploy/            # Dockerfile + docker-compose (Azure VM)
  mcp_lrm/             # MCP LRM server (port 9500)
  skills/              # Agent YAML definitions + skill .md files
  projects/            # Per-project configs
  data/                # Runtime data (PG uniquement — plus de SQLite)
  tests/               # pytest + Playwright E2E
  scripts/             # Utility scripts (enrich_agents, migrate_env_to_infisical...)
  deploy/              # Helm charts
```

Legacy: `_SOFTWARE_FACTORY-old/` (core/, factory CLI, brain, TDD workers — archived)

## GAME SPRINT v2 (game-sprint workflow — Innovation server)

```
Workflow: game-sprint (is_builtin=0, PostgreSQL)
6 phases: game-inception → env-setup → tdd-sprint (loop) → adversarial-review → feature-e2e → feature-deploy

Agents game (PostgreSQL):
  game-architect (David Rousseau) — tools: code_write, read_file, list_files, create_feature, create_story, create_sprint
  game-dev-lead  (Alex Martin)    — tools: code_read, code_write, code_edit, list_files, run_tests
  game-dev-js    (Sofia Chen)     — tools: code_read, code_write, code_edit, list_files
  game-qa        (Marco Rivera)   — tools: generic
  game-critic    (Jordan Kim)     — tools: read_file, list_files, code_read (adversarial reviewer)
  game-designer  (Emma Larsson)   — tools: code_write, read_file

Tool create_sprint: PlatformCreateSprintTool (platform/tools/platform_tools.py)
  → tool_runner.py dispatch: name=="create_sprint"
  → SprintDef: +type, +quality_score, +team_agents (ALTER TABLE done on PG)

Pac-Man run: epic=pac-epic-c1722e87, last_run=546ddd29 (paused, needs resume)
Old stuck run a9628f7f → cancelled
```

## PROBLÈME ORCHESTRATION — À IMPLÉMENTER (PRIORITÉ HAUTE)

```
CONSTAT: tout ce qui devrait être fait par Jarvis/RTE/PO est fait manuellement.
Le flow cible autonome:
  Brief → [Jarvis] → délègue à [PO] → create_feature/create_story/create_sprint
                   → délègue à [RTE] → launch_epic_run / monitor / resume / escalate
                   → [RTE] surveille phases → re-trigger si paused → rapporte dans Hub

MANQUANT:
  1. Agent "jarvis" — top-level orchestrateur (reçoit brief, délègue PO+RTE)
  2. Tools RTE: launch_epic_run, resume_run, check_run_status (dans platform_tools.py)
  3. Auto-resume watchdog: reset paused→paused au lieu de relancer réellement
  4. PO (product/Laura Vidal) non branché au lancement workflow

AGENTS EXISTANTS MAIS NON CONNECTÉS:
  rte (Marc Delacroix) — Release Train Engineer
  release_train_engineer (Bastien Clément) — RTE
  product (Laura Vidal) — Product Owner
  product-manager-art (Isabelle Renaud) — Product Manager

SPRINT TYPES (sprints.type column, PG):
  inception | infra | tdd | adversarial | qa | deploy
```

## LLM METRICS FIX (commit 0dac8744b)

```
Problème: stream() n'appelait jamais _trace() → metrics page 0 data
Fix 1: LLMStreamChunk +tokens_in +tokens_out; _do_stream() capture data.usage SSE
Fix 2: stream() accumule content+tokens → appelle _trace()+_persist_usage() post-stream
Fix 3: observability.stats() _coerce() Decimal→float (PG AVG retourne NUMERIC)
Résultat: 4540 calls/24h, $7.72/24h visible en metrics
```

## REPOSITORIES (2 dépôts séparés)

```
~/_MACARON-SOFTWARE/                         ← GitHub (macaron-software/software-factory)
  .git/ → origin = github.com/macaron-software/software-factory (AGPL-3.0)
  platform/  cli/  dashboard/  ...           ← CODE TRACKÉ par git
  _SOFTWARE_FACTORY/                         ← ⚠️ NON TRACKÉ (.gitignore) = runtime local
    platform/  dashboard/  data/  logs/      ←   instance de dev en cours (DB, logs, etc.)

~/_LAPOSTE/_SOFTWARE_FACTORY/                ← GitLab La Poste (GITLAB_LAPOSTE_REMOTE dans .env)
  .git/ → origin = <gitlab-laposte>          ← URL SSH chargée depuis .env (non commitée)
  platform/  cli/  dashboard/  ...           ← squelette : agents/workflows/projets VIDES
  Auth: SSH ~/.ssh/gitlab_laposte_ed25519
  README: FR uniquement, branding "Plateforme Agents La Poste", usage interne La Poste
```

**Workflow** : développer dans `~/_MACARON-SOFTWARE/` → `git push origin main` (GitHub).
**Sync La Poste** (one-way) : `cd ~/_MACARON-SOFTWARE && ./sync-to-laposte.sh`
⚠️ Ne jamais éditer `~/_LAPOSTE/_SOFTWARE_FACTORY/` directement — écrasé à chaque sync.

## ENVIRONMENTS (3 deployments)

```
┌────────────────┬─────────────────────────┬──────────────────────────────────┐
│ Environment    │ URL / Access            │ Details                          │
├────────────────┼─────────────────────────┼──────────────────────────────────┤
│ Azure Innov    │ http://52.143.158.19    │ D4as_v5 4CPU/16GB, francecentral │
│ Node 1         │ SSH: sfadmin@52.143.…   │ LLM: azure-openai / gpt-5-mini  │
│                │ ⚠️ SSH bloqué NSG ext.  │ Service: systemd sf-platform     │
│                │ → az vm run-command     │ WorkDir: /home/sfadmin/          │
│                │                         │ Module: platform.server:app      │
│                │                         │ Port: 8090                       │
│                │                         │ OTEL → Jaeger :16686             │
├────────────────┼─────────────────────────┼──────────────────────────────────┤
│ Azure Innov    │ http://40.89.174.75     │ D4as_v5 4CPU/16GB, francecentral │
│ Node 2         │ SSH: sfadmin@40.89.…    │ LLM: azure-openai / gpt-5-mini  │
│                │ ⚠️ SSH bloqué NSG ext.  │ Service: systemd sf-platform     │
│                │ → az vm run-command     │ WorkDir: /home/sfadmin/          │
├────────────────┼─────────────────────────┼──────────────────────────────────┤
│ OVH Demo       │ http://54.36.183.124    │ VPS OVH, Debian                  │
│                │ SSH: debian@54.36.…     │ LLM: minimax / MiniMax-M2.5     │
│                │                         │ Blue-green: platform-blue-1 ou   │
│                │                         │   platform-green-1               │
│                │                         │ Slots: /opt/software-factory/    │
│                │                         │   slots/{blue,green}/            │
│                │                         │ Active: /opt/software-factory/   │
│                │                         │   active-slot                    │
├────────────────┼─────────────────────────┼──────────────────────────────────┤
│ Local Dev      │ http://localhost:8099    │ macOS, Python 3.12               │
│                │ Dashboard: :8080        │ LLM: minimax / MiniMax-M2.5     │
│                │                         │ Module: platform                 │
│                │                         │ DB: PostgreSQL localhost:5432     │
│                │                         │   (DATABASE_URL dans .env)        │
│                │                         │ No Docker, direct uvicorn        │
└────────────────┴─────────────────────────┴──────────────────────────────────┘
```

## DEPLOY

```
Docker: git clone → make setup → make run → http://localhost:8090
Demo:   PLATFORM_LLM_PROVIDER=demo (mock, no key)
```

## RUN

```bash
# Platform CLI
sf status | sf ideation "prompt" | sf missions list | sf projects chat ID "msg"

# Platform dev (NEVER --reload, ALWAYS --ws none)
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning

# Dashboard (local monitoring)
python3 -m dashboard.server  # → http://localhost:8080

# Tests
python3 -m pytest tests/ -v                    # 52 tests
cd platform/tests/e2e && npx playwright test   # 82 tests (9 specs)
```

## LLM

```
Default: PLATFORM_LLM_PROVIDER=minimax  PLATFORM_LLM_MODEL=MiniMax-M2.5
Azure:   PLATFORM_LLM_PROVIDER=azure-openai  PLATFORM_LLM_MODEL=gpt-5-mini
```

Fallback: minimax → azure-openai → azure-ai. Cooldown 90s on 429.
Keys: `~/.config/factory/*.key` — NEVER `*_API_KEY=dummy`
MiniMax: <think> consume tokens (min 16K). GPT-5-mini: NO temperature, max_completion_tokens≥8K.

## AZURE (Innovation Nodes)

```
Node 1:  52.143.158.19 (D4as_v5 4CPU/16GB, francecentral)
Node 2:  40.89.174.75  (D4as_v5 4CPU/16GB, francecentral)
SSH:     sfadmin@<IP> avec ~/.ssh/sf_innovation_ed25519
         ⚠️ NSG bloque SSH depuis externe — utiliser az vm run-command invoke
         Ex: az vm run-command invoke --resource-group RG-SOFTWARE-FACTORY --name sf-node-1 \
                --command-id RunShellScript --scripts "systemctl status sf-platform"
Service: systemd sf-platform.service
         WorkingDirectory=/home/sfadmin
         ExecStart=/home/sfadmin/.venv/bin/python3 -m uvicorn platform.server:app \
           --host 0.0.0.0 --port 8090 --ws none --log-level warning
         User=sfadmin, Restart=always, EnvironmentFile=/etc/sf-platform/secrets
Deploy:  rsync platform/ sfadmin@<IP>:/home/sfadmin/platform/
         ssh sfadmin@<IP> "sudo systemctl restart sf-platform"
PG:      macaron-platform-pg.postgres.database.azure.com — B1ms PG17 32GB, pgvector, pg_trgm
         DB: macaron_platform, user: macaron, SSL required, dual adapter (adapter.py)
LLM:     ascii-ui-openai (francecentral) — gpt-5-mini, 100req/min, 100K tok/min
DR:      L3 full 14/14 — blob GRS (macaronbackups), snapshots, PG PITR 7d
         RPO: PG 24h+PITR 7d, SQLite 24h, VM 7d, secrets 24h, code 0 (git)
         RTO: PG 15min, SQLite 5min, VM 30min
         Cron: daily 3h, weekly dimanche 2h. Runbook: ops/RUNBOOK.md
```

## DEPLOY WORKFLOW

```
OVH:     rsync → blue-green slot swap (slots/blue/ ou slots/green/). Active slot dans active-slot.
         Container restart: docker stop/rm old → docker run new → health check → switch active-slot
Azure:   rsync platform/ sfadmin@<IP>:/home/sfadmin/platform/
         → sudo systemctl restart sf-platform → wait 5s → health check
         ⚠️ Module = platform (NOT macaron_platform)
After:   clear __pycache__ → service restart → wait 15s → health check
Auto-resume: lifespan restarts running missions on service restart.
```

## SECURITY

```
Auth: AuthMiddleware bearer (MACARON_API_KEY), GET public, mutations require token
Headers: HSTS, X-Frame DENY, CSP, X-XSS, Referrer strict
XSS: Jinja2 autoescaping, CSP connect-src 'self'
SQL: parameterized queries (? placeholders, zero f-strings)
Prompt injection: L0+L1 adversarial guards
Docker: non-root 'macaron', minimal image
Secrets: Infisical vault (config.py._load_infisical()) — .env = bootstrap only (INFISICAL_TOKEN)
         Fallback: ~/.config/factory/*.key. NEVER *_API_KEY=dummy
Rate limit: PG-backed per-IP+token, survives restart
```

## SECRETS MANAGEMENT (Infisical)

```
Flow: .env → INFISICAL_TOKEN → vault injects os.environ → platform reads normally
Config: INFISICAL_TOKEN + INFISICAL_SITE_URL + INFISICAL_ENVIRONMENT in .env
Self-host: docker run -p 80:8080 infisical/infisical:latest
Migrate: python3 scripts/migrate_env_to_infisical.py --dry-run
Agent tools: infisical_get_secret, infisical_list_secrets, infisical_set_secret
Skill: skills/secrets-management.md (35 secrets cataloguées par catégorie)
Write ops require agent role: secrets_manager | devops | security | admin
35 secret vars categorisées: llm_providers, infrastructure, integrations,
  notifications, infra_ssh, oauth — reste dans .env: PLATFORM_*, LOG_*, feature flags
```

## MODULES vs INTEGRATIONS

```
Integrations (/settings tab) = services EXTERNES avec clé API (Jira, GitHub, fal.ai...)
  → table integrations en DB, status connected/disconnected, config_json avec token
Modules (/settings tab) = capacités LOCALES optionnelles (CLI tools, bases de connaissance)
  → platform/modules/registry.yaml (25 modules), enabled_ids dans settings table (JSON)

25 modules (registry.yaml):
  ux-design:      component-gallery, mdn-web-docs, can-i-use, wcag-guidelines
  development:    npm-registry, pypi-registry, github-trending
  security:       infisical, cve-nvd, owasp-top10, snyk-vuln
  legal:          spdx-licenses, gdpr-knowledge
  marketing-seo:  lighthouse-patterns, schema-org, og-protocol
  data:           sql-patterns, regex-library
  infra:          redis, docker
  browser:        browser-cli (agent-browser), playwright-mcp
  ai-llm:         prompt-patterns, huggingface-models
  knowledge:      wiki-guidelines
```

## PLATFORM ARCHITECTURE

```
FastAPI + HTMX + Jinja2 + SSE | Dark purple | PostgreSQL uniquement (plus de SQLite)
AgentLoop ←→ MessageBus (per-agent queues) → SSE → Frontend
AgentExecutor → LLM → tool calls → route via bus
Dual SSE: _push_sse() → _sse_queues (runner) + bus._sse_listeners (broadcast)
```

### 192 AGENTS (store.py + skills/definitions/\*.yaml) — 100% enrichis

```
Dev (35+):     brain, lead_dev, dev_backend/frontend, workers, mobile_ios/android
QA (18+):      testeur, test_automation, perf-tester, fixture-gen, mobile_qa
Security (14+): securite, devsecops, pentester-lead, exploit-dev, license-scanner
Product (10+): product_owner, metier, business_owner, ao-compliance
Architecture (7+): architecte, enterprise_architect, adr-writer, iac-engineer
DevOps (8+):   devops, sre, pipeline_engineer, backup-ops, monitoring-ops, canary-deployer, data-migrator
Doc (3):       doc-writer (tech writer lead), changelog-gen, tech_writer
RSE (8+):      rse-dpo, rse-ethique-ia, rse-eco, rse-a11y, rse-audit-social
SAFe (6):      rte, epic_owner, lean_portfolio_manager, solution_train_engineer
```

### 36 WORKFLOWS (builtins.py)

```
Lifecycle:     product-lifecycle (11 phases), feature-sprint (5), feature-request (6)
DSI:           dsi-platform-features (9), dsi-platform-tma (6)
Security:      security-hacking (8), sast-continuous (4)
TMA:           tma-maintenance (4), tma-autoheal (4)
SAFe:          pi-planning (5), epic-decompose (5)
Mobile:        mobile-ios-epic (5), mobile-android-epic (5)
Quality:       documentation-pipeline (6), performance-testing (5), license-compliance (4)
Compliance:    rse-compliance (7), ao-compliance (5)
Ops:           cicd-pipeline (4), monitoring-setup (5), chaos-scheduled (5),
               canary-deployment (5), backup-restore (4)
Data:          data-migration (7), test-data-pipeline (4), i18n-validation (4)
Infra:         iac-pipeline (5)
Other:         tech-debt-reduction (5), review-cycle (2), sf-pipeline (3),
               migration-sharelook (8)
```

### 15 PATTERNS (12 in DB + 3 engine-only)

DB: solo-chat, sequential, parallel, hierarchical, router, aggregator,
human-in-the-loop, adversarial-pair, adversarial-cascade, debate, sf-tdd, wave
Engine-only: solo, loop, network

### ADVERSARIAL (Team of Rivals — arXiv:2601.14351)

```
L0: deterministic (test.skip, @ts-ignore, empty catch) → VETO ABSOLU
L1: LLM semantic (SLOP, hallucination, logic) → VETO ABSOLU
L2: architecture (RBAC, validation, API design) → VETO + ESCALATION
Multi-vendor: Brain=Opus, Worker=MiniMax, Security=GLM, Arch=Opus
Rule: "Code writers cannot declare their own success"
Retry: 5 attempts max → NodeStatus.FAILED
CoVe (arXiv:2309.11495): 4-stage anti-hallucination (Draft→Verify→Answer→Final)
```

### MISSION CONTROL (11 phases)

```
1.Idéation(network) 2.Comité(HITL) 3.Constitution(seq) 4.Archi(aggregator)
5.Sprints(hierarchical) 6.CI/CD(seq) 7.QA(loop) 8.Tests(parallel)
9.Deploy(HITL) 10.TMA Routage(router) 11.Correctif(loop)
Semaphore: 2 concurrent missions. Phase timeout: 600s. Reloop max 2x.
```

### SAFe (~7/10)

WSJF real calc, sprint auto-creation, feature pull PO, velocity tracking.
Gates GO/NOGO/PIVOT. Learning loop + I&A retrospective. Error reloop max 2x.

### PRODUCT MANAGEMENT

```
Hierarchy: Epic(mission) → Feature → UserStory
WSJF: 4 components → CoD/JD auto-compute. Slider UI.
Kanban: SortableJS drag-drop. Sprint planning: assign/unassign stories.
Dependencies: feature_deps table + visual 🔗 badges.
Charts: Chart.js velocity, burndown, cycle time histogram, Gantt.
```

### REST API (dual JSON + form via \_parse_body)

```
POST /api/projects, /api/missions, /api/missions/{id}/start, /api/missions/{id}/run
POST /api/missions/{id}/wsjf, /api/missions/{id}/sprints, /api/missions/{id}/validate
POST /api/epics/{id}/features, /api/features/{id}/stories, /api/features/{id}/deps
PATCH /api/features/{id}, /api/stories/{id}, /api/tasks/{id}/status, /api/backlog/reorder
GET /api/sprints/{id}/available-stories, /api/features/{id}/deps, /api/releases/{pid}
GET /api/metrics/cycle-time, /api/llm/stats, /api/llm/traces, /api/health
GET /api/agents, /api/sessions, /api/mcps, /api/monitoring/live
DELETE /api/features/{id}/deps/{dep}, /api/sprints/{id}/stories/{id}
Swagger: /docs (FastAPI auto-generated)
```

### MCP

```
MCP LRM (port 9500): lrm_locate/read/conventions/task_*/build, confluence, jira
MCP Platform (port 9501): agents/missions/phases/messages/memory/git/code/metrics
MCP Servers: fetch (pip), memory-kg (npx), playwright (npx, Chrome :9222)
Agent tools: mcp_fetch_fetch, mcp_memory_*, mcp_playwright_* in tool_schemas.py
Dispatch: tool_runner.py _tool_mcp_dynamic() → parse mcp_<server>_<tool> → JSON-RPC
```

### MEMORY

4-layer: session → pattern → project → global (FTS5/tsvector)
Wiki `/memory`, confidence bars. Retrospectives → LLM → lessons → global.

### MONITORING

DORA: deploy freq, lead time, CFR, MTTR + velocity + sparklines.
LLM: per-call tracing (provider, model, tokens, cost). Live: `/monitoring` SSE.
OpenTelemetry: opt-in via `OTEL_ENABLED=1`. Exports to Jaeger/OTEL collector via OTLP/HTTP.
  Env vars: `OTEL_ENABLED=1`, `OTEL_SERVICE_NAME=macaron-prod`, `OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317`
  Jaeger UI: http://localhost:16686 (traces, spans, latency).
  Requires: `pip install opentelemetry-api opentelemetry-sdk opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp-proto-http`

### DASHBOARDS

DSI/CTO `/dsi`, Métier `/metier` (SAFe value stream), Portfolio `/`, Board `/projects/{id}/board`
Ideation `/ideation` → 5 agents network debate → "Créer Epic"
Analytics `/analytics` — Chart.js: skills, missions, agents leaderboard, system health

## KEY FILES (all under platform/)

```
server.py, models.py, config.py (+ _load_infisical() vault bootstrap)
llm/client.py, llm/observability.py
a2a/bus.py, a2a/negotiation.py, a2a/veto.py
agents/loop.py, agents/executor.py, agents/store.py, agents/tool_schemas.py
patterns/engine.py, patterns/store.py
missions/store.py, missions/product.py
sessions/store.py, sessions/runner.py
workflows/builtins.py, workflows/store.py
memory/manager.py, memory/vectors.py
db/adapter.py, db/migrations.py, db/schema_pg.sql
tools/tool_runner.py, tools/code_tools.py, tools/mcp_bridge.py
tools/browser_tools.py (agent-browser: 7 tools)
tools/infisical_tools.py (vault: get/list/set secret)
web/routes/{helpers,pages,missions,projects,agents,sessions,patterns,workflows,metrics,settings}.py
ops/auto_heal.py, ops/chaos_endurance.py (+ SCENARIOS_MODULES), ops/run_backup.py
mcps/manager.py
modules/registry.yaml (25 modules)
cli/sf.py, cli/_api.py, cli/_db.py, cli/_output.py, cli/_stream.py
scripts/migrate_env_to_infisical.py
skills/browser-exploration.md, skills/secrets-management.md
```

## DB

## DB

PostgreSQL partout — `DATABASE_URL` obligatoire dans chaque env.
Local: `postgresql://macaron:macaron@localhost:5432/macaron_platform`
OVH: `postgresql://macaron:macaron_pg_ovh_2024@postgres:5432/macaron_platform` (container interne)
Azure: `macaron-platform-pg.postgres.database.azure.com` (PaaS, SSL required)
⚠️ NEVER `*_API_KEY=dummy`. `cli/_db.py` garde une couche SQLite offline-only pour le CLI `sf` (lecture locale).


## CONVENTIONS

- ⛔ ZERO SKIP: NEVER test.skip/@ts-ignore/#[ignore] — FIX > SKIP
- Adversarial 100% LLM (never regex)
- HTMX: readyState check (not DOMContentLoaded). Enum: `_s(val)` helper.
- Process cleanup: start_new_session=True + os.killpg() on timeout

## EXTERNAL TOOLS INTÉGRÉS

| Outil | Statut | Fichier | Notes |
|-------|--------|---------|-------|
| **rtk** (Rust Token Killer) | ✅ intégré | `tools/sandbox.py` | 15 auto-rewrites, 60-90% token savings |
| **agent-browser** (Vercel Labs) | ✅ intégré | `tools/browser_tools.py` | 7 tools, accessibility tree @refs, npm -g |
| **Infisical** (secrets vault) | ✅ intégré | `tools/infisical_tools.py` + `config.py` | MIT, self-hosted, remplace .env |
| **Playwright MCP** | ✅ intégré | `mcps/store.py` + `tool_runner.py` | 3 shortcuts navigate/screenshot/snapshot |

### Playwright dans la SF — 3 rôles

```
1. QA nightly (ops/e2e_scheduler.py) → lance platform/tests/e2e/*.spec.ts à 05h UTC
2. Tool agent (tools/test_tools.py) → playwright_test(spec=), playwright_screenshot(url=)
3. MCP browser (mcps/store.py mcp-playwright) → navigate/snapshot temps réel via MCP
   agent-browser = plus structuré (accessibility tree), playwright MCP = screenshots + DOM
```

### rtk — intégration SF (v0.22.2)

**Statut** : proxy actif dans `platform/tools/sandbox.py` — toutes les commandes des agents passent par `_rtk_wrap()`.
**Seeded en DB** : `integrations` table (id=rtk-compression) via `_ensure_darwin_tables()` → appelée depuis `_migrate_pg()`.

**Commandes auto-rewrites** (15 règles) :
`git/grep/ls/cat/pytest/docker/cargo/go/npm/playwright/curl/gh` → `rtk <cmd>`

**Config** : `RTK_ENABLED=auto` (auto-détecte PATH), `RTK_PATH=/chemin/vers/rtk`. Désactiver: `RTK_ENABLED=false`.
**Install** : `curl -fsSL https://raw.githubusercontent.com/rtk-ai/rtk/refs/heads/master/install.sh | sh`

## SÉCURITÉ — INSPIRATIONS & CHOIX

### SecureByDesign v1.1 (MIT, Abdoulaye Sylla)
Source : https://github.com/Yems221/securebydesign-llmskill

**Ce qu'on a intégré** (concepts, pas le fichier complet — trop lourd en tokens) :
- Tiered enforcement LOW/STANDARD/REGULATED → `skills/security-audit.md` STEP A
- Security theater detection → `skills/security-audit.md` STEP B
- OWASP LLM Top 10 section (SBD-02/SBD-17/SBD-18/SBD-19) → `skills/security-audit.md`
- Scope-of-assurance closing statement → output format de security-audit + qa-adversarial-llm
- SBD-09/SBD-10 conflict resolution (log event, never content) → `tools/monitoring_tools.py`

**Ce qu'on n'a PAS intégré** (et pourquoi) :
- STEP 0 version check : LLM self-fetching = anti-pattern (token cost + injection vector)
- STEP 1 language detection : géré au niveau LLM client, pas dans chaque skill
- Les 25 contrôles complets en system prompt : trop lourd (25 contrôles × tous les agents)
- Exemples de code Argon2/bcrypt en prompt : déjà implémentés dans sast_tools.py

### Adversarial Guard (agents/adversarial.py)
**Couverture** : qualité OUTPUT des agents (slop, hallucination, mock, stack mismatch).
**Swiss Cheese model** (James Reason 1990) : L0 déterministe (0ms) + L1 LLM reviewer.
**L1 pattern** : inspiré de Constitutional AI (Anthropic 2022) — reviewer LLM différent du producteur.
**Inspirations** : Pentagi red-team loops (vxcontrol/pentagi), adversarial collaboration GoodAI.
**Ne couvre PAS** : prompt injection, system prompt leakage, RAG isolation → voir ci-dessous.

### QA Adversarial LLM (skills/qa-adversarial-llm.md)
Red-team offensif du système LLM lui-même (7 suites de tests) :
- Suite 1 : Prompt injection (direct + indirect via RAG/tools)
- Suite 2 : System prompt leakage (8 payloads SBD-17)
- Suite 3 : Jailbreak / role-play bypass
- Suite 4 : RAG cross-user data isolation (LLM08/SBD-18)
- Suite 5 : LLM output → exec injection (LLM05/SBD-19)
- Suite 6 : Token DoS / runaway agent loops (LLM10/SBD-11)
- Suite 7 : Excessive agent agency (LLM06/SBD-06)
- + Tests du guard adversarial.py lui-même (peut-il être bypassé ?)
Sources : OWASP LLM Top 10:2025 + SecureByDesign SBD-02/17/18/19 + Pentagi

### RSSI Team (workflows/definitions/security-hacking.yaml)
Équipe offensive complète : 8 phases (recon → exploit → post-exploit → rapport).
Inspirée de Pentagi (vxcontrol) — mais adaptée au meta-workflow teams/agents/patterns de la SF,
sans LangChain. Les agents utilisent les outils SF natifs (sast_tools, pentest_tools, trivy).


## CHAOS MONKEY (ops/chaos_endurance.py)

```
SCENARIOS_VM1: container_restart, cpu_stress_30s, network_latency_200ms,
               wal_checkpoint_truncate, memory_pressure_85pct, disk_fill_500mb
SCENARIOS_VM2: kill_app, network_partition_30s, disk_fill_200mb
SCENARIOS_MODULES: module_browser_cli, module_redis_down, module_rtk_missing, module_docker_down
  → non-destructif: rename temporaire du binaire → health check → restore (finally)
Loop: 80% infra (VM1×4) + 20% module health. Max 3/day. Interval: 2-6h random.
Trigger manuel: python3 -m platform.ops.chaos_endurance --once [--scenario <name>]
```

## AUDIT COVERAGE (46/46 = 100%)

```
Stabilité:        chaos-scheduled, tma-autoheal, monitoring-setup, canary-deployment ✓
Maintenabilité:   tech-debt-reduction, review-cycle, adversarial cascade ✓
Lisibilité:       documentation-pipeline (API docs, ADR, changelog, onboarding) ✓
Légalité:         rse-compliance (RGPD, AI Act), license-compliance (SBOM), ao-compliance (CCTP/PV recette) ✓
Sécurité:         security-hacking (8 phases), sast-continuous, secrets scan, pentest ✓
Reproductibilité: cicd-pipeline, feature-sprint TDD, iac-pipeline, test-data-pipeline ✓
Déploiement:      canary-deployment (1%→10%→50%→100% + HITL), cicd-pipeline, mobile epics ✓
Documentation:    documentation-pipeline (6 phases: API→ADR→changelog→user→onboarding→review) ✓
Data:             backup-restore (RPO/RTO + DR runbook), data-migration (7 phases + HITL GO/NOGO) ✓
Performance:      performance-testing (k6 load→analysis→fix loop→report) ✓
i18n:             i18n-validation (hardcoded scan, translation check, RTL, format) ✓
Accessibilité:    rse-a11y agent + rse-compliance a11y-audit phase ✓
RSE/Green IT:     rse-compliance (eco + social + ethical AI audit) ✓
SAFe:             pi-planning + epic-decompose (ART, portfolio, WSJF) ✓
```
