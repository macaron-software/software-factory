# SOFTWARE FACTORY - RLM (MIT CSAIL arXiv:2512.24601)

## ARCH
```
BRAIN (Opus4.5) → scan → backlog enrichi
    ↓
WIGGUM TDD (MiniMax×N) → RED/GREEN/VERIFY → commit
    ↓
WIGGUM DEPLOY → staging → E2E → prod → rollback
    ↓
FEEDBACK → errs → new tasks
```

## CORE

### Brain (`core/brain.py`)
- scan codebase/domain (rust/ts/swift/kotlin/e2e/proto)
- tasks enrichies (ctx, imports, conventions)
- WSJF score
- LLM: Opus4.5 `claude` CLI / opencode

### Wiggum TDD (`core/wiggum_tdd.py`)
- pool workers // (daemon)
- cycle: lock → TDD (test fail→code→pass) → adversarial → commit
- FRACTAL: big task → subtasks (max 3 depth)
- LLM: MiniMax M2.1 `opencode`

### Wiggum Deploy (`core/wiggum_deploy.py`)
- pipeline: build→staging→E2E→prod→verify
- rollback auto
- feedback tasks on err

### Adversarial (`core/adversarial.py`)
- reject: test.skip, @ts-ignore, TODO>2, .unwrap()>3, panic!
- score>=5 → REJECT → retry (max 10)
- deep: Qwen semantic (SLOP, BYPASS, SECURITY)

### XP Agent (`core/experience_agent.py`)
- meta-brain auto-improve (GenAI Divide: 5% success)
- learning memory: `learnings` table
- pattern evolution: `pattern_evolutions` table
- ROI tracking
- **chaos**: resilience tests (retry, circuit breaker, timeout)
- **security**: CVE fetch, OWASP Top10, pentest staging/prod
- **journeys**: Playwright E2E w/ RBAC personas, real data
- **logs**: prod log analysis → backlog tasks
- auto-fix: reset stuck, apply patterns, create tasks

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
# Brain
factory <p> brain run              # full
factory <p> brain run --legacy     # opencode
factory <p> brain run -q "mobile"  # focus

# Wiggum TDD
factory <p> wiggum start           # daemon bg
factory <p> wiggum start -w 10     # 10 workers
factory <p> wiggum start -f        # fg debug
factory <p> wiggum stop
factory <p> wiggum restart
factory <p> wiggum status
factory <p> wiggum once            # 1 task

# Deploy
factory <p> deploy start/stop/status/once

# XP Agent
factory xp analyze                 # no LLM
factory xp analyze --apply         # +auto-fix
factory xp report                  # Opus report
factory xp fix                     # reset stuck
factory xp impact                  # ROI
factory xp learn                   # full cycle
factory xp chaos -p ppz            # resilience tests
factory xp security -p ppz         # CVE/OWASP/pentest
factory xp journeys -p ppz         # E2E personas RBAC
factory xp logs -p ppz             # prod log analysis
factory xp full -p ppz --apply     # ALL + create tasks

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
    build_cmd: xcodebuild -scheme App -destination 'platform=iOS Simulator,name=iPhone 15' build

fractal:
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
  brain: anthropic/opus
  wiggum: minimax/m2.1
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
│   ├── brain.py
│   ├── wiggum_tdd.py
│   ├── wiggum_deploy.py
│   ├── adversarial.py
│   ├── experience_agent.py
│   ├── fractal.py
│   ├── task_store.py
│   ├── daemon.py
│   └── llm_client.py
├── projects/*.yaml
├── data/
│   ├── factory.db
│   └── logs/
└── /tmp/factory/*.pid
```

## WORKFLOW

```bash
factory psy brain run --legacy   # 1. analyse
factory psy wiggum start -w 10   # 2. workers
tail -f data/logs/wiggum-tdd-psy.log  # 3. monitor
factory status --all
factory psy wiggum stop          # 4. stop
```
