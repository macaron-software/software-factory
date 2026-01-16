# Plan: RLM (LEAN Requirements Manager) pour Fervenza

## Vue d'ensemble

Adapter le systeme RLM pour automatiser l'analyse, correction TDD et deploiement du codebase Fervenza.

---

## Architecture Adaptee

```
┌──────────────────────────────────────────────────────────────────────┐
│                           RLM FERVENZA                               │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                    RLM BRAIN (Orchestrateur)                    │  │
│  │  LLM: Claude via Anthropic API (deja configure)                 │  │
│  │  Analyse: cargo clippy, pytest, proto lint, sql                 │  │
│  │  Output: backlog_tasks.json                                     │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                 WIGGUM TDD (Workers Paralleles)                 │  │
│  │  LLM: Claude Sonnet via LiteLLM (stack existante)               │  │
│  │  Cycle: RED → GREEN → VERIFY → COMMIT                           │  │
│  │  Tests: cargo test / pytest / playwright                        │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                  ADVERSARIAL (Quality Gate)                     │  │
│  │  Fast: regex patterns (skip, ignore, todo)                      │  │
│  │  Deep: Claude via LiteLLM (optionnel)                           │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │                                      │
│                               ▼                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                   WIGGUM DEPLOY (Release)                       │  │
│  │  Utilise: fervenza deploy server/agents/dashboard               │  │
│  │  Pipeline: staging → tests → prod (blue/green)                  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Domaines Fervenza

| Domaine | Cible | Commandes Analyse |
|---------|-------|-------------------|
| `rust` | `crates/` | `cargo clippy`, `cargo test` |
| `python` | `agents/` | `ruff check`, `pytest` |
| `typescript` | `apps/web/static/`, `e2e/` | `npx tsc` (si applicable) |
| `proto` | `proto/` | `protoc --lint` |
| `sql` | `migrations/` | Analyse syntaxique |
| `e2e` | `e2e/` | `npx playwright test` |

---

## Fichiers a Creer

```
agents/fervenza_agents/rlm/
├── __init__.py
├── brain.py              # RLM Brain - Analyse codebase
├── wiggum_tdd.py         # Workers TDD paralleles
├── adversarial.py        # Quality gate
├── wiggum_deploy.py      # Pipeline deploiement
├── models.py             # Pydantic models (Task, Finding)
├── backlog_tasks.json    # Taches generees
└── deploy_backlog.json   # Taches a deployer
```

---

## Phase 1: Models et Structure

### `agents/fervenza_agents/rlm/models.py`

```python
from pydantic import BaseModel
from enum import Enum
from typing import Optional, List
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskType(str, Enum):
    FIX = "fix"
    REFACTOR = "refactor"
    TEST = "test"
    SECURITY = "security"
    LINT = "lint"

class Domain(str, Enum):
    RUST = "rust"
    PYTHON = "python"
    TYPESCRIPT = "typescript"
    PROTO = "proto"
    SQL = "sql"
    E2E = "e2e"

class Finding(BaseModel):
    type: str
    severity: str  # low, medium, high, critical
    message: str
    line: Optional[int] = None

class Task(BaseModel):
    id: str
    type: TaskType
    domain: Domain
    description: str
    files: List[str]
    finding: Finding
    file_content: Optional[str] = None  # Max 3000 chars
    conventions: dict = {}
    status: TaskStatus = TaskStatus.PENDING
    business_value: int = 5
    time_criticality: int = 5
    risk_reduction: int = 5
    job_size: int = 5
    wsjf_score: float = 0.0
    created_at: datetime = datetime.utcnow()
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

class Backlog(BaseModel):
    updated: datetime
    tasks: List[Task]
```

---

## Phase 2: RLM Brain

### `agents/fervenza_agents/rlm/brain.py`

Fonctionnalites:
1. Scanner les domaines avec leurs outils respectifs
2. Parser les erreurs/warnings en tasks
3. Enrichir avec contexte fichier
4. Calculer score WSJF
5. Sauvegarder backlog_tasks.json

```python
# Commandes par domaine
DOMAIN_COMMANDS = {
    "rust": [
        ("cargo clippy --workspace --message-format=json", "clippy"),
        ("cargo test --workspace --no-run 2>&1", "build"),
    ],
    "python": [
        ("cd agents && ruff check . --output-format=json", "ruff"),
        ("cd agents && python -m pytest --collect-only -q 2>&1", "pytest"),
    ],
    "proto": [
        ("buf lint proto/", "buf"),
    ],
}
```

---

## Phase 3: Wiggum TDD

### `agents/fervenza_agents/rlm/wiggum_tdd.py`

Fonctionnalites:
1. Pool de workers async (5-20 par defaut)
2. Cycle TDD: lire fichier → generer fix → tester → commit
3. Utilise LiteLLM (deja dans le stack Fervenza)
4. Retry max 3 fois

```python
# Exemple de prompt TDD
SYSTEM_PROMPT = """
Tu es un developpeur TDD strict. Pour chaque tache:
1. Lis le fichier source et comprends l'erreur
2. Ecris le fix minimal (pas de gold plating)
3. Le test DOIT passer apres ton fix

Conventions Fervenza:
- Rust: utilise `?` pour les erreurs, pas `.unwrap()`
- Python: pas de `# type: ignore`
- Jamais de `test.skip`, `#[ignore]`, `TODO`
"""
```

---

## Phase 4: Adversarial

### `agents/fervenza_agents/rlm/adversarial.py`

Patterns de rejet (5+ points = REJECT):

| Pattern | Points | Description |
|---------|--------|-------------|
| `test.skip`, `describe.skip` | 5 | Tests desactives |
| `#[ignore]` | 5 | Tests Rust ignores |
| `# type: ignore` | 2 | Suppression type Python |
| `.unwrap()` > 3 | 2 | Unwrap excessif |
| `TODO`, `FIXME` > 2 | 1 | Stubs non resolus |

---

## Phase 5: Wiggum Deploy

### `agents/fervenza_agents/rlm/wiggum_deploy.py`

Utilise les commandes CLI existantes:

```python
DEPLOY_COMMANDS = {
    "rust": "fervenza deploy server -y",
    "python": "fervenza deploy agents -y",
    "typescript": "fervenza deploy dashboard -y",
}

# Pipeline
# 1. Verifier commit existe
# 2. Deploy staging (si disponible)
# 3. Lancer tests E2E
# 4. Deploy prod
# 5. Verifier health
```

---

## Phase 6: Integration CLI

Ajouter commandes au CLI `fervenza`:

```bash
# Analyse
fervenza rlm analyze              # Lance RLM Brain
fervenza rlm analyze --domain rust
fervenza rlm status               # Voir backlog

# TDD
fervenza rlm tdd                  # Lance Wiggum TDD (5 workers)
fervenza rlm tdd --workers 10     # 10 workers
fervenza rlm tdd --once           # 1 tache

# Deploy
fervenza rlm deploy               # Pipeline deploy
fervenza rlm deploy --once
```

---

## Fichiers a Modifier

| Fichier | Action |
|---------|--------|
| `agents/fervenza_agents/rlm/__init__.py` | CREATE |
| `agents/fervenza_agents/rlm/models.py` | CREATE |
| `agents/fervenza_agents/rlm/brain.py` | CREATE |
| `agents/fervenza_agents/rlm/wiggum_tdd.py` | CREATE |
| `agents/fervenza_agents/rlm/adversarial.py` | CREATE |
| `agents/fervenza_agents/rlm/wiggum_deploy.py` | CREATE |
| `agents/fervenza_agents/api.py` | EDIT (ajouter routes /rlm/*) |
| `crates/fervenza-cli/src/main.rs` | EDIT (ajouter commandes rlm) |

---

## Verification

1. `cd agents && python -m pytest tests/` - Tests Python passent
2. `cargo test --workspace` - Tests Rust passent
3. `fervenza rlm analyze` - Genere backlog_tasks.json
4. `fervenza rlm tdd --once` - Fixe 1 tache
5. `fervenza rlm status` - Affiche statistiques

---

## Estimation

- Phase 1 (Models): 30 min
- Phase 2 (Brain): 2h
- Phase 3 (Wiggum TDD): 3h
- Phase 4 (Adversarial): 1h
- Phase 5 (Deploy): 1h
- Phase 6 (CLI): 1h

**Total: ~8h**
