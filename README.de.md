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

**Multi-Agenten-Softwarefabrik — Autonome KI-Agenten orchestrieren den vollstaendigen Produktlebenszyklus**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live-Demo: sf.macaron-software.com](https://sf.macaron-software.com)** — klicken Sie auf "Skip (Demo)" zum Erkunden

[Funktionen](#funktionen) · [Schnellstart](#schnellstart) · [Screenshots](#screenshots) · [Architektur](#architektur) · [Mitwirken](#mitwirken)

</div>

---

## Was ist das?

Software Factory ist eine **autonome Multi-Agenten-Plattform**, die den gesamten Software-Entwicklungszyklus orchestriert — von der Ideenfindung bis zur Bereitstellung — mithilfe spezialisierter KI-Agenten, die zusammenarbeiten.

Stellen Sie sich eine **virtuelle Softwarefabrik** vor, in der 161 KI-Agenten ueber strukturierte Workflows zusammenarbeiten, der SAFe-Methodik folgen, TDD-Praktiken anwenden und automatisierte Qualitaets-Gates nutzen.

### Hauptmerkmale

- **161 spezialisierte Agenten** — Architekten, Entwickler, Tester, SRE, Sicherheitsanalysten, Product Owner
- **10 Orchestrierungsmuster** — Solo, Sequentiell, Parallel, Hierarchisch, Netzwerk, Schleife, Router, Aggregator, Welle, Human-in-the-Loop
- **SAFe-ausgerichteter Lebenszyklus** — Portfolio → Epic → Feature → Story mit PI-Kadenz
- **Selbstheilung** — autonome Vorfallserkennung, Triage und Selbstreparatur
- **LLM-Resilienz** — Multi-Provider-Fallback, Jitter-Retry, Rate-Limit-Management, umgebungsvariablengesteuerte Modellkonfiguration
- **OpenTelemetry-Observabilitaet** — Distributed Tracing mit Jaeger, Pipeline-Analytics-Dashboard
- **Kontinuierlicher Watchdog** — Auto-Wiederaufnahme pausierter Runs, Sitzungswiederherstellung, Bereinigung fehlgeschlagener Runs
- **Sicherheit zuerst** — Prompt-Injection-Guard, RBAC, Secret-Scrubbing, Connection-Pooling
- **DORA-Metriken** — Bereitstellungshaeufigkeit, Lead Time, MTTR, Change Failure Rate

## Screenshots

<table>
<tr>
<td width="50%">
<strong>Dashboard — Adaptive SAFe-Perspektive</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — Strategischer Backlog & WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Program Increment Planung</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Ideation Workshop — KI-gestuetztes Brainstorming</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Trains & Agenten-Teams</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>Zeremonien — Workflow-Vorlagen & Muster</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoring — DORA-Metriken & Systemzustand</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — SAFe-Rollenauswahl-Assistent</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
</table>

## Schnellstart

### Option 1: Docker (Empfohlen)

Das Docker-Image enthaelt: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # kopiert .env.example → .env (bearbeiten Sie die Datei, um Ihren LLM-API-Key einzutragen)
make run     # baut und startet die Plattform
```

Oeffnen Sie http://localhost:8090 — klicken Sie auf **"Skip (Demo)"** um ohne API-Key zu erkunden.

### Option 2: Lokale Installation

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # Konfiguration erstellen (LLM-Key eintragen — siehe Schritt 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Plattform starten
make dev
# oder manuell: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Oeffnen Sie http://localhost:8090 — beim ersten Start erscheint der **Onboarding-Assistent**.
Waehlen Sie Ihre SAFe-Rolle oder klicken Sie auf **"Skip (Demo)"** um sofort loszulegen.

### Schritt 3: LLM-Anbieter konfigurieren

Ohne API-Key laeuft die Plattform im **Demo-Modus** — Agenten antworten mit simulierten Antworten.
Dies ist nuetzlich zum Erkunden der Oberflaeche, aber Agenten generieren keinen echten Code oder Analysen.

Um echte KI-Agenten zu aktivieren, bearbeiten Sie `.env` und fuegen Sie **einen** API-Key hinzu:

```bash
# Option A: MiniMax (empfohlen zum Einstieg)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# Option B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Option C: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

Dann neu starten: `make run` (Docker) oder `make dev` (lokal)

| Anbieter | Umgebungsvariable | Modelle |
|----------|-------------------|---------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

Die Plattform wechselt automatisch zu anderen konfigurierten Anbietern, wenn der primaere ausfaellt.
Sie koennen Anbieter auch ueber die **Einstellungen**-Seite im Dashboard konfigurieren (`/settings`).

## Erste Schritte — Ihr erstes Projekt

Nach der Installation koennen Sie wie folgt von der Idee zum fertigen Projekt gelangen:

### Weg A: Von einer Idee starten (Ideation Workshop)

1. **Oeffnen Sie die Ideation-Seite** — gehen Sie zu `/ideation` (oder klicken Sie auf "Ideation" in der Seitenleiste)
2. **Beschreiben Sie Ihre Idee** — z.B. *"Unternehmens-Fahrgemeinschafts-App mit Echtzeit-Matching"*
3. **Beobachten Sie die Agenten-Diskussion** — 5 spezialisierte Agenten (Product Manager, Business Analyst, Architekt, UX Designer, Security) analysieren Ihre Idee in Echtzeit per SSE-Streaming
4. **Erstellen Sie ein Projekt aus dem Ergebnis** — klicken Sie auf **"Epic aus dieser Idee erstellen"**. Die Plattform wird:
   - Ein neues **Projekt** mit generierter `VISION.md` und CI/CD-Gerueststruktur erstellen
   - Ein **Epic** mit Features und User Stories erstellen, aufgeschluesselt durch den PO-Agenten
   - Automatisch **TMA**- (Wartung), **Sicherheits**- und **Technische-Schulden**-Missionen bereitstellen

Sie haben nun einen vollstaendigen SAFe-Backlog, der zur Ausfuehrung bereit ist.

### Weg B: Projekt manuell erstellen

1. Gehen Sie zu `/projects` und klicken Sie auf **"Neues Projekt"**
2. Fuellen Sie aus: Name, Beschreibung, Tech-Stack, Repository-Pfad
3. Die Plattform erstellt automatisch:
   - Einen **Product-Manager-Agenten**, der dem Projekt zugewiesen wird
   - Eine **TMA-Mission** (kontinuierliche Wartung — ueberwacht den Zustand, erstellt Vorfaelle)
   - Eine **Sicherheits-Mission** (woechentliche Sicherheitsaudits — SAST, Abhaengigkeitspruefungen)
   - Eine **Technische-Schulden-Mission** (monatliche Schuldenreduktion — geplant)

### Dann: Epics & Features erstellen

- Erstellen Sie auf der **Portfolio**-Seite (`/portfolio`) Epics mit WSJF-Priorisierung
- Fuegen Sie aus einem Epic heraus **Features** hinzu und gliedern Sie diese in **User Stories**
- Verwenden Sie das **PI Board** (`/pi-board`) zur Planung von Program Increments und Zuweisung von Features zu Sprints

### Missionen ausfuehren

- Klicken Sie auf **"Start"** bei einer beliebigen Mission, um die Agenten-Ausfuehrung zu starten
- Waehlen Sie ein **Orchestrierungsmuster** (hierarchisch, Netzwerk, parallel...)
- Beobachten Sie die Agenten in Echtzeit ueber **Mission Control**
- Agenten nutzen ihre Werkzeuge (code_read, git, build, test, security scan) autonom

### TMA & Sicherheit — Immer aktiv

Diese sind fuer jedes Projekt **automatisch aktiviert** — keine Konfiguration erforderlich:

| Mission | Typ | Zeitplan | Was sie tut |
|---------|-----|----------|-------------|
| **TMA** | Programm | Kontinuierlich | Zustandsueberwachung, Vorfallserkennung, Auto-Reparatur, Ticket-Erstellung |
| **Sicherheit** | Review | Woechentlich | SAST-Scans (bandit/semgrep), Abhaengigkeitsaudit, Secret-Erkennung |
| **Technische Schulden** | Reduktion | Monatlich | Code-Qualitaetsanalyse, Refactoring-Empfehlungen |
| **Selbstheilung** | Programm | Kontinuierlich | Auto-Erkennung von 5xx/Abstuerzen → TMA-Mission → Agenten-Diagnose → Code-Fix → Validierung |

Alle vier werden mit dem Projekt erstellt. TMA, Sicherheit und Selbstheilung starten als **aktiv**, Technische Schulden starten als **Planung** (aktivieren, wenn bereit).

## Funktionen

### 161 spezialisierte KI-Agenten

Agenten sind in Teams organisiert, die echte Software-Organisationen widerspiegeln:

| Team | Agenten | Rolle |
|------|---------|-------|
| **Produkt** | Product Manager, Business Analyst, PO | SAFe-Planung, WSJF-Priorisierung |
| **Architektur** | Solution Architect, Tech Lead, System Architect | Architekturentscheidungen, Design Patterns |
| **Entwicklung** | Backend/Frontend/Mobile/Data Engineers | TDD-Implementierung pro Stack |
| **Qualitaet** | QA Engineers, Security Analysts, Test Automation | Tests, Sicherheitsaudits, Penetrationstests |
| **Design** | UX Designer, UI Designer | Benutzererfahrung, visuelles Design |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, Monitoring, Infrastruktur |
| **Management** | Scrum Master, RTE, Agile Coach | Zeremonien, Moderation, Hindernisbeseitigung |

### 10 Orchestrierungsmuster

- **Solo** — einzelner Agent fuer einfache Aufgaben
- **Sequentiell** — Pipeline von Agenten in Reihenfolge
- **Parallel** — mehrere Agenten arbeiten gleichzeitig
- **Hierarchisch** — Manager delegiert an Unter-Agenten
- **Netzwerk** — Agenten arbeiten Peer-to-Peer zusammen
- **Schleife** — Agent iteriert bis Bedingung erfuellt
- **Router** — einzelner Agent leitet basierend auf Eingabe an Spezialisten weiter
- **Aggregator** — mehrere Eingaben werden von einem Aggregator zusammengefuehrt
- **Welle** — parallel innerhalb von Wellen, sequentiell ueber Wellen hinweg
- **Human-in-the-Loop** — Agent schlaegt vor, Mensch validiert

### SAFe-ausgerichteter Lebenszyklus

Vollstaendige Portfolio → Epic → Feature → Story-Hierarchie mit:

- **Strategisches Portfolio** — Portfolio Canvas, strategische Themen, Wertströme
- **Program Increment** — PI-Planung, Ziele, Abhaengigkeiten
- **Team-Backlog** — User Stories, Aufgaben, Akzeptanzkriterien
- **Sprint-Ausfuehrung** — Daily Standups, Sprint Reviews, Retrospektiven

### Sicherheit & Compliance

- **Authentifizierung** — JWT-basierte Authentifizierung mit RBAC
- **Prompt-Injection-Guard** — Erkennung und Blockierung boesartiger Prompts
- **Secret-Scrubbing** — automatische Schwärzung sensibler Daten
- **CSP (Content Security Policy)** — gehaertete Header
- **Rate Limiting** — API-Kontingente pro Benutzer
- **Audit-Logging** — umfassende Aktivitaetsprotokolle

### DORA-Metriken & Monitoring

- **Bereitstellungshaeufigkeit** — wie oft Code in Produktion gelangt
- **Lead Time** — Dauer von Commit bis Deployment
- **MTTR** — mittlere Wiederherstellungszeit nach Vorfaellen
- **Change Failure Rate** — Prozentsatz fehlgeschlagener Bereitstellungen
- **Echtzeit-Dashboards** — Chart.js-Visualisierungen
- **Prometheus-Metriken** — /metrics-Endpunkt

### Qualitaetsmetriken — Industrielles Monitoring

Deterministisches Qualitaets-Scanning (ohne LLM) mit 10 Dimensionen, wie eine Produktionslinie:

| Dimension | Werkzeuge | Was gemessen wird |
|-----------|-----------|-------------------|
| **Komplexitaet** | radon, lizard | Zyklomatische Komplexitaet, kognitive Komplexitaet |
| **Unit-Test-Abdeckung** | coverage.py, nyc | Zeilen-/Branch-Abdeckung in Prozent |
| **E2E-Test-Abdeckung** | Playwright | Anzahl der Testdateien, Spec-Abdeckung |
| **Sicherheit** | bandit, semgrep | SAST-Befunde nach Schweregrad (kritisch/hoch/mittel/niedrig) |
| **Barrierefreiheit** | pa11y | WCAG 2.1 AA Verstoesse |
| **Performance** | Lighthouse | Core Web Vitals Scores |
| **Dokumentation** | interrogate | README, Changelog, API-Docs, Docstring-Abdeckung |
| **Architektur** | madge, jscpd, mypy | Zirkulaere Abhaengigkeiten, Code-Duplizierung, Typfehler |
| **Wartbarkeit** | custom | Dateigroessenverteilung, Anteil grosser Dateien |
| **Adversarial** | built-in | Vorfallsrate, Adversarial-Ablehnungsrate |

**Qualitaets-Gates auf Workflow-Phasen** — jede Workflow-Phase zeigt ein Qualitaets-Badge (PASS/FAIL/PENDING) basierend auf Dimensions-Schwellenwerten, die pro Gate-Typ konfiguriert sind:

| Gate-Typ | Schwellenwert | Verwendet in |
|----------|---------------|--------------|
| `always` | 0% | Analyse-, Planungsphasen |
| `no_veto` | 50% | Implementierungs-, Sprint-Phasen |
| `all_approved` | 70% | Review-, Release-Phasen |
| `quality_gate` | 80% | Deploy-, Produktionsphasen |

**Qualitaets-Dashboard** unter `/quality` — globale Scorecard, projektbezogene Bewertungen, Trend-Snapshots.
Qualitaets-Badges sichtbar auf Missionsdetails, Projekt-Board, Workflow-Phasen und dem Haupt-Dashboard.

### Workflows zur kontinuierlichen Verbesserung

Drei integrierte Workflows zur Selbstverbesserung:

| Workflow | Zweck | Agenten |
|----------|-------|---------|
| **quality-improvement** | Metriken scannen → schlechteste Dimensionen identifizieren → Verbesserungen planen & umsetzen | QA Lead, Dev, Architect |
| **retrospective-quality** | Sprint-Retro: ROTI, Vorfaelle, Qualitaetsdaten sammeln → Massnahmen ableiten | Scrum Master, QA, Dev |
| **skill-evolution** | Agenten-Performance analysieren → System-Prompts aktualisieren → Faehigkeiten weiterentwickeln | Brain, Lead Dev, QA |

Diese Workflows erzeugen eine **Feedback-Schleife**: Metriken → Analyse → Verbesserung → erneuter Scan → Fortschritt verfolgen.

### Integrierte Agenten-Werkzeuge

Das Docker-Image enthaelt alles, was Agenten benoetigen, um autonom zu arbeiten:

| Kategorie | Werkzeuge | Beschreibung |
|-----------|-----------|--------------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | Projektdateien lesen, schreiben und durchsuchen |
| **Build** | `build`, `test`, `local_ci` | Builds, Tests und lokale CI-Pipelines ausfuehren (npm/pip/cargo automatisch erkannt) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | Versionskontrolle mit Agenten-Branch-Isolation |
| **Sicherheit** | `sast_scan`, `dependency_audit`, `secrets_scan` | SAST via bandit/semgrep, CVE-Audit, Secret-Erkennung |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright E2E-Tests und Screenshots (Chromium enthalten) |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | Vorfaelle/Tickets fuer TMA-Tracking erstellen |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | Container-Bereitstellung und CI/CD-Status |
| **Speicher** | `memory_store`, `memory_search`, `deep_search` | Persistenter Projektspeicher ueber Sitzungen hinweg |

### Selbstheilung & Selbstreparatur (TMA)

Autonomer Zyklus fuer Vorfallserkennung, Triage und Selbstreparatur:

- **Heartbeat-Monitoring** — kontinuierliche Zustandspruefungen aller laufenden Missionen und Dienste
- **Automatische Vorfallserkennung** — HTTP 5xx, Timeout, Agenten-Absturz → automatische Vorfallserstellung
- **Triage & Klassifizierung** — Schweregrad (P0-P3), Auswirkungsanalyse, Ursachenhypothese
- **Selbstreparatur** — Agenten diagnostizieren und beheben Probleme autonom (Code-Patches, Konfigurationsaenderungen, Neustarts)
- **Ticket-Erstellung** — ungeloeste Vorfaelle erstellen automatisch nachverfolgte Tickets fuer menschliche Ueberpruefung
- **Eskalation** — P0/P1-Vorfaelle loesen Slack/E-Mail-Benachrichtigungen an das Bereitschaftsteam aus
- **Retrospektiv-Schleife** — Post-Incident-Erkenntnisse werden im Speicher abgelegt und in zukuenftige Sprints injiziert

### SAFe-Perspektiven & Onboarding

Rollenbasierte adaptive Oberflaeche, die reale SAFe-Organisationen widerspiegelt:

- **9 SAFe-Perspektiven** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Adaptives Dashboard** — KPIs, Schnellaktionen und Seitenleisten-Links aendern sich je nach gewaehlter Rolle
- **Onboarding-Assistent** — 3-stufiger Erstbenutzer-Flow (Rolle waehlen → Projekt waehlen → starten)
- **Perspektiven-Auswahl** — SAFe-Rolle jederzeit ueber das Dropdown in der Kopfleiste wechseln
- **Dynamische Seitenleiste** — zeigt nur Navigation, die fuer die aktuelle Perspektive relevant ist

### 4-Schichten-Speicher & RLM Deep Search

Persistentes Wissen ueber Sitzungen hinweg mit intelligenter Abfrage:

- **Sitzungsspeicher** — Konversationskontext innerhalb einer einzelnen Sitzung
- **Musterspeicher** — Erkenntnisse aus der Ausfuehrung von Orchestrierungsmustern
- **Projektspeicher** — projektbezogenes Wissen (Entscheidungen, Konventionen, Architektur)
- **Globaler Speicher** — projektuebergreifendes Organisationswissen (FTS5-Volltextsuche)
- **Automatisch geladene Projektdateien** — CLAUDE.md, SPECS.md, VISION.md, README.md werden in jeden LLM-Prompt injiziert (max 8K)
- **RLM Deep Search** — Recursive Language Model (arXiv:2512.24601) — iterativer WRITE-EXECUTE-OBSERVE-DECIDE-Zyklus mit bis zu 10 Explorationsiterationen

### Agenten-Mercato (Transfermarkt)

Token-basierter Agenten-Marktplatz fuer Teamzusammenstellung:

- **Agenten-Angebote** — Agenten mit Preisvorstellung zum Transfer anbieten
- **Free-Agent-Pool** — nicht zugewiesene Agenten, die zum Drafting verfuegbar sind
- **Transfers & Leihen** — Agenten zwischen Projekten kaufen, verkaufen oder leihen
- **Marktbewertung** — automatische Agentenbewertung basierend auf Faehigkeiten, Erfahrung und Leistung
- **Wallet-System** — Token-Wallets pro Projekt mit Transaktionsverlauf
- **Draft-System** — freie Agenten fuer Ihr Projekt beanspruchen

### Adversarial Quality Guard

Zweischichtiges Qualitaets-Gate, das gefaelschten/Platzhalter-Code am Durchkommen hindert:

- **L0 Deterministisch** — sofortige Erkennung von Slop (Lorem Ipsum, TBD), Mocks (NotImplementedError, TODO), Fake-Builds, Halluzinationen, Stack-Unstimmigkeiten
- **L1 LLM Semantisch** — separates LLM bewertet die Ausgabequalitaet fuer Ausfuehrungsmuster
- **Bewertung** — Score < 5 bestanden, 5-6 Soft-Pass mit Warnung, 7+ abgelehnt
- **Zwangsablehnung** — Halluzinationen, Slop, Stack-Unstimmigkeiten, Fake-Builds werden unabhaengig vom Score immer abgelehnt

### Auto-Dokumentation & Wiki

Automatische Dokumentationsgenerierung waehrend des gesamten Lebenszyklus:

- **Sprint-Retrospektiven** — LLM-generierte Retro-Notizen, im Speicher abgelegt und in die naechsten Sprint-Prompts injiziert (Lernschleife)
- **Phasen-Zusammenfassungen** — jede Missionsphase erzeugt eine LLM-generierte Zusammenfassung der Entscheidungen und Ergebnisse
- **Architecture Decision Records** — Architekturmuster dokumentieren automatisch Design-Entscheidungen im Projektspeicher
- **Projekt-Kontextdateien** — automatisch geladene Anweisungsdateien (CLAUDE.md, SPECS.md, CONVENTIONS.md) dienen als lebende Dokumentation
- **Confluence-Sync** — bidirektionale Synchronisation mit Confluence-Wiki-Seiten fuer Unternehmensdokumentation
- **Swagger Auto-Docs** — 94 REST-Endpunkte automatisch dokumentiert unter `/docs` mit OpenAPI-Schema

## Vier Schnittstellen

### 1. Web-Dashboard (HTMX + SSE)

Hauptoberflaeche unter http://localhost:8090:

- **Echtzeit-Multi-Agenten-Konversationen** mit SSE-Streaming
- **PI Board** — Program-Increment-Planung
- **Mission Control** — Ausfuehrungsueberwachung
- **Agenten-Verwaltung** — Agenten anzeigen, konfigurieren, ueberwachen
- **Vorfall-Dashboard** — Selbstheilungs-Triage
- **Mobil-responsiv** — funktioniert auf Tablets und Smartphones

### 2. CLI (`sf`)

Vollstaendige Kommandozeilenschnittstelle:

```bash
# Installation (zum PATH hinzufuegen)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Durchsuchen
sf status                              # Plattform-Zustand
sf projects list                       # Alle Projekte
sf missions list                       # Missionen mit WSJF-Scores
sf agents list                         # 145 Agenten
sf features list <epic_id>             # Epic-Features
sf stories list --feature <id>         # User Stories

# Arbeiten
sf ideation "e-commerce app in React"  # Multi-Agenten-Ideation (gestreamt)
sf missions start <id>                 # Mission starten
sf metrics dora                        # DORA-Metriken

# Ueberwachen
sf incidents list                      # Vorfaelle
sf llm stats                           # LLM-Nutzung (Token, Kosten)
sf chaos status                        # Chaos Engineering
```

**22 Befehlsgruppen** · Dualer Modus: API (Live-Server) oder DB (Offline) · JSON-Ausgabe (`--json`) · Spinner-Animationen · Markdown-Tabellenrendering

### 3. REST API + Swagger

94 API-Endpunkte automatisch dokumentiert unter `/docs` (Swagger UI):

```bash
# Beispiele
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

### 4. MCP Server (Model Context Protocol)

24 MCP-Tools fuer KI-Agenten-Integration (Port 9501):

```bash
# MCP-Server starten
python3 -m platform.mcp_platform.server

# Verfuegbare Tools:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architektur

### Plattform-Uebersicht

```
                        ┌──────────────────────┐
                        │   CLI (sf) / Web UI  │
                        │   REST API :8090     │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     FastAPI Server           │
                    │  Auth (JWT + RBAC + OAuth)   │
                    │  17 route modules            │
                    └──┬──────────┬────────────┬───┘
                       │          │            │
          ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
          │ Agent Engine │   │ Workflow │   │   Mission    │
          │ 161 agents   │   │  Engine  │   │    Layer     │
          │ executor     │   │ 39 defs  │   │ SAFe cycle   │
          │ loop+retry   │   │ 10 ptrns │   │ Portfolio    │
          └──────┬───────┘   │ phases   │   │ Epic/Feature │
                 │           │ retry    │   │ Story/Sprint │
                 │           │ skip     │   └──────────────┘
                 │           │ ckpoint  │
                 │           └────┬─────┘
                 │                │
     ┌───────────┴────────────────┴───────────────┐
     │              Services                       │
     │  LLM Client (multi-provider fallback)       │
     │  Tools (code, git, deploy, memory, security)│
     │  MCP Bridge (fetch, memory, playwright)     │
     │  Quality Engine (10 dimensions)             │
     │  Notifications (Slack, Email, Webhook)      │
     └───────────────────┬─────────────────────────┘
                         │
     ┌───────────────────┴─────────────────────────┐
     │              Operations                      │
     │  Watchdog (auto-resume, stall detection)     │
     │  Auto-Heal (incident > triage > fix)         │
     │  OpenTelemetry (tracing + metrics > Jaeger)  │
     └───────────────────┬─────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   SQLite + Memory   │
              │   4-layer memory    │
              │   FTS5 search       │
              └─────────────────────┘
```

### Pipeline-Ablauf

```
Mission Created
     │
     ▼
┌─────────────┐     ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Select     │────▶│sequential│    │ parallel │    │hierarchic│
│  Pattern    │────▶│          │    │          │    │          │
└─────────────┘────▶│ adversar.│    │          │    │          │
                    └────┬─────┘    └────┬─────┘    └────┬─────┘
                         └───────────────┴───────────────┘
                                         │
                    ┌────────────────────────────────────────┐
                    │         Phase Execution                 │
                    │                                        │
                    │  Agent ──▶ LLM Call ──▶ Result         │
                    │                          │             │
                    │              ┌───success──┴──failure──┐│
                    │              ▼                        ▼│
                    │         Code phase?            Retries? │
                    │           │ yes                  │ yes │
                    │           ▼                      ▼     │
                    │     Sandbox Build         Retry w/     │
                    │     Validation            backoff      │
                    │           │                      │ no  │
                    │           ▼                      ▼     │
                    │     Quality Gate          skip_on_fail?│
                    │      │        │            │yes  │no   │
                    │    pass     fail            │     │     │
                    │      │        │             │     ▼     │
                    │      ▼        ▼             │   PAUSED  │
                    │  Checkpoint  PAUSED ◀───────┘     │     │
                    └──────┬─────────────────────────────┘    │
                           │                                  │
                    More phases? ──yes──▶ next phase          │
                           │ no                               │
                           ▼                    watchdog      │
                    Mission Completed     auto-resume ◀───────┘
```

### Observabilitaet

```
┌──────────────────────┐    ┌────────────────────────────────┐
│   OTEL Middleware     │    │     Continuous Watchdog         │
│   (every request)     │    │                                │
│   spans + metrics     │    │  health check    every 60s     │
│         │             │    │  stall detection  phases>60min │
│         ▼             │    │  auto-resume     5/batch 5min  │
│   OTLP/HTTP export    │    │  session recovery  >30min      │
│         │             │    │  failed cleanup   zombies      │
│         ▼             │    └────────────────────────────────┘
│   Jaeger :16686       │
└──────────────────────┘    ┌────────────────────────────────┐
                            │     Failure Analysis            │
┌──────────────────────┐    │                                │
│   Quality Engine      │    │  error classification          │
│   10 dimensions       │    │  phase heatmap                 │
│   quality gates       │    │  recommendations               │
│   radar chart         │    │  resume-all button             │
│   badge + scorecard   │    └────────────────────────────────┘
└──────────────────────┘
                            ┌────────────────────────────────┐
         All data ─────────▶│  Dashboard /analytics           │
                            │  tracing stats + latency chart  │
                            │  error doughnut + phase bars    │
                            │  quality radar + scorecard      │
                            └────────────────────────────────┘
```

### Bereitstellung

```
                          Internet
                     ┌───────┴────────┐
                     │                │
          ┌──────────▼─────┐  ┌───────▼────────┐
          │ Azure VM (Prod)│  │ OVH VPS (Demo) │
          │ sf.macaron-software.com   │  │ demo.macaron-software.com  │
          │                │  │                │
          │ Nginx :443     │  │ Nginx :443     │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Platform :8090 │  │ Platform :8090 │
          │ GPT-5-mini     │  │ MiniMax-M2.5   │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Jaeger :16686  │  │ Jaeger :16686  │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ SQLite DB      │  │ SQLite DB      │
          │ /patches (ro)  │  │                │
          └────────────────┘  └────────────────┘
                     │                │
                     └───────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ GitHub          │
                    │ macaron-software│
                    │ /software-factory│
                    └─────────────────┘
```

## Projektkonfiguration

Projekte werden in `projects/*.yaml` definiert:

```yaml
project:
  name: my-project
  root_path: /path/to/project
  vision_doc: CLAUDE.md

agents:
  - product_manager
  - solution_architect
  - backend_dev
  - qa_engineer

patterns:
  ideation: hierarchical
  development: parallel
  review: adversarial-pair

deployment:
  strategy: blue-green
  auto_prod: true
  health_check_url: /health

monitoring:
  prometheus: true
  grafana_dashboard: project-metrics
```

## Verzeichnisstruktur

```
├── platform/                # Agenten-Plattform (152 Python-Dateien)
│   ├── server.py            # FastAPI-App, Port 8090
│   ├── agents/              # Agenten-Schleife, Executor, Store
│   ├── a2a/                 # Agent-zu-Agent-Nachrichtenbus
│   ├── patterns/            # 10 Orchestrierungsmuster
│   ├── missions/            # SAFe-Missionslebenszyklus
│   ├── sessions/            # Konversations-Runner + SSE
│   ├── web/                 # Routen + Jinja2-Templates
│   ├── mcp_platform/        # MCP-Server (23 Tools)
│   └── tools/               # Agenten-Werkzeuge (Code, Git, Deploy)
│
├── cli/                     # CLI 'sf' (6 Dateien, 2100+ LOC)
│   ├── sf.py                # 22 Befehlsgruppen, 40+ Unterbefehle
│   ├── _api.py              # httpx REST-Client
│   ├── _db.py               # sqlite3 Offline-Backend
│   ├── _output.py           # ANSI-Tabellen, Markdown-Rendering
│   └── _stream.py           # SSE-Streaming mit Spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm Charts, Docker, K8s
├── tests/                   # E2E Playwright-Tests
├── skills/                  # Agenten-Faehigkeitsbibliothek
├── projects/                # Projekt-YAML-Konfigurationen
└── data/                    # SQLite-Datenbank
```

## Tests

```bash
# Alle Tests ausfuehren
make test

# E2E-Tests (Playwright — erfordert vorherige Installation)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Unit-Tests
pytest tests/

# Chaos Engineering
python3 tests/test_chaos.py

# Ausdauertests
python3 tests/test_endurance.py
```

## Bereitstellung

### Docker

Das Docker-Image enthaelt: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.
Agenten koennen Projekte bauen, E2E-Tests mit Screenshots ausfuehren und SAST-Sicherheitsscans sofort durchfuehren.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### Umgebungsvariablen

Siehe [`.env.example`](.env.example) fuer die vollstaendige Liste. Wichtige Variablen:

```bash
# LLM-Anbieter (erforderlich fuer echte Agenten)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API-Key

# Authentifizierung (optional)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# Integrationen (optional)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Neuheiten in v2.1.0 (Feb 2026)

### Qualitaetsmetriken — Industrielles Monitoring
- **10 deterministische Dimensionen** — Komplexitaet, Abdeckung (UT/E2E), Sicherheit, Barrierefreiheit, Performance, Dokumentation, Architektur, Wartbarkeit, Adversarial
- **Qualitaets-Gates auf Workflow-Phasen** — PASS/FAIL-Badges pro Phase mit konfigurierbaren Schwellenwerten (always/no_veto/all_approved/quality_gate)
- **Qualitaets-Dashboard** unter `/quality` — globale Scorecard, projektbezogene Bewertungen, Trend-Snapshots
- **Qualitaets-Badges ueberall** — Missionsdetails, Projekt-Board, Workflow-Phasen, Haupt-Dashboard
- **Kein LLM erforderlich** — alle Metriken deterministisch berechnet mit Open-Source-Tools (radon, bandit, semgrep, coverage.py, pa11y, madge)

### 4 automatisch bereitgestellte Missionen pro Projekt
Jedes Projekt erhaelt automatisch 4 operative Missionen:
- **MCO/TMA** — kontinuierliche Wartung: Zustandsueberwachung, Vorfall-Triage (P0-P4), TDD-Fix, Nicht-Regressionsvalidierung
- **Sicherheit** — woechentliche SAST-Scans, Abhaengigkeitsaudit, CVE-Ueberwachung, Code-Review
- **Technische Schulden** — monatliche Schuldenreduktion: Komplexitaetsaudit, WSJF-Priorisierung, Refactoring-Sprints
- **Selbstheilung** — autonome Vorfall-Pipeline: 5xx-Erkennung → TMA-Missionserstellung → Agenten-Diagnose → Code-Fix → Validierung

### Kontinuierliche Verbesserung
- **quality-improvement Workflow** — Scan → schlechteste Dimensionen identifizieren → Verbesserungen planen & umsetzen
- **retrospective-quality Workflow** — Sprint-Retro mit ROTI, Vorfaellen, Qualitaetsmetriken → Massnahmen
- **skill-evolution Workflow** — Agenten-Performance analysieren → Prompts aktualisieren → Faehigkeiten weiterentwickeln
- **Feedback-Schleife** — Metriken → Analyse → Verbesserung → erneuter Scan → Fortschritt verfolgen

### SAFe-Perspektiven & Onboarding
- **9 SAFe-Rollenperspektiven** — adaptives Dashboard, Seitenleiste und KPIs pro Rolle
- **Onboarding-Assistent** — 3-stufiger Erstbenutzer-Flow mit Rollen- und Projektauswahl
- **Perspektiven-Auswahl** — SAFe-Rolle jederzeit ueber die Kopfleiste wechseln

### Selbstheilung & Selbstreparatur
- **TMA-Heartbeat** — kontinuierliches Zustandsmonitoring mit automatischer Vorfallserstellung
- **Selbstreparatur-Agenten** — autonome Diagnose und Behebung gaengiger Fehler
- **Ticket-Eskalation** — ungeloeste Vorfaelle erstellen nachverfolgte Tickets mit Benachrichtigungen

### 4-Schichten-Speicher & RLM
- **Persistentes Wissen** — Sitzungs-, Muster-, Projekt- und globale Speicherschichten mit FTS5
- **RLM Deep Search** — rekursive Explorationsschleife (bis zu 10 Iterationen) fuer komplexe Codebase-Analyse
- **Automatisch geladener Projektkontext** — CLAUDE.md, SPECS.md, VISION.md werden in jeden Agenten-Prompt injiziert

### Adversarial Quality Guard
- **L0 deterministisch** — sofortige Erkennung von Slop, Mocks, Fake-Builds, Halluzinationen
- **L1 semantisch** — LLM-basierte Qualitaetspruefung fuer Ausfuehrungsausgaben
- **Zwangsablehnung** — Halluzinationen und Stack-Unstimmigkeiten werden immer blockiert

### Agenten-Mercato
- **Token-basierter Marktplatz** mit Agenten-Angeboten, Transfers, Leihen und Free-Agent-Draft
- **Marktbewertung** — automatische Agentenpreisgestaltung basierend auf Faehigkeiten und Leistung
- **Wallet-System** — Token-Oekonomie pro Projekt mit Transaktionsverlauf

### Authentifizierung & Sicherheit
- **JWT-basierte Authentifizierung** mit Login/Registrierung/Refresh/Logout
- **RBAC** — Rollen: Admin, Project Manager, Developer, Viewer
- **OAuth** — GitHub und Azure AD SSO-Login
- **Admin-Panel** — Benutzerverwaltungsoberflaeche (`/admin/users`)
- **Demo-Modus** — Ein-Klick-"Skip"-Button fuer sofortigen Zugang

### Auto-Dokumentation
- **Sprint-Retrospektiven** — LLM-generierte Retro-Notizen mit Lernschleife
- **Phasen-Zusammenfassungen** — automatische Dokumentation der Missionsphasen-Ergebnisse
- **Confluence-Sync** — bidirektionale Wiki-Integration

### LLM-Anbieter
- **Multi-Provider** mit automatischer Fallback-Kette
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Demo-Modus** zur Oberflaechenerkundung ohne API-Keys

### Plattform-Verbesserungen
- DORA-Metriken-Dashboard mit LLM-Kostenverfolgung
- Bidirektionale Jira-Synchronisation
- Playwright E2E-Testsuite (11 Spec-Dateien)
- Internationalisierung (EN/FR)
- Echtzeit-Benachrichtigungen (Slack, E-Mail, Webhook)
- Design-System-Pipeline in Workflows (UX → Dev → Review)
- 3D-Agentenwelt-Visualisierung

## Neuheiten in v2.2.0 (Feb 2026)

### OpenTelemetry & Distributed Tracing
- **OTEL-Integration** — OpenTelemetry SDK mit OTLP/HTTP-Exporter zu Jaeger
- **ASGI-Tracing-Middleware** — jede HTTP-Anfrage wird mit Spans, Latenz und Status getrackt
- **Tracing-Dashboard** unter `/analytics` — Request-Statistiken, Latenz-Diagramme, Operationstabelle
- **Jaeger-UI** — vollstaendige Distributed-Trace-Exploration auf Port 16686

### Pipeline-Fehleranalyse
- **Fehlerklassifizierung** — Python-basierte Fehlerkategorisierung (setup_failed, llm_provider, timeout, phase_error, etc.)
- **Phasen-Fehler-Heatmap** — identifiziert welche Pipeline-Phasen am haeufigsten fehlschlagen
- **Empfehlungs-Engine** — umsetzbare Vorschlaege basierend auf Fehlermustern
- **Resume-All-Button** — Ein-Klick-Massenwiederaufnahme pausierter Runs vom Dashboard

### Kontinuierlicher Watchdog
- **Auto-Wiederaufnahme** — pausierte Runs automatisch batchweise fortsetzen (5/Batch, alle 5 Min, max 10 gleichzeitig)
- **Sitzungswiederherstellung** — erkennt Sitzungen, die >30 Min inaktiv sind, markiert sie fuer Retry
- **Bereinigung fehlgeschlagener Sitzungen** — Zombie-Sitzungen bereinigen, die den Pipeline-Fortschritt blockieren
- **Blockadeerkennung** — Missionen, die >60 Min in einer Phase feststecken, werden automatisch neu gestartet

### Phasen-Resilienz
- **Retry pro Phase** — konfigurierbarer Retry-Zaehler (Standard 3x) mit exponentiellem Backoff pro Phase
- **skip_on_failure** — Phasen koennen als optional markiert werden, sodass die Pipeline fortfahren kann
- **Checkpointing** — abgeschlossene Phasen werden gespeichert, intelligente Wiederaufnahme ueberspringt erledigte Arbeit
- **Phasen-Timeout** — 10-Minuten-Limit verhindert endloses Haengen

### Sandbox Build-Validierung
- **Post-Code-Build-Pruefung** — nach Code-Generierungsphasen automatisch Build/Lint ausfuehren
- **Automatische Build-System-Erkennung** — npm, cargo, go, maven, python, docker
- **Fehlereinspeisung** — Build-Fehler werden in den Agentenkontext injiziert zur Selbstkorrektur

### Qualitaets-UI-Verbesserungen
- **Radar-Chart** — Chart.js-Radar-Visualisierung der Qualitaetsdimensionen auf `/quality`
- **Qualitaets-Badge** — farbiger Score-Kreis fuer Projekt-Header (`/api/dashboard/quality-badge`)
- **Missions-Scorecard** — Qualitaetsmetriken in der Missionsdetail-Seitenleiste (`/api/dashboard/quality-mission`)

## Mitwirken

Wir freuen uns ueber Beitraege! Bitte lesen Sie [CONTRIBUTING.md](CONTRIBUTING.md) fuer Richtlinien.

## Lizenz

Dieses Projekt ist unter der AGPL v3 Lizenz lizenziert — siehe die [LICENSE](LICENSE)-Datei fuer Details.

## Support

- Live-Demo: https://sf.macaron-software.com
- Issues: https://github.com/macaron-software/software-factory/issues
- Diskussionen: https://github.com/macaron-software/software-factory/discussions
