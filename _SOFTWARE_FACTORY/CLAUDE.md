# SOFTWARE FACTORY - RLM (MIT CSAIL arXiv:2512.24601)

## PHILOSOPHIE: Lean + Agile + KISS + XP

| Principe | Implémentation |
|----------|----------------|
| **Lean** | WIP limits, flow continu, éliminer waste |
| **Agile** | Feedback rapide, adapt, WSJF priorité |
| **KISS** | FRACTAL atomic tasks, minimal code |
| **XP** | TDD first, pair review, refactor continu |

## ⛔ ZERO SKIP POLICY (MANDATORY)

**JAMAIS DE SKIP. NULLE PART. SOUS AUCUN PRÉTEXTE.**

La Factory doit CORRIGER les problèmes, pas les contourner.

### Interdit absolument:
| Interdit | Pourquoi |
|----------|----------|
| `--skip-*` flags | Masque les vrais problèmes |
| `--skip-deploy` | Bypass du pipeline qualité |
| `--skip-chaos` | Évite les tests de résilience |
| `--skip-e2e` | Saute la validation end-to-end |
| `test.skip()` | Tests non exécutés = bugs cachés |
| `@ts-ignore` | Erreurs TypeScript ignorées |
| `#[ignore]` | Tests Rust désactivés |
| Regex "rapide" vs LLM | Analyse superficielle = faux positifs |

### Quand un déploiement échoue:
```
1. NE PAS skipper le check qui échoue
2. ANALYSER la cause racine
3. CRÉER une tâche de fix (feedback loop)
4. LAISSER la Factory corriger via TDD
5. RETENTER le déploiement une fois fixé
```

### Adversarial Reviews:
```
TOUJOURS LLM (MiniMax-M2.1), JAMAIS regex
   ↓
Analyse sémantique complète du code
   ↓
Comprend le contexte (CLI print() = OK, test skip = REJECT)
   ↓
Qualité > Vitesse
```

### Si bloqué:
- La Factory crée automatiquement une tâche de fix
- Le feedback loop s'en charge
- Les workers TDD corrigent le problème
- Le déploiement est retenté automatiquement

**RULE: FIX > SKIP. TOUJOURS.**

### ⚠️ NO MANUAL FIXES - IMPROVE THE FACTORY

**JAMAIS de fix manuel en prod/infra.**

```
❌ WRONG: SSH → fix nginx manually
   → Bypass la Factory
   → Pas d'audit trail
   → Pas reproductible

✅ RIGHT: Factory detects → Factory fixes
   → wiggum_infra diagnose + fix
   → Task créée si échec
   → Pattern appris pour next time
```

**Si la Factory ne sait pas fixer:**
1. Créer une tâche feedback (`factory-infra-*`)
2. Améliorer wiggum_infra.py pour ce pattern
3. Laisser la Factory fixer la prochaine fois

**Exemple pattern appris:**
```
403 Forbidden + localhost:3000 = 200
  → nginx static (try_files) vs SSR (Node.js)
  → Fix: proxy_pass http://localhost:3000
  → wiggum_infra.fix_nginx_403() auto-détecte et corrige
```

## ARCH
```
BRAIN (Opus4.5) + MCP + CoVe → deep recursive → backlog WSJF priorité
    ↓
FRACTAL L1 → 3 concerns // : feature/guards/failures
    ↓
WIP-LIMITED WORKERS → TDD atomic
    ↓
ADVERSARIAL PAIR + CoVe → 2 LLMs débattent qualité (verified)
    ↓
BUILD + QUALITY GATES → coverage 80%+, complexity check
    ↓
INFRA CHECK (wiggum_infra) → docker/nginx/db/sites verified BEFORE E2E
    ↓
DEPLOY CANARY → 1% traffic, metrics watch
    ↓
E2E DIRECT → subprocess.run() PAS LLM (real Playwright)
    ↓
PROMOTE/ROLLBACK AUTO → based on error rate
    ↓
FEEDBACK → errs + metrics → new tasks WSJF recalc
    ↓
XP AGENT → retrospective auto → SELF-MODIFY FACTORY
```

## TEAM OF RIVALS - Multi-Agent Adversarial (arXiv:2601.14351)

**Référence:** "If You Want Coherence, Orchestrate a Team of Rivals: Multi-Agent Models of Organizational Intelligence" - Isotopes AI, Jan 2025

**Concept clé:** La cohérence émerge de forces opposées avec droit de veto. Chaque critic pousse dans une direction différente: un pour la complétude, un pour la praticité, un pour la correction.

### Cascade de Critics (Swiss Cheese Model)

```
Code Changes
    ↓
┌─────────────────────────────────────────────────────────────┐
│ L0: FAST CHECKS (deterministic, 0ms)                        │
│     - test.skip, @ts-ignore, #[ignore]                      │
│     - Empty catch blocks                                    │
│     - Protected files (.md, node_modules)                   │
│     Catch rate: ~25%                                        │
└─────────────────────────────────────────────────────────────┘
    ↓ (si L0 passe)
┌─────────────────────────────────────────────────────────────┐
│ L1a: CODE CRITIC (MiniMax M2.5, ~5s)                        │
│     - Syntax/logic errors                                   │
│     - API misuse (axum extractors, sqlx FromRow)            │
│     - SLOP detection (code qui compile mais ne fait rien)   │
│     Catch rate: ~60%                                        │
└─────────────────────────────────────────────────────────────┘
    ↓ (si L1a passe)
┌─────────────────────────────────────────────────────────────┐
│ L1b: SECURITY CRITIC (GLM-4.7-free, ~10s)                   │
│     - SQL injection, XSS, command injection                 │
│     - Secrets in code (not fixtures)                        │
│     - OWASP Top 10                                          │
│     Catch rate: ~15%                                        │
└─────────────────────────────────────────────────────────────┘
    ↓ (si L1b passe)
┌─────────────────────────────────────────────────────────────┐
│ L2: ARCHITECTURE CRITIC (Claude Opus 4.5, ~20s)             │
│     - RBAC/Auth coverage                                    │
│     - Input validation completeness                         │
│     - Error handling (all error codes)                      │
│     - API design (pagination, rate limit)                   │
│     Catch rate: ~10%                                        │
└─────────────────────────────────────────────────────────────┘
    ↓
✅ APPROVED (ALL critics passed) → 90%+ erreurs interceptées
```

### Multi-Vendor Cognitive Diversity

| Role | LLM | Provider | Raison |
|------|-----|----------|--------|
| **Brain** | Opus 4.5 | Anthropic | Best reasoning |
| **TDD Worker** | MiniMax M2.5 | MiniMax | Fast, cheap |
| **Code Critic** | MiniMax M2.5 | MiniMax | Same perspective as worker |
| **Security Critic** | GLM-4.7-free | Zhipu AI | Different provider = cognitive diversity |
| **Arch Critic** | Opus 4.5 | Anthropic | Architectural reasoning |

**Règle:** "Le même processus de raisonnement qui a produit la réponse initiale ne peut pas l'évaluer de manière fiable." → Multi-vendor obligatoire.

### Veto Hierarchy

```
L0: VETO ABSOLU (deterministic, always correct)
    ↓
L1: VETO ABSOLU (LLM agreed, no override)
    ↓
L2: VETO with ESCALATION (human can override exceptionnellement)
```

**Règle paper:** "Code writers cannot declare their own success. Executors cannot declare success. Only independent critics can approve."

### Métriques (core/metrics.py)

| Métrique | Target | Source Paper |
|----------|--------|--------------|
| L0 catch rate | 25% | 24.9% (paper) |
| L1 catch rate | 75% | 87.8% (Code+Chart) |
| L2 catch rate | 85% | 14.6% supplémentaire |
| Final success | 90%+ | 92.1% (paper) |
| Residual (user reject) | <10% | 7.9% (paper) |

### Config (projects/*.yaml)

```yaml
adversarial:
  cascade_enabled: true
  l0_fast: true           # Deterministic checks
  l1_code: minimax        # Code critic
  l1_security: glm-free   # Security critic (different provider)
  l2_arch: opus           # Architecture critic
  metrics_enabled: true   # Track catch rates
```

## CoVe (Chain-of-Verification) - arxiv:2309.11495

**Anti-hallucination pour Brain/Adversarial/Infra**

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: DRAFT       │ Initial response (peut halluciner)  │
│ STAGE 2: PLAN VERIFY │ Questions à vérifier                │
│ STAGE 3: ANSWER INDEP│ Réponses SANS biais (tools/cmds)    │
│ STAGE 4: FINAL       │ Réponse vérifiée, factuelle         │
└─────────────────────────────────────────────────────────────┘
```

**Brain + CoVe:**
- Draft: génère features depuis VISION.md
- Verify: "Cette feature est-elle dans l'AO?"
- Answer: grep AO_TRACEABILITY.md pour REQ-ID
- Final: features WITH traceability only

**Adversarial + CoVe:**
- Draft: "Ce code est bon"
- Verify: "Y a-t-il des skip/ignore/bypass?"
- Answer: grep file for patterns
- Final: rejet si bypass détecté

**Infra + CoVe:**
- Draft: "Site down, probablement nginx"
- Verify: "Docker running? Nginx config? Port open?"
- Answer: run docker ps, nginx -t, curl
- Final: diagnostic vérifié + fix

## AO TRACEABILITY (MANDATORY)

**RULE: Pas de feature sans AO ref. Sinon = SLOP.**

```
AO Document (Appel d'Offres)
    ↓ REQ-ID (traçabilité)
VISION.md (product roadmap)
    ↓ User Story
Test E2E
    ↓ implements
Code
```

**Config (`projects/*.yaml`):**
```yaml
ao_compliance:
  enabled: true
  refs_file: AO_TRACEABILITY.md

tenants:
  - name: idfm
    ao_ref: "IDFM T6, Annexe 10"
  - name: nantes
    ao_ref: "MOBIA - Véligo - Documentation/02 - Réponse AO Nantes/"
  # NO Lyon - no AO exists = SLOP removed
```

## DEPLOY LLM + CLI (telegram)

```
DEPLOY = MiniMax-M2.1 via opencode + projet CLI tools
├─ ppz:  ppz test native-unit --platform ios|android, ppz deploy staging|prod
├─ psy:  psy git promote-staging|prod, psy test e2e
├─ veligo: veligo build all, veligo deploy staging|prod
├─ fervenza: fervenza ci test-python --check-only
├─ yolonow: yolonow build ios|android

ADVERSARIAL → NEVER skip, all stages gated (build, staging, E2E, prod)
STUCK_DETECT → 0 chars 5min → fallback to GLM-4.7-free → MiniMax-M2
MOBILE → full pipeline: compile → unit tests → E2E journey → run on sim
FEEDBACK → build errors → new tasks auto-created → WSJF recalc

📱 MOBILE E2E PIPELINE (swift/kotlin domains):
1. Compile app for simulator: {cli} build ios|android
2. Run unit tests: {cli} test native-unit --platform ios|android
3. Run E2E journeys: {cli} test e2e
4. Verify on simulator
5. Adversarial review of all stages
→ Mark deployed only if ALL pass
```

## POST-DEPLOY VALIDATION (TMC + Chaos Monkey)

```
PROD DEPLOY → VERIFY HEALTH → TMC BASELINE → CHAOS MONKEY → TMC VERIFY → DEPLOYED
                                    │                │              │
                                    ↓                ↓              ↓
                               Bottleneck?     No recovery?    Degradation?
                                    │                │              │
                               Brain task       ROLLBACK        ROLLBACK
                               (type=perf)    + Brain task    + feedback
```

### TMC (Tests de Montee en Charge)
- **Tool**: k6 (CLI-first, JSON output)
- **Scenarios**: baseline, ramp_10x, spike, soak
- **Metrics**: p50/p95/p99 latency, throughput (rps), error rate
- **Thresholds**: p95 < 500ms, errors < 1%, throughput > 50rps
- **On fail**: Create perf task (NOT rollback — app works, just slow)

### Chaos Monkey
- **Scenarios**: kill_backend, network_latency_200ms, cpu_stress_80pct, memory_pressure, db_connection_kill, disk_pressure
- **Recovery timeout**: 30s max
- **On fail**: AUTO-ROLLBACK + create resilience fix task

### TMC Verify (post-chaos)
- Re-run baseline after chaos
- Compare vs pre-chaos baseline
- **Tolerance**: 15% degradation max
- **On fail**: ROLLBACK (chaos left residual damage)

### Feedback Loop
```
TMC bottleneck → Brain analyse → tâche type=perf → TDD worker optimize → re-deploy → TMC re-test
                                                                                         ↓
                                                                                  Improved? → KEEP
                                                                                  Worse?    → REVERT fix
```

### Config (projects/*.yaml)
```yaml
deploy:
  post_deploy:
    tmc:
      enabled: true
      tool: k6
      thresholds: {p95_latency_ms: 500, error_rate_pct: 1, min_throughput_rps: 50}
      scenarios: [baseline, ramp_10x, spike]
      duration_sec: 120
    chaos:
      enabled: true
      scenarios: [kill_backend, network_latency_200ms, cpu_stress_80pct]
      recovery_timeout_sec: 30
      rollback_on_fail: true
    feedback:
      create_perf_tasks: true
      revert_if_worse: true
      tolerance_pct: 15
```

**Files:** `core/tmc_runner.py`, `core/chaos_runner.py`, stages in `core/wiggum_deploy.py`

## LEAN/XP FEATURES (NEW)

### WIP Limits
```yaml
# projects/*.yaml
wip:
  max_concurrent: 5        # workers actifs max
  max_per_domain: 2        # évite saturation d'un domaine
  queue_priority: wsjf     # WSJF dynamique, pas FIFO
```

### WSJF Dynamique
- Brain calcule WSJF initial
- Recalcul après feedback (erreurs = boost priorité)
- Decay temporel (vieilles tasks montent)

### Adversarial Pair Review
```
LLM1 (impl) → code
LLM2 (review) → critique, trouve failles
LLM1 → fix ou argue
Consensus → merge ou reject
```

### Quality Gates
| Gate | Seuil | Action si fail |
|------|-------|----------------|
| Coverage | 80%+ | Block build |
| Complexity | <15 cyclomatic | Warn, suggest refactor |
| Security | 0 critical | Block deploy |
| Perf | <200ms p95 | Canary rollback |

### Canary Deploy
```
1% traffic → 10% → 50% → 100%
Rollback auto si error_rate > baseline + 5%
Feature flags pour rollback granulaire
```

### Retrospective Auto (XP Agent)
- Analyse weekly: success rate, time-to-deploy, rework %
- Identifie patterns: "Rust .unwrap() = 80% failures"
- Auto-patch adversarial rules
- Propose factory improvements

## MCP ARCHITECTURE (Single Daemon)
```
MCP LRM Server (1 daemon, port 9500)
         ▲ HTTP
    ┌────┼────┐
    │    │    │
 proxy proxy proxy  (stdio, ~10MB each)
    │    │    │
 opencode × 5 workers (OOM safe)
```

**Commandes:**
```bash
factory mcp start/stop/status/restart
```

**Config opencode** (`~/.config/opencode/opencode.json`):
```json
"mcp": {"lrm": {"type": "local", "command": ["python3", ".../mcp_lrm/proxy.py"]}}
```

**Fichiers:** `mcp_lrm/server_sse.py` (daemon), `mcp_lrm/proxy.py` (bridge)

**MCP Tools:**
| Tool | Description |
|------|-------------|
| `lrm_locate` | Find files by pattern/description |
| `lrm_summarize` | Summarize file/directory content |
| `lrm_conventions` | Get project conventions for domain |
| `lrm_examples` | Get code examples from codebase |
| `lrm_build` | Run build/test/lint commands |
| `lrm_context` | **NEW** - RAG context (vision, arch, data_model, api) |

**lrm_context** (ProjectContext RAG via MCP):
```json
{
  "name": "context",
  "inputSchema": {
    "category": "vision|architecture|data_model|api_surface|conventions|state|history|all",
    "max_chars": 8000
  }
}
```

**Usage Brain:** `mcp.call("lrm", "context", {"category": "vision"})` → VISION.md + AO refs

## MCP PLATFORM SERVER (Internal Tools)

```
MCP Platform Server (port 9501, auto-start with platform)
    ↓ HTTP REST + SSE
Agents / CLI / opencode / any MCP client
```

**Auto-start:** lifespan hook in `platform/server.py` → subprocess `platform.mcp_platform.server`
**PID:** `/tmp/factory/mcp-platform.pid`

**Tools:**
| Tool | Source | Description |
|------|--------|-------------|
| `platform_agents` | agents/store | List/get agents (id, name, role, model, skills) |
| `platform_missions` | missions/store | List/get missions + phase statuses |
| `platform_phases` | missions/store | Phase details for a mission |
| `platform_messages` | sessions/store | Agent conversations (from, to, content) |
| `platform_memory` | memory/manager | FTS5 search project/global memory |
| `platform_git` | subprocess | log/status/diff/show/branch on workspace |
| `platform_code` | filesystem | read/search/list files in workspace |
| `platform_metrics` | platform.db | Agent/mission/session/message/memory counts |

**Endpoints:**
- `GET /health` → status + tool count
- `GET /tools` → tool names list
- `POST /tool` → `{"name":"platform_agents","arguments":{}}` → direct REST call
- `GET /sse` → MCP SSE session
- `POST /message?session_id=X` → JSON-RPC MCP messages

**Config opencode:**
```json
"mcp": {"platform": {"type": "local", "command": ["python3", ".../platform/mcp_platform/proxy.py"]}}
```

**Files:** `platform/mcp_platform/server.py` (daemon), `platform/mcp_platform/proxy.py` (stdio bridge)

## GLOBAL BUILD QUEUE (Cross-Project Singleton)

**Problème:** N projets × M tests = CPU/IO saturés (vitest, gradle, pytest //)
**Solution:** Queue globale, 1 job à la fois, tous projets confondus

```
┌─────────────────────────────────────────────────────────────────────┐
│ PROJET PPZ                           PROJET PSY                     │
│                                                                     │
│ wiggum TDD ──┐                      wiggum TDD ──┐                  │
│ wiggum TDD ──┼─→ enqueue(build)     wiggum TDD ──┼─→ enqueue(build) │
│ wiggum TDD ──┘       ↓              wiggum TDD ──┘       ↓          │
│              (20 commits)                       (20 commits)        │
│                      ↓                                   ↓          │
│               enqueue(deploy)                   enqueue(deploy)     │
└──────────────────────┼───────────────────────────────────┼──────────┘
                       ↓                                   ↓
              ┌────────────────────────────────────────────────┐
              │           GLOBAL BUILD QUEUE                   │
              │           (max_jobs=1, SÉQUENTIEL)             │
              │                                                │
              │  [ppz-build] → [psy-build] → [ppz-test] → ...  │
              │                       ↓                        │
              │                 CPU OK ✅                       │
              └────────────────────────────────────────────────┘
```

**Intégration:**
- `cycle_worker._build_domain()` → enqueue() si `build_queue.enabled`
- `build_worker._run_build/tests()` → enqueue() si `build_queue.enabled`
- `wiggum_deploy._stage_build()` → enqueue() si `build_queue.enabled`

**Commandes:**
```bash
factory queue start       # Daemon global (1 seul pour tous projets)
factory queue start -j 2  # 2 jobs // max
factory queue stop
factory queue status      # Jobs pending/running/done
factory queue list        # Contenu queue
factory queue clear       # Vider
```

**Config (`projects/*.yaml`):**
```yaml
build_queue:
  enabled: true           # Use global queue (default: TRUE, auto)
  priority: 10            # WSJF priority (higher = first)
  timeout: 300            # Per-job timeout seconds
```

**Fichiers:** `core/build_queue.py` (singleton+daemon), `data/build_queue.db`

**Comportement FULL AUTO:**
- `enabled: true` par défaut (pas de config nécessaire)
- Daemon auto-start au premier build si non démarré
- Tous les projets utilisent la queue automatiquement
- Pour désactiver: `build_queue.enabled: false` dans le projet

## CYCLE WORKER (PREFERRED over wiggum)

**Pourquoi cycle > wiggum:**
| Mode | Build | CPU | Usage |
|------|-------|-----|-------|
| `wiggum` | 1 par 1 immédiat | Explose CPU | Legacy |
| `cycle` | Batch de N | Optimisé | Recommandé |

```
Phase1 TDD: N workers // écrivent code, PAS DE BUILD
    ↓ batch_size atteint OU timeout
Phase2 BUILD: cargo build/npm build UNE SEULE FOIS
    ↓ si OK
Phase3 DEPLOY: staging→E2E→prod
    ↓ si err
FEEDBACK: new tasks → retour Phase1
```

**Config:** `-w workers -b batch -t timeout`

**Exemple:** `factory ppz cycle start -w 5 -b 20 -t 30`
- 5 workers génèrent code en //
- Build déclenché quand 20 tâches CODE_WRITTEN (ou timeout 30min)
- 1 build pour 20 changements = ~20x moins CPU

## CORE

### Project Context RAG `core/project_context.py`

**"Big Picture" pour Brain** - 10 catégories extraites auto, SQLite+FTS5

```
┌─────────────────────────────────────────────────────────────────────┐
│  PROJECT CONTEXT (Auto-refresh 1h, update post-deploy)             │
├─────────────────────────────────────────────────────────────────────┤
│  1. VISION      │ README, roadmap, features planned                │
│  2. ARCHITECTURE│ Patterns, layers, modules, tech stack            │
│  3. STRUCTURE   │ File tree, extensions, folder conventions        │
│  4. DATA_MODEL  │ Proto, SQL migrations, TypeScript types, Rust    │
│  5. API_SURFACE │ OpenAPI, endpoints, public interfaces            │
│  6. CONVENTIONS │ Style guide par domain (rust/ts/swift/kotlin)    │
│  7. DEPENDENCIES│ Cargo.toml, package.json, libs versions          │
│  8. STATE       │ Tasks pending/failed, errors récents             │
│  9. HISTORY     │ Git commits 30j, hot files (>10 commits)         │
│ 10. DOMAIN      │ Business glossary, entities                      │
└─────────────────────────────────────────────────────────────────────┘
```

**Flow:**
```
Brain.run() → load ProjectContext → refresh if stale (>1h)
    ↓
get_summary(max_chars=12000) → inject in prompt
    ↓
Opus analyse avec FULL context projet
    ↓
Deploy success → ctx.refresh(['state', 'history'])
```

**CLI:**
```bash
# Refresh manuel
python3 -c "from core.project_context import ProjectContext; ProjectContext('ppz').refresh()"

# Query FTS
python3 -c "from core.project_context import ProjectContext; print(ProjectContext('ppz').query('authentication'))"
```

**Storage:** `data/project_context.db` (SQLite + FTS5 pour search)

### Brain `core/brain.py`
- deep recursive ~1500 files ~500K lines
- `--chat "q"` → conversationnel | default → tasks JSON WSJF
- tools: lrm_locate/summarize/conventions/examples/build
- **context**: ProjectContext RAG auto-loaded (12K chars max)
- tiers: Opus→MiniMax→Qwen

**Brain Modes** (`--mode`):
| Mode | Focus |
|------|-------|
| `all` | Complete analysis (default) |
| `vision` | NEW features, roadmap, innovation |
| `fix` | Bugs, build errors, crashes |
| `security` | OWASP, secrets, vulns |
| `perf` | N+1, caching, optimization |
| `refactor` | DRY, patterns, architecture |
| `test` | Coverage gaps, missing tests |
| `migrate` | REST→gRPC, v1→v2, deprecations |
| `debt` | TODOs, FIXMEs, tech debt |
| `missing` | **TDD RED phase**: tests importing non-existent modules |

```bash
factory <p> brain run --mode vision    # features only
factory <p> brain run --mode fix       # bugs only
factory <p> brain run --mode security  # vulns only
factory <p> brain run --mode missing   # TDD: implement missing code
```

### TDD Missing Mode (`--mode missing`)

**TRUE TDD**: Finds tests that import modules that don't exist yet.
Creates IMPLEMENT tasks to write the missing code (WSJF=15, high priority).

```
Test exists → Code doesn't → Create task to IMPLEMENT code
```

**Filters out** (not missing - external):
- Swift system frameworks (Foundation, UIKit, XCTest, Combine, ...)
- Kotlin/Java standard library (java.*, android.*, androidx.*)
- TypeScript node_modules
- Python standard library

**Example output:**
```
Found 5 REAL missing implementations:
  [rust] Implement helpers to satisfy test: crates/mobile-sdk/tests/sync_test.rs
  [kotlin] Implement com.popinz.network.ApiClient to satisfy test: src/test/ApiClientTest.kt
```

### Cycle `core/cycle_worker.py`
- phases: TDD→BUILD→DEPLOY
- no FRACTAL (batch mode, pas subtasks)
- workers // avec lock
- process cleanup on timeout (killpg)

### Wiggum TDD `core/wiggum_tdd.py`
- pool workers daemon
- FRACTAL enabled: 3 concerns (L1) → KISS atomic (L2)
- cycle: lock→FRACTAL?→TDD→adversarial→commit
- LLM: MiniMax M2.5 opencode
- process cleanup: `start_new_session=True` + `os.killpg()` on timeout
- **Skills auto-load**: domain → skills prompt injection

### Skills System `core/skills.py`

**Specialized prompts auto-loaded by domain/task type**

```
skills/
├── smoke_ihm.md   # HTTP 200 + content + 0 console/network errors
├── e2e_api.md     # fetch direct, guards 401/403, failures 400/404/409
├── e2e_ihm.md     # browser tests, workflows complets, multi-users
├── ui.md          # Figma tokens, design system, a11y, data-testid
├── ux.md          # WCAG 2.1 AA, loading/error/empty states, keyboard nav
└── tdd.md         # Red-Green-Refactor, Arrange-Act-Assert, mocking
```

**Auto-mapping domain → skills:**
| Domain | Skills |
|--------|--------|
| `e2e` | e2e_ihm, smoke_ihm |
| `smoke` | smoke_ihm |
| `api_test` | e2e_api, tdd |
| `svelte`/`frontend` | ui, ux, tdd |
| `rust`/`typescript` | tdd |
| `accessibility` | ux |

**Usage in prompt:**
```python
skills_prompt = load_skills_for_task(task.domain, task_type)
# → Injects: Checklist, Template, Anti-patterns (adversarial rejects if violated)
```

**CLI:**
```bash
python3 core/skills.py list                    # Available skills
python3 core/skills.py build e2e smoke_test   # Preview prompt
```

### FRACTAL `core/fractal.py`
```
L1 (depth=0): Split into 3 CONCERNS (SEQUENTIAL execution)
  1. FEATURE: happy path, core business logic (runs FIRST)
  2. GUARDS: auth(401) + permission(403) + validation (builds on feature)
  3. FAILURES: errors(400/404/409) + edge cases (builds on guards)

  Order matters: feature → guards → failures
  Each concern ENRICHES the code written by the previous one

L2 (depth=1): KISS atomic
  ├── IMPL: minimal code
  ├── TEST: focused unit test
  └── VERIFY: run & fix
```

**Thinking activé**: `opencode --variant high` pour extended reasoning

**Streaming + Timeouts** (`core/llm_client.py`):
- MAX_TIMEOUT: 40 min (2400s) - safety net
- PROGRESS_INTERVAL: 60s - log chars produced
- Stream logs: `[STREAM] 120s | +5432 chars | total 12456 chars`
- Kill on stuck: `os.killpg()` process group cleanup
- No fallback on timeout (model working, just slow)

**Config** (`projects/*.yaml`):
```yaml
fractal:
  enabled: true
  force_level1: true  # Always split root tasks
  max_depth: 3
  min_subtasks: 3
```

**Coverage comparison:**
- Standard: 38% (3/8 checks) - LLM focuses on happy path
- FRACTAL:  100% (8/8 checks) - explicit prompts per concern

### Adversarial `core/adversarial.py`

**100% LLM + CoVe - Zero Regex**
```
Code → LLM (MiniMax-M2.1) → CoVe 4-stage → Approve/Reject
```

**CoVe stages:**
1. Draft: "Code looks OK"
2. Verify: "Check for skip/ignore/bypass patterns?"
3. Answer: grep + semantic analysis (independent)
4. Final: verified decision

**Comprend le contexte:**
- `typer.Exit(1)` → CLI normal, PAS un test skip
- `print()` dans CLI → OK
- Secrets dans fixtures/tests → OK
- `NotImplementedError` avec pragma → stub OK

**Config (optionnelle):**
```yaml
adversarial:
  threshold: 5    # Score max avant rejet
  cove_enabled: true  # Chain-of-Verification
```

### Wiggum Infra `core/wiggum_infra.py`

**Infrastructure verification BEFORE E2E (CoVe-based)**

```
┌─────────────────────────────────────────────────────────────┐
│ DIRECT TOOLS (no LLM hallucination)                         │
├─────────────────────────────────────────────────────────────┤
│ check_site(url)  │ curl -sI, check HTTP status             │
│ check_docker()   │ docker ps, verify containers running     │
│ check_nginx()    │ nginx -t, config syntax                  │
│ check_db()       │ SELECT 1, connection test                │
│ ssh_command()    │ Remote verification on server            │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ CoVe DIAGNOSIS                                              │
├─────────────────────────────────────────────────────────────┤
│ 1. Draft: "Site 403, probable nginx"                        │
│ 2. Verify: "Docker up? Config OK? Port bound?"             │
│ 3. Answer: RUN commands, get REAL output                    │
│ 4. Final: Verified diagnosis + fix plan                     │
└─────────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────────┐
│ AUTO-FIX (if fixable) OR create feedback task              │
└─────────────────────────────────────────────────────────────┘
```

**CLI:**
```bash
factory <p> infra check           # Run all checks
factory <p> infra diagnose        # CoVe diagnosis
factory <p> infra fix --auto      # Auto-fix fixable issues
```

### Wiggum Deploy `core/wiggum_deploy.py`

**BUILD + E2E = DIRECT subprocess, NOT LLM**

```python
# BEFORE (broken - LLM changes env → cargo recompiles everything)
await run_opencode("cargo check")  # ❌ 2min+ timeout, fingerprint changes

# AFTER (fixed - preserves cargo cache)
proc = await asyncio.create_subprocess_shell(
    build_cmd,  # cargo check --workspace
    env=dict(os.environ),  # ✅ Same env = same fingerprint = incremental
)
# Result: 54 seconds vs timeout
```

```python
# E2E also DIRECT (real Playwright, not LLM hallucination)
proc = await asyncio.create_subprocess_shell(
    smoke_cmd,  # veligo test smoke
    env={"TEST_ENV": "staging"},
)
returncode = proc.returncode  # ✅ Real exit code
```

**Pipeline (avec INFRA CHECK intégré):**
```
BUILD → ADVERSARIAL
         ↓
    INFRA CHECK ← wiggum_infra.verify_all() + fix_issues()
         ↓
      STAGING
         ↓
    E2E SMOKE (subprocess direct)
         ↓
   E2E JOURNEYS
         ↓
       PROD
```

**INFRA CHECK automatique:**
- Vérifie tous les URLs configurés (tenants staging/prod)
- Auto-fix si possible (nginx 403 → proxy_pass)
- Feedback task si échec → Factory corrige

### TaskStore `core/task_store.py`
- SQLite data/factory.db
- status: pending→locked→tdd_in_progress→code_written→build→commit→deploy

### Daemon `core/daemon.py`
- double-fork, PID /tmp/factory/*.pid
- logs data/logs/

## CLI

```bash
# Brain
factory <p> brain run              # tasks JSON
factory <p> brain --chat "q"       # conversationnel

# Cycle (RECOMMANDÉ - batch build, CPU optimisé)
factory <p> cycle start            # daemon (default: w=5, b=10, t=30)
factory <p> cycle start -f         # foreground
factory <p> cycle start -w 5 -b 20 -t 30  # 10workers, batch20, 30min timeout
# NOTE: --skip-deploy INTERDIT (voir ZERO SKIP POLICY)
factory <p> cycle stop
factory <p> cycle status

# Wiggum (LEGACY - build 1 par 1, explose CPU, ÉVITER)
factory <p> wiggum start -w 5     # À éviter: build immédiat par tâche
factory <p> wiggum stop

# Deploy (legacy, continuous)
factory <p> deploy start/stop

# Build (legacy, continuous)
factory <p> build start/stop

# XP Agent
factory xp analyze --apply
factory xp full -p <proj> --apply

# Tasks Management
factory <p> tasks retry                  # build_failed → code_written (rebuild)
factory <p> tasks retry -t pending       # build_failed → pending (full TDD)
factory <p> tasks retry -s tdd_failed    # retry tdd failures
factory <p> tasks cleanup --dry-run      # preview delete failed

# Meta-Awareness
factory meta status                      # cross-project error stats
factory meta analyze --create-tasks      # create factory tasks for systemic

# Status
factory status --all
```

## PROJECTS

ppz psy veligo yolonow fervenza solaris **factory** (self)

## LLM

- brain: claude CLI Opus4.5
- wiggum/cycle: opencode + MCP proxy
- fallback: MiniMax-M2.5 → MiniMax-M2.1 → GLM-4.7-free
- timeout: 30min max, kills process group (parent + children)

## MONITOR

```bash
tail -f data/logs/cycle-*.log
sqlite3 data/factory.db "SELECT project_id,status,COUNT(*) FROM tasks GROUP BY 1,2"
ps aux | grep opencode | wc -l
```

## LLM FALLBACK LOGIC

```
Rate limit detected → immediate fallback to next model
No timeout → model runs until complete (never cut working response)
```

Fallback chain: MiniMax-M2.5 → MiniMax-M2.1 → GLM-4.7-free

## META-AWARENESS (Cross-Project Learning)

```
BUILD ERROR → record_build_error(project, error)
    ↓
Normalize (rm paths/timestamps) → Hash → Check thresholds
    ↓
50+ occurrences OR 2+ projects same error + infra pattern?
    ↓ YES
CREATE FACTORY TASK (priority=100, project=factory)
```

**Seuils:** 50+ répétitions → SYSTEMIC | 2+ projets → CROSS-PROJECT

**Infra patterns:** `command not found`, `unrecognized subcommand`, `file lock`, `timeout`

**CLI:**
```bash
factory meta status        # stats
factory meta analyze       # voir patterns
factory meta analyze --create-tasks
```

**Files:** `core/meta_awareness.py` ← `cycle_worker._create_build_feedback()`

## SELF-IMPROVEMENT (META)

La Factory s'auto-améliore comme tout autre projet: `factory factory brain run`

### Refactoring Triggers

| Trigger | Seuil | Action |
|---------|-------|--------|
| **Duplication** | >10 lignes, 85% sim | Extract to shared module |
| **Complexity** | cyclomatic >10 | Split function |
| **Long functions** | >100 LOC | Decompose |
| **Too many params** | >5 | Introduce config object |

### Mutualization Candidates

| Pattern | Target Module | Raison |
|---------|---------------|--------|
| `start_new_session`, `os.killpg` | `core/utils/process.py` | Process cleanup |
| `fallback.*chain`, `rate.*limit` | `core/utils/llm.py` | LLM resilience |
| `logging.getLogger`, `RotatingFileHandler` | `core/utils/logging.py` | Logging setup |
| `_run_(tests\|build\|lint)` | `core/utils/subprocess.py` | Subprocess patterns |

### Service Consolidation

| Service | Pattern | Objectif |
|---------|---------|----------|
| TaskStore | Singleton | 1 instance DB par process |
| LLMClient | Singleton + pool | Rate limit global |
| MCPServer | Daemon unique | Pas de spawn multiple |

### Interface Extraction

```
Worker (interface)
├── WiggumTDD
├── CycleWorker
├── BuildWorker
└── DeployWorker

Analyzer (interface)
├── RustAnalyzer
├── TypeScriptAnalyzer
└── PlaywrightAnalyzer
```

### Brain Self-Improvement

```bash
# Analyser la factory elle-même
factory factory brain run

# Focus refactoring
factory factory brain run -q "duplication and consolidation"

# Lancer amélioration
factory factory wiggum start -w 5
```

## CROSS-CUTTING CONCERNS

### Niveau 1: FRACTAL (systematic checks)

| Concern | Check | Applicable si |
|---------|-------|---------------|
| **Security** | OWASP, secrets env, parameterized queries, CSP | toujours |
| **Robustesse** | input validation, null safety, error codes | toujours |
| **Résilience** | retry+backoff, timeout, fallback, idempotence | API, async |
| **i18n** | clés traduites, RTL, formats locaux | UI, user-facing |
| **Accessibilité** | WCAG 2.1 AA, aria-*, contraste, nav clavier | UI |
| **RGPD** | consentement, anonymisation, retention | user data |
| **Multi-devise** | ISO 4217, Decimal, conversion | e-commerce |

### Niveau 2: Brain (context-dependent)

**Frontend (si UI):**
| Concern | Check |
|---------|-------|
| Design System | tokens (no hardcoded), composants, Figma sync |
| Theming | light/dark, CSS vars, multi-brand |
| SEO | meta, sitemap, JSON-LD, canonical |
| PWA | service worker, offline, manifest |
| Performance | bundle <200KB, lazy load, WebP/AVIF |
| Visual QA | Storybook, visual regression tests |

**Backend (si API):**
| Concern | Check |
|---------|-------|
| API Design | REST conventions, versioning, pagination, rate limit |
| Database | migrations, indexing, N+1, connection pool |
| Caching | TTL, invalidation, cache-aside, CDN |
| Async | queues, events, webhooks idempotents |
| Auth | OAuth2/JWT, refresh, RBAC, session |

**Domaines métier (si applicable):**
| Concern | Check | Projet |
|---------|-------|--------|
| Paiements | Stripe, idempotency, PCI-DSS | ppz, yolonow |
| Notifications | email templates, push, unsubscribe | all |
| Search | full-text, fuzzy, facets | veligo, ppz |
| Files | upload, S3, streaming, virus scan | all |
| Multi-tenancy | isolation, context, partitioning | veligo |
| Real-time | WebSocket, SSE, reconnection | psy |

**Ops (si deploy):**
| Concern | Check |
|---------|-------|
| Health checks | liveness/readiness, deep health |
| Graceful shutdown | drain, SIGTERM, cleanup |
| Observabilité | logs JSON, traces OTEL, métriques |
| Audit logs | who/what/when, immutable |
| Cost | resource sizing, query optimization |

**Qualité code:**
| Concern | Check |
|---------|-------|
| Testabilité | DI, mocking, coverage >80% |
| Clean code | SOLID, <200 LOC/fn, cyclomatic <10 |
| Documentation | OpenAPI, changelog, ADRs |
| Backward compat | semver, deprecation warnings |
| Green IT | cache, requêtes optimisées |

**Refactoring (Brain détecte, FRACTAL corrige):**
| Concern | Check | Action |
|---------|-------|--------|
| Duplication | >10 lignes similaires | Extract shared function/module |
| God class | >500 LOC, >10 methods | Split by responsibility |
| Feature envy | Accès fréquent autre classe | Move method |
| Long param list | >5 params | Introduce parameter object |
| Primitive obsession | Strings partout | Value objects |
| Divergent change | 1 fichier, N raisons | SRP split |
| Shotgun surgery | 1 change, N fichiers | Consolidate |
| Dead code | Unused imports/functions | Remove |
| Speculative generality | Abstract sans impl | YAGNI delete |

## CONVENTIONS

- **⛔ ZERO SKIP**: JAMAIS de `--skip-*`, `test.skip()`, `@ts-ignore`, `#[ignore]` - FIX > SKIP
- **Adversarial 100% LLM**: TOUJOURS MiniMax-M2.1, JAMAIS regex - analyse sémantique pure
- **Feedback Loop**: Erreur deploy → créer tâche fix → TDD corrige → retry automatique
- SvelteKit: NEVER create test files with `+` prefix in routes (reserved)
- Tests go in `__tests__/` subfolder (e.g., `routes/admin/__tests__/auth.test.ts`)
- **Cycle > Wiggum**: Toujours utiliser `cycle` pour batch build (wiggum = legacy, explose CPU)
- **Batch size**: 10-20 tâches avant build selon CPU disponible

### Test Types (terminology)

| Type | Description | Example |
|------|-------------|---------|
| **Smoke IHM** | Page load + content + HTTP 200 + 0 console/network errors | `page.goto()` + `expect(h1).toContainText()` + `consoleErrors.length === 0` |
| **E2E API** | Direct API tests (fetch/curl), guards 401/403, failures | `request.get('/api/users')` + status + body validation |
| **E2E IHM** | Browser tests, real clicks, full workflows, multi-user | `page.fill()` + `page.click()` + `test.step()` + `browser.newContext()` |

```
tests/
├── smoke/          # Smoke IHM (pages load correctly)
├── e2e/
│   ├── api/        # E2E API (fetch direct)
│   └── browser/    # E2E IHM (real clicks, workflows)
└── unit/           # Unit tests (vitest/cargo test)
```

## OPENCODE CONFIG (~/.config/opencode/opencode.json)

CRITICAL: Must have `permission: { "doom_loop": "allow" }` to prevent infinite hang in non-interactive mode. Default is "ask" which waits for stdin.

## FILES

```
cli/factory.py
core/brain.py              # Opus orchestrator + CoVe + ProjectContext
core/project_context.py    # RAG "Big Picture" (10 categories)
core/cycle_worker.py       # phases TDD→Build→Deploy
core/wiggum_tdd.py         # FRACTAL enabled + Skills auto-load
core/wiggum_deploy.py      # Deploy + E2E + TMC + Chaos post-deploy
core/tmc_runner.py         # k6 load testing (TMC baseline/verify)
core/chaos_runner.py       # Chaos Monkey (process kill, latency, stress)
core/wiggum_infra.py       # Infra verification + CoVe diagnosis
core/fractal.py            # 3 concerns decomposition
core/adversarial.py        # 100% LLM + CoVe semantic review
core/skills.py             # Skills loader (domain → specialized prompts)
core/task_store.py         # SQLite tasks
core/llm_client.py         # process group cleanup
core/meta_awareness.py     # cross-project error detection
core/daemon.py
skills/*.md                # Skill prompts (smoke_ihm, e2e_api, e2e_ihm, ui, ux, tdd)
mcp_lrm/server_sse.py      # SSE daemon (single instance)
mcp_lrm/proxy.py           # stdio→HTTP bridge
projects/*.yaml            # + ao_compliance, vision_doc: VISION.md
data/factory.db            # tasks
data/project_context.db    # RAG context (FTS5)
data/logs/
```

## BRAIN PHASE CYCLE (MANDATORY ORDER)

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE 1: FEATURES (vision) ──► TDD ──► DEPLOY ──► OK?     │
│           business value first, from VISION.md              │
│                                              │               │
│           ◄── NON (retry) ───────────────────┘               │
│           ▼ OUI (all deployed)                               │
│  PHASE 2: FIXES (bugs/security) ──► TDD ──► DEPLOY ──► OK? │
│           only AFTER features deployed                       │
│                                              │               │
│           ◄── NON (retry) ───────────────────┘               │
│           ▼ OUI (all deployed)                               │
│  PHASE 3: REFACTOR (clean) ──► TDD ──► DEPLOY ──► OK?      │
│           only AFTER fixes deployed                          │
│                                              │               │
│           ◄── NON (retry) ───────────────────┘               │
│           ▼ OUI (all deployed)                               │
│  ─────► LOOP BACK TO PHASE 1                                │
└─────────────────────────────────────────────────────────────┘
```

**RULE: NO REFACTOR UNTIL FIXES DEPLOYED. NO FIXES UNTIL FEATURES DEPLOYED.**

**Config (`projects/*.yaml`):**
```yaml
brain:
  current_phase: features  # features|fixes|refactor
  phase_gate: deployed     # move to next when all current phase deployed
  vision_doc: VISION.md    # MUST be product roadmap, NOT technical doc
```

**Commands:**
```bash
factory <p> brain run --mode vision    # PHASE 1: features from VISION.md
factory <p> brain run --mode fix       # PHASE 2: bugs, security (ONLY if phase1 deployed)
factory <p> brain run --mode refactor  # PHASE 3: clean code (ONLY if phase2 deployed)
```

## WORKFLOW

```bash
# 0. Start MCP server (once)
factory mcp start

# 1. Brain PHASE 1: Features (business value + AO traceability)
factory ppz brain run --mode vision -q "V2 mobile features"
# Brain uses CoVe: Draft → Verify AO refs → Final (no slop)

# 2. Cycle until all FEATURES deployed
factory ppz cycle start -w 5 -b 20 -t 30
# E2E = subprocess DIRECT (real Playwright)

# 3. BEFORE E2E: Infra check (if sites 403/broken)
factory ppz infra check
factory ppz infra diagnose  # CoVe diagnosis
factory ppz infra fix --auto

# 4. When features deployed → PHASE 2: Fixes
factory ppz brain run --mode fix

# 5. Cycle until all FIXES deployed
# (repeat cycle start)

# 6. When fixes deployed → PHASE 3: Refactor
factory ppz brain run --mode refactor

# 7. Monitor
tail -f data/logs/cycle-ppz.log
sqlite3 data/factory.db "SELECT type,status,COUNT(*) FROM tasks WHERE project_id='ppz' GROUP BY type,status"
```

## FIGMA MCP INTEGRATION

### Architecture
```
Figma (SOURCE OF TRUTH)
    ↓ MCP
Brain/Wiggum → proxy_figma.py → Figma Desktop (127.0.0.1:3845)
                              ↘ Figma Remote (mcp.figma.com) [fallback]
```

### Config opencode
```json
"mcp": {
  "figma": {
    "type": "local",
    "command": ["python3", ".../mcp_lrm/proxy_figma.py"]
  }
}
```

### Usage
```bash
# Brain can query Figma specs
factory veligo brain run --mode vision  # Uses Figma MCP for component specs

# Wiggum TDD validates against Figma
# Adversarial rejects if CSS != Figma specs
```

### Figma MCP Tools
- `get_file` - Get file structure
- `get_node` - Get specific node (component, frame)
- `get_styles` - Get design tokens (colors, typography)
- `get_selection` - Get currently selected element (desktop only)

### Workflow
1. Brain analyses Svelte component
2. Calls Figma MCP: "get_node(Button, Size=Medium)"
3. Compares with component CSS
4. If mismatch → generate fix task
5. Adversarial validates Figma compliance before commit

---

## MIGRATION FACTORY (Separate Architecture)

**Location:** `../_MIGRATION_FACTORY/` + `../_FACTORY_CORE/` (shared utils)

**Différence fondamentale SF vs MF:**

| Aspect | Software Factory (TDD) | Migration Factory (Transform) |
|--------|------------------------|-------------------------------|
| **Vision** | VISION.md (features/fixes) | MIGRATION_PLAN.md (before→after) |
| **Workflow** | RED→GREEN→REFACTOR | PRE-VALIDATE→TRANSFORM→COMPARE |
| **Success** | Tests pass, features work | OLD === NEW (bit-à-bit) |
| **Adversarial** | Code quality (SLOP, security) | Behavioral comparison (0% diff) |
| **Workers** | TDD atomic | Transform + golden files |
| **Tolerance** | 80%+ coverage, <15 complexity | 0% API diff, 0% pixel diff, +0 errors |

### Principe ISO 100% (Migration)

```
LEGACY (Angular 16) = RÉFÉRENCE ABSOLUE (read-only)
              ↓
       Migration ISO (0% functional changes)
              ↓
NEW (Angular 17) = LEGACY (comportement identique bit-à-bit)
```

**Règles d'or:**
- ❌ Pas de nouvelles features pendant migration
- ❌ Pas d'améliorations (même "évidentes")
- ❌ Pas de refactoring (même si code sale)
- ✅ Legacy = read-only (aucune modification)
- ✅ Old === New (validated par adversarials stricts)

### Transform Worker Workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PRE-VALIDATE  │ Capture before state                     │
│                  │ - API responses → golden_files/legacy/   │
│                  │ - Screenshots (Playwright)               │
│                  │ - Console logs, test outputs             │
├─────────────────────────────────────────────────────────────┤
│ 2. TRANSFORM     │ Codemod (jscodeshift) OR LLM            │
│                  │ Priority: Codemods > LLM (deterministic) │
├─────────────────────────────────────────────────────────────┤
│ 3. POST-VALIDATE │ Capture after state                      │
│                  │ - API responses → golden_files/migration/│
│                  │ - Screenshots, logs, tests               │
├─────────────────────────────────────────────────────────────┤
│ 4. COMPARE       │ Comparative Adversarial (3 layers)       │
│                  │ - L0: Golden diff (0ms, deterministic)   │
│                  │ - L1: Backward compat (LLM)              │
│                  │ - L2: Breaking changes documented (LLM)  │
│                  │ → REJECT if ANY diff detected            │
├─────────────────────────────────────────────────────────────┤
│ 5. COMMIT/ROLLBACK│ Commit if approved, git reset if not   │
└─────────────────────────────────────────────────────────────┘
```

### Comparative Adversarial (vs SF Adversarial)

| Layer | SF (Code Quality) | MF (Behavioral Comparison) |
|-------|-------------------|----------------------------|
| **L0** | test.skip, @ts-ignore, empty catch | Golden diff: API/screenshots/console (0% tolerance) |
| **L1a** | Code critic (SLOP, syntax) | Backward compat (old clients still work?) |
| **L1b** | Security (OWASP, XSS) | **RLM exhaustiveness (MCP LRM)** ← NEW |
| **L2** | Architecture (RBAC, validation) | Breaking changes documented + rollback strategy |

**L1b RLM Exhaustiveness** (25% catch rate, ~60s):
- Uses MCP LRM to explore legacy + migrated codebases
- Inventories: ALL routes, components, guards, validators, error handlers
- Compares: migrated must have SAME or MORE (no missing functionality)
- Behavioral analysis: Sample endpoints, verify guards/errors identical
- **Deep recursive**: Not just file-level, but semantic completeness

**L0 Golden Diff (deterministic, 0ms):**
```python
# API responses: must be IDENTICAL
diff legacy/api/users.json migration/api/users.json
# Expected: no output (0 diff)

# Screenshots: 0% pixel diff
pixelmatch legacy/screenshots/dashboard.png \
            migration/screenshots/dashboard.png \
            --threshold 0.0
# Expected: 0 pixels different

# Console errors: same count
legacy_errors = count_errors(legacy/console.json)
migration_errors = count_errors(migration/console.json)
assert migration_errors <= legacy_errors  # MUST NOT increase
```

### Codemods (Deterministic Transforms)

**Priority:** Codemods > LLM (reproducibility)

```typescript
// Example: codemods/angular/standalone.ts (jscodeshift)
// NgModule → standalone component

// BEFORE (Angular 16)
@NgModule({
  declarations: [AuthComponent],
  imports: [CommonModule],
})
export class AuthModule {}

// AFTER (Angular 17) - automated by codemod
@Component({
  selector: 'app-auth',
  standalone: true,
  imports: [CommonModule],
})
export class AuthComponent {}
```

**Codemods disponibles:**
- `codemods/angular/standalone.ts` - NgModule → standalone
- `codemods/angular/typed_forms.ts` - FormGroup → FormGroup<T>
- `codemods/angular/control_flow.ts` - *ngIf → @if, *ngFor → @for

### Migration Brain (vs SF Brain)

**Différence:**
- SF Brain: Analyse code pour trouver bugs/features à développer
- Migration Brain: Analyse DELTA (breaking changes, usage patterns, risk)

**Workflow:**
```
MIGRATION_PLAN.md (before/after state)
    ↓
Load breaking changes (framework CHANGELOG)
    ↓
Scan codebase usage patterns (CoVe)
    ↓
Calculate risk scores (HIGH/MEDIUM/LOW)
    ↓
Generate tasks ordered by dependency + risk
    ↓
Tasks → Transform Workers (1 module = 1 task = 1 commit)
```

### Breaking Changes Database

```python
# core/breaking_changes.py
ANGULAR_16_17 = [
    {
        "id": "ANG-17-001",
        "title": "ModuleWithProviders<T> type param required",
        "impact": "MEDIUM",
        "auto_fixable": True,
        "codemod": "codemods/angular/module_providers.ts"
    },
    {
        "id": "ANG-17-002",
        "title": "RouterModule.forRoot → provideRouter",
        "impact": "HIGH",
        "auto_fixable": False,  # Requires manual adaptation
        "migration_guide": "docs/angular/router_migration.md"
    },
    # ... 50+ breaking changes
]
```

### CLI Migration Factory

```bash
cd ../_MIGRATION_FACTORY

# 1. Analyse (génère MIGRATION_PLAN.md + tasks)
python3 cli/migrate.py sharelook analyze

# 2. Exécution par phase
python3 cli/migrate.py sharelook execute --phase deps
python3 cli/migrate.py sharelook execute --phase standalone --workers 3

# 3. Status
python3 cli/migrate.py sharelook status

# 4. Rollback
python3 cli/migrate.py sharelook rollback --phase standalone

# 5. Deploy canary
python3 cli/migrate.py sharelook deploy --canary 1,10,50,100
```

### Config Migration (projects/*.yaml)

```yaml
# _MIGRATION_FACTORY/projects/sharelook.yaml
project_id: sharelook
migration:
  framework: angular
  from_version: "16.2.12"
  to_version: "17.3.0"
  root_path: /Users/sylvain/_LAPOSTE/_SHARELOOK/sharelook-legacy

phases:
  - name: deps
    auto: true
    risk: LOW
    command: "ng update @angular/core@17 @angular/cli@17"

  - name: standalone
    auto: false  # Manual/codemod hybrid
    risk: HIGH
    workers: 3
    codemod: codemods/angular/standalone.ts

  - name: typed-forms
    auto: true
    risk: MEDIUM
    codemod: codemods/angular/typed_forms.ts

adversarial:
  cascade_enabled: true

  l0_golden_diff:
    enabled: true
    tolerance_pct: 0.0  # ZERO tolerance (ISO 100%)

  l1a_backward_compat:
    enabled: true
    model: minimax

  l1b_rlm_exhaustiveness:
    enabled: true
    model: minimax
    mcp:
      server: lrm
      tools: [locate, summarize, context]
    queries:
      - "List ALL API routes with auth guards"
      - "List ALL components with @Input/@Output"
      - "List ALL error handlers (try/catch, catchError)"
      - "List ALL form validators (custom + built-in)"
      - "List ALL guards (CanActivate, CanDeactivate)"
    timeout_sec: 120

  l2_breaking_docs:
    enabled: true
    model: opus

deploy:
  canary:
    enabled: true
    steps: [1, 10, 50, 100]  # % traffic
    auto_rollback: true
    error_threshold_pct: 5  # Rollback if error_rate > baseline + 5%
```

### Skills Migration-Specific

```
../_MIGRATION_FACTORY/skills/
├── breaking_changes.md  # Detection + documentation checklist
├── backward_compat.md   # Testing old API clients
├── golden_files.md      # Snapshot capture + comparison (0% tolerance)
└── codemod_patterns.md  # AST transformations (jscodeshift)
```

### Files Structure

```
../_FACTORY_CORE/              # Shared between SF + MF
├── subprocess_util.py
├── log.py
├── llm_client.py
├── project_context.py
└── daemon.py

../_MIGRATION_FACTORY/
├── core/
│   ├── migration_brain.py           # Analyse delta before→after
│   ├── transform_worker.py          # PRE→TRANSFORM→POST→COMPARE
│   ├── comparative_adversarial.py   # L0+L1a+L1b(RLM)+L2 cascade (✅ créé)
│   ├── migration_state.py           # DB tracking (LEGACY→MIGRATED→VERIFIED) (✅ créé)
│   ├── breaking_changes.py          # Database framework breaking changes
│   └── analyzers/
│       └── angular_analyzer.py      # Scan @NgModule, FormGroup, etc.
├── codemods/
│   └── angular/
│       ├── standalone.ts
│       ├── typed_forms.ts
│       ├── control_flow.ts
│       └── add_migration_marker.ts  # Add MIGRATION comments (✅ créé)
├── skills/
│   ├── breaking_changes.md
│   ├── backward_compat.md
│   ├── golden_files.md
│   └── codemod_patterns.md
├── cli/
│   └── migrate.py
├── projects/
│   └── sharelook.yaml
└── data/
    ├── migration.db
    └── golden_files/
        ├── legacy/
        └── migration/
```

### Success Criteria (Zero Tolerance)

| Criterion | SF Target | MF Target (ISO) |
|-----------|-----------|-----------------|
| API responses | N/A | IDENTICAL (0% diff) |
| Screenshots | N/A | IDENTICAL (0% pixel diff) |
| Console errors | N/A | SAME or FEWER (+0) |
| Tests pass | 80%+ | 100% (same as legacy) |
| Coverage | 80%+ | ≥ legacy (no decrease) |
| Build time | Optimize | ≤ baseline (+0s) |
| Bundle size | Optimize | ≤ baseline (+0KB) |
| Error rate (prod) | <1% | ≤ baseline (+0.0%) |

**Règle:** Toute régression = REJECT + ROLLBACK immédiat

### Migration State Tracking

**Problème:** Migrations incrémentales → besoin de tracer ce qui est migré vs legacy

**Solution multi-layer:**

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1: Git Tags (phase-level)                             │
│   pre-phase-standalone → post-phase-standalone              │
│   → Rollback: git reset --hard pre-phase-standalone         │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2: Code Annotations (file-level)                      │
│   /** MIGRATION: Angular 16 → 17                            │
│    *  Phase: standalone                                     │
│    *  Date: 2026-02-10                                      │
│    *  Task: standalone-auth-001                             │
│    *  Status: MIGRATED ✅ */                                │
│   @Component({ standalone: true, ... })                     │
│   → Codemod: add_migration_marker.ts                        │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3: Database Tracking (migration_state.py)             │
│   SQLite: file_path → LEGACY|IN_PROGRESS|MIGRATED|VERIFIED  │
│   → Query: progress, rollback safety, list unverified       │
└─────────────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4: Feature Flags (runtime detection)                  │
│   STANDALONE_ROUTING: false → hybrid state (legacy + new)   │
│   → Rollback: flip flag to false (instant, no deploy)       │
└─────────────────────────────────────────────────────────────┘
```

**CLI queries:**
```bash
# Progress
migrate sharelook status
# → Progress: 32/50 files migrated (64%)

# File status
migrate sharelook status --file src/app/auth/auth.component.ts
# → Status: MIGRATED ✅, Verified by: adversarial-l1b-rlm-001

# Unverified files
migrate sharelook status --filter in_progress
# → 5 files IN_PROGRESS (not yet verified)

# Rollback safety
migrate sharelook status --rollback-safe
# → ✅ SAFE: All migrated files verified by adversarial
```

**Files:**
- `core/migration_state.py` - Database tracking (SQLite)
- `codemods/angular/add_migration_marker.ts` - Code annotations (jscodeshift)

### Example Migration: Angular 16→17 (Sharelook)

**Projet:** `/Users/sylvain/_LAPOSTE/_SHARELOOK/sharelook-legacy`

**Documentation complète (84KB):**
- `Prompt.md` - Inventaire technique (2 apps, 50 modules, 150 components)
- `Plans.md` - 4 phases, ~30 milestones avec checkboxes
- `Architecture.md` - Principes ISO 100%, contraintes (@cddng libs, flex-layout)
- `Implement.md` - Commandes exactes, exemples before/after
- `Documentation.md` - Templates suivi, décisions, métriques
- `MIGRATION_STATUS.md` - État global

**Config:** `../_MIGRATION_FACTORY/projects/sharelook.yaml`

**Next actions:**
1. Capturer golden files (baseline avant migration)
2. Créer codemods (standalone.ts, typed_forms.ts)
3. Lancer phase deps: `migrate sharelook execute --phase deps`
4. Phase standalone: 50 modules, 3 workers //, comparative adversarial strict
5. Deploy canary: 1% → 10% → 50% → 100% (auto-rollback si erreur)

---

## MACARON AGENT PLATFORM (Web Multi-Agent)

**Location:** `_SOFTWARE_FACTORY/platform/` | **Port:** 8099
**Stack:** FastAPI + HTMX + Jinja2 + SSE + SQLite | Dark purple/indigo theme

### VISION: Real Agentic ≠ Workflow Automation

n8n/LangFlow/Flowise = RPA + LLM wrapper = if/then glorifié = bullshit
Macaron = VRAIE orchestration: autonomie, communication, conflits, mémoire, émergence
Team of Rivals: agents débattent, véto, négocient, délèguent — PAS des boîtes avec flèches

### ARCH

```
Projects (centre) → Agent conversationnel par projet
    ↓
Workflows = collaboration agents (graphe SVG éditable)
    ↓
Patterns = topologies (hiérarchique, débat, adversarial, pipeline, 8 total)
    ↓
Agents = rôles SAFe (48 agents, 5 niveaux Portfolio→Team)
    ↓
Skills = compétences (1200+ GitHub + locales)
    ↓
Memory = 4 layers (session/pattern/project/global, FTS5)
    ↓
MCPs = outils (Figma, GitHub, LRM, etc.)
```

### NAV
Projects → Workflows → Patterns → Agents → Skills → Memory → MCPs | Settings (bas)

### MULTI-AGENT RUNTIME

```
AgentLoop (agents/loop.py) ←→ MessageBus (a2a/bus.py)
    ↓ think                         ↓ route
AgentExecutor (agents/executor.py)  SSE → Frontend
    ↓ LLM call
Azure OpenAI / MiniMax / Foundry (llm/client.py)
```

**AgentLoop** — boucle autonome asyncio.Task par agent:
- inbox (bus) → think (executor+LLM) → parse actions → route via bus → idle
- Actions: `[DELEGATE:id]`, `[VETO:reason]`, `[APPROVE]`, `[ASK:id:q]`, `[ESCALATE]`
- Status: IDLE→THINKING→ACTING→IDLE, 120s think timeout
- AgentLoopManager: singleton, gère tous loops keyed `{session_id}:{agent_id}`

**MessageBus** (a2a/bus.py) — async queues per-agent:
- Topics, SSE bridge (`add_sse_listener`), dead letter, DB persistence
- Protocol: 11 message types (REQUEST/RESPONSE/DELEGATE/VETO/APPROVE/INFORM/NEGOTIATE/ESCALATE/...)
- Priority mapping (VETO=10, REQUEST=5)

**Conflicts:** Negotiation (propose→counter→vote), Veto 3 niveaux (ABSOLUTE/STRONG/ADVISORY)

### DUAL SSE SYSTEM (CRITICAL)

**Deux systèmes SSE coexistent — les deux doivent livrer au frontend:**

```
_push_sse(session_id, dict)          → _sse_queues (runner.py L51)
                                     → AUSSI bus._sse_listeners (broadcast)
bus.publish(A2AMessage)              → bus._sse_listeners (bus.py L143)
                                     → via _notify_sse()
SSE endpoint /sse/session/{id}       → bus.add_sse_listener() (ws.py L38)
                                     → filtre par session_id (dict ou A2AMessage)
```

**`_push_sse()` enrichit dict avec session_id + push aux DEUX systèmes.**
Sans ça: events mission control jamais reçus par frontend (bug fixé).

### PATTERN ENGINE (patterns/engine.py)

**8 patterns implémentés — TOUS avec vrai LLM streaming:**

```
run_pattern(PatternDef, session_id, task) → PatternRun
    ↓
_execute_node(run, node_id, task) → agent LLM call
    ↓ SSE events:
    agent_status(thinking) → stream_start(agent_name) → stream_thinking(heartbeat)
    → stream_delta(chunk) → stream_end(content) → message(final) → agent_status(idle)
```

| Pattern | Impl | Flow |
|---------|------|------|
| `solo` | 1 agent | task → response |
| `sequential` | chain | A→B→C, output forwards |
| `parallel` | concurrent | all agents //, results merged |
| `loop` | iterate | repeat until convergence/max |
| `hierarchical` | tree | leader delegates to subordinates |
| `network` | mesh | brief→analyse→débat rounds→synthèse (judge) |
| `router` | dispatch | classifier routes to specialist |
| `aggregator` | merge | all contribute → last agent synthesizes |
| `human-in-the-loop` | gate | agents analyze → checkpoint GO/NOGO/PIVOT |

**Streaming dans _execute_node:**
- `<think>` blocks filtré (heartbeat every 20 chunks)
- `<tool_call>` artifacts strippé
- VETO/APPROVE détecté dans content
- Tools: code_edit, code_read, code_search, git, deploy, memory

**Adversarial Guard (dans _execute_node):**
```
Agent output → L0 fast (regex slop/mock/hallucination) → L1 semantic (LLM)
    ↓ REJECT?
Retry loop: feedback injection → re-run agent → re-check (max 2 retries)
    ↓ still REJECT after 3 attempts?
NodeStatus.FAILED + rejection prepended to content
```
- L0: slop patterns, mock/stub, hallucination claims, lies, echo, min length
- L1: semantic LLM review (diff model than producer) — only for execution patterns
- Skip L1 for discussion patterns (network, human-in-the-loop)
- Skip TOO_SHORT when agent used code_write/code_edit tools
- Non-blocking phases: FAILED → downgrade to DONE, rebuild LLM summary

**Dev Sprint Protocols (compressed, télégraphique):**
- `_EXEC_PROTOCOL`: "Round 1: list_files. Round 2+: code_write ONLY. 30+ lines per file."
- `_DECOMPOSE_PROTOCOL`: "Split into [SUBTASK 1]...[SUBTASK N]. 1 file = 1 subtask."
- Write-only tool stripping: after round 1 without code_write, remove read-only tools
- Smart fallback: if lead fails to decompose, parse architecture for file paths + distribute

### MISSION CONTROL (Mega-Workflow Lifecycle)

**CDP (Alexandre Moreau) orchestre 11 phases product lifecycle:**

```
GET  /mission-control                    → liste missions
GET  /missions/start/{workflow_id}       → form brief + lancement
POST /api/missions/start                 → crée mission + session + CDP agent
GET  /missions/{id}/control              → dashboard mission control
POST /api/missions/{id}/run              → exécute phases via pattern engine
POST /api/missions/{id}/validate         → GO/NOGO/PIVOT checkpoint
```

**Pipeline 11 phases (product-lifecycle workflow):**

```
1. Idéation (network) — BA+UX+Archi+PM débattent
2. Comité Stratégique (human-in-the-loop) — CPO+CTO+Portfolio+Lean+DSI → GO/NOGO
3. Constitution Projet (sequential) — Scrum+RH+Lead+PO
4. Architecture & Design (aggregator) — Archi+UX+Sécu+DevOps+Lead
5. Sprints Dev (hierarchical) — Lead→Backend+Frontend+QA
6. Pipeline CI/CD (sequential) — DevOps+Lead+Sécu
7. Campagne Tests QA (loop) — QA Lead+QA Engineer
8. Tests Parallèles (parallel) — QA fonc+tech+sécu+lead
9. Deploy Prod (human-in-the-loop) — DevOps+QA+Sécu+CDP → GO/NOGO
10. Routage TMA (router) — Support N1→N2+QA+Lead
11. Correctif TMA (loop) — Dev TMA+QA
```

**Chaque phase = run_pattern() réel:**
- PatternDef construit depuis workflow config (agents + edges)
- Prompt contextuel par phase (`_build_phase_prompt()`)
- Agents LLM streaming: thinking indicator → text delta → final message
- Checkpoints phases 2+9: pause + boutons GO/NOGO/PIVOT

**Template mission_control.html:**
- Timeline pipeline vertical (dots pulse par status)
- Accordion par phase: SVG flow graph (gauche) + discussions agents (droite)
- Streaming: `stream_start` → bubble "réfléchit…" + cursor ▊ → `stream_delta` text
- Sidebar: CDP activity feed + Mémoire + Git graph
- `AGENT_INFO` lookup: résout nom/role/avatar depuis PHASE_AGENTS
- `PHASE_GRAPHS` per-phase: sub-graph extrait du graph global (27 nodes, 34 edges)

**Workflow config** (workflows/store.py L894-1068):
- 11 phases avec pattern_id, agents, config
- Graph global: 27 nodes + 34 edges avec colors + labels
- Phase→agents mapping pour sub-graph extraction

### LIVE IHM — 3 Modes Switchables

```
session_live.html — SSE /sse/session/{id}
├── Thread (📋)     — feed chronologique, color-coded par type, avatars
├── Chat+Panel (💬) — 1:1 gauche + activité inter-agents droite
└── Graph Live (🔮) — SVG animé (nodes pulsent = thinking) + message log
```

**Graph Live (session_live.html):**
- NODE_W=230, NODE_H=110 — full agent cards (avatar, name, role, tagline, skills, status)
- autoLayoutGraph: layers par hierarchy_rank
- renderLiveEdges: pattern-colored (sequential=blue, hierarchical=amber, loop=pink, network=purple)
- renderLiveNodes: avatar clipPath, pulse ring (thinking/acting), skill tags, tool counts
- Pan+Zoom: wheel zoom, mouse drag, fit button, minimap
- Legend: active patterns auto-detected
- Focus mode: click node → dim unconnected

### ROUTES LIVE
```
GET  /sessions/{id}/live              → session_live.html (3 modes)
POST /api/sessions/{id}/agents/start  → démarre AgentLoops (agent_ids=a,b,c)
POST /api/sessions/{id}/agents/stop   → arrête tous loops session
POST /api/sessions/{id}/agents/{aid}/message → user→agent via bus
GET  /sse/session/{id}                → SSE filtered par session_id
```

### STACK COMPLET
```
platform/
├── server.py                    # FastAPI app factory + lifespan
├── models.py                    # Pydantic: A2AMessage, AgentStatus, MessageType, PhaseStatus, MissionStatus
├── llm/client.py                # Multi-provider (Azure/MiniMax/NVIDIA), fallback, streaming
├── a2a/
│   ├── bus.py                   # MessageBus singleton, SSE bridge (add_sse_listener), dead letter
│   ├── protocol.py              # Message types, priority, permissions
│   ├── negotiation.py           # Proposal→counter→vote cycle
│   └── veto.py                  # 3 niveaux, cooldown, override
├── agents/
│   ├── loop.py                  # AgentLoop autonome + AgentLoopManager
│   ├── executor.py              # LLM + 8 rounds tool calling + _tool_run_phase
│   └── store.py                 # SQLite CRUD + YAML seed (48 agents)
├── patterns/
│   ├── engine.py                # run_pattern() + _execute_node() streaming + 8 pattern impls
│   └── store.py                 # PatternDef, PatternRun, NodeState, NodeStatus
├── missions/
│   ├── store.py                 # MissionRunStore CRUD (~L407), MissionRun, PhaseRun
│   └── product.py               # Product lifecycle config
├── sessions/
│   ├── store.py                 # SessionDef + MessageDef
│   └── runner.py                # _push_sse() dual SSE (queues + bus), context builder
├── memory/manager.py            # 4 layers, FTS5 search
├── workflows/store.py           # WorkflowDef + product-lifecycle (27 nodes, 34 edges, 11 phases)
├── skills/
│   ├── library.py               # Scan local + GitHub (1200+ skills)
│   └── definitions/*.yaml       # 42 YAML agents SAFe
├── tools/                       # code_tools, git_tools, deploy_tools, memory_tools, phase_tools, etc.
├── web/
│   ├── routes.py                # Toutes routes (~5100 lignes)
│   ├── ws.py                    # SSE endpoints (bus.add_sse_listener, dict+A2AMessage filter)
│   └── templates/
│       ├── base.html            # Layout + sidebar nav
│       ├── mission_control.html # CDP mega-workflow dashboard (accordion+streaming+SVG graphs)
│       ├── mission_control_list.html # Liste missions
│       ├── mission_start.html   # Form lancement mission
│       ├── session_live.html    # 3-mode live view (Thread/Chat/Graph) pan+zoom
│       ├── conversation.html    # Session classique + bouton "Go Live"
│       ├── workflow_edit.html   # Éditeur SVG graphe d'agents
│       ├── ideation.html        # 5-agent network ideation
│       ├── dsi.html             # Dashboard DSI/CTO
│       ├── metier.html          # Dashboard Métier
│       ├── portfolio.html       # Vue portefeuille
│       ├── project_board.html   # Kanban 4 colonnes
│       ├── skills.html          # 50/page, search, filtres source
│       └── memory.html          # Wiki-like, FTS5
└── data/
    ├── platform.db              # SQLite (rm pour re-seed, 48 agents + 4 workflows)
    └── github_skills/           # Cache 1156 skills .md
```

### WORKFLOWS BUILTIN

**Product Lifecycle** (id=`product-lifecycle`):
```
11 phases, 27 agents, 34 edges
CDP Alexandre Moreau orchestre séquentiellement
Patterns: network → human-in-the-loop → sequential → aggregator → hierarchical
          → sequential → loop → parallel → human-in-the-loop → router → loop
```

**Migration Sharelook Angular 16→17** (id=`migration-sharelook`):
```
7 agents, 4 phases, 10 edges
Hierarchical + Network hybride
CDP Migration → Lead Dev → Dev Pilot + Dev Main + QA + Security + DevOps
```

### DB PATH
⚠️ `data/platform.db` (à la racine _SOFTWARE_FACTORY), PAS `platform/data/platform.db`
- Config: `platform/config.py` → `FACTORY_ROOT = PLATFORM_ROOT.parent` → `DB_PATH = FACTORY_ROOT / "data" / "platform.db"`
- Seed: `rm -f data/platform.db` pour re-seed (48 agents + 4 workflows)

### CONVENTIONS
- Pas de `--reload` (conflit module `platform` stdlib)
- `--ws none` obligatoire (websocket issue)
- `start_new_session=True` pour process persistant (survit shell close)
- Skills GitHub: git clone shallow (pas API rate-limited)
- Theme: CSS vars `--bg-primary:#0f0d1a` `--purple:#7c3aed`
- Views: 4 modes display (card/compact/list/list-compact)
- SSE: `_push_sse()` → dual delivery (queues + bus), `bus.add_sse_listener()` → filter session_id, keepalive 30s
- `_agent_map_for_template(agents)` → returns dicts (access `a["name"]` NOT `a.name`)
- `MissionRunStore.update()` persists session_id (was bug, fixed)
- `SessionStore.get_messages()` (NOT `list_messages`)

### START
```bash
cd _SOFTWARE_FACTORY
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning
```

### ⚠️ CRITICAL RULES — DO NOT BREAK
1. **NEVER `rm -f data/platform.db`** — The DB is persistent. It contains user missions, sessions, messages, memory. Deleting it destroys all user work. `init_db()` handles migrations idempotently (CREATE IF NOT EXISTS + ALTER TABLE safe).
2. **NEVER set `MINIMAX_API_KEY=dummy`** (or any `*_API_KEY=dummy`) — API keys are loaded from `~/.config/factory/*.key` files automatically. Setting dummy env vars overrides real keys and breaks all LLM calls. Just start the server without any env var overrides.

### DASHBOARD VIEWS (4 profiles)

| Vue | Route | Contenu |
|-----|-------|---------|
| **DSI/CTO** | `/dsi` | Comité stratégique IA, carte systèmes/patterns, intelligence score, métriques |
| **Métier** | `/metier` | Flux processus métier par département, productivité agents, calendrier activité |
| **Portefeuille** | `/` | Projets sidebar, graph stratégique, épics progression table, Gantt milestones |
| **Projet Board** | `/projects/{id}/board` | Kanban 4 colonnes, backlog/PRs, flux agents projet |

Tabs conditionnels: DSI=décisions/metrics, Métier=flux/KPI, Dev=agents/skills/MCP

### IDEATION FLOW

```
/ideation → saisie idée → LLM meeting-style → Brief → Analyse → Synthèse
```

- 5 agents: Camille (BA), Pierre (Archi), Chloé (UX), Nadia (Sécu), Alexandre (PM)
- Uses run_pattern(network) → real LLM streaming with debate rounds
- @mentions + roles + direction (→ @Pierre)
- Graph SVG: edges light up FROM speaker TO target
- Phase headers: 📋 Brief → 🔍 Analyse → 📊 Synthèse
- Persistence: sessions+messages+findings SQLite, sidebar historique
- "Créer Epic" → PO prend le relai, crée projet+git

### MEMORY & RETROSPECTIVES

```
Memory 4-layer: session → pattern → project → global (FTS5)
```

- `/memory` wiki-like: categories (architecture, vision, team, process, backlog)
- Confidence bars + occurrence counts + category badges
- Auto-population: epic creation → stack/vision/team/features stored
- Retrospectives: POST `/api/retrospectives/generate` → LLM analyze → lessons → memory_global
- Recursive self-improvement: lessons feed back into global memory

### DB MIGRATIONS
- `platform/db/migrations.py` — ALTER TABLE safe (PRAGMA table_info check)
- Colonnes ajoutées: agents(avatar,tagline,motivation), ideation_messages(role,target)

### BUGS CONNUS FIXÉS
- `_push_sse()` ne livrait PAS au SSE endpoint → ajout broadcast bus._sse_listeners
- `MissionRunStore.update()` perdait session_id → ajouté dans UPDATE SQL
- `list_messages` n'existe pas → c'est `get_messages`
- `PatternDef` dans `patterns/store.py` (PAS `patterns/models.py`)
- Mission phases utilisaient mock templates → remplacé par vrai `run_pattern()`
