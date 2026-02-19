# RLM - LEAN Requirements Manager
## Spécification Complète v2.2 (2026-01-15)

**Date**: 2026-01-15
**Auteur**: Équipe Popinz + Claude Opus 4.5
**Version**: 2.2 (Multi-LLM Architecture + Build/Deploy split + E2E/Perf/Chaos)

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
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│                                         RLM SYSTEM                                         │
├────────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                            │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                           RLM BRAIN (Orchestrateur)                                │    │
│   │   LLM: Claude Opus 4.5 via claude CLI                                               │    │
│   │   Rôle: Vision + Valeur (WSJF), cartographie repo, contrats, DoD, tags de risque    │    │
│   │   Sub-agents: Qwen 30B (local) via opencode pour lectures ciblées / analyses rapides │   │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │                                                        │
│                                   ▼                                                        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                               backlog_tasks.json                                   │    │
│   │   Tasks atomiques + contrat + DoD + scope + tags (perf-risk, security, …)          │    │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │                                                        │
│                                   ▼                                                        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                          WIGGUM TDD (Build / Implémentation)                       │    │
│   │   LLM: MiniMax M2.1 via opencode                                                    │    │
│   │   Mode: Pools // (10–50) + décomposition fractale si scope trop large               │    │
│   │   Cycle: RED → GREEN → VERIFY → (DONE ou SPLIT)                                     │    │
│   │   Aide contexte: RLM local (scopé) = locate/summarize sur dossiers fournis          │    │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │ patch + tests OK                                      │
│                                   ▼                                                        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                            ADVERSARIAL LLM (Quality Gate)                           │    │
│   │   Fast: regex + policy                                                               │    │
│   │   Deep: Qwen 30B (local) pour red-team / sécurité / contournements / incomplet      │    │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │ OK                           │ KO                     │
│                                   ▼                              └───────────────┐        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                             GIT COMMIT + HOOKS LOCAUX                               │    │
│   │   pre-commit: format/lint + fail-on-stubs (lean)                                    │    │
│   │   commit-msg: task id obligatoire                                                   │    │
│   │   post-commit: écrit l'état (sha, diff_hash)                                        │    │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │                                                        │
│                                   ▼                                                        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                              deploy_backlog.json                                     │    │
│   │   1 tâche = 1 commit/artefact, déploiement séquentiel (staging puis prod)           │    │
│   └───────────────────────────────┬───────────────────────────────────────────────────┘    │
│                                   │                                                        │
│                                   ▼                                                        │
│   ┌───────────────────────────────────────────────────────────────────────────────────┐    │
│   │                           WIGGUM DEPLOY (Release / CI-CD CLI)                       │    │
│   │   Déploie une par une via CLI projet: staging → E2E → perf-smoke → chaos (opt)      │    │
│   │   Puis prod (blue/green/canary) → smoke/journey → perf-smoke (opt)                  │    │
│   │   Si échec: rollback + evidence pack + retour Wiggum TDD                             │    │
│   └───────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---


## 2. LLM Agents

### 2.1 Tableau des Agents

| Agent | LLM | Outil | Responsabilité | Scope | Coût |
|-------|-----|-------|----------------|-------|------|
| **RLM Brain** | Claude Opus 4.5 | `claude` CLI | Vision + Valeur, cartographie repo, contrats, DoD, scoring WSJF, génération de tasks | Repo complet | $$$ |
| **RLM local (helper)** | GLM-4.7-Flash (local) | `opencode` + `mlx_lm.server` | `locate/summarize` ciblés (conventions, exemples, points d'extension) | Dossiers / fichiers explicités par la task | Local |
| **Wiggum TDD (Build)** | MiniMax M2.1 | `opencode` | Implémentation TDD en //, décomposition fractale, génération de sous-tasks si nécessaire | Périmètre borné par task | $ |
| **Adversarial** | GLM-4.7-Flash (local) | `opencode` + `mlx_lm.server` | Gate qualité: bypass, incomplet, patterns dangereux, sécurité | Diff + fichiers touchés | Local |
| **Wiggum Deploy (Release)** | MiniMax M2.1 (ou LLM low-cost) | Shell + CLI CI/CD projet | Déploiement séquentiel, Playwright E2E/journey, perf-smoke, chaos (opt), rollback + evidence pack | Environnements (staging/prod) | $ |

---

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

### 2.3 Configuration GLM-4.7-Flash (Local via mlx_lm)

```bash
# Télécharger le modèle (une fois)
huggingface-cli download mlx-community/GLM-4.7-Flash-4bit --local-dir ~/models/GLM-4.7-Flash-4bit

# Démarrer mlx_lm server (API OpenAI-compatible)
python -m mlx_lm.server --model mlx-community/GLM-4.7-Flash-4bit --port 8002

# Utiliser via opencode
opencode run -m local/glm "prompt"

# Ou directement mlx_lm generate (sans tools)
python -m mlx_lm generate --model ~/models/GLM-4.7-Flash-4bit --prompt "prompt" -m 2048
```

**Performances (M5 32GB)**: 43 tok/s génération, ~800 tok/s prefill

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

### 4.3 Cycle TDD

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

### 4.8 Fractal / Décomposition (anti-code partiel)

**Objectif**: éliminer structurellement le *code partiel* (routes/actions manquantes, stubs, TODO).

**Règle d'or**: un Wiggum ne “livre” pas une feature partielle.
- Si la task est *trop large* → il **découpe** en sous-tasks et s'arrête.
- Exception unique: livrer un **scaffolding** explicitement identifié (contrat + tests rouges + backlog), jamais présenté comme “DONE”.

**Seuils de “task trop large” (déclencheur de split)**:
- > 3–5 fichiers “cœur” (hors tests/docs),
- > 200–400 LOC net (hors tests),
- > 1 domaine supplémentaire (ex: DB + API + UI),
- > 10 items homogènes sans test de complétude (ex: 30 routes).

**Sortie attendue lors d'un split**:
- une liste de sous-tasks atomiques (id, description, files, DoD),
- dépendances explicites (task A avant B),
- tags de risque (ex: `perf-risk`, `security`, `migration`).

### 4.9 Contrats & tests de complétude

Pour les tâches “inventaire” (routes/actions/handlers), le Brain fournit un inventaire canonique.
Le Wiggum ajoute / maintient un **test de complétude** qui rend l'oubli impossible.

Exemples de complétude:
- “Toutes les routes listées doivent être enregistrées dans le routeur”
- “Chaque route legacy doit avoir une RPC / action correspondante”
- “Aucun `TODO` / `NotImplemented` dans le diff”

### 4.10 Usage du RLM par Wiggum (contexte ciblé)

Le Wiggum peut utiliser le RLM local **uniquement** en mode “précision”, scopé par la task.

Primitives recommandées (implémentation libre):
- `locate(query, scope=[paths...])` → chemins + extraits + conventions repérées
- `summarize(files=[...], goal)` → résumé court + “where to edit”

**Interdit**: re-scanner tout le repo, redéfinir l'architecture, ou changer le contrat.

### 4.11 Isolation, locks, et writes atomiques

Pour éviter la corruption et les conflits:
- Un worker opère dans un **workspace isolé** (git worktree ou répertoire temporaire).
- Verrouillage au niveau task + (optionnel) verrouillage de chemins (`files[]`) pour éviter collisions.
- Écritures JSON en **write atomique** (temp file + rename) + file lock.

**Option recommandée** (si charge élevée): migrer l'état des tasks vers SQLite (transactions + locks + audit).

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


### 5.7 Cycles après rejet (Adversarial / Gate LLM)

**But**: garantir qu’un rejet produit un **nouveau cycle** au bon endroit, sans ambiguïté ni boucle infinie.

#### 5.7.1 Contrat de sortie du Gate

Tout rejet doit produire :
- un `verdict` normalisé (ex: `ADVERSARIAL_REJECTED`),
- une liste `issues[]` actionnable (fichier/ligne/pattern/message),
- un `evidence_pack_ref` (ou artefacts inline si léger),
- un `next_owner` unique: `wiggum_tdd|wiggum_deploy|brain`.

#### 5.7.2 Routage par défaut

- **Si `approved=false`** → retour **Wiggum TDD** (corriger code/tests) :
  - incrémenter `adversarial_attempts`,
  - marquer la task `status=adversarial_rejected`,
  - attacher `issues[]` à la task (et au log),
  - notifier `wiggum_tdd` (pool) avec task id + issues + evidence.

#### 5.7.3 Anti-thrash / escalade

- `adversarial_rejects_max = 2` par task.
- Au-delà (ou si les motifs se répètent) → `next_owner=brain` pour re-scoping (split, changement de stratégie, complétude manquante).

> Règle: un rejet “scope mismatch” (contrat ambigu / trop large) doit escalader vers **Brain** plutôt que de boucler indéfiniment sur Wiggum TDD.


---

## 6. Wiggum Deploy

### 6.1 Description

Wiggum Deploy exécute la **validation d'intégration** et le **déploiement séquentiel** des tâches déjà committées.

Principes:
- **1 task = 1 commit = 1 déploiement** (diagnostic clair).
- **Staging d'abord**, puis **Production** (blue/green ou canary).
- **Playwright** comme source de vérité E2E/journey.
- **Gates optionnels** selon tags: `perf-risk` → perf-smoke, `chaos` → chaos suite.
- En cas d'échec: **rollback**, collecte d'un **evidence pack**, retour Wiggum TDD (ou incident infra si non déterministe).

### 6.2 Fichier

**Path**: `/Users/sylvain/_POPINZ/popinz-dev/rlm/wiggum_deploy.py`

### 6.3 Pipeline

```
┌────────────────────────────────────────────────────────────────────────────────────┐
│                                  WIGGUM DEPLOY PIPELINE                             │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                    │
│  deploy_backlog.json                                                                │
│        │                                                                           │
│        ▼                                                                           │
│  ┌─────────────────────┐                                                          │
│  │ 1. Verify Commit     │  SHA existe, working tree clean, task id tracée          │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 2. Build Artifact    │  Build immuable (tag = commit SHA)                       │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 3. Deploy STAGING    │  CLI projet (blue/green si dispo)                        │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 4. E2E SMOKE         │  Playwright @smoke + healthchecks                         │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐   (si tag perf-risk)                                      │
│  │ 5. PERF SMOKE        │   p95/p99 + erreurs + saturation                          │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐   (si tag journey)                                        │
│  │ 6. E2E JOURNEY       │   Playwright @journey (parcours critiques)                │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐   (option)                                                │
│  │ 7. CHAOS / TMC       │   injection fautes + journeys / monkey UI                 │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 8. Deploy PROD       │  CLI projet (blue/green/canary)                           │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 9. Verify PROD       │  smoke + health + (option perf-smoke)                     │
│  └──────────┬───────────┘                                                          │
│             │                                                                      │
│             ▼                                                                      │
│  ┌─────────────────────┐                                                          │
│  │ 10. Mark Done        │  status=PROD_OK + liens artefacts/logs/reports            │
│  └─────────────────────┘                                                          │
│                                                                                    │
│  On failure at any step: rollback + evidence pack + task->FAILED (+ retour build)  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 6.4 Playwright (E2E / Journey)

**Règles de base**:
- `@smoke`: rapide, exécuté à chaque déploiement staging.
- `@journey`: plus long, exécuté selon tags de risque ou avant prod.
- `@chaos-ui`: monkey UI / scénarios non déterministes (staging uniquement).

**Politique anti-flaky**:
- 1 retry max (`--retries=1`), trace “on-first-retry”.
- 2 échecs consécutifs = échec dur → retour Wiggum TDD avec traces/vidéos.

### 6.5 Tests de performance / montée en charge

Objectifs:
- détecter régressions de latence (p95/p99), timeouts, erreurs,
- valider que l'architecture tient les chemins critiques,
- signaler code lent (N+1, contention, serialisation, I/O).

**Deux niveaux**:
1) **Perf Smoke (gating)**: court (1–3 min) sur staging, déclenché par `perf-risk`.
2) **Load/Capacity (release train / nightly)**: plus long (10–30 min), non bloquant par task sauf régression majeure.

**Budgets (exemple de DoD perf)**:
- p95 < X ms, p99 < Y ms
- error rate < Z%
- absence de timeouts
- saturation sous contrôle (CPU/mem/pool DB)

> Recommandation: générer la charge via un outil HTTP dédié (k6/Gatling/Artillery) plutôt que via Playwright, et conserver Playwright pour la vérité fonctionnelle.

### 6.6 Chaos Monkey / TMC

**But**: valider la résilience (dégradation contrôlée, retries, timeouts, rollback).

Deux familles:
- **Chaos infra**: latence, erreurs 5xx, coupure réseau, kill d'instance/service (staging).
- **Chaos UI**: monkey testing de l'interface (staging), en suite séparée.

TMC = “tests complémentaires” configurable (ex: chaos + perf + checks SLO). La spec impose uniquement:
- exécution **hors prod** par défaut,
- rapport + evidence pack systématiques.

### 6.7 Rollback & evidence pack

En cas d'échec (E2E/perf/chaos/health):
- rollback staging/prod (selon étape),
- capture evidence pack:
  - rapport Playwright (traces/vidéos/screenshots),
  - logs applicatifs,
  - métriques (CPU/mem/DB/pools),
  - rapport perf (latences/erreurs) si concerné,
  - commande CLI exécutée + exit codes.

Le retour Wiggum TDD doit inclure ces éléments (ou pointeurs vers eux) afin de corriger sans “deviner”.

### 6.8 Commandes CLI

```bash
# Une tâche du backlog deploy
ppz wiggum deploy --once

# Mode daemon
ppz wiggum deploy --daemon

# Déploiement staging uniquement
ppz wiggum deploy --once --env staging

# Avec suites explicites
ppz wiggum deploy --once --e2e smoke
ppz wiggum deploy --once --e2e smoke,journey
ppz wiggum deploy --once --perf-smoke
ppz wiggum deploy --once --chaos

# Status
ppz wiggum deploy status
```


### 6.9 Gestion des échecs, cycles et ownership

Cette section définit **où** le système “cycle” lorsqu’un gate rejette, lorsqu’un test échoue, ou lorsqu’un incident survient (staging/prod/perf/chaos).

#### 6.9.1 Règles d’ownership (qui corrige quoi)

- **Wiggum TDD**: corrige **le code** et ajoute/renforce les tests jusqu’à passer les gates.
- **Wiggum Deploy**: exécute **la release** (deploy/rollback/rerun), collecte les preuves, *ne modifie pas le code*.
- **Brain RLM**: intervient pour **re-scoper** (split), **changer de stratégie** (release train, feature flags), ou traiter un problème **architecture/capacité**.

> Heuristique: *si un correctif nécessite un diff de code → Wiggum TDD.*  
> *Si un correctif nécessite un rollback / rerun / paramétrage env → Wiggum Deploy.*  
> *Si le problème dépasse la task (design/architecture/découpage) → Brain.*

#### 6.9.2 Verdicts normalisés

Tout échec dans le pipeline Deploy produit un verdict (exemples) :
- `STAGING_DEPLOY_FAILED`
- `STAGING_E2E_SMOKE_FAILED`
- `STAGING_E2E_JOURNEY_FAILED`
- `PERF_SMOKE_FAILED`
- `LOAD_CAPACITY_FAILED`
- `CHAOS_FAILED`
- `PROD_DEPLOY_FAILED`
- `PROD_SMOKE_FAILED`
- `PROD_INCIDENT`

Chaque verdict doit fournir :
- `last_failed_step`,
- `attempt_count` par gate,
- `evidence_pack_ref`,
- `next_owner`.

#### 6.9.3 Table de routage (où ça cycle)

| Événement | Action immédiate | Next owner | Cycle attendu |
|---|---|---|---|
| **Deploy staging échoue** | 1 retry si transient, sinon stop + evidence | `wiggum_deploy` ou `wiggum_tdd` | rerun si env ; sinon fix code/infra-as-code |
| **E2E smoke staging échoue** | collect traces + logs | `wiggum_tdd` (par défaut) | fix + tests non-régression |
| **E2E journey staging échoue** | collect traces + logs | `wiggum_tdd` ou `wiggum_deploy` | fix produit vs env seed/flags |
| **Perf smoke échoue** | rerun 1× (warmup) | `wiggum_tdd` ou `brain` | optimisation locale ; escalade si limite architecture |
| **Load/Capacity échoue** | classify régression vs plafond | `wiggum_tdd` ou `brain` | fix régression ; sinon tasks architecture |
| **Chaos/TMC échoue** | collect fautes injectées + traces | `wiggum_tdd` ou `brain` | durcissement résilience ; patterns d’archi si nécessaire |
| **Prod échoue / incident** | **rollback immédiat** + bundle incident | `wiggum_tdd` (hotfix) puis `brain` si répétition | hotfix + test ; re-scope/release train si pattern |

**Routage par défaut**:
- échec *fonctionnel* (E2E, erreurs 5xx, logique) → **Wiggum TDD**,
- échec *pipeline/env* (CLI, creds, seed) → **Wiggum Deploy**,
- échec *systémique* (capacité, architecture, stratégie de release) → **Brain**.

#### 6.9.4 Anti-thrash (limiter les boucles)

Seuils recommandés par task (ajustables) :
- `tdd_attempts_max = 3`
- `staging_e2e_fail_max = 2` (Playwright: 1 retry max)
- `perf_smoke_fail_max = 2` (avec warmup)
- `prod_fail_max = 1` (échec prod → freeze de la task)
- `adversarial_rejects_max = 2` (défini en 5.7)

Au-delà des seuils:
- marquer `status=blocked`,
- escalader `next_owner=brain`,
- attacher l’evidence pack consolidé.

#### 6.9.5 Gestion des incidents prod

En prod, l’objectif est la **réduction du blast radius** :
1) **Rollback** (blue/green/canary) dès détection `PROD_*_FAILED`.
2) Marquer `rolled_back=true` + conserver `rollback_target`.
3) Générer un `incident_bundle` (logs, métriques, traces, timestamps, commit SHA).
4) Ouvrir une task **hotfix** vers Wiggum TDD (DoD: test de non-régression + smoke).
5) Si 2 incidents similaires sur une fenêtre courte → escalade Brain (stratégie de release, découpage, feature flag).

#### 6.9.6 Performance insuffisante (régression vs plafond)

- **Régression** (vs baseline): route vers **Wiggum TDD** (optimisation + éventuel index/cache + tests/perf ciblés).
- **Plafond d’architecture** (saturation DB/pool/CPU): escalade **Brain** pour créer des tasks d’architecture (caching, queueing, pooling, indexing, partitioning, etc.) et/ou bascule en “release train”.

#### 6.9.7 Notifications

Tout changement d’état (reject/fail/rollback/escalation) notifie le **propriétaire** (`next_owner`) via webhook (Slack/Teams/HTTP).

Payload minimal :
```json
{
  "task_id": "rust-security-0001-auth.rs",
  "stage": "adversarial|tdd|deploy",
  "verdict": "STAGING_E2E_SMOKE_FAILED",
  "next_owner": "wiggum_tdd",
  "attempts": {"tdd": 1, "adversarial": 1, "staging_e2e": 2},
  "last_failed_step": "E2E_SMOKE",
  "evidence_pack_ref": "s3://.../task_id/run_2026-01-15/",
  "summary": "Login journey fails: 500 on /api/auth/login (trace attached)"
}
```

**Règle**: le système doit **dédupliquer** les notifications (pas de spam) et inclure un lien direct vers l’evidence pack.


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
      "status": "pending|locked|tdd_in_progress|tdd_success|adversarial_rejected|merged|queued_for_deploy|deploying|prod_ok|blocked|failed",
      "locked_by": null,
      "lock_expires_at": null,
      "attempts": {"tdd": 0, "adversarial": 0, "staging_e2e": 0, "perf_smoke": 0, "prod": 0},
      "last_verdict": null,
      "commit_sha": null,
      "artifact_id": null,
      "evidence_pack_ref": null,
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

**Status possibles (recommandé)**:

| Status | Description |
|--------|-------------|
| `pending` | En attente de traitement |
| `locked` | Réservée par un worker (lock actif) |
| `tdd_in_progress` | Wiggum TDD en cours |
| `tdd_success` | Tests locaux OK (pré-gate) |
| `adversarial_rejected` | Rejeté par le gate (retour TDD) |
| `merged` | Commit réalisé + hooks OK |
| `queued_for_deploy` | Ajoutée au deploy backlog |
| `deploying` | Déploiement en cours |
| `prod_ok` | Déployée en prod avec validations OK |
| `blocked` | Trop d’échecs → escalade Brain |
| `failed` | Échec terminal (abandonné / manual) |

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
      "status": "pending|deploying|staging_ok|prod_ok|failed|rolled_back|blocked",
      "attempts": {"staging_deploy": 0, "e2e_smoke": 0, "e2e_journey": 0, "perf_smoke": 0, "load": 0, "chaos": 0, "prod_deploy": 0},
      "last_failed_step": null,
      "verdict": null,
      "evidence_pack_ref": null,
      "rolled_back": false,
      "rollback_target": null,
      "next_owner": null,
      "deployed_at": null,
      "environment": null
    }
  ]
}
```

**Status possibles (deploy)**:

| Status | Description |
|--------|-------------|
| `pending` | En attente de déploiement |
| `deploying` | Déploiement en cours (staging ou prod) |
| `staging_ok` | Staging OK (smoke/perf/journey selon tags) |
| `prod_ok` | Prod OK (smoke/journey/perf selon tags) |
| `rolled_back` | Rollback effectué (prod ou staging) |
| `blocked` | Trop d’échecs → escalade Brain |
| `failed` | Échec terminal / intervention manuelle |

---

### 7.3 Store d’état unifié (recommandé)

Pour industrialiser les cycles (rejets, retries, escalades, rollback) et éviter la corruption JSON sous concurrence, le système doit idéalement stocker l’état dans un store transactionnel (ex: **SQLite**).

**Bénéfices**:
- transactions + locks (évite courses),
- audit trail (qui a fait quoi, quand),
- métriques fiables (attempts, rejects, rollbacks),
- routage automatique (`next_owner`) sans ambiguïté.

**Fallback** (si JSON conservé): write atomique (temp + rename) + file lock + champ `lock_expires_at` obligatoire.


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

### 8.3 Git hooks locaux (pré/post commit)

Objectif: renforcer la **complétude** et la **traçabilité** sans ralentir le cycle.

**Principes**:
- Hooks **LEAN**: ne pas exécuter de suites longues (E2E/charge) en local.
- Les hooks doivent échouer vite sur: format, lint, stubs, absence d'id task.

#### 8.3.1 pre-commit (lean)
- format / lint (selon stack),
- fail-on-stubs: `TODO`, `FIXME`, `NotImplemented`, `todo!()`, `unimplemented!()`, `test.skip`, `describe.skip`.

#### 8.3.2 commit-msg (traçabilité)
- exige un identifiant de task (ex: `TASK-123`, ou id interne `security-0566-...`).

#### 8.3.3 post-commit (state)
- écrit `commit_sha`, `diff_hash`, `task_id` dans le store d'état (JSON atomique ou SQLite recommandé).

> Les suites Playwright, perf, chaos et autres TMC restent exécutées par **Wiggum Deploy** en staging.

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
| **mlx-lm** | `pip install mlx-lm>=0.30.3` | GLM-4.7-Flash local (Apple Silicon) |

### 10.2 API Keys

| Service | Variable | Fichier |
|---------|----------|---------|
| **MiniMax** | - | `~/.config/opencode/opencode.json` |
| **Anthropic** | `ANTHROPIC_API_KEY` | `~/.zshrc` |

### 10.3 Serveur LLM Local (Optionnel)

```bash
# Télécharger GLM-4.7-Flash (4-bit, rapide)
huggingface-cli download mlx-community/GLM-4.7-Flash-4bit --local-dir ~/models/GLM-4.7-Flash-4bit

# Démarrer mlx_lm server
python -m mlx_lm.server --model mlx-community/GLM-4.7-Flash-4bit --port 8002

# Vérifier
curl http://localhost:8002/v1/models
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

Objectif: piloter le système (LEAN) avec des métriques actionnables, pas décoratives.

### 12.1 Productivité & Qualité (build)

- **Cycle time**: `picked → merged`
- **First-pass success rate** (TDD SUCCESS sans retour adversarial)
- **Retry rate** (par cause: tests, compilation, lint, flake)
- **Churn** (LOC modifiées / task)
- **Timeout rate**
- **Adversarial reject rate** + motifs

### 12.2 Intégration & Déploiement (release)

- **Deploy success rate** (staging/prod)
- **E2E smoke pass rate** / **journey pass rate**
- **Flaky rate Playwright** (échecs résolus par retry)
- **Rollback count** et causes
- **MTTR** (temps moyen de correction après échec staging)

### 12.3 Performance / Charge / Résilience

- **p50/p95/p99 latences** (par scénario)
- **Erreur / timeout rate**
- **Débit** (req/s ou transactions/s)
- **Saturation** (CPU, mémoire, pool DB, queue depth)
- **Drift** (augmentation latence au plateau)
- **Chaos outcomes** (dégradation contrôlée vs panne)

### 12.4 Session 2026-01-14 (exemple)

| Métrique | Valeur |
|----------|--------|
| **Tasks analysées** | 588 |
| **Workers** | 10 |
| **Timeout** | 1 heure |
| **Taux de succès** | ~70% |
| **Temps moyen/tâche** | 1-3 minutes |

### 12.5 Historique (exemple)

| Date | Workers | Timeout | Succès | Timeouts |
|------|---------|---------|--------|----------|
| 2026-01-14 09:00 | 50 | 5 min | 80 (26%) | 215 (72%) |
| 2026-01-14 10:00 | 10 | 1h | 412 (70%) | 176 (30%) |

---

## 13. Roadmap

### 13.1 Améliorations prioritaires (stabilité)

- [ ] État transactionnel (SQLite) + locks + audit trail (remplacer JSON si > 10 workers)
- [ ] Writes atomiques pour backlogs JSON (temp + rename) si JSON conservé
- [ ] Workspaces isolés (git worktree) + verrouillage de chemins pour éviter collisions
- [ ] Completeness gates (routes/actions/RPC) pour éliminer le code partiel
- [ ] Politique anti-flaky Playwright (retry unique, traces, classification flake vs régression)

### 13.2 Qualité système (release)

- [ ] Suites Playwright taggées `@smoke/@journey/@chaos-ui` + rapports centralisés
- [ ] Evidence pack standardisé (logs + traces + métriques + perf report)
- [ ] Rollback automatique (staging/prod) + policy d'escalade après N échecs
- [ ] Intégration SLO/alerting (Grafana/Prometheus ou équivalent)

### 13.3 Performance / Charge / Résilience

- [ ] Perf smoke gating sur `perf-risk`
- [ ] Tests de montée en charge (nightly / release train) + baselines versionnées
- [ ] Scénarios chaos infra (staging) + journeys ciblés
- [ ] Profiling/tracing (OpenTelemetry) déclenchable automatiquement sur régression perf

### 13.4 Extensions

- [ ] Support multi-repo
- [ ] Agent spécialisé Rust (cargo + clippy)
- [ ] Agent spécialisé Frontend (ESLint + Prettier)
- [ ] Intégration GitHub Actions / GitLab CI (selon stack)
- [ ] Webhook notifications (Slack)

---

