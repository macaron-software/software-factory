# PHASE 1 : Cadrage Stratégique - RLM Macaron Agent Platform
## Date: 2025-02-12
## Équipe: dsi, strat-cpo, strat-cto, architecte, strat-portfolio

---

## 📋 LIVRABLE 1 : Vision Validée

### Vision du Projet
**RLM Macaron Agent Platform** - Usine logicielle autonome basée sur MIT CSAIL arXiv:2512.24601 "Recursive Language Models"

### Fonctionnalités Clés Validées

| Fonctionnalité | Status | Commentaire |
|----------------|--------|-------------|
| 🧠 RLM Brain (Claude Opus 4.5) | ✅ Validé | Analyse stratégique, vision planning |
| ⚙️ Wiggum TDD Workers (50x MiniMax M2.1) | ✅ Validé | Génération code TDD parallèle |
| 🔴 Adversarial Gate | ✅ Validé | Quality gate multi-LLM |
| 📦 FRACTAL Decomposition | ✅ Validé | Décomposition tâches atomiques |
| 🏗️ Multi-project Support | ✅ Validé | ppz, veligo, factory, solaris, etc. |
| 🔄 Self-Improvement | ✅ Validé | Auto-rétrospective et refactoring |

### Alignment Stratégique
- **Lean + Agile + KISS + XP** : Principes cohérents avec les objectifs
- **ZERO SKIP POLICY** : Différenciateur fort contre la dette technique
- **Team of Rivals** : Approche novatrice (référence Isototes AI Jan 2025)

### Gaps Identifiés
⚠️ **GAP-1**: Pas de mention explicite de l'API pricing/cost management
⚠️ **GAP-2**: Dépendance forte aux API Anthropic (Opus 4.5) et MiniMax
⚠️ **GAP-3**: Configuration complexe pour les nouveaux projets

---

## 💰 LIVRABLE 2 : Budget Estimé

### Coûts de Développement (Estimés)

| Poste | Estimation | Hypothèses |
|-------|------------|------------|
| Développement Core | 3-6 mois-homme | Équipe 2-3 développeurs |
| Intégration projets | 1 mois par projet | ppz, veligo, etc. |
| Infrastructure Cloud | 500-1500€/mois | Azure VM, API LLM |
| Monitoring/Observabilité | 100-300€/mois | Logs, métriques |

### Coûts d'Exploitation (Mensuel)

| Service | Coût Estimé |
|---------|-------------|
| Azure VM (4CPU/16GB) | ~100€ |
| API Claude Opus 4.5 | 500-2000€ (usage) |
| API MiniMax M2.1 | 200-800€ (usage) |
| Base de données (SQLite) | Inclus VM |
| **Total Mensuel** | **800-2900€** |

### ROI Attendu
- Réduction ~40-60% du temps de développement fitur
- Amélioration qualité code (coverage 80%+)
- Auto-correction des régressions

---

## ⚠️ LIVRABLE 3 : Risques Identifiés

### Matrice des Risques

| ID | Risque | Probabilité | Impact | Mitigation |
|----|--------|-------------|--------|------------|
| **R1** | Dépendance API LLM externe | Élevée | Critique | Fallback chain (Qwen local), cache prompts |
| **R2** | Coûts API explosion | Moyenne | Élevé | Cost tier architecture (Brain→Wiggum→Qwen) |
| **R3** | Complexité configuration | Moyenne | Moyen | Templates projet, documentation |
| **R4** | Qualié outputs LLM variable | Élevée | Moyen | Adversarial gate, human review |
| **R5** | OOM workers parallèle | Moyenne | Élevé | Limite workers (OOM-safe),监控 |
| **R6** | Intégration projets legacy | Faible | Moyen | Conventions par projet, validation |
| **R7** | Vendor lock-in (Anthropic/MiniMax) | Moyenne | Moyen | AbstractionLLMClient, multi-provider |

### Risques Techniques Spécifiques
- **Timeouts LLM** : 10min timeout configuré, retry chain
- **Rate limiting** : Gestion via error_patterns.is_transient()
- **Build failures** : Feedback loop automatique

---

## ✅ LIVRABLE 4 : Décision GO/NOGO

### Critères de Décision

| Critère | Seuil GO | Status |
|---------|-----------|--------|
| Vision alignée stratégie | ✅ | GO |
| Architecture cohérente | ✅ | GO |
| Budget réaliste | ✅ | GO |
| Risques identifiées & mitigables | ✅ | GO |
| Equipe disponible | ✅ | GO |
| Infrastructure accessible | ⚠️ | **CONDITIONNEL** |

### Décision : **GO** ✅

**Conditions** :
1. Validation du budget par la DSI (800-2900€/mois)
2. Accès aux API keys Anthropic/MiniMax confirmé
3. Accès VM Azure (4.233.64.30) pour déploiement

### Prochaines Étapes (Phase 2)
1. Spécifications détaillées des composants
2. Plan d'intégration premier projet (ppz ou veligo)
3. POC minimal (Brain + 1 Wiggum worker)

---

## 📊 Résumé Exécutif

| Livrable | Status |
|----------|--------|
| Vision validée | ✅ Complet |
| Budget estimé | ✅ Complet (800-2900€/mois) |
| Risques identifiés | ✅ 7 risques + mitigations |
| Décision GO/NOGO | **GO CONDITIONNEL** |

---

## Détail des Analyses

### Architecture Technique Validée

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 RLM BRAIN (Claude Opus 4.5)                                 │
│  Vision LEAN + Project Analysis + Task Generation               │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  QUEUE 1: TDD       │      │  QUEUE 2: DEPLOY    │
│  MiniMax M2.1 × 50  │      │  MiniMax M2.1 × 10  │
│                     │      │                     │
│  TDD Cycle:         │      │  Pipeline:          │
│  1. FRACTAL check   │      │  1. Build           │
│  2. RED (test)      │      │  2. Staging         │
│  3. GREEN (code)    │      │  3. E2E smoke       │
│  4. VERIFY          │      │  4. Prod            │
│  5. ADVERSARIAL     │      │  5. Rollback        │
│  6. COMMIT          │      │                     │
└─────────────────────┘      └─────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│  🔴 ADVERSARIAL GATE                                             │
│  Core: test.skip, @ts-ignore, TODO, STUB                        │
│  Custom: project-specific patterns from YAML                    │
└─────────────────────────────────────────────────────────────────┘
```

### Projets Supportés
- **ppz (Popinz)**: SaaS Rust + TypeScript
- **veligo**: Platforme La Poste (multi-tenant IDFM/Nantes)
- **factory**: Auto-improvement
- **fervenza**, **solaris**, **yolonow**, **psy**, **logs-facteur**

### Technologies Clés
- Python 3.10+ (core framework)
- Claude Opus 4.5 (Anthropic)
- MiniMax M2.1 (code generation)
- SQLite (task store)
- Docker (deployment)
- MCP (Model Context Protocol)
