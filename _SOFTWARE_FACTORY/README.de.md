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

**Multi-Agenten-Softwarefabrik — Autonome KI-Agenten orchestrieren den vollständigen Produktlebenszyklus**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

</div>

---

## Was ist das?

Software Factory ist eine **autonome Multi-Agenten-Plattform**, die den gesamten Software-Entwicklungszyklus orchestriert — von der Ideenfindung bis zur Bereitstellung — mithilfe spezialisierter KI-Agenten, die zusammenarbeiten.

Stellen Sie sich eine **virtuelle Softwarefabrik** vor, in der 158 KI-Agenten über strukturierte Workflows zusammenarbeiten, der SAFe-Methodik folgen, TDD-Praktiken anwenden und automatisierte Qualitätstorwerden nutzen.

### Hauptmerkmale

- **145 spezialisierte Agenten** — Architekten, Entwickler, Tester, SRE, Sicherheitsanalysten, Product Owner
- **12 Orchestrierungsmuster** — Solo, parallel, hierarchisch, Netzwerk, adversarial-pair, human-in-the-loop
- **SAFe-ausgerichteter Lebenszyklus** — Portfolio → Epic → Feature → Story mit PI-Kadenz
- **Selbstheilung** — autonome Vorfallserkennung, Triage und Selbstreparatur mit Echtzeit-Benachrichtigungen
- **Sicherheit zuerst** — Prompt-Injection-Guard, RBAC, Secret-Scrubbing
- **DORA-Metriken** — Bereitstellungshäufigkeit, Lead Time, MTTR, Change Failure Rate
- **Mehrsprachig** — automatische Erkennung der Browser-Sprache (8 Sprachen: en, fr, es, it, de, pt, ja, zh)
- **Benutzerdefinierte KI-Anbieter** — GUI zur Konfiguration jedes OpenAI-kompatiblen LLM mit verschlüsselten API-Schlüsseln
- **Echtzeit-Analytik** — Live-Performance-Dashboards mit Chart.js-Visualisierungen
- **In-App-Benachrichtigungen** — Glockensymbol mit Dropdown für TMA-Tickets, Vorfälle und Systemwarnungen

## Screenshots

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/de/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/de/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/de/cli.png" width="100%"></td>
</tr>
</table>

## Schnellstart

Das Docker-Image enthält: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env       # LLM-Schlüssel konfigurieren (siehe unten)
docker-compose up -d
```

Öffnen Sie http://localhost:8090

### LLM-Anbieter konfigurieren

Die Plattform benötigt mindestens **einen LLM-Anbieter** für echte Code-Generierung. Ohne API-Key läuft sie im **Demo-Modus**.

```bash
cp .env.example .env
# .env bearbeiten und API-Keys eintragen
```

| Anbieter         | Umgebungsvariable                                | Kostenlos |
| ---------------- | ------------------------------------------------ | --------- |
| **MiniMax**      | `MINIMAX_API_KEY`                                | ✅        |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | ❌        |
| **NVIDIA NIM**   | `NVIDIA_API_KEY`                                 | ✅        |

`PLATFORM_LLM_PROVIDER` auf Ihren primären Anbieter setzen. Konfiguration auch über **Settings** (`/settings`).

## Funktionen

- **158 KI-Agenten** in Teams organisiert
- **Integrierte Tools**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Vollständiges CLI** — 40+ Befehle
- **REST API** — 94 dokumentierte Endpunkte
- **MCP Server** — 23 Tools
- **Lizenz AGPL v3**

## Tests

```bash
# Unit-Tests
pytest tests/

# E2E-Tests (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
