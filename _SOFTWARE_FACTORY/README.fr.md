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

# Macaron Software Factory

**Usine Logicielle Multi-Agents — Des agents IA autonomes orchestrant le cycle de vie produit complet**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Fonctionnalités](#fonctionnalités) · [Démarrage rapide](#démarrage-rapide) · [Captures d'écran](#captures-décran) · [Architecture](#architecture) · [Contribuer](#contribuer)

</div>

---

## Qu'est-ce que c'est ?

Macaron est une **plateforme multi-agents autonome** qui orchestre l'ensemble du cycle de vie du développement logiciel — de l'idéation au déploiement — en utilisant des agents IA spécialisés qui collaborent.

Imaginez une **usine logicielle virtuelle** où 94 agents IA collaborent via des workflows structurés, suivant la méthodologie SAFe, les pratiques TDD et des portails qualité automatisés.

### Points clés

- **94 agents spécialisés** — architectes, développeurs, testeurs, SRE, analystes sécurité, product owners
- **12 patterns d'orchestration** — solo, parallèle, hiérarchique, réseau, adversarial-pair, human-in-the-loop
- **Cycle de vie aligné SAFe** — Portfolio → Epic → Feature → Story avec cadence PI
- **Auto-réparation** — détection d'incidents, triage et réparation autonomes
- **Sécurité d'abord** — protection injection, RBAC, nettoyage des secrets, pool de connexions
- **Métriques DORA** — fréquence de déploiement, lead time, MTTR, taux d'échec

## Captures d'écran

<table>
<tr>
<td width="50%">
<strong>Portfolio — Comité Stratégique & Gouvernance</strong><br>
<img src="docs/screenshots/fr/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI Board — Planification des Incréments Programme</strong><br>
<img src="docs/screenshots/fr/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agents — 94 Agents IA Spécialisés</strong><br>
<img src="docs/screenshots/fr/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>Atelier d'Idéation — Brainstorming assisté par IA</strong><br>
<img src="docs/screenshots/fr/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Contrôle de Mission — Suivi d'exécution en temps réel</strong><br>
<img src="docs/screenshots/fr/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>Monitoring — Santé système & Métriques</strong><br>
<img src="docs/screenshots/fr/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## Démarrage rapide

### Option 1 : Docker (Recommandé)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### Option 2 : Docker Compose (Manuel)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### Option 3 : Développement local

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### Vérifier l'installation

```bash
curl http://localhost:8090/api/health
```

## Contribuer

Les contributions sont les bienvenues ! Consultez [CONTRIBUTING.md](CONTRIBUTING.md) pour les directives.

## Licence

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**Construit avec amour par [Macaron Software](https://github.com/macaron-software)**

[Signaler un bug](https://github.com/macaron-software/software-factory/issues) · [Demander une fonctionnalité](https://github.com/macaron-software/software-factory/issues)

</div>
