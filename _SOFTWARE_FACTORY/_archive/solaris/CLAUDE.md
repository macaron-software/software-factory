# Solaris Design System - Copilot Instructions
> Version simplifiée - 9 Janvier 2026

## 🔌 MCP SOLARIS - SOURCE DE VÉRITÉ

**Toutes les informations détaillées sont dans le MCP Solaris. UTILISER LE MCP !**

### Outils disponibles
| Outil | Usage |
|-------|-------|
| `solaris_component` | Détails d'un composant (variants, properties) |
| `solaris_variant` | Styles exacts d'un variant (borderRadius, padding, dimensions) |
| `solaris_wcag` | Pattern WCAG pour un type de composant |
| `solaris_knowledge` | Query la knowledge base |
| `solaris_validation` | Statut de validation d'un composant |
| `solaris_grep` | Recherche dans CSS/HTML générés |
| `solaris_stats` | Statistiques globales |
| `solaris_list_components` | Liste des composants disponibles |

### Exemples d'utilisation
```
# Obtenir borderRadius d'un bouton depuis Figma
solaris_variant(component="button", properties={"Size": "Small", "Style": "Primary"})
→ {"borderRadius": "8px", "paddingLeft": "8px", ...}

# Obtenir le pattern WCAG d'un accordion
solaris_wcag(pattern="accordion")
→ {keyboard: {Enter: "toggle"}, states: {...}, ...}

# Statistiques globales
solaris_stats()
→ {component_families: 41, validation_pass_rate: "81.3%", ...}
```

---

## ⚠️ RÈGLES ABSOLUES (3 règles)

### RÈGLE #0 - JAMAIS DE VALEURS HARDCODÉES

**TOUTES les valeurs attendues DOIVENT être lues depuis les extracts Figma ou le MCP.**

```javascript
// ❌ INTERDIT - Valeurs hardcodées
const expected = { borderRadius: '4px' }; // D'où vient ce 4px ???

// ✅ OBLIGATOIRE - Via MCP ou lecture Figma
const figmaData = await solaris_variant({component: "button", properties: {Size: "Small"}});
const expected = { borderRadius: figmaData.styles.borderRadius };
```

### RÈGLE #1 - SOLARIS CLI OBLIGATOIRE

**TOUTES les opérations passent par `./solaris` CLI - AUCUNE EXCEPTION**

```bash
./solaris                    # Full pipeline automatique
./solaris validate           # Validation seule
./solaris commit -m "msg"    # Commit avec validation

# ❌ INTERDIT
git commit --no-verify       # JAMAIS
node tools/generate-*.js     # Utiliser ./solaris
```

### RÈGLE #2 - 0 HALLUCINATION

**Tout élément mentionné DOIT avoir un Node ID Figma valide ou être vérifié via MCP.**

```javascript
// ✅ CORRECT - Vérifier via MCP avant d'affirmer
const component = await solaris_component({component: "button"});
// → component.variants contient les vraies données

// ❌ INTERDIT - Inventer des valeurs
"Le bouton a un borderRadius de 4px" // Sans vérification
```

---

## 🎯 Architecture Simplifiée

### Structure du Projet
```
/Users/sylvain/_LAPOSTE/_SD3/
├── design-system/
│   ├── figma-data/          # Extracts Figma (source de vérité)
│   ├── knowledge/           # Knowledge base (WCAG, patterns)
│   └── libs/ui/src/styles/  # CSS/SCSS générés
├── generated-pages/         # HTML générés
├── tools/                   # Scripts d'automatisation
└── mcp_solaris_server.py    # Serveur MCP
```

### Fichiers Figma
| Fichier | File Key |
|---------|----------|
| Components | `fLrViJ3v412OR0n2XxrWco` |
| Assets | `CcEr1eOfvEBg8S3xa7R6Qj` |
| Foundations | `ejXhAdPYb6roElBpIh8y1q` |

### Statistiques (via `solaris_stats`)
- **41 familles** de composants
- **~4600 variants** au total
- **81%+ validation pass rate**

---

## 📚 Knowledge Base

La knowledge base est dans `design-system/knowledge/` et accessible via `solaris_knowledge`.

| Catégorie | Contenu |
|-----------|---------|
| `1-semantic-html` | Mapping Figma → HTML tags |
| `2-wcag-patterns` | Patterns accessibilité (accordion, button, tabs...) |
| `3-ds-best-practices` | Best practices Material, Carbon, Spectrum |
| `4-interactive-behaviors` | Keyboard, focus, state machines |

---

## 🔧 Commandes Principales

```bash
# Pipeline complet
./solaris

# Validation
./solaris validate
./solaris validate Button

# Git (avec validation)
./solaris commit -m "message"
./solaris push

# Ralph (agent autonome)
./solaris ralph
```

---

## 🧠 Architecture LRM (Recursive Language Model)

> Basé sur MIT CSAIL arXiv:2512.24601

### Vue d'ensemble

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 LRM BRAIN (Claude Opus 4.5 headless via claude CLI)         │
│  - Analyse VISION (structure, patterns)                         │
│  - Analyse LEAN (dépendances, gaps)                             │
│  - Génère backlog priorisé → backlog_solaris.json               │
│                                                                 │
│  MCP Tools: solaris_component, solaris_variant, solaris_wcag,   │
│             solaris_validation, solaris_grep, solaris_stats     │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  🤖 SUB-AGENTS (Qwen3-30B local via llama-cpp port 8002)        │
│  - Récursion pour analyses détaillées                           │
│  - Accès direct aux MCP tools                                   │
│  - Context: 32768 tokens                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔧 WIGGUM TDD + FRACTAL (MiniMax M2.1 × 50 parallèle)          │
│  - Dépile backlog_solaris.json                                  │
│  - MODE FRACTAL: décompose tâches trop larges (MIT RLM)         │
│  - Génère code via MiniMax Coding Plan (1000 prompts/5h)        │
│  - Fallback: Qwen3-30B local si rate limit                      │
│  - Contrôle Adversarial à chaque itération                      │
│  - Max 10 retries si SLOP détecté                               │
│  - Validation via ./solaris validate                            │
│  → Résultats: completed_solaris.json                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔴 ADVERSARIAL AGENT (intégré)                                 │
│  Détecte SLOP, FAKE, HALLUCINATIONS:                            │
│  - test.skip (+10 pts) | @ts-ignore (+5 pts)                    │
│  - TODO/STUB (+4 pts) | ... code tronqué (+3 pts)               │
│  - OVERCONFIDENT: "ensures", "perfect", "100%" (+3-5 pts)       │
│  - Valeurs hardcodées sans source Figma (+2-3 pts)              │
│  → Score >= 5 = REJET + retry avec feedback                     │
└─────────────────────────────────────────────────────────────────┘
```

### 🔀 Mode FRACTAL (Nouveau)

Le mode FRACTAL décompose automatiquement les tâches trop larges pour éviter le code partiel.

**Seuils de décomposition:**
| Métrique | Seuil | Action |
|----------|-------|--------|
| Composants | > 3 | Décomposer |
| Critères d'acceptation | > 5 | Décomposer |
| Fichiers touchés | > 5 | Décomposer |
| LOC estimées | > 200 | Décomposer |

**Règles FRACTAL:**
- Profondeur max: 3 niveaux de récursion
- Chaque sous-tâche est ATOMIQUE et INDÉPENDANTE
- Sous-tâches traitées récursivement par le même Wiggum
- Agrégation des résultats à la fin

```
┌─────────────────────────────────────────────────────────────────┐
│  TÂCHE PARENTE (trop large)                                     │
│  - 6 composants, 8 critères                                     │
│                         │                                       │
│          ┌──────────────┼──────────────┐                       │
│          ▼              ▼              ▼                        │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│   │ Sous-tâche 1│ │ Sous-tâche 2│ │ Sous-tâche 3│              │
│   │ 2 composants│ │ 2 composants│ │ 2 composants│              │
│   └──────┬──────┘ └──────┬──────┘ └──────┬──────┘              │
│          ▼              ▼              ▼                        │
│      ATOMIQUE       ATOMIQUE       ATOMIQUE                     │
│      (traitement)   (traitement)   (traitement)                 │
│          │              │              │                        │
│          └──────────────┼──────────────┘                       │
│                         ▼                                       │
│                   AGRÉGATION                                    │
│              (completed/partial)                                │
└─────────────────────────────────────────────────────────────────┘
```

### Configuration LLM

| Rôle | Modèle | Provider | Usage |
|------|--------|----------|-------|
| Brain | Claude Opus 4.5 | `claude -p --model claude-opus-4-5-20251101` | Analyse lourde, vision, LEAN |
| Sub-agents | Qwen3-30B-A3B | `localhost:8002` (llama-cpp) | Récursion, MCP tools (32K ctx) |
| Wiggum | MiniMax M2.1 | API directe + opencode fallback | Génération code (1h timeout) |
| Fallback | Qwen3-30B-A3B | `localhost:8002` | Si MiniMax rate limité |

### Fichiers LRM

| Fichier | Rôle |
|---------|------|
| `tools/lrm/run.py` | Orchestrateur (brain + wiggum) |
| `tools/lrm/lrm_brain_solaris.py` | Brain principal (Claude Opus 4.5) |
| `tools/lrm/wiggum_solaris.py` | Agent itératif (MiniMax M2.1) |
| `tools/lrm/run_parallel_wiggums.py` | Orchestrateur parallèle (50 workers) |
| `tools/lrm/backlog_solaris.json` | Backlog généré par Brain |
| `tools/lrm/completed_solaris.json` | Tâches complétées |

### Commandes LRM

```bash
# 1. Lancer le Brain seul (génère le backlog)
python3 tools/lrm/run.py brain --question "trouve les routes non implémentées"

# 2. Lancer les Wiggums en parallèle (50 workers)
python3 tools/lrm/run.py wiggum --workers 50

# 3. Lancer le pipeline complet (Brain + Wiggums)
python3 tools/lrm/run.py all --question "..." --workers 50

# Via solaris CLI
./solaris lrm --question "..."
./solaris wiggum --workers 50
```

### Règles Adversarial

| Pattern | Score | Action |
|---------|-------|--------|
| `test.skip` | +10 | REJET - tests contournés |
| `@ts-ignore` | +5 | REJET - types contournés |
| `TODO/STUB` | +4 | REJET - code incomplet |
| `...` (tronqué) | +3 | REJET - code manquant |
| "ensures/perfect" | +3-5 | REJET - overconfident |
| borderRadius hardcodé | +3 | REJET - doit venir de Figma |
| Score total ≥ 5 | - | **RETRY avec feedback** |

---

## 🧪 Tests

**Tous les tests doivent lire les valeurs depuis Figma dynamiquement.**

Fichiers de test conformes :
- `test-visual-audit-v2.spec.js` ✅
- `test-accordion-real-validation.spec.js` ✅
- `test-interactivity-quick.spec.js` ✅

---

## 🤖 Workflow Recommandé

1. **Avant de coder** → Interroger le MCP pour les vraies valeurs
   ```
   solaris_variant(component="X", properties={...})
   solaris_wcag(pattern="X")
   ```

2. **Générer/Modifier** → Via `./solaris` CLI

3. **Valider** → `./solaris validate`

4. **Commiter** → `./solaris commit -m "message"`

---

## ⚠️ Anti-Patterns à Éviter

| ❌ Anti-Pattern | ✅ Solution |
|----------------|-------------|
| Valeurs hardcodées | Lire via MCP ou Figma extract |
| `git commit --no-verify` | `./solaris commit` |
| Inventer des Node IDs | Vérifier dans Figma extract |
| Deviner les patterns WCAG | `solaris_wcag(pattern="...")` |
| Scripts directs | Passer par `./solaris` |
| `test.skip` / TODO | Code complet et fonctionnel |
| "ensures", "perfect" | Preuves concrètes uniquement |
| API MiniMax directe | Utiliser opencode CLI (Coding Plan) |

---

## 📖 Documentation Complémentaire

Pour les détails techniques spécifiques, consulter le MCP ou les fichiers :
- `MCP-SOLARIS-README.md` - Configuration du MCP
- `docs/TODO-REFACTORING-V2.md` - Plan de refactoring
- `design-system/knowledge/` - Knowledge base complète
- `tools/lrm/` - Scripts LRM Brain et Wiggums

---

## 📊 Status Actuel (14 Janvier 2026)

| Métrique | Valeur |
|----------|--------|
| Composants Figma | 41 familles, ~4600 variants |
| Validation | 166/166 (100%) |
| Backlog Brain | 20 tâches générées |
| Tasks Wiggum | 10 completed, 10 failed (timeout) |
| Timeout Wiggum | 1 heure (3600s) |
| Wiggums parallèles | 50 workers max |
| Mode FRACTAL | ✅ Activé (profondeur max: 3) |

### Seuils FRACTAL actifs
| Métrique | Seuil |
|----------|-------|
| `max_components` | 3 |
| `max_criteria` | 5 |
| `max_files` | 5 |
| `max_loc_estimate` | 200 |

---

## 🚀 Lancement du Système LRM

### Prérequis

```bash
# 1. Qwen3-30B local sur port 8002 (fallback)
llama-server -m Qwen3-30B-A3B-Instruct-Q4_K_S.gguf -c 32768 --port 8002

# 2. MiniMax API key configurée
export MINIMAX_API_KEY="sk-cp-..."
```

### 1. LRM Brain (génère le backlog)

```bash
# Via run.py
python3 tools/lrm/run.py brain --question "trouve les routes non implémentées"

# Via solaris CLI
./solaris lrm --question "..."
```

### 2. Wiggums Parallèles (50 workers, 1h timeout)

```bash
# Lancer 50 workers avec MiniMax M2.1
python3 tools/lrm/run.py wiggum --workers 50

# Ou via run_parallel_wiggums.py
python3 tools/lrm/run_parallel_wiggums.py --workers 50
```

### 3. Pipeline complet (Brain + Wiggums)

```bash
python3 tools/lrm/run.py all --question "..." --workers 50
```

### 4. Surveiller

```bash
# Voir le backlog
cat tools/lrm/backlog_solaris.json | python3 -c "
import json, sys
d = json.load(sys.stdin)
tasks = d.get('tasks', [])
completed = sum(1 for t in tasks if t.get('status') == 'completed')
failed = sum(1 for t in tasks if t.get('status') == 'failed')
pending = sum(1 for t in tasks if t.get('status') not in ['completed', 'failed'])
print(f'Tasks: {len(tasks)} total')
print(f'  Completed: {completed}')
print(f'  Failed: {failed}')
print(f'  Pending: {pending}')
"
```

---

## 🔑 Configuration MiniMax M2.1 Coding Plan

```bash
# Clé API (1000 prompts / 5 heures)
export MINIMAX_API_KEY="sk-cp-..."

# Endpoint Anthropic-compatible
MINIMAX_URL="https://api.minimax.io/anthropic/v1/messages"

# Headers requis
x-api-key: $MINIMAX_API_KEY
anthropic-version: 2023-06-01
Content-Type: application/json
```

---

*Le MCP Solaris est la source de vérité. En cas de doute, interroger le MCP.*
