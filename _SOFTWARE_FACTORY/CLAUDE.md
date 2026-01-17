# SOFTWARE FACTORY - RLM (MIT CSAIL arXiv:2512.24601)

## PHILOSOPHIE: Lean + Agile + KISS + XP

| Principe | Implémentation |
|----------|----------------|
| **Lean** | WIP limits, flow continu, éliminer waste |
| **Agile** | Feedback rapide, adapt, WSJF priorité |
| **KISS** | FRACTAL atomic tasks, minimal code |
| **XP** | TDD first, pair review, refactor continu |

## ARCH
```
BRAIN (Opus4.5) + MCP → deep recursive → backlog WSJF priorité
    ↓
FRACTAL L1 → 3 concerns // : feature/guards/failures
    ↓
WIP-LIMITED WORKERS → TDD atomic
    ↓
ADVERSARIAL PAIR → 2 LLMs débattent qualité
    ↓
BUILD + QUALITY GATES → coverage 80%+, complexity check
    ↓
DEPLOY CANARY → 1% traffic, metrics watch
    ↓
PROMOTE/ROLLBACK AUTO → based on error rate
    ↓
FEEDBACK → errs + metrics → new tasks WSJF recalc
    ↓
XP AGENT → retrospective auto → SELF-MODIFY FACTORY
```

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
 opencode × 50 workers
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

## CYCLE WORKER (NEW)
```
Phase1 TDD: N workers // écrivent code, pas build
    ↓ batch_size atteint ou timeout
Phase2 BUILD: compile tout CODE_WRITTEN
    ↓ si OK
Phase3 DEPLOY: staging→E2E→prod
    ↓ si err
FEEDBACK: new tasks → retour Phase1
```

Config: `-w workers -b batch -t timeout --skip-deploy`

## CORE

### Brain `core/brain.py`
- deep recursive ~1500 files ~500K lines
- `--chat "q"` → conversationnel | default → tasks JSON WSJF
- tools: lrm_locate/summarize/conventions/examples/build
- tiers: Opus→MiniMax→Qwen

### Cycle `core/cycle_worker.py`
- phases: TDD→BUILD→DEPLOY
- no FRACTAL (batch mode, pas subtasks)
- workers // avec lock
- process cleanup on timeout (killpg)

### Wiggum TDD `core/wiggum_tdd.py`
- pool workers daemon
- FRACTAL enabled: 3 concerns (L1) → KISS atomic (L2)
- cycle: lock→FRACTAL?→TDD→adversarial→commit
- LLM: MiniMax M2.1 opencode
- process cleanup: `start_new_session=True` + `os.killpg()` on timeout

### FRACTAL `core/fractal.py`
```
L1 (depth=0): Split into 3 CONCERNS
  ├── FEATURE: happy path, core business logic
  ├── GUARDS: auth(401) + permission(403) + validation + sanitization
  └── FAILURES: errors(400/404/409) + edge cases + LIMIT + logging

L2 (depth=1): KISS atomic
  ├── IMPL: minimal code
  ├── TEST: focused unit test
  └── VERIFY: run & fix
```

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
- reject: test.skip, @ts-ignore, TODO>2, .unwrap()>3
- score>=5 → REJECT → retry max10

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

# Cycle (NEW - phases TDD→Build→Deploy)
factory <p> cycle start            # daemon
factory <p> cycle start -f         # foreground
factory <p> cycle start -w 5 -b 10 -t 30  # 5workers, batch10, 30min
factory <p> cycle start --skip-deploy     # dev mode
factory <p> cycle stop
factory <p> cycle status

# Wiggum (legacy, continuous)
factory <p> wiggum start -w 10
factory <p> wiggum stop

# Deploy (legacy, continuous)
factory <p> deploy start/stop

# Build (legacy, continuous)
factory <p> build start/stop

# XP Agent
factory xp analyze --apply
factory xp full -p <proj> --apply

# Status
factory status --all
```

## PROJECTS

ppz psy veligo yolonow fervenza solaris **factory** (self)

## LLM

- brain: claude CLI Opus4.5
- wiggum/cycle: opencode + MCP proxy
- fallback: MiniMax-M2.1 → GLM-4.7-free → MiniMax-M2
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

Fallback chain: MiniMax-M2.1 → GLM-4.7-free → MiniMax-M2

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

- SvelteKit: NEVER create test files with `+` prefix in routes (reserved)
- Tests go in `__tests__/` subfolder (e.g., `routes/admin/__tests__/auth.test.ts`)
- Adversarial uses LLM (not regex) for context-aware validation

## OPENCODE CONFIG (~/.config/opencode/opencode.json)

CRITICAL: Must have `permission: { "doom_loop": "allow" }` to prevent infinite hang in non-interactive mode. Default is "ask" which waits for stdin.

## FILES

```
cli/factory.py
core/cycle_worker.py   # phases TDD→Build→Deploy
core/brain.py
core/wiggum_tdd.py     # FRACTAL enabled
core/fractal.py        # 3 concerns decomposition
core/adversarial.py
core/task_store.py
core/llm_client.py     # process group cleanup
core/daemon.py
mcp_lrm/server_sse.py  # SSE daemon (single instance)
mcp_lrm/proxy.py       # stdio→HTTP bridge
projects/*.yaml
data/factory.db
data/logs/
```

## WORKFLOW

```bash
# 0. Start MCP server (once)
factory mcp start

# 1. Brain analyse
factory psy brain run -q "focus"

# 2. Cycle (phases TDD→Build→Deploy)
factory psy cycle start -w 5 -b 10 -t 60

# 3. Monitor
tail -f data/logs/cycle-psy.log
curl localhost:9500/health  # MCP connections

# 4. XP improve
factory xp full -p psy --apply
```
