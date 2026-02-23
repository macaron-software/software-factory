<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a>
</p>

<div align="center">

# Software Factory

**Usine Logicielle Multi-Agents — Agents IA autonomes orchestrant le cycle de vie complet des produits**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Fonctionnalités](#fonctionnalités) · [Démarrage rapide](#démarrage-rapide) · [Captures d'écran](#captures-décran) · [Architecture](#architecture) · [Contribuer](#contribuer)

</div>

---

## C'est quoi ?

Software Factory est une **plateforme multi-agents autonome** qui orchestre l'intégralité du cycle de développement logiciel — de l'idéation au déploiement — en utilisant des agents IA spécialisés travaillant ensemble.

Imaginez une **usine logicielle virtuelle** où 158 agents IA collaborent à travers des workflows structurés, suivant la méthodologie SAFe, les pratiques TDD et des portes de qualité automatisées.

### Points clés

- **158 agents spécialisés** — architectes, développeurs, testeurs, SRE, analystes sécurité, product owners
- **12 patterns d'orchestration** — solo, parallèle, hiérarchique, réseau, adversarial-pair, human-in-the-loop
- **Cycle de vie SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Auto-réparation** — détection autonome d'incidents, triage et auto-réparation avec notifications temps réel
- **Sécurité prioritaire** — garde injection de prompt, RBAC, masquage secrets, connection pooling
- **Métriques DORA** — fréquence déploiement, lead time, MTTR, taux échec changements
- **Multilingue** — détection automatique de la langue du navigateur (8 langues : en, fr, es, it, de, pt, ja, zh)
- **Fournisseurs IA personnalisés** — interface pour configurer n'importe quel LLM compatible OpenAI avec chiffrement des clés API
- **Analytics temps réel** — tableaux de bord de performance en direct avec visualisations Chart.js
- **Notifications intégrées** — icône cloche avec dropdown pour tickets TMA, incidents et alertes système

## Captures d'écran

<table>
<tr>
<td width="33%">
<strong>Dashboard — Streaming SSE Temps Réel</strong><br>
<img src="docs/screenshots/fr/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="33%">
<strong>API Swagger — 94 Endpoints REST</strong><br>
<img src="docs/screenshots/fr/swagger.png" alt="API Swagger" width="100%">
</td>
<td width="33%">
<strong>CLI — 40+ Commandes</strong><br>
<img src="docs/screenshots/fr/cli.png" alt="CLI" width="100%">
</td>
</tr>
</table>

## Démarrage rapide

### Option 1 : Docker (Recommandé)

L'image inclut : **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env       # Configurer les clés LLM (voir Étape 3)
docker-compose up -d
```

Ouvrir http://localhost:8090

### Option 2 : Installation locale

```bash
# Cloner le dépôt
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

# Installer les dépendances
pip install -r requirements.txt

# Démarrer la plateforme
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Ouvrir http://localhost:8090

### Étape 3 : Configurer un fournisseur LLM

La plateforme nécessite au moins **un fournisseur LLM** pour que les agents génèrent du vrai code, des tests et des décisions.
Sans clé API, elle tourne en **mode demo** (réponses simulées — utile pour explorer l'interface).

```bash
# Copier le fichier d'environnement exemple
cp .env.example .env

# Éditer .env et ajouter vos clés API
```

| Fournisseur          | Variable d'env                                   | Modèles            | Gratuit |
| -------------------- | ------------------------------------------------ | ------------------ | ------- |
| **MiniMax**          | `MINIMAX_API_KEY`                                | MiniMax-M2.5, M2.1 | ✅ Oui  |
| **Azure OpenAI**     | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini         | ❌      |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT`         | GPT-5.2            | ❌      |
| **NVIDIA NIM**       | `NVIDIA_API_KEY`                                 | Kimi K2            | ✅ Oui  |

Définir `PLATFORM_LLM_PROVIDER` sur votre fournisseur principal (`minimax`, `azure-openai`, `azure-ai`, `nvidia`).
La plateforme bascule automatiquement sur les autres fournisseurs configurés en cas d'échec.

```bash
# Exemple : MiniMax comme fournisseur principal
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-votre-clé-ici
```

Vous pouvez aussi configurer les fournisseurs depuis la page **Settings** du dashboard (`/settings`).

## Fonctionnalités

### 🤖 145 Agents IA Spécialisés

Les agents sont organisés en équipes reflétant de vraies organisations logicielles :

| Équipe            | Agents                                           | Rôle                                      |
| ----------------- | ------------------------------------------------ | ----------------------------------------- |
| **Product**       | Product Manager, Business Analyst, PO            | Planification SAFe, priorisation WSJF     |
| **Architecture**  | Solution Architect, Tech Lead, System Architect  | Décisions architecture, design patterns   |
| **Développement** | Backend/Frontend/Mobile/Data Engineers           | Implémentation TDD par stack              |
| **Qualité**       | QA Engineers, Security Analysts, Test Automation | Tests, audits sécurité, tests pénétration |
| **Design**        | UX Designer, UI Designer                         | Expérience utilisateur, design visuel     |
| **DevOps**        | DevOps Engineer, SRE, Platform Engineer          | CI/CD, monitoring, infrastructure         |
| **Management**    | Scrum Master, RTE, Agile Coach                   | Cérémonies, facilitation, levée obstacles |

### 🎯 12 Patterns d'Orchestration

- **Solo** — un seul agent pour tâches simples
- **Séquentiel** — pipeline d'agents exécutant dans l'ordre
- **Parallèle** — plusieurs agents travaillant simultanément
- **Hiérarchique** — manager déléguant à sous-agents
- **Réseau** — agents collaborant peer-to-peer
- **Adversarial-pair** — un agent génère, un autre critique
- **Human-in-the-loop** — agent propose, humain valide
- **Ensemble** — plusieurs agents votent sur décisions
- **Récursif** — agent spawne sous-agents récursivement
- **Boucle** — agent itère jusqu'à condition remplie
- **Saga** — transaction distribuée avec compensations
- **Event-driven** — agents réagissent aux événements de manière asynchrone

### 📊 Cycle de Vie Aligné SAFe

Hiérarchie complète Portfolio → Epic → Feature → Story avec :

- **Portfolio Stratégique** — canvas portfolio, thèmes stratégiques, value streams
- **Program Increment** — planification PI, objectifs, dépendances
- **Team Backlog** — user stories, tâches, critères d'acceptation
- **Sprint Execution** — daily standups, sprint reviews, rétrospectives

### 🛡️ Sécurité & Conformité

- **Authentification** — auth JWT avec RBAC
- **Garde injection prompt** — détection et blocage prompts malveillants
- **Masquage secrets** — redaction automatique données sensibles
- **CSP (Content Security Policy)** — headers durcis
- **Rate limiting** — quotas API par utilisateur
- **Audit logging** — logs d'activité complets

### 📈 Métriques DORA & Monitoring

- **Deployment frequency** — fréquence du code en production
- **Lead time** — durée commit vers déploiement
- **MTTR** — temps moyen de récupération des incidents
- **Change failure rate** — pourcentage de déploiements échoués
- **Dashboards temps réel** — visualisations Chart.js
- **Métriques Prometheus** — endpoint /metrics

### 🔧 Outils Intégrés des Agents

L'image Docker inclut tout le nécessaire pour que les agents travaillent en autonomie :

| Catégorie    | Outils                                                | Description                                                   |
| ------------ | ----------------------------------------------------- | ------------------------------------------------------------- |
| **Code**     | `code_read`, `code_write`, `code_edit`, `code_search` | Lecture, écriture et recherche de fichiers                    |
| **Build**    | `build`, `test`, `local_ci`                           | Builds, tests, pipeline CI local (npm/pip/cargo auto-détecté) |
| **Git**      | `git_commit`, `git_diff`, `git_log`                   | Contrôle de version avec isolation par branche agent          |
| **Sécurité** | `sast_scan`, `dependency_audit`, `secrets_scan`       | SAST via bandit/semgrep, audit CVE, détection de secrets      |
| **QA**       | `playwright_test`, `browser_screenshot`               | Tests E2E Playwright et captures d'écran (Chromium inclus)    |
| **Tickets**  | `create_ticket`, `jira_search`, `jira_create`         | Création d'incidents/tickets pour le suivi TMA                |
| **Deploy**   | `docker_deploy`, `github_actions`                     | Déploiement conteneur et statut CI/CD                         |
| **Mémoire**  | `memory_store`, `memory_search`, `deep_search`        | Mémoire projet persistante entre sessions                     |

## Quatre Interfaces

### 1. Dashboard Web (HTMX + SSE)

Interface principale sur http://localhost:8090 :

- **Conversations multi-agents temps réel** avec streaming SSE
- **PI Board** — planification program increment
- **Mission Control** — monitoring d'exécution
- **Gestion Agents** — voir, configurer, monitorer agents
- **Dashboard Incidents** — triage auto-réparation
- **Responsive mobile** — fonctionne sur tablettes et téléphones

### 2. CLI (`sf`)

Interface ligne de commande complète :

```bash
# Installation (ajouter au PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Navigation
sf status                              # Santé plateforme
sf projects list                       # Tous les projets
sf missions list                       # Missions avec scores WSJF
sf agents list                         # 158 agents
sf features list <epic_id>             # Features d'un epic
sf stories list --feature <id>         # User stories

# Travail
sf ideation "app e-commerce React"     # Idéation multi-agents (streamé)
sf missions start <id>                 # Démarrer une mission
sf metrics dora                        # Métriques DORA

# Monitoring
sf incidents list                      # Incidents
sf llm stats                           # Usage LLM (tokens, coût)
sf chaos status                        # Chaos engineering
```

**22 groupes de commandes** · Mode dual : API (serveur live) ou DB (offline) · Sortie JSON (`--json`) · Animations spinner · Rendu tables Markdown

### 3. API REST + Swagger

94 endpoints API auto-documentés sur `/docs` (Swagger UI) :

```bash
# Exemples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "app GPS vélo"}'
```

Swagger UI : http://localhost:8090/docs

### 4. Serveur MCP (Model Context Protocol)

23 outils MCP pour intégration agents IA (port 9501) :

```bash
# Démarrer serveur MCP
python3 -m platform.mcp_platform.server

# Outils disponibles :
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  🎯 Portfolio Stratégique (Canvas Portfolio, Value Streams)     │
│  Vision, Thèmes, Epics → Priorisation WSJF                      │
└────────────────────────┬─────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  PI Planning Board  │      │  Mission Execution  │
│  Program Increment  │      │  145 Agents         │
│  Features → Stories │      │  12 Patterns        │
│  Dépendances        │      │  Pipeline TDD       │
└─────────────────────┘      └─────────────────────┘
          │                             │
          ▼                             ▼
┌─────────────────────┐      ┌─────────────────────┐
│  Sprint Backlog     │      │  Deploy Pipeline    │
│  Daily Standups     │      │  Build → Stage →    │
│  Reviews            │      │  E2E → Prod         │
└─────────────────────┘      └─────────────────────┘
          │                             │
          └──────────────┬──────────────┘
                         ▼
┌──────────────────────────────────────────────────────────────────┐
│  🔴 Portes Qualité + Auto-Réparation                             │
│  Tests, Sécurité, Performance → Détection Incidents → Auto-Fix  │
└──────────────────────────────────────────────────────────────────┘
```

## Nouveautés v1.2.0 (21-22 fév 2026)

### CLI 'sf' - Interface Ligne de Commande Complète

- 40+ commandes miroir de toutes les fonctionnalités du dashboard web
- Mode dual : API (serveur live) ou DB (offline)
- Streaming SSE avec sortie colorée par agent
- Sortie JSON pour scripting
- 52 tests automatisés

### Améliorations Product Management

- 11 nouvelles capacités PM
- Algorithmes de priorisation WSJF
- Cartographie value stream

### Durcissement Sécurité

- AuthMiddleware activé par défaut
- Headers CSP renforcés
- Masquage secrets dans logs et réponses API
- Rate limiting par utilisateur

### Tests & Qualité

- Suite de tests d'endurance
- Tests chaos engineering
- Tests E2E Playwright sur toutes les pages
- Validation installation Debian 13

#### Lancer les tests E2E (Playwright)

```bash
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```

### DevOps & Monitoring

- Intégration webhooks GitHub
- Chart Helm pour Kubernetes
- Endpoint métriques Prometheus
- Dashboards Grafana
- Automatisation pipeline CD

### Améliorations UI

- Notifications temps réel
- Visualisations analytics Chart.js
- Design responsive mobile
- Stabilité streaming SSE améliorée

## Contribuer

Les contributions sont bienvenues ! Veuillez lire [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives.

## Licence

Ce projet est sous licence AGPL v3 - voir le fichier [LICENSE](LICENSE) pour détails.

## Support

- Documentation : https://docs.software-factory.dev
- Issues : https://github.com/macaron-software/software-factory/issues
- Discussions : https://github.com/macaron-software/software-factory/discussions
