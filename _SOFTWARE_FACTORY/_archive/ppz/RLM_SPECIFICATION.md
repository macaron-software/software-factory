# RLM - LEAN Requirements Manager
## Spécification Complète v2.0

**Date**: 2026-01-14
**Auteur**: Équipe Popinz + Claude Opus 4.5
**Version**: 2.0 (Multi-LLM Architecture)

---

## 1. Vue d'Ensemble

RLM (LEAN Requirements Manager) est un système autonome d'analyse, correction et déploiement de code basé sur le cycle TDD (Test-Driven Development) avec des agents LLM parallèles.

### 1.1 Principes LEAN

| Principe | Application |
|----------|-------------|
| **Eliminate Waste** | Pas de gold plating, code uniquement ce qui est demandé |
| **One-Piece Flow** | Petits batches, max 3 fichiers par cycle TDD |
| **Jidoka** | Arrêt à la première erreur, analyse root cause |
| **Continuous Flow** | Daemon avec workers parallèles |

### 1.2 Architecture Globale

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              RLM SYSTEM                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                    RLM BRAIN (Orchestrateur)                       │    │
│   │   LLM: Claude Opus 4.5 via claude CLI                             │    │
│   │   Rôle: Analyse LEAN, vision, scoring WSJF, enrichissement        │    │
│   │   Sub-agents: Qwen 30B via opencode (analyses rapides)            │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                    BACKLOG TASKS                                   │    │
│   │   Format: backlog_tasks.json                                       │    │
│   │   Contenu: ~588 tâches avec contexte enrichi                       │    │
│   │   Priorité: Score WSJF (Weighted Shortest Job First)              │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│                                ▼                                            │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                    WIGGUM TDD (10-50 Workers)                      │    │
│   │   LLM: MiniMax M2.1 via opencode                                  │    │
│   │   Outils: Read, Write, Bash, MCP                                  │    │
│   │   Cycle: RED → GREEN → VERIFY → SUCCESS                           │    │
│   │   Timeout: 1 heure par tâche                                      │    │
│   └────────────────────────────┬──────────────────────────────────────┘    │
│                                │                                            │
│              ┌─────────────────┴─────────────────┐                         │
│              ▼                                   ▼                         │
│   ┌─────────────────────┐           ┌─────────────────────┐               │
│   │   ADVERSARIAL       │           │   DEPLOY BACKLOG    │               │
│   │   LLM: Qwen 30B     │           │   deploy_backlog.json│              │
│   │   Mode: Fast + Deep │           │   Tâches validées    │              │
│   └─────────────────────┘           └──────────┬──────────┘               │
│                                                │                           │
│                                                ▼                           │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                    WIGGUM DEPLOY                                   │    │
│   │   Pipeline: Staging → E2E → Production                            │    │
│   │   Blue/Green Deployment                                           │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. LLM Agents

### 2.1 Tableau des Agents

| Agent | LLM | Outil | Usage | Coût |
|-------|-----|-------|-------|------|
| **RLM Brain** | Claude Opus 4.5 | claude CLI | Orchestration, analyse LEAN, vision | $$$ |
| **Brain sub-agents** | Qwen 30B | opencode + llama serve | Sous-tâches, analyses rapides | Local |
| **Wiggum TDD** | MiniMax M2.1 | opencode | Code gen, TDD (10-50 workers //) | $ |
| **Adversarial** | Qwen 30B | opencode + llama serve | Quality check, red team | Local |

### 2.2 Configuration MiniMax M2.1

**Fichier**: `~/.config/opencode/opencode.json`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "minimax": {
      "npm": "@ai-sdk/anthropic",
      "options": {
        "baseURL": "https://api.minimax.io/anthropic/v1",
        "apiKey": "sk-cp-xxx..."
      },
      "models": {
        "MiniMax-M2.1": {
          "name": "MiniMax-M2.1"
        }
      }
    }
  }
}
```

**Documentation**: https://platform.minimax.io/docs/guides/text-ai-coding-tools

### 2.3 Configuration Qwen 30B (Local)

```bash
# Démarrer llama serve
llama serve qwen3-30b-a3b

# Utiliser via opencode
opencode run -m qwen3-30b-a3b "prompt"
```

---

## 3. RLM Brain

### 3.1 Description

Le Brain RLM est l'orchestrateur principal du système. Il analyse le codebase entier et génère des tâches **enrichies** avec tout le contexte nécessaire pour que les agents Wiggum TDD puissent travailler de manière autonome.

### 3.2 Fichier

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/rlm_brain.py`

### 3.3 Domaines Analysés

| Domaine | Cible | Commandes |
|---------|-------|-----------|
| `rust` | `popinz-v2-rust/` | `cargo check`, `cargo test`, `cargo clippy` |
| `typescript` | `popinz-saas/`, `popinz-entities/`, `popinz-tasks/` | `npx tsc`, `npx vitest` |
| `e2e` | `popinz-tests/` | `npx playwright test` |
| `proto` | `popinz-v2-rust/proto/` | `protoc --lint` |
| `sql` | `docker/migrations/` | Analyse syntaxique |
| `php` | `popinz-api-php/` | `php -l` (legacy) |

### 3.4 Enrichissement de Contexte

Chaque tâche générée contient un contexte enrichi pour MiniMax M2.1:

```json
{
  "id": "rust-security-0001-auth.rs",
  "type": "fix",
  "domain": "rust",
  "description": "[HIGH] auth.rs - SQL injection potential",
  "files": ["popinz-v2-rust/crates/api-grpc/src/services/auth.rs"],
  "line": 42,
  "finding": {
    "type": "security",
    "severity": "high",
    "message": "User input in SQL query without parameterization"
  },
  "file_content": "// Source code (3000 chars max)...",
  "imports": ["use crate::...", "use sqlx::..."],
  "types_defined": ["AuthService", "LoginRequest"],
  "error_context": {
    "type": "security",
    "message": "SQL injection potential"
  },
  "test_example": "// Exemple de test existant dans le projet...",
  "conventions": {
    "error_handling": "Use ? operator, avoid unwrap()",
    "testing": "#[cfg(test)] mod tests",
    "skip_pattern": "NEVER bare test.skip()"
  },
  "status": "pending",
  "business_value": 9,
  "time_criticality": 9,
  "risk_reduction": 10,
  "job_size": 2,
  "wsjf_score": 14.0
}
```

### 3.5 Scoring WSJF

```
WSJF = (Business Value + Time Criticality + Risk Reduction) / Job Size
```

| Critère | Description | Valeurs |
|---------|-------------|---------|
| **Business Value** | Impact utilisateur | 1-10 |
| **Time Criticality** | Urgence | 1-10 |
| **Risk Reduction** | Réduction dette/risque | 1-10 |
| **Job Size** | Effort estimé | 1-10 |

### 3.6 Commandes CLI

```bash
# Analyse complète du codebase
ppz brain run

# Analyse avec focus prompt
ppz brain run "mobile apps v1"

# Analyse domaine spécifique
ppz brain run "" rust

# Scan rapide (skip security deep)
ppz brain quick

# Voir le backlog
ppz brain status
```

---

## 4. Wiggum TDD

### 4.1 Description

Wiggum TDD spawne N agents (10-50) en parallèle, chacun exécutant un cycle TDD complet sur une tâche du backlog.

### 4.2 Fichier

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/wiggum_tdd.py`

### 4.3 Pool Dynamique

Le daemon utilise un **pool dynamique** où les workers se réaffectent immédiatement après chaque tâche, au lieu d'attendre qu'un batch complet finisse.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    POOL DYNAMIQUE (10 workers)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   W01: task-001 ✅ → task-011 ✅ → task-021 → ...                       │
│   W02: task-002 ✅ → task-012 → ...                                     │
│   W03: task-003 ✅ → task-013 ✅ → task-023 → ...                       │
│   ...                                                                   │
│   W10: task-010 ✅ → task-020 ✅ → task-030 → ...                       │
│                                                                         │
│   Chaque worker prend une nouvelle tâche IMMÉDIATEMENT                  │
│   Pas d'attente du batch complet = ~4x plus rapide                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Cycle TDD

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CYCLE TDD PAR AGENT                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐    ┌─────────┐              │
│  │  RED    │ →  │  GREEN  │ →  │ VERIFY  │ →  │ SUCCESS │              │
│  │         │    │         │    │         │    │         │              │
│  │ Lit le  │    │ Écrit   │    │ Lance   │    │ Marque  │              │
│  │ fichier │    │ le fix  │    │ le test │    │ complet │              │
│  │         │    │         │    │         │    │         │              │
│  └─────────┘    └─────────┘    └─────────┘    └─────────┘              │
│                                     │                                   │
│                                     ▼                                   │
│                              Test ÉCHOUE ?                              │
│                                     │                                   │
│                         ┌───────────┴───────────┐                      │
│                         │                       │                      │
│                        OUI                     NON                     │
│                         │                       │                      │
│                         ▼                       ▼                      │
│                    Retry (max 3)          TDD SUCCESS                  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4.4 Configuration

```python
# wiggum_tdd.py
DEFAULT_WORKERS = 50      # Nombre de workers par défaut
AGENT_TIMEOUT = 3600      # 1 heure par tâche
```

### 4.5 Tests par Domaine

| Domaine | Test créé | Runner | Commande |
|---------|-----------|--------|----------|
| `e2e` | Modifie `.spec.ts` | Playwright | `npx playwright test {file}` |
| `typescript` | Crée `.test.ts` | Vitest | `npx vitest run {file}` |
| `rust` | Ajoute `#[cfg(test)]` | Cargo | `cargo test --package {crate}` |

### 4.6 Commandes CLI

```bash
# Mode daemon avec 50 workers (défaut)
ppz wiggum

# 10 workers (évite rate limiting)
ppz wiggum 10

# Mode daemon explicite
ppz wiggum tdd --workers 10

# Une seule tâche
ppz wiggum tdd --once

# Tâche spécifique
ppz wiggum tdd --task rust-security-0001-auth.rs

# En background
ppz wiggum bg 50

# Arrêter
ppz wiggum stop

# Status
ppz wiggum status
```

### 4.7 Output

```
[09:36:38] [TDD] [INFO] ======================================================================
[09:36:38] [TDD] [INFO] WIGGUM TDD - 10 parallel agents
[09:36:38] [TDD] [INFO] Using: opencode with MiniMax M2.1
[09:36:38] [TDD] [INFO] ======================================================================
[09:36:38] [TDD] [INFO] Tools: Read, Write, Bash, MCP
[09:36:38] [TDD] [INFO] Cycle: RED → GREEN → VERIFY (test must pass)
[09:36:38] [TDD] [INFO]
[09:36:38] [TDD] [INFO] Launching 10 agents...
[09:36:38] [W01] [INFO] Starting agent: security-security-0565-webhook.rs
[09:36:38] [W02] [INFO] Starting agent: security-security-0566-auth.rs
...
[09:37:10] [W07] [INFO] ✅ TDD SUCCESS: security-security-0571-5d176d2624c8.js
[09:37:23] [W10] [INFO] ✅ TDD SUCCESS: security-security-0574-1a28dbbbb7e3.js
...
[09:39:23] [TDD] [INFO] Batch: 10✅ 0❌ 0💥
```

---

## 5. Adversarial Agent

### 5.1 Description

L'agent adversarial vérifie la qualité du code généré par Wiggum TDD. Il opère en deux modes:
- **Fast**: Regex (instantané)
- **Deep**: Qwen 30B via opencode (~30s)

### 5.2 Fichier

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/adversarial.py`

### 5.3 Règles de Rejet (5+ points = REJECT)

| Pattern | Points | Description |
|---------|--------|-------------|
| `test.skip`, `describe.skip` | 5 | Tests désactivés |
| `#[ignore]` | 5 | Tests Rust ignorés |
| `@ts-ignore`, `@ts-expect-error` | 2 | Suppression erreurs TS |
| `as any` | 2 | Type unsafe |
| "100%", "perfect" dans commentaires | 2 | SLOP patterns |

### 5.4 Warnings (1 point chacun)

- `.unwrap()` > 3 occurrences
- `TODO`, `FIXME`, `STUB` > 2
- `catch {}` vide
- `todo!()`, `unimplemented!()`

### 5.5 Mode Deep (Qwen 30B)

```python
async def check_code_deep(self, code: str, file_type: str = "rust", timeout: int = 60) -> Dict:
    """
    Deep semantic analysis using Qwen 30B via opencode.
    Catches issues that regex can't detect.
    """
```

**Détecte**:
- SLOP: Code qui "semble bien" mais ne fonctionne pas
- BYPASS: Contournements cachés
- INCOMPLET: Logique manquante
- SECURITY: Injections, XSS, secrets hardcodés

### 5.6 API

```python
from adversarial import AdversarialAgent

agent = AdversarialAgent()

# Mode fast (regex)
result = agent.check_code(code, "rust")

# Mode deep (Qwen 30B)
result = await agent.check_code_deep(code, "rust")

# Résultat
{
    "approved": True/False,
    "score": 0-10,
    "issues": [
        {"type": "skip", "line": 42, "message": "test.skip without condition"}
    ]
}
```

---

## 6. Wiggum Deploy

### 6.1 Description

Pipeline de déploiement automatisé: Staging → E2E → Production avec Blue/Green.

### 6.2 Fichier

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/wiggum_deploy.py`

### 6.3 Pipeline

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         WIGGUM DEPLOY PIPELINE                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  deploy_backlog.json                                                    │
│         │                                                               │
│         ▼                                                               │
│  ┌─────────────────┐                                                   │
│  │ 1. Verify Commit│  Vérifie que le commit existe                     │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │ 2. Run Tests    │  cargo build / E2E selon type                     │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │ 3. Deploy       │  ppz deploy staging                               │
│  │    Staging      │                                                   │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │ 4. E2E Staging  │  Playwright tests                                 │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │ 5. Deploy Prod  │  ppz deploy prod (Blue/Green)                     │
│  └────────┬────────┘                                                   │
│           │                                                             │
│           ▼                                                             │
│  ┌─────────────────┐                                                   │
│  │ 6. Verify Prod  │  Health check + smoke tests                       │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Commandes CLI

```bash
# Une tâche du backlog deploy
ppz wiggum deploy --once

# Mode daemon
ppz wiggum deploy --daemon

# Status
ppz wiggum deploy status
```

---

## 7. Backlogs

### 7.1 backlog_tasks.json

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/backlog_tasks.json`

**Structure**:

```json
{
  "updated": "2026-01-14T09:56:49.123456",
  "tasks": [
    {
      "id": "rust-security-0001-auth.rs",
      "type": "fix",
      "domain": "rust",
      "description": "[HIGH] auth.rs - SQL injection potential",
      "files": ["popinz-v2-rust/crates/.../auth.rs"],
      "line": 42,
      "finding": {...},
      "file_content": "...",
      "imports": [...],
      "types_defined": [...],
      "conventions": {...},
      "status": "pending|in_progress|completed|failed",
      "business_value": 9,
      "time_criticality": 9,
      "risk_reduction": 10,
      "job_size": 2,
      "wsjf_score": 14.0,
      "updated_at": "2026-01-14T09:30:00",
      "completed_at": null,
      "error": null
    }
  ]
}
```

**Status possibles**:

| Status | Description |
|--------|-------------|
| `pending` | En attente de traitement |
| `in_progress` | Agent en cours |
| `completed` | TDD SUCCESS |
| `failed` | TDD échoué ou timeout |

### 7.2 deploy_backlog.json

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/deploy_backlog.json`

**Structure**:

```json
{
  "updated": "2026-01-14T10:00:00",
  "tasks": [
    {
      "id": "deploy-rust-001",
      "source_task": "rust-security-0001-auth.rs",
      "commit_hash": "abc1234def5678",
      "files_modified": ["auth.rs"],
      "status": "pending|deployed|failed",
      "deployed_at": null,
      "environment": null
    }
  ]
}
```

---

## 8. Intégration CLI (ppz)

### 8.1 Fichier CLI

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/bin/ppz`

### 8.2 Commandes RLM

```bash
# ═══════════════════════════════════════════════════════════════════════
# BRAIN (Analyse)
# ═══════════════════════════════════════════════════════════════════════

ppz brain run                    # Analyse complète du codebase
ppz brain run "mobile apps v1"   # Analyse avec focus prompt
ppz brain run "" rust            # Analyse domaine spécifique
ppz brain quick                  # Scan rapide (skip security deep)
ppz brain status                 # Voir le backlog

# ═══════════════════════════════════════════════════════════════════════
# WIGGUM TDD (Parallel Agents - MiniMax M2.1)
# ═══════════════════════════════════════════════════════════════════════

ppz wiggum                       # 50 workers daemon (défaut)
ppz wiggum 10                    # 10 workers (évite rate limiting)
ppz wiggum tdd --workers 10      # Équivalent
ppz wiggum tdd --once            # 1 tâche et exit
ppz wiggum tdd --task TASK_ID    # Tâche spécifique

# ═══════════════════════════════════════════════════════════════════════
# WIGGUM DEPLOY
# ═══════════════════════════════════════════════════════════════════════

ppz wiggum deploy                # Deploy pipeline
ppz wiggum deploy --once         # 1 tâche deploy
ppz wiggum deploy --daemon       # Mode continu

# ═══════════════════════════════════════════════════════════════════════
# CONTRÔLE
# ═══════════════════════════════════════════════════════════════════════

ppz wiggum bg 50                 # Background: TDD + Deploy
ppz wiggum stop                  # Arrêter tous les workers
ppz wiggum status                # État du système

# ═══════════════════════════════════════════════════════════════════════
# WORKFLOW COMPLET
# ═══════════════════════════════════════════════════════════════════════

ppz brain run                    # 1. Analyser → génère backlog
ppz wiggum 10                    # 2. Lancer 10 workers MiniMax M2.1
tail -f rlm/logs/*.log           # 3. Monitorer
ppz wiggum status                # 4. Vérifier l'état
ppz wiggum stop                  # 5. Arrêter quand terminé
```

---

## 9. Logs et Monitoring

### 9.1 Fichiers de Log

```
rlm/logs/
├── wiggum_10workers_20260114_093638.log    # Log daemon principal
├── agent_01_rust-security-0001.log         # Log agent individuel
├── agent_02_e2e-test_failure-0043.log      # ...
└── prompt_01_rust-security-0001.txt        # Prompt envoyé à l'agent
```

### 9.2 Monitoring en Temps Réel

```bash
# Suivre le daemon
tail -f rlm/logs/wiggum_*.log

# Compter les succès
grep -c "TDD SUCCESS" rlm/logs/wiggum_*.log

# Compter les timeouts
grep -c "Timeout" rlm/logs/wiggum_*.log

# Voir un agent spécifique
cat rlm/logs/agent_33_e2e-security-0297-gr.log
```

### 9.3 Statistiques

```bash
# Status backlog
python3 -c "
import json
with open('rlm/backlog_tasks.json') as f:
    data = json.load(f)
tasks = data.get('tasks', [])
by_status = {}
for t in tasks:
    s = t.get('status', 'unknown')
    by_status[s] = by_status.get(s, 0) + 1
for s, c in sorted(by_status.items()):
    print(f'{s}: {c}')
print(f'TOTAL: {len(tasks)}')
"
```

---

## 10. Prérequis

### 10.1 Outils Requis

| Outil | Installation | Usage |
|-------|--------------|-------|
| **opencode** | `npm install -g @opencode-ai/cli` | Agents MiniMax M2.1 |
| **claude** | `npm install -g @anthropic-ai/claude-cli` | Brain RLM + fallback |
| **llama** | `brew install llama.cpp` | Qwen 30B local |

### 10.2 API Keys

| Service | Variable | Fichier |
|---------|----------|---------|
| **MiniMax** | - | `~/.config/opencode/opencode.json` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `~/.zshrc` |

### 10.3 Serveur LLM Local (Optionnel)

```bash
# Démarrer Qwen 30B
llama serve qwen3-30b-a3b

# Vérifier
curl http://localhost:8080/v1/models
```

---

## 11. Troubleshooting

### 11.1 Rate Limiting MiniMax

**Symptôme**: Timeouts fréquents avec 50 workers

**Solution**: Réduire à 10 workers
```bash
ppz wiggum 10
```

### 11.2 JSON Backlog Corrompu

**Symptôme**: `JSONDecodeError: Expecting ',' delimiter`

**Cause**: Écritures concurrentes (file locking insuffisant)

**Solution**:
```bash
# Sauvegarder
cp rlm/backlog_tasks.json rlm/backlog_tasks.json.backup

# Réparer manuellement ou restaurer
python3 << 'EOF'
import json
with open('rlm/backlog_tasks.json') as f:
    lines = f.readlines()
# Identifier et supprimer lignes corrompues
# ...
EOF
```

### 11.3 opencode ne Trouve pas MiniMax

**Symptôme**: `Unknown provider: minimax`

**Solution**: Vérifier config
```bash
cat ~/.config/opencode/opencode.json
# Doit contenir section "minimax" avec apiKey
```

### 11.4 Timeout 5 minutes Insuffisant

**Symptôme**: Tâches Rust complexes timeout systématiquement

**Solution**: Augmenter `AGENT_TIMEOUT` dans `wiggum_tdd.py`
```python
AGENT_TIMEOUT = 3600  # 1 heure
```

---

## 12. Métriques de Performance

### 12.1 Session 2026-01-14

| Métrique | Valeur |
|----------|--------|
| **Tasks analysées** | 588 |
| **Workers** | 10 |
| **Timeout** | 1 heure |
| **Taux de succès** | ~70% |
| **Temps moyen/tâche** | 1-3 minutes |

### 12.2 Historique

| Date | Workers | Timeout | Succès | Timeouts |
|------|---------|---------|--------|----------|
| 2026-01-14 09:00 | 50 | 5 min | 80 (26%) | 215 (72%) |
| 2026-01-14 09:36 | 10 | 5 min | 17 (100%) | 0 |
| 2026-01-14 09:56 | 10 | 1 h | En cours | - |

---

## 13. Roadmap

### 13.1 Améliorations Prévues

- [ ] Atomic writes pour backlog JSON (éviter corruption)
- [ ] Retry intelligent (backoff exponentiel)
- [ ] Metrics dashboard (Grafana)
- [ ] Webhook notifications (Slack)
- [ ] Cache des prompts enrichis

### 13.2 Extensions

- [ ] Support multi-repo
- [ ] Agent spécialisé Rust (cargo + clippy)
- [ ] Agent spécialisé Frontend (ESLint + Prettier)
- [ ] Integration GitHub Actions

---

## 14. Architecture Avancée : Fractal + TMC + Chaos

### 14.1 Philosophie Fractale

Le problème du "code partiel" est résolu par une approche fractale avec **contrats de complétude** :

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    RÈGLE FRACTALE ANTI-PARTIEL                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Un Wiggum n'a JAMAIS le droit de livrer une feature partielle.        │
│                                                                         │
│   Si la tâche dépasse les seuils :                                      │
│   • max 5 fichiers touchés                                              │
│   • max 400 LOC                                                         │
│   • 1 seul domaine (DB OU API OU UI)                                    │
│   • liste items > 10 sans test complétude                               │
│                                                                         │
│   → Le Wiggum DOIT :                                                    │
│   (A) Livrer un scaffolding (tests rouges + contrat + sous-backlog)     │
│   (B) OU découper en sous-tâches et s'arrêter                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.2 Tests de Complétude (Gate Anti-Partiel)

| Test | Description | Quand |
|------|-------------|-------|
| **Inventaire routes** | Compare `routes_inventory.json` vs routes réelles | Chaque task API |
| **Contract test** | Vérifie mapping route → RPC | Migration gRPC |
| **Fail-on-stubs** | Échoue si `TODO`, `NotImplemented`, `pass` | Chaque commit |
| **Coverage delta** | Pas de baisse de couverture | Chaque task |

### 14.3 TMC - Tests de Montée en Charge

#### Niveaux TMC

| Niveau | Durée | Charge | Quand | Gating |
|--------|-------|--------|-------|--------|
| **Perf Smoke** | 1-3 min | 5-20 VUs | Tasks `perf-risk` | Bloquant |
| **Load Test** | 10-30 min | Ramp-up plateau | Release train | Bloquant prod |
| **Stress + Chaos** | 30+ min | Saturation + fautes | Hebdo | Non bloquant |

#### Budgets Performance

```yaml
# perf-budgets.yaml
endpoints:
  login:
    p50_ms: 200
    p95_ms: 500
    p99_ms: 1000
    error_rate_max: 0.1%

  dashboard:
    p50_ms: 300
    p95_ms: 800
    p99_ms: 1500

  search:
    p50_ms: 150
    p95_ms: 400

rules:
  regression_threshold: 15%  # Max dégradation vs baseline
  warmup_duration: 30s
  plateau_duration: 60s
```

#### Outils Recommandés

| Outil | Usage |
|-------|-------|
| **k6** | Load testing API (léger, scriptable) |
| **Artillery** | Alternative k6 |
| **Playwright** | E2E fonctionnel (pas charge) |
| **OpenTelemetry** | Tracing spans |
| **Prometheus** | Métriques saturation |

### 14.4 Chaos Monkey

#### Types de Chaos

| Type | Description | Environnement |
|------|-------------|---------------|
| **Infra chaos** | Kill pods, latence réseau, 5xx | Staging uniquement |
| **UI chaos** | gremlins.js (random clicks) | Staging |
| **DB chaos** | Latence queries, connexions | Staging |

#### Intégration Pipeline

```bash
# Chaos sur staging après TMC OK
ppz chaos staging --scenario=network-latency --duration=5m
ppz test e2e --tag=@journey --env=staging  # Pendant le chaos
```

### 14.5 Machine à États Unifiée

```sql
-- Store SQLite pour traçabilité
CREATE TABLE tasks (
  id TEXT PRIMARY KEY,
  status TEXT CHECK(status IN (
    'PENDING',
    'IMPLEMENTING',
    'TDD_DONE',
    'ADVERSARIAL_OK',
    'ADVERSARIAL_KO',
    'MERGED',
    'QUEUED_FOR_DEPLOY',
    'STAGING_DEPLOYED',
    'SMOKE_OK',
    'PERF_SMOKE_OK',
    'JOURNEY_OK',
    'PROD_DEPLOYED',
    'TMC_OK',
    'CHAOS_OK',
    'DONE',
    'FAILED'
  )),
  commit_sha TEXT,
  artifact_id TEXT,
  attempt_count INTEGER DEFAULT 0,
  max_attempts INTEGER DEFAULT 3,
  last_error TEXT,
  e2e_run_id TEXT,
  perf_run_id TEXT,
  locked_by TEXT,
  lock_expires_at DATETIME,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 14.6 Pipeline Complet Wiggum Deploy

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    WIGGUM DEPLOY PIPELINE                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. STAGING                                                             │
│     ├── ppz deploy staging                                              │
│     ├── Smoke E2E (@smoke) ─────────────────┐                          │
│     │   └── KO → cycle Wiggum TDD           │                          │
│     ├── Perf Smoke (si perf-risk) ──────────┤                          │
│     │   └── KO → evidence pack + cycle      │                          │
│     ├── Journey E2E (@journey) ─────────────┤                          │
│     │   └── KO → traces + cycle             │                          │
│     └── OK → promote to PROD                │                          │
│                                              │                          │
│  2. PROD                                     │                          │
│     ├── ppz deploy prod (blue/green)        │                          │
│     ├── Smoke Prod (@smoke-prod) ───────────┤                          │
│     │   └── KO → rollback immédiat          │                          │
│     ├── TMC Load (si release train) ────────┤                          │
│     │   └── KO → rollback + analyse         │                          │
│     └── OK → DONE                           │                          │
│                                              │                          │
│  3. CHAOS (hebdo / pre-release)              │                          │
│     ├── ppz chaos staging                   │                          │
│     ├── Journeys sous stress                │                          │
│     └── Rapport résilience                  │                          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### 14.7 Anti-Flaky / Anti-Boucle

| Règle | Description |
|-------|-------------|
| **Max attempts** | 3 tentatives puis escalade humaine |
| **Retry E2E** | 1 retry auto, 2 échecs → échec dur |
| **Evidence pack** | Logs + traces + métriques à chaque échec |
| **Baseline versionnée** | Comparaison perf par commit SHA |
| **Warm-up obligatoire** | 30s avant mesures perf |

### 14.8 Commandes CLI Étendues

```bash
# === TMC ===
ppz tmc smoke --env=staging              # Perf smoke (1-3 min)
ppz tmc load --env=staging --duration=10m # Load test
ppz tmc stress --env=staging             # Stress test

# === CHAOS ===
ppz chaos network --latency=500ms --env=staging
ppz chaos kill-service --service=api --env=staging
ppz chaos db --slow-queries --env=staging

# === PIPELINE COMPLET ===
ppz deploy full --task=TASK-123          # Deploy + tous tests
ppz deploy staging --with-perf           # Staging + TMC
ppz deploy prod --with-tmc               # Prod + Load test
```

---

## 15. Intégration Hooks Git

### 15.1 pre-commit (ultra court)

```bash
#!/bin/bash
# Format + lint
npm run lint --fix

# Fail-on-stubs
if grep -rE "(TODO|FIXME|NotImplemented|pass\s*$)" --include="*.py" --include="*.ts" .; then
  echo "❌ Stubs détectés - corrigez avant commit"
  exit 1
fi

# Unit tests ciblés (packages touchés)
npm run test:changed
```

### 15.2 post-commit

```bash
#!/bin/bash
# Enregistre dans le store SQLite
python3 rlm/update_task_store.py \
  --commit=$(git rev-parse HEAD) \
  --status=MERGED \
  --task=$(git log -1 --format=%s | grep -oE 'TASK-[0-9]+')
```

---

**Fin de la spécification RLM v2.1**
