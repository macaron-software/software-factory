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
- **Selbstheilung** — autonome Vorfallserkennung, Triage und Selbstreparatur
- **Sicherheit zuerst** — Prompt-Injection-Guard, RBAC, Secret-Scrubbing
- **DORA-Metriken** — Bereitstellungshäufigkeit, Lead Time, MTTR, Change Failure Rate

## Screenshots

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/de/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/de/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/de/cli.png" width="100%"></td>
</tr>
</table>

## Schnellstart

### Option 1: Docker (Empfohlen)

Das Docker-Image enthält: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # erstellt .env aus .env.example (bearbeiten Sie die LLM-Schlüssel)
make run     # baut und startet die Plattform
```

### Option 2: Lokale Installation

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # Config erstellen (LLM-Schlüssel eintragen — siehe unten)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make dev
```

Öffnen Sie http://localhost:8090 — beim ersten Start erscheint der **Onboarding-Assistent**.
Wählen Sie Ihre SAFe-Rolle oder klicken Sie auf **„Skip (Demo)"**.

### LLM-Anbieter konfigurieren

Ohne API-Key läuft die Plattform im **Demo-Modus** (simulierte Antworten — nützlich zum Erkunden der Oberfläche).

Bearbeiten Sie `.env` und fügen Sie **einen** API-Key hinzu:

```bash
# Option A: MiniMax (kostenlos — empfohlen zum Einstieg)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-ihr-key-hier

# Option B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=ihr-key
AZURE_OPENAI_ENDPOINT=https://ihre-resource.openai.azure.com

# Option C: NVIDIA NIM (kostenlos)
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-ihr-key-hier
```

Dann neu starten: `make run` (Docker) oder `make dev` (lokal)

| Anbieter | Umgebungsvariable | Modelle | Kostenlos |
|----------|------------------|---------|-----------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 | ✅ |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini | ❌ |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 | ❌ |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 | ✅ |

Konfiguration auch über **Settings** (`/settings`).

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
