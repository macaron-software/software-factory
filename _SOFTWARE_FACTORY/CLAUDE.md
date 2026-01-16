# SOFTWARE FACTORY - RLM (MIT CSAIL arXiv:2512.24601)

## ARCH
```
BRAIN (Opus4.5 RLM) → deep recursive → backlog enrichi
    ↓ llm_query() → MiniMax sub-agents
WIGGUM TDD (MiniMax×N) → FRACTAL L1 forced → 3 sub-agents // → commit
    ↓
WIGGUM DEPLOY → staging → E2E → prod → rollback
    ↓
FEEDBACK → errs → new tasks
    ↓
XP AGENT → learn → SELF-MODIFY FACTORY
```

## CORE

### Brain RLM (`core/brain.py`)
**Deep Recursive Analysis Engine** per MIT CSAIL arXiv:2512.24601:

**COST TIERS** (like GPT-5 → GPT-5-mini in paper):
- depth=0: **Opus 4.5** ($$$) - Strategic orchestration
- depth=1-2: **MiniMax M2.1** ($$) via opencode + MCP tools
- depth=3: **Qwen 30B local** (free) - Fallback

5-phase analysis:
1. Structure decomposition (project→modules→files)
2. Deep recursive llm_query() per module
3. Parallel llm_query_batched() for files
4. Cross-cutting (security, perf, arch, testing)
5. Synthesis → WSJF scored backlog

### Wiggum TDD (`core/wiggum_tdd.py`)
- pool workers // (daemon)
- **FRACTAL L1 FORCED**: ALL depth=0 tasks → 3 sub-agents //
  - impl (core logic), test (validation), integ (edge cases)
  - `asyncio.gather()` parallel execution
  - parent DONE ssi ALL sub-agents succeed
- cycle: lock → TDD (test fail→code→pass) → adversarial → commit
- LLM: MiniMax M2.1 `opencode`

### FRACTAL (`core/fractal.py`)
```yaml
fractal:
  force_level1: true      # FORCED for depth=0
  min_subtasks: 3         # 3 parallel sub-agents
  parallel_subagents: true
  max_depth: 3
  max_files: 5
  max_loc: 400
```

### Wiggum Deploy (`core/wiggum_deploy.py`)
- pipeline: build→staging→E2E→prod→verify
- rollback auto
- feedback tasks on err

### Adversarial (`core/adversarial.py`)
- reject: test.skip, @ts-ignore, TODO>2, .unwrap()>3, panic!
- score>=5 → REJECT → retry (max 10)
- deep: Qwen semantic (SLOP, BYPASS, SECURITY)
- **XP-learned patterns**: auto-injected from factory failures

### XP Agent (`core/experience_agent.py`)
Meta-brain that **SELF-MODIFIES THE FACTORY**:
- learning memory: `learnings` table
- pattern evolution: `pattern_evolutions` table
- ROI tracking (GenAI Divide: 5% success)
- **chaos**: resilience tests (retry, circuit breaker, timeout)
- **security**: CVE fetch NVD, OWASP Top10, pentest staging/prod
- **journeys**: Playwright E2E w/ RBAC personas, real data
- **logs**: prod log analysis → backlog tasks
- **improve**: patches adversarial.py, fractal.py, brain prompts

### TaskStore (`core/task_store.py`)
- SQLite `data/factory.db`
- semantic+zlib: 53% reduction
- status: pending→tdd_in_progress→tdd_success→queued_for_deploy→completed

### Daemon (`core/daemon.py`)
- double-fork Unix
- PID `/tmp/factory/wiggum-tdd-<proj>.pid`
- logs rotatifs `data/logs/`
- SIGTERM graceful

## CLI

```bash
# Brain (Deep Recursive RLM with cost tiers)
factory <p> brain run              # full RLM 5-phase (Opus→MiniMax→Qwen)
factory <p> brain run --quick      # reduced depth
factory <p> brain run -q "iOS security"  # focus

# Wiggum TDD (FRACTAL L1 forced)
factory <p> wiggum start           # daemon bg
factory <p> wiggum start -w 10     # 10 workers
factory <p> wiggum start -f        # fg debug
factory <p> wiggum stop
factory <p> wiggum restart
factory <p> wiggum status
factory <p> wiggum once            # 1 task → 3 sub-agents

# Deploy
factory <p> deploy start/stop/status/once

# XP Agent (Self-Modifying Factory)
factory xp analyze                 # no LLM
factory xp analyze --apply         # +auto-fix
factory xp report                  # Opus report
factory xp fix                     # reset stuck
factory xp impact                  # ROI metrics
factory xp learn                   # full cycle
factory xp chaos -p ppz            # resilience tests
factory xp security -p ppz         # CVE/OWASP/pentest
factory xp journeys -p ppz         # E2E personas RBAC
factory xp logs -p ppz             # prod log analysis
factory xp improve                 # SELF-MODIFY factory code
factory xp full -p ppz --apply     # ALL + improve + create tasks

# Status
factory status --all
```

## PROJECTS

`projects/*.yaml`:
- ppz (rust/ts/swift/kotlin/e2e)
- psy (rust/ts/swift/kotlin/svelte)
- veligo (rust/svelte/e2e)
- yolonow (rust/py/ts/swift/kotlin)
- fervenza (py)
- solaris (angular/figma)

### Config ex
```yaml
project:
  name: psy
  root_path: /path
  vision_doc: CLAUDE.md

domains:
  rust:
    paths: [backend/]
    build_cmd: cargo check
    test_cmd: cargo test
  swift:
    paths: [ios/]
    build_cmd: xcodebuild -scheme App build

fractal:
  force_level1: true      # NEW: force 3 sub-agents
  min_subtasks: 3
  parallel_subagents: true
  max_files: 5
  max_loc: 400
  max_depth: 3

adversarial:
  threshold: 5
  custom_patterns:
    - pattern: '\.unwrap\(\)'
      score: 2
      max_occurrences: 3
```

## LLM CFG

`~/.config/factory/llm.yaml`:
```yaml
providers:
  minimax:
    base_url: https://api.minimax.io/anthropic/v1
    api_key: ${MINIMAX_API_KEY}
    models:
      m2.1: MiniMax-M2.1
  local:
    base_url: http://localhost:8002/v1
    models:
      qwen: qwen3-30b-a3b

defaults:
  brain: anthropic/opus        # root RLM
  brain_sub: opencode/minimax  # llm_query() via opencode + MCP
  wiggum: opencode/minimax     # TDD workers via opencode
```

## MONITOR

```bash
tail -f data/logs/wiggum-tdd-*.log
sqlite3 data/factory.db "SELECT project_id,status,COUNT(*) FROM tasks GROUP BY 1,2"
ls /tmp/factory/*.pid
for f in /tmp/factory/*.pid; do kill $(cat $f) 2>/dev/null; rm $f; done
```

## RATE LIMIT

MiniMax timeout w/ too many workers:
- 10 workers/proj max
- 50 total
- timeout 600s → reduce or fallback Qwen

## FILES

```
_SOFTWARE_FACTORY/
├── cli/factory.py
├── core/
│   ├── brain.py           # Single RLM Brain (Opus→MiniMax→Qwen tiers)
│   ├── wiggum_tdd.py      # FRACTAL L1 + 3 sub-agents
│   ├── wiggum_deploy.py
│   ├── adversarial.py     # XP-learned patterns
│   ├── experience_agent.py # Self-modifying XP
│   ├── fractal.py         # force_level1, parallel_subagents
│   ├── task_store.py
│   ├── daemon.py
│   └── llm_client.py
├── _rlm/                  # MIT CSAIL RLM lib
│   └── rlm/clients/opencode.py  # Custom opencode client
├── projects/*.yaml
├── data/
│   ├── factory.db
│   ├── rlm_logs/          # RLM execution logs
│   └── logs/
└── /tmp/factory/*.pid
```

## WORKFLOW

```bash
# 1. Deep recursive analysis
factory psy brain run -q "iOS security RBAC"

# 2. Start workers (FRACTAL L1 → 3 sub-agents per task)
factory psy wiggum start -w 10

# 3. Monitor
tail -f data/logs/wiggum-tdd-psy.log
factory status --all

# 4. XP Agent self-improve
factory xp full -p psy --apply

# 5. Stop
factory psy wiggum stop
```
