# Solaris LRM - Recursive Language Model Pipeline

> Design System automation avec Brain LRM + Wiggum TDD

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 LRM BRAIN (Claude Opus 4.5)                                 │
│  - Analyse complète du codebase                                 │
│  - Génère backlog priorisé → backlog_solaris.json               │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔧 WIGGUM TDD (MiniMax M2.1 × 50 parallèle)                    │
│  - Dépile backlog_solaris.json                                  │
│  - Mode FRACTAL: décompose tâches trop larges                   │
│  - Contrôle Adversarial à chaque itération                      │
│  - Max 10 retries si SLOP détecté                               │
│  → Résultats: completed_solaris.json                            │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔴 ADVERSARIAL AGENT                                           │
│  Détecte SLOP, FAKE, HALLUCINATIONS:                            │
│  - test.skip (+10 pts) | @ts-ignore (+5 pts)                    │
│  - TODO/STUB (+4 pts) | ... code tronqué (+3 pts)               │
│  → Score >= 5 = REJET + retry avec feedback                     │
└─────────────────────────────────────────────────────────────────┘
```

## Fichiers

| Fichier | Rôle |
|---------|------|
| `tools/lrm/run.py` | Orchestrateur principal |
| `tools/lrm/lrm_brain_solaris.py` | Brain (Claude Opus 4.5) |
| `tools/lrm/wiggum_solaris.py` | Agent TDD (MiniMax M2.1) |
| `tools/lrm/run_parallel_wiggums.py` | Parallélisation (50 workers) |
| `mcp_solaris_server.py` | Serveur MCP (source de vérité) |
| `knowledge/` | Knowledge base WCAG, patterns |

## Usage

```bash
# 1. Brain: analyse et génère backlog
python3 tools/lrm/run.py brain --question "analyse les gaps"

# 2. Wiggums: exécute le backlog en parallèle
python3 tools/lrm/run_parallel_wiggums.py --workers 50

# 3. Pipeline complet
python3 tools/lrm/run.py all --question "..." --workers 50
```

## Prérequis

- Python 3.11+
- Qwen3-30B local sur port 8002 (fallback)
- MiniMax API key (optionnel, pour Coding Plan)

## Résultats Solaris La Poste

| Backlog | Completed | Rate |
|---------|-----------|------|
| Solaris | 20/20 | 100% |
| Angular19 | 20/20 | 100% |
| Gaps | 8/8 | 100% |
| **TOTAL** | **48/48** | **100%** |
