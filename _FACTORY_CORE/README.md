# Factory Core - Shared Resources

This directory contains **common utilities** shared between:

1. **_SOFTWARE_FACTORY/** - TDD-based development (features, bugs, refactoring)
2. **_MIGRATION_FACTORY/** - Code migrations (Angular 16→17, React 17→18, etc.)

## Why Separate?

The two factories have **fundamentally different workflows**:

| Aspect | Software Factory | Migration Factory |
|--------|------------------|-------------------|
| **Vision** | VISION.md (features roadmap) | MIGRATION_PLAN.md (before→after state) |
| **Workers** | TDD (RED→GREEN→REFACTOR) | Transform (VALIDATE→TRANSFORM→COMPARE) |
| **Adversarial** | Code quality (no skip/stub) | Behavioral equivalence (old === new) |
| **Skills** | `tdd.md`, `e2e_ihm.md` | `breaking_changes.md`, `golden_files.md` |
| **Task Flow** | pending → tdd → build → deploy | pending → pre_validate → transform → compare |

Mixing them would create conceptual conflicts and confusion in agents.

## Shared Modules

### subprocess_util.py
Process management with cleanup:
- `run_subprocess()` - Async subprocess with timeout
- Process group cleanup (`os.killpg`)
- Streaming output handling

### log.py
Logging with rotation:
- `get_logger()` - Factory-specific loggers
- `RotatingFileHandler` (10MB, 5 backups)
- Consistent format: `[factory.component]`

### llm_client.py
LLM interactions:
- Multi-model support (MiniMax, Opus, Qwen, GLM)
- Fallback chains (rate limit → next model)
- Timeout handling (40min max)
- Stream logging

### project_context.py
RAG "Big Picture":
- 10 categories (vision, architecture, data_model, etc.)
- SQLite + FTS5 for fast search
- Auto-refresh (1h stale threshold)
- Used by Brain for context injection

### daemon.py
Daemonization:
- Double-fork Unix daemon
- PID file management
- Signal handling (SIGTERM)
- stdout/stderr redirection

## What's NOT Shared

**Software Factory specific:**
- `brain.py` - Feature/bug analysis
- `wiggum_tdd.py` - TDD workflow
- `fractal.py` - FRACTAL decomposition
- `adversarial.py` - Quality gates
- `cycle_worker.py` - Batch TDD

**Migration Factory specific:**
- `migration_brain.py` - Delta analysis (before→after)
- `transform_worker.py` - Transform workflow
- `comparative_adversarial.py` - Behavioral equivalence
- `breaking_changes.py` - Framework breaking changes DB
- `codemods/` - AST transformations (jscodeshift)

## Usage

```python
# In _SOFTWARE_FACTORY/core/brain.py
from _FACTORY_CORE.subprocess_util import run_subprocess
from _FACTORY_CORE.log import get_logger
from _FACTORY_CORE.llm_client import LLMClient

# In _MIGRATION_FACTORY/core/migration_brain.py
from _FACTORY_CORE.subprocess_util import run_subprocess
from _FACTORY_CORE.log import get_logger
from _FACTORY_CORE.llm_client import LLMClient
```

## Architecture Diagram

```
/_MACARON-SOFTWARE/
│
├── _FACTORY_CORE/              # SHARED RESOURCES
│   ├── subprocess_util.py      # Process management
│   ├── log.py                  # Logging
│   ├── llm_client.py           # LLM interactions
│   ├── project_context.py      # RAG context
│   └── daemon.py               # Daemonization
│
├── _SOFTWARE_FACTORY/          # TDD DEVELOPMENT
│   ├── core/
│   │   ├── brain.py            # Features/bugs analysis
│   │   ├── wiggum_tdd.py       # TDD workers
│   │   ├── adversarial.py      # Quality gates
│   │   └── ...
│   ├── cli/factory.py
│   └── data/factory.db
│
└── _MIGRATION_FACTORY/         # CODE MIGRATIONS
    ├── core/
    │   ├── migration_brain.py  # Delta analysis
    │   ├── transform_worker.py # Transform workflow
    │   ├── comparative_adversarial.py
    │   ├── breaking_changes.py
    │   └── codemods/
    ├── cli/migrate.py
    └── data/migration.db
```

## Principles

1. **Lean Core** - Only truly common code (utils, no business logic)
2. **No Cross-References** - SF never imports MF, MF never imports SF
3. **Independent Evolution** - Each factory can evolve without affecting the other
4. **Shared Context** - ProjectContext used by both for RAG
5. **Minimal Duplication** - Utils written once, used twice

## Testing

```bash
# Test imports from Software Factory
cd _SOFTWARE_FACTORY
python3 -c "from _FACTORY_CORE.log import get_logger; print('✅ SF imports OK')"

# Test imports from Migration Factory (when created)
cd _MIGRATION_FACTORY
python3 -c "from _FACTORY_CORE.log import get_logger; print('✅ MF imports OK')"
```

## Maintenance

When adding new shared modules:
1. Ask: "Is this truly common to BOTH factories?"
2. If YES → Add to `_FACTORY_CORE/`
3. If NO → Keep in factory-specific `core/`
4. Update this README

**Rule of thumb:** If it's about process execution, logging, LLM calls, or project context → Core. If it's about workflows, strategies, or domain logic → Factory-specific.
