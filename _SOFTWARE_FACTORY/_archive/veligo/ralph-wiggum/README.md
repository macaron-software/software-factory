# Ralph Wiggum - Veligo Platform

Système d'orchestration TDD et déploiement automatisé pour la plateforme Veligo.

## Vue d'ensemble

Ralph Wiggum utilise **Qwen3-Coder-30B** via llama-server pour générer des patches et corriger progressivement les tâches du backlog Veligo.

### Architecture à 2 Queues

```
┌────────────────────────────────────────────────────────────────────┐
│                      RALPH WIGGUM - VELIGO                         │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  QUEUE 1: TDD Red/Green                QUEUE 2: Deploy + Prod      │
│  ─────────────────────                 ────────────────────────    │
│  T001 → Docker Setup                   D001 → Build Backend        │
│  T002 → gRPC-Web Proxy                 D002 → Build Frontend       │
│  T003 → Security Headers               D003 → Deploy Staging       │
│  T004 → Rate Limiting                  D004 → E2E Staging          │
│  T005 → DB Migrations                  D005 → Deploy Prod          │
│  T006 → RLS Security Fix               D006 → Smoke Prod           │
│  T007 → Auth Service                   D007 → Verify Health        │
│  T008 → Booking Service                D008 → Notify Complete      │
│  T009 → Subscription Service                                       │
│  T010 → MFA UI                                                     │
│  T011 → Dashboard UI                                               │
│  T012 → Station Map                                                │
│  T013 → E2E Auth Tests                                             │
│  T014 → E2E Booking Tests                                          │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

## Pré-requis

### 1. Modèles LLM (pas d'appels API!)

**TIER 1 - Claude Opus 4.5 (Complex tasks)**
```bash
# Claude Code headless (Claude Max subscription - gratuit)
# Le CLI claude est déjà installé
claude --version
```

**TIER 2 - GLM-4 / Minimax (Medium tasks)**
```bash
# OpenCode server (gratuit)
# Installer opencode CLI
npm install -g opencode
opencode --version
```

**TIER 3 - Qwen3-Coder / DeepSeek (Simple tasks)**
```bash
# llama-server local (Qwen3-Coder sur :8000)
llama-server -m ~/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf \
    --port 8000 -c 65536 -t 8 --host 127.0.0.1 -ngl 99 &

# Optionnel: DeepSeek sur :8001
llama-server -m ~/models/DeepSeek-V3.gguf \
    --port 8001 -c 65536 -t 8 --host 127.0.0.1 -ngl 99 &
```

### 2. Docker installé et démon actif

### 3. Scripts exécutables
```bash
chmod +x tools/ralph-wiggum/*.sh
```

## Usage

### Meta-Orchestrator (Analyse automatique)

Le meta-orchestrator analyse tout le projet et génère automatiquement les queues de tâches:

```bash
cd tools/ralph-wiggum

# Analyse complète + génération de tâches
python3 ralph_meta_orchestrator.py

# Avec projet spécifique
python3 ralph_meta_orchestrator.py --project /path/to/veligo --output ./tasks
```

Le meta-orchestrator:
1. **Scanne** tous les fichiers (code, AO, docs)
2. **Analyse LEAN** avec le modèle le plus puissant disponible
3. **Génère** les tâches TDD + Deploy triées par WSJF
4. **Applique** les guardrails anti-loop (25 turns, 5min timeout)

### Lancer Ralph Wiggum

```bash
cd tools/ralph-wiggum

# Queue TDD (génération code)
./ralph_wiggum_veligo.sh tdd

# Queue Deploy (build + deploy)
./ralph_wiggum_veligo.sh deploy

# Les deux queues (deploy seulement si TDD OK)
./ralph_wiggum_veligo.sh all
```

### Vérifier le LLM

```bash
./llm_worker.sh check
# ✓ LLM is available (Qwen3-Coder-30B)
```

### Générer un patch manuellement

```bash
./llm_worker.sh get tasks/T002.md
# Retourne un patch au format diff
```

## Structure des Fichiers

```
tools/ralph-wiggum/
├── ralph_wiggum_veligo.sh   # Script principal orchestrateur
├── llm_worker.sh            # Interface avec Qwen3-Coder
├── README.md                # Ce fichier
├── tasks/                   # 22 tâches (T001-T014 + D001-D008)
│   ├── T001.md             # Docker Setup
│   ├── T002.md             # gRPC-Web Proxy
│   ├── ...
│   ├── D001.md             # Build Backend
│   └── D008.md             # Notify Complete
├── logs/                    # Logs d'exécution
│   └── ralph_wiggum_*.log
└── .ralph_patches/          # Historique des patches
    └── T002_123456.diff
```

## Format des Tâches

Chaque fichier task suit ce format borné:

```markdown
# Task TXXX: [TITRE CONCIS]

**Priority**: P0/P1/P2
**Time Estimate**: Xh
**WSJF Score**: X

## Success Criteria
- [ ] Critère 1 (mesurable)
- [ ] Critère 2 (mesurable)

## Actions
1. Action concrète 1
2. Action concrète 2

## Files to Create/Modify
- [ ] fichier1 (CRÉER|MODIFIER)

## Technical Notes
Notes techniques...

## Ralph Status Block
---RALPH_STATUS---
STATUS: PENDING | COMPLETE | BLOCKED
...
---END_RALPH_STATUS---
```

## Workflow

### Queue TDD (T001-T014)

```
Pour chaque task:
  1. Vérifier si STATUS: COMPLETE → skip
  2. Lire le fichier task
  3. Boucle (max 15 itérations):
     a. Appeler llm_worker.sh get → obtenir patch
     b. Si TASK_COMPLETE → marquer et passer à la suite
     c. Appliquer le patch (patch -p1)
     d. Lancer les tests appropriés
     e. Si tests OK → task complete
     f. Sinon → nouvelle itération
  4. Si max itérations → marquer BLOCKED
```

### Queue Deploy (D001-D008)

```
D001: cargo build --release
D002: ADAPTER=static npm run build
D003: veligo deploy rsync --env=staging
D004: npx playwright test (sur staging)
  └─ Si échec → STOP (pas de deploy prod)
D005: veligo deploy blue-green --env=prod
D006: npx playwright test --grep="@smoke" (sur prod)
  └─ Si échec → ROLLBACK
D007: curl health endpoints
D008: git tag + notification
```

## Ordre d'Exécution (WSJF)

### Queue TDD

| Task | WSJF | Priority | Description |
|------|------|----------|-------------|
| T001 | 9.5 | P0 | Docker Setup |
| T006 | 9.0 | P0 | RLS Security Fix |
| T002 | 9.0 | P0 | gRPC-Web Proxy |
| T003 | 8.5 | P0 | Security Headers |
| T004 | 8.0 | P1 | Rate Limiting |
| T005 | 8.0 | P0 | DB Migrations |
| T007 | 7.5 | P1 | Auth Service |
| T008 | 7.5 | P1 | Booking Service |
| T009 | 7.0 | P1 | Subscription Service |
| T010 | 6.5 | P2 | MFA UI |
| T011 | 6.0 | P2 | Dashboard UI |
| T012 | 6.0 | P2 | Station Map |
| T013 | 5.5 | P2 | E2E Auth Tests |
| T014 | 5.5 | P2 | E2E Booking Tests |

### Queue Deploy

| Task | WSJF | Description |
|------|------|-------------|
| D001 | 9.0 | Build Backend |
| D002 | 9.0 | Build Frontend |
| D003 | 8.5 | Deploy Staging |
| D004 | 8.5 | E2E Staging |
| D005 | 8.0 | Deploy Prod |
| D006 | 8.0 | Smoke Prod |
| D007 | 7.5 | Verify Health |
| D008 | 5.0 | Notify |

## Configuration

### Variables d'Environnement

```bash
# Local LLM (llama-server)
export LLM_URL="http://127.0.0.1:8000/v1/completions"
export LLM_MODEL="Qwen3-Coder-30B"
export MAX_TOKENS=8000

# Optionnel
export MAX_ITERATIONS=15        # Max itérations par task
export MAX_WAIT_SECONDS=600     # Timeout par task
```

### Accès aux Modèles (PAS d'API calls!)

| Tier | Model | Accès | Coût |
|------|-------|-------|------|
| TIER1 | Claude Opus 4.5 | `claude` CLI (Claude Code headless) | Claude Max abo |
| TIER2 | GLM-4-Plus | `opencode` CLI | Gratuit |
| TIER2 | Minimax | `opencode` CLI | Gratuit |
| TIER3 | Qwen3-Coder | llama-server :8000 | Local |
| TIER3 | DeepSeek-V3 | llama-server :8001 | Local |

**Fallback Chain:**
- TIER1 (Complex): opus → glm → deepseek
- TIER2 (Medium): glm → minimax → local
- TIER3 (Simple): local → deepseek → minimax

## Dépannage

### LLM non disponible

```bash
# Vérifier le port
curl http://127.0.0.1:8000/v1/models

# Lancer le serveur
llama-server -m ~/models/Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf \
    --port 8000 -c 65536 -ngl 99 &
```

### Patches échouent

```bash
# Voir le dernier patch
cat .ralph_patches/last_patch.diff

# Logs Ralph Wiggum
tail -100 logs/ralph_wiggum_*.log

# Git status
git status
git diff
```

### Tests échouent

```bash
# Backend tests
cd veligo-platform/backend
cargo test --lib 2>&1 | tail -50

# E2E tests
cd veligo-platform/frontend
npx playwright test --debug
```

## Intégration avec Veligo CLI

Ralph Wiggum s'intègre avec le CLI Veligo existant:

```bash
# Utiliser les commandes veligo pour le deploy
veligo cicd pipeline    # Pipeline complet
veligo deploy rsync     # Deploy direct
veligo test e2e         # Tests E2E
```

## Références

- **CLAUDE.md**: Configuration projet Veligo
- **llama-ctl.sh**: Contrôle llama-server
- **ralph_batch.py**: Orchestrateur Python (alternative)
- **ralph_rag.py**: Système RAG local

---

**Last Updated**: 2026-01-12
**Version**: 1.0.0
**Model**: Qwen3-Coder-30B-A3B-Instruct
