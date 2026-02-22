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

**Multi-Agenten-Softwarefabrik — Autonome KI-Agenten orchestrieren den gesamten Produktlebenszyklus**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Funktionen](#funktionen) · [Schnellstart](#schnellstart) · [Screenshots](#screenshots) · [Architektur](#architektur) · [Mitwirken](#mitwirken)

</div>

---

## Was ist das?

Macaron ist eine **autonome Multi-Agenten-Plattform**, die den gesamten Softwareentwicklungszyklus orchestriert — von der Ideenfindung bis zum Deployment — mit spezialisierten KI-Agenten, die zusammenarbeiten.

Stellen Sie es sich als eine **virtuelle Softwarefabrik** vor, in der 94 KI-Agenten über strukturierte Workflows zusammenarbeiten und der SAFe-Methodik, TDD-Praktiken und automatisierten Qualitäts-Gates folgen.

### Highlights

- **94 spezialisierte Agenten** — Architekten, Entwickler, Tester, SREs, Sicherheitsanalysten, Product Owner
- **12 Orchestrierungsmuster** — Solo, Parallel, Hierarchisch, Netzwerk, Adversarial-Pair, Human-in-the-Loop
- **SAFe-ausgerichteter Lebenszyklus** — Portfolio → Epic → Feature → Story mit PI-Kadenz
- **Selbstreparatur** — autonome Vorfallerkennung, Triage und Reparatur
- **Sicherheit zuerst** — Injektionsschutz, RBAC, Secret-Scrubbing, Verbindungspool
- **DORA-Metriken** — Deployment-Frequenz, Vorlaufzeit, MTTR, Änderungsfehlerrate

## Screenshots

<table>
<tr>
<td width="50%">
<strong>Portfolio — Strategiekomitee & Governance</strong><br>
<img src="docs/screenshots/de/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI Board — Programminkrement-Planung</strong><br>
<img src="docs/screenshots/de/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agenten — 94 Spezialisierte KI-Agenten</strong><br>
<img src="docs/screenshots/de/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>Ideenfindungs-Workshop — KI-gestütztes Brainstorming</strong><br>
<img src="docs/screenshots/de/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Missionskontrolle — Echtzeit-Ausführungsmonitoring</strong><br>
<img src="docs/screenshots/de/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>Monitoring — Systemgesundheit & Metriken</strong><br>
<img src="docs/screenshots/de/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## Schnellstart

### Option 1: Docker (Empfohlen)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### Option 2: Docker Compose (Manuell)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### Option 3: Lokale Entwicklung

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### Installation überprüfen

```bash
curl http://localhost:8090/api/health
```

## Mitwirken

Beiträge sind willkommen! Siehe [CONTRIBUTING.md](CONTRIBUTING.md) für Richtlinien.

## Lizenz

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**Mit Liebe gebaut von [Macaron Software](https://github.com/macaron-software)**

[Bug melden](https://github.com/macaron-software/software-factory/issues) · [Feature anfragen](https://github.com/macaron-software/software-factory/issues)

</div>
