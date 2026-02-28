<p align="center">
  <a href="README.md">English</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.zh-CN.md">中文</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.ja.md">日本語</a> |
  <a href="README.pt.md">Português</a> |
  <a href="README.de.md">Deutsch</a> |
  <a href="README.ko.md">한국어</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ru.md">Русский</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.id.md">Bahasa</a> |
  <a href="README.tr.md">Türkçe</a> |
  <a href="README.it.md">Italiano</a> |
  <a href="README.nl.md">Nederlands</a> |
  <a href="README.vi.md">Tiếng Việt</a> |
  <a href="README.pl.md">Polski</a> |
  <a href="README.sv.md">Svenska</a>
</p>

<div align="center">

# Software Factory

**Fabbrica Software Multi-Agente — Agenti IA autonomi orchestrano l'intero ciclo di vita del prodotto**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live: sf.macaron-software.com](https://sf.macaron-software.com)**

[Funzionalità](#funzionalità) · [Avvio rapido](#avvio-rapido) · [Screenshot](#screenshot) · [Architettura](#architettura) · [Contribuire](#contribuire)

</div>

---

## Cos'è questo?

Software Factory è una **piattaforma multi-agente autonoma** che orchestra l'intero ciclo di sviluppo software — dall'ideazione alla distribuzione — tramite agenti IA specializzati che collaborano tra loro.

Immaginate una **fabbrica software virtuale** in cui 191 agenti IA collaborano attraverso flussi di lavoro strutturati, seguendo la metodologia SAFe, applicando le pratiche TDD e sfruttando gate di qualità automatizzati.

### Caratteristiche principali

- **191 agenti specializzati** — architetti, sviluppatori, tester, SRE, analisti della sicurezza, product owner
- **36 workflow integrati** — cerimonie SAFe, gate di qualità, manutenzione notturna, sicurezza, gestione della conoscenza
- **Gestione della conoscenza** — 4 agenti dedicati, team ART-Knowledge, workflow notturno `knowledge-maintenance`
- **Memory Intelligence** — punteggio di rilevanza, tracciamento degli accessi, eliminazione automatica delle voci obsolete
- **Monitoraggio dei costi LLM** — costi per missione visualizzati nell'intestazione della scheda Timeline della missione
- **Timeline della missione** — scheda Timeline swimlane che mostra la durata delle fasi in Mission Control
- **10 pattern di orchestrazione** — Solo, Sequenziale, Parallelo, Gerarchico, Rete, Ciclo, Router, Aggregatore, Onda, Human-in-the-Loop
- **Ciclo di vita allineato a SAFe** — Portfolio → Epic → Feature → Story con cadenza PI
- **Auto-guarigione** — rilevamento autonomo degli incidenti, triage e auto-riparazione
- **Resilienza LLM** — fallback multi-provider, retry con jitter, gestione dei limiti di frequenza, configurazione del modello tramite variabili d'ambiente
- **Osservabilità OpenTelemetry** — distributed tracing con Jaeger, dashboard di analytics della pipeline
- **Watchdog continuo** — ripresa automatica delle esecuzioni in pausa, recupero della sessione, pulizia delle esecuzioni fallite
- **Sicurezza prima di tutto** — protezione contro prompt injection, RBAC, eliminazione dei segreti, connection pooling
- **Metriche DORA** — frequenza di deployment, lead time, MTTR, tasso di failure dei cambiamenti

## Screenshot

<table>
<tr>
<td width="50%">
<strong>Dashboard — Prospettiva SAFe adattiva</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — Backlog strategico e WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Pianificazione degli incrementi di programma</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Workshop di ideazione — Brainstorming assistito dall'IA</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Train e team di agenti</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>Cerimonie — Modelli di workflow e pattern</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoraggio — Metriche DORA e stato del sistema</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — Assistente per la selezione del ruolo SAFe</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Pagina iniziale — CTO Jarvis / Ideazione business / Ideazione progetto</strong><br>
<img src="docs/screenshots/en/home.png" alt="Pagina iniziale" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — Consulente strategico IA</strong><br>
<img src="docs/screenshots/en/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Ideazione business — Team marketing a 6 agenti</strong><br>
<img src="docs/screenshots/en/mkt_ideation.png" alt="Ideazione business" width="100%">
</td>
<td width="50%">
<strong>Ideazione progetto — Team tecnico multi-agente</strong><br>
<img src="docs/screenshots/en/ideation_projet.png" alt="Ideazione progetto" width="100%">
</td>
</tr>
</table>

## Avvio rapido

### Opzione 1: Docker (Consigliato)

L'immagine Docker include: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # copia .env.example → .env (modificare il file per inserire la propria chiave API LLM)
make run     # compila e avvia la piattaforma
```

Aprire http://localhost:8090 — cliccare su **"Skip (Demo)"** per esplorare senza chiave API.

### Opzione 2: Installazione locale

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # creare la configurazione (inserire la chiave LLM — vedere il passo 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Avviare la piattaforma
make dev
# oppure manualmente: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

Aprire http://localhost:8090 — al primo avvio apparirà l'**assistente di onboarding**.
Scegliere il proprio ruolo SAFe oppure cliccare su **"Skip (Demo)"** per iniziare subito.

### Passo 3: Configurare il provider LLM

Senza chiave API la piattaforma funziona in **modalità demo** — gli agenti rispondono con risposte simulate.
Questo è utile per esplorare l'interfaccia, ma gli agenti non generano codice reale né analisi.

Per attivare gli agenti IA reali, modificare `.env` e aggiungere **una** chiave API:

```bash
# Opzione A: MiniMax (consigliato per iniziare)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# Opzione B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Opzione C: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

Poi riavviare: `make run` (Docker) oppure `make dev` (locale)

| Provider | Variabile d'ambiente | Modelli |
|----------|----------------------|---------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

La piattaforma passa automaticamente ad altri provider configurati in caso di guasto del provider primario.
È possibile configurare i provider anche dalla pagina **Impostazioni** nel dashboard (`/settings`).

## Per iniziare — Il vostro primo progetto

Dopo l'installazione, potete passare dall'idea al progetto completato nel modo seguente:

### Percorso A: Chiedere al CTO Jarvis (Accesso più rapido)

1. **Aprire la pagina iniziale** (`/`) — la piattaforma si avvia nella scheda CTO Jarvis
2. **Digitare la propria idea di progetto** — ad es. *"Crea un progetto per un'app aziendale di carpooling con React e Python"*
3. **Jarvis (Gabriel Mercier, Orchestratore Strategico)** analizza la richiesta, crea il progetto, predispone il backlog SAFe e avvia la prima missione — tutto in una conversazione

Questo è il **punto di ingresso consigliato** per ogni nuovo progetto.

### Percorso B: Creare il progetto manualmente

1. Andare a `/projects` e cliccare su **"Nuovo progetto"**
2. Compilare: nome, descrizione, stack tecnologico, percorso del repository
3. La piattaforma crea automaticamente:
   - Un **agente Product Manager** assegnato al progetto
   - Una **missione TMA** (manutenzione continua — monitora lo stato, crea incidenti)
   - Una **missione Sicurezza** (audit di sicurezza settimanali — SAST, verifica delle dipendenze)
   - Una **missione Debito tecnico** (riduzione mensile del debito — pianificata)

### Poi: Creare Epic e Feature

- Creare Epic nella pagina **Portfolio** (`/portfolio`) con prioritizzazione WSJF
- Aggiungere **Feature** da un Epic e suddividerle in **User Story**
- Utilizzare il **PI Board** (`/pi-board`) per pianificare gli incrementi di programma e assegnare le feature agli sprint

### Eseguire le missioni

- Cliccare su **"Avvia"** su qualsiasi missione per avviare l'esecuzione degli agenti
- Scegliere un **pattern di orchestrazione** (gerarchico, rete, parallelo...)
- Osservare gli agenti in tempo reale tramite **Mission Control**
- Gli agenti utilizzano i propri strumenti (code_read, git, build, test, security scan) in modo autonomo

### TMA e Sicurezza — Sempre attivi

Questi sono **attivati automaticamente** per ogni progetto — nessuna configurazione necessaria:

| Missione | Tipo | Pianificazione | Cosa fa |
|----------|------|----------------|---------|
| **TMA** | Programma | Continua | Monitoraggio dello stato, rilevamento incidenti, auto-riparazione, creazione ticket |
| **Sicurezza** | Revisione | Settimanale | Scansioni SAST (bandit/semgrep), audit delle dipendenze, rilevamento segreti |
| **Debito tecnico** | Riduzione | Mensile | Analisi della qualità del codice, raccomandazioni di refactoring |
| **Auto-guarigione** | Programma | Continua | Rilevamento auto di 5xx/crash → missione TMA → diagnosi agenti → fix del codice → validazione |

Tutte e quattro vengono create con il progetto. TMA, Sicurezza e Auto-guarigione partono come **attive**, il Debito tecnico parte come **pianificazione** (da attivare quando si è pronti).

## Funzionalità

### 191 agenti IA specializzati

Gli agenti sono organizzati in team che rispecchiano le vere organizzazioni software:

| Team | Agenti | Ruolo |
|------|--------|-------|
| **Prodotto** | Product Manager, Business Analyst, PO | Pianificazione SAFe, prioritizzazione WSJF |
| **Architettura** | Solution Architect, Tech Lead, System Architect | Decisioni architetturali, design pattern |
| **Sviluppo** | Backend/Frontend/Mobile/Data Engineers | Implementazione TDD per stack |
| **Qualità** | QA Engineers, Security Analysts, Test Automation | Test, audit di sicurezza, penetration test |
| **Design** | UX Designer, UI Designer | Esperienza utente, design visuale |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, monitoraggio, infrastruttura |
| **Management** | Scrum Master, RTE, Agile Coach | Cerimonie, facilitazione, rimozione degli impedimenti |

### 10 pattern di orchestrazione

- **Solo** — agente singolo per compiti semplici
- **Sequenziale** — pipeline di agenti in sequenza
- **Parallelo** — più agenti lavorano contemporaneamente
- **Gerarchico** — un manager delega a sotto-agenti
- **Rete** — agenti collaborano peer-to-peer
- **Ciclo** — un agente itera finché la condizione è soddisfatta
- **Router** — un agente instrada verso gli specialisti in base all'input
- **Aggregatore** — più input vengono consolidati da un aggregatore
- **Onda** — parallelo all'interno delle onde, sequenziale tra le onde
- **Human-in-the-Loop** — l'agente propone, l'umano valida

### Ciclo di vita allineato a SAFe

Gerarchia completa Portfolio → Epic → Feature → Story con:

- **Portfolio strategico** — Portfolio Canvas, temi strategici, value stream
- **Incremento di programma** — pianificazione PI, obiettivi, dipendenze
- **Backlog del team** — User Story, attività, criteri di accettazione
- **Esecuzione dello sprint** — Daily Standup, Sprint Review, Retrospettive

### Sicurezza e conformità

- **Autenticazione** — autenticazione basata su JWT con RBAC
- **Protezione prompt injection** — rilevamento e blocco dei prompt malevoli
- **Eliminazione dei segreti** — oscuramento automatico dei dati sensibili
- **CSP (Content Security Policy)** — header rafforzati
- **Rate limiting** — quote API per utente
- **Audit logging** — registri completi delle attività

### Metriche DORA e monitoraggio

- **Frequenza di deployment** — quante volte il codice arriva in produzione
- **Lead time** — durata dal commit al deployment
- **MTTR** — tempo medio di ripristino dopo gli incidenti
- **Tasso di failure dei cambiamenti** — percentuale di deployment falliti
- **Dashboard in tempo reale** — visualizzazioni Chart.js
- **Metriche Prometheus** — endpoint /metrics

### Metriche di qualità — Monitoraggio industriale

Scansione qualitativa deterministica (senza LLM) con 10 dimensioni, come una linea di produzione:

| Dimensione | Strumenti | Cosa misura |
|------------|-----------|-------------|
| **Complessità** | radon, lizard | Complessità ciclomatica, complessità cognitiva |
| **Copertura unit test** | coverage.py, nyc | Copertura di righe/branch in percentuale |
| **Copertura E2E** | Playwright | Numero di file di test, copertura delle spec |
| **Sicurezza** | bandit, semgrep | Risultati SAST per gravità (critico/alto/medio/basso) |
| **Accessibilità** | pa11y | Violazioni WCAG 2.1 AA |
| **Performance** | Lighthouse | Punteggi Core Web Vitals |
| **Documentazione** | interrogate | README, Changelog, API docs, copertura docstring |
| **Architettura** | madge, jscpd, mypy | Dipendenze circolari, duplicazione del codice, errori di tipo |
| **Manutenibilità** | custom | Distribuzione dimensione file, proporzione file grandi |
| **Avversariale** | built-in | Tasso di incidenti, tasso di rifiuto avversariale |

**Gate di qualità sulle fasi del workflow** — ogni fase del workflow mostra un badge di qualità (PASS/FAIL/PENDING) basato sulle soglie delle dimensioni configurate per tipo di gate:

| Tipo di gate | Soglia | Usato in |
|--------------|--------|----------|
| `always` | 0% | Fasi di analisi e pianificazione |
| `no_veto` | 50% | Fasi di implementazione e sprint |
| `all_approved` | 70% | Fasi di revisione e rilascio |
| `quality_gate` | 80% | Fasi di deploy e produzione |

**Dashboard qualità** su `/quality` — scorecard globale, valutazioni per progetto, snapshot di tendenza.
Badge di qualità visibili nei dettagli delle missioni, nella board del progetto, nelle fasi del workflow e nel dashboard principale.

### Workflow di miglioramento continuo

Tre workflow integrati di auto-miglioramento:

| Workflow | Scopo | Agenti |
|----------|-------|--------|
| **quality-improvement** | Scansiona le metriche → identifica le dimensioni peggiori → pianifica e attua i miglioramenti | QA Lead, Dev, Architect |
| **retrospective-quality** | Retro sprint: raccoglie ROTI, incidenti, dati di qualità → definisce le azioni | Scrum Master, QA, Dev |
| **skill-evolution** | Analizza le performance degli agenti → aggiorna i prompt di sistema → evolve le competenze | Brain, Lead Dev, QA |

Questi workflow generano un **ciclo di feedback**: metriche → analisi → miglioramento → nuova scansione → tracciamento dei progressi.

### Strumenti integrati degli agenti

L'immagine Docker contiene tutto il necessario affinché gli agenti operino in modo autonomo:

| Categoria | Strumenti | Descrizione |
|-----------|-----------|-------------|
| **Codice** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | Leggere, scrivere e cercare file di progetto |
| **Build** | `build`, `test`, `local_ci` | Eseguire build, test e pipeline CI locali (npm/pip/cargo rilevati automaticamente) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | Controllo versione con isolamento del branch per agente |
| **Sicurezza** | `sast_scan`, `dependency_audit`, `secrets_scan` | SAST tramite bandit/semgrep, audit CVE, rilevamento segreti |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Test E2E Playwright e screenshot (Chromium incluso) |
| **Ticket** | `create_ticket`, `jira_search`, `jira_create` | Creare incidenti/ticket per il tracciamento TMA |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | Distribuzione container e stato CI/CD |
| **Memoria** | `memory_store`, `memory_search`, `deep_search` | Memoria persistente del progetto tra le sessioni |

### Auto-guarigione e auto-riparazione (TMA)

Ciclo autonomo per il rilevamento degli incidenti, triage e auto-riparazione:

- **Monitoraggio heartbeat** — controlli continui dello stato di tutte le missioni e i servizi in esecuzione
- **Rilevamento automatico degli incidenti** — HTTP 5xx, timeout, crash degli agenti → creazione automatica dell'incidente
- **Triage e classificazione** — gravità (P0-P3), analisi dell'impatto, ipotesi sulla causa principale
- **Auto-riparazione** — gli agenti diagnosticano e risolvono i problemi in modo autonomo (patch del codice, modifiche alla configurazione, riavvii)
- **Creazione ticket** — gli incidenti irrisolti creano automaticamente ticket tracciati per la revisione umana
- **Escalation** — gli incidenti P0/P1 attivano notifiche Slack/email al team di guardia
- **Ciclo retrospettivo** — i risultati post-incidente vengono memorizzati e iniettati negli sprint futuri

### Prospettive SAFe e onboarding

Interfaccia adattiva basata sul ruolo che rispecchia le vere organizzazioni SAFe:

- **9 prospettive SAFe** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Dashboard adattivo** — KPI, azioni rapide e link nella barra laterale cambiano in base al ruolo selezionato
- **Assistente di onboarding** — flusso a 3 fasi per i nuovi utenti (scegliere il ruolo → scegliere il progetto → avviare)
- **Selezione della prospettiva** — cambiare il ruolo SAFe in qualsiasi momento tramite il menu a tendina nell'intestazione
- **Barra laterale dinamica** — mostra solo la navigazione pertinente alla prospettiva corrente

### Memoria a 4 livelli e RLM Deep Search

Conoscenza persistente tra le sessioni con interrogazione intelligente:

- **Memoria di sessione** — contesto della conversazione all'interno di una singola sessione
- **Memoria dei pattern** — conoscenze acquisite dall'esecuzione dei pattern di orchestrazione
- **Memoria di progetto** — conoscenza specifica del progetto (decisioni, convenzioni, architettura)
- **Memoria globale** — conoscenza organizzativa cross-progetto (ricerca full-text FTS5)
- **File di progetto caricati automaticamente** — CLAUDE.md, SPECS.md, VISION.md, README.md vengono iniettati in ogni prompt LLM (max 8K)
- **RLM Deep Search** — Recursive Language Model (arXiv:2512.24601) — ciclo iterativo WRITE-EXECUTE-OBSERVE-DECIDE con fino a 10 iterazioni di esplorazione

### Agenti Mercato (Mercato dei trasferimenti)

Mercato degli agenti basato su token per la composizione dei team:

- **Offerte di agenti** — mettere in vendita agenti con un prezzo richiesto
- **Pool di agenti liberi** — agenti non assegnati disponibili per il draft
- **Trasferimenti e prestiti** — acquistare, vendere o prestare agenti tra progetti
- **Valutazione di mercato** — valutazione automatica degli agenti basata su competenze, esperienza e performance
- **Sistema wallet** — portafogli token per progetto con storico delle transazioni
- **Sistema draft** — richiedere agenti liberi per il proprio progetto

### Guardia di qualità avversariale

Gate di qualità a due livelli che impedisce al codice finto/segnaposto di superare i controlli:

- **L0 Deterministico** — rilevamento immediato di slop (Lorem Ipsum, TBD), mock (NotImplementedError, TODO), build false, allucinazioni, incoerenze di stack
- **L1 LLM Semantico** — un LLM separato valuta la qualità dell'output per i pattern di esecuzione
- **Punteggio** — score < 5 superato, 5-6 soft pass con avviso, 7+ rifiutato
- **Rifiuto forzato** — allucinazioni, slop, incoerenze di stack, build false vengono sempre rifiutati indipendentemente dal punteggio

### Auto-documentazione e Wiki

Generazione automatica della documentazione durante l'intero ciclo di vita:

- **Retrospettive sprint** — note retro generate da LLM, memorizzate e iniettate nei prompt degli sprint successivi (ciclo di apprendimento)
- **Riepiloghi di fase** — ogni fase della missione genera un riepilogo LLM delle decisioni e dei risultati
- **Architecture Decision Records** — i pattern architetturali documentano automaticamente le decisioni di design nella memoria del progetto
- **File di contesto del progetto** — file di istruzioni caricati automaticamente (CLAUDE.md, SPECS.md, CONVENTIONS.md) fungono da documentazione vivente
- **Sincronizzazione Confluence** — sincronizzazione bidirezionale con le pagine wiki Confluence per la documentazione aziendale
- **Swagger Auto-Docs** — 94 endpoint REST documentati automaticamente su `/docs` con schema OpenAPI

## Quattro interfacce

### 1. Web Dashboard (HTMX + SSE)

Interfaccia principale su http://localhost:8090:

- **Conversazioni multi-agente in tempo reale** con streaming SSE
- **PI Board** — pianificazione degli incrementi di programma
- **Mission Control** — monitoraggio dell'esecuzione
- **Gestione agenti** — visualizzare, configurare, monitorare gli agenti
- **Dashboard incidenti** — triage per l'auto-guarigione
- **Responsive per mobile** — funziona su tablet e smartphone

### 2. CLI (`sf`)

Interfaccia completa a riga di comando:

```bash
# Installazione (aggiungere al PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Esplorare
sf status                              # stato della piattaforma
sf projects list                       # tutti i progetti
sf missions list                       # missioni con punteggi WSJF
sf agents list                         # 145 agenti
sf features list <epic_id>             # feature dell'epic
sf stories list --feature <id>         # user story

# Lavorare
sf ideation "e-commerce app in React"  # ideazione multi-agente (in streaming)
sf missions start <id>                 # avviare una missione
sf metrics dora                        # metriche DORA

# Monitorare
sf incidents list                      # incidenti
sf llm stats                           # utilizzo LLM (token, costi)
sf chaos status                        # chaos engineering
```

**22 gruppi di comandi** · Modalità doppia: API (server live) o DB (offline) · Output JSON (`--json`) · Animazioni spinner · Rendering tabelle Markdown

### 3. REST API + Swagger

94 endpoint API documentati automaticamente su `/docs` (Swagger UI):

```bash
# Esempi
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

### 4. Server MCP (Model Context Protocol)

24 strumenti MCP per l'integrazione di agenti IA (porta 9501):

```bash
# Avviare il server MCP
python3 -m platform.mcp_platform.server

# Strumenti disponibili:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## Architettura

### Panoramica della piattaforma

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
          │ 191 agents   │   │  Engine  │   │    Layer     │
          │ executor     │   │ 36 defs  │   │ SAFe cycle   │
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

### Flusso della pipeline

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

### Osservabilità

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

### Distribuzione

```
Docker (consigliato) → http://localhost:8090
Locale (sviluppo)    → http://localhost:8090
Produzione           → infrastruttura propria
```

## Configurazione del progetto

I progetti sono definiti in `projects/*.yaml`:

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

## Struttura delle directory

```
├── platform/                # Piattaforma agenti (152 file Python)
│   ├── server.py            # App FastAPI, porta 8090
│   ├── agents/              # Ciclo agenti, executor, store
│   ├── a2a/                 # Bus messaggi agente-agente
│   ├── patterns/            # 10 pattern di orchestrazione
│   ├── missions/            # Ciclo di vita missioni SAFe
│   ├── sessions/            # Runner conversazioni + SSE
│   ├── web/                 # Route + template Jinja2
│   ├── mcp_platform/        # Server MCP (23 strumenti)
│   └── tools/               # Strumenti agenti (codice, git, deploy)
│
├── cli/                     # CLI 'sf' (6 file, 2100+ LOC)
│   ├── sf.py                # 22 gruppi di comandi, 40+ sottocomandi
│   ├── _api.py              # Client REST httpx
│   ├── _db.py               # Backend offline sqlite3
│   ├── _output.py           # Tabelle ANSI, rendering Markdown
│   └── _stream.py           # Streaming SSE con spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm Charts, Docker, K8s
├── tests/                   # Test E2E Playwright
├── skills/                  # Libreria competenze agenti
├── projects/                # Configurazioni YAML del progetto
└── data/                    # Database SQLite
```

## Test

```bash
# Eseguire tutti i test
make test

# Test E2E (Playwright — richiede installazione preliminare)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Unit test
pytest tests/

# Chaos engineering
python3 tests/test_chaos.py

# Test di resistenza
python3 tests/test_endurance.py
```

## Distribuzione

### Docker

L'immagine Docker include: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.
Gli agenti possono compilare progetti, eseguire test E2E con screenshot e scansioni di sicurezza SAST immediatamente.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### Variabili d'ambiente

Vedere [`.env.example`](.env.example) per l'elenco completo. Variabili principali:

```bash
# Provider LLM (richiesto per agenti reali)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # Chiave API MiniMax

# Autenticazione (opzionale)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# Integrazioni (opzionale)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Intelligenza adattiva — GA · RL · Thompson Sampling · OKR

La piattaforma si ottimizza da sola attraverso tre motori IA complementari.

### Thompson Sampling — Selezione probabilistica del team
- `Beta(wins+1, losses+1)` per contesto `(agent_id, pattern_id, technology, phase_type)`
- Punteggio di fitness granulare — punteggio separato per contesto, nessun bleeding tra contesti
- Fallback cold-start tramite catena di prefissi tecnologici (`angular_19` → `angular_*` → `generic`)
- Ritiro morbido: `weight_multiplier=0.1` per i team deboli, reversibile
- A/B shadow run automatici; un valutatore neutrale sceglie il vincitore
- **Darwin LLM**: estende Thompson Sampling alla selezione del modello LLM per contesto

### Algoritmo genetico — Evoluzione dei workflow
- Genoma = lista ordinata di PhaseSpec (pattern, agenti, gate)
- Popolazione: 40 genomi, max 30 generazioni, elitismo=2, tasso di mutazione=15%, torneo k=3
- Fitness: tasso di successo delle fasi × fitness agenti × (1 − tasso veto) × bonus lead time
- Le prime 3 proposte vengono memorizzate in `evolution_proposals` per la revisione umana
- Trigger manuale: `POST /api/evolution/run/{wf_id}` — visualizzare in Workflow → Evoluzione
- Scheduler notturno; saltato se < 5 missioni

### Reinforcement Learning — Adattamento del pattern durante la missione
- Policy Q-learning (`platform/agents/rl_policy.py`)
- Azioni: keep, switch_parallel, switch_sequential, switch_hierarchical, switch_debate, add_agent, remove_agent
- Stato: `(wf_id, phase_position, rejection_pct, quality_score)` raggruppato
- Aggiornamento Q: α=0.1, γ=0.9, ε=0.1 — batch offline sulla tabella `rl_experience`
- Attivato solo con confidenza ≥ 70% con ≥ 3 visite di stato; degradazione graduale

### Sistema OKR / KPI
- 8 seed standard: code/migration, security/audit, architecture/design, testing, docs
- Il raggiungimento degli OKR influisce direttamente sulla fitness del GA e sul segnale di reward RL
- Modifica inline su `/teams` con stato verde/giallo/rosso
- Override OKR specifici per progetto tramite impostazioni

---

## Novità in v2.1.0 (Feb 2026)

### Metriche di qualità — Monitoraggio industriale
- **10 dimensioni deterministiche** — complessità, copertura (UT/E2E), sicurezza, accessibilità, performance, documentazione, architettura, manutenibilità, avversariale
- **Gate di qualità sulle fasi del workflow** — badge PASS/FAIL per fase con soglie configurabili (always/no_veto/all_approved/quality_gate)
- **Dashboard qualità** su `/quality` — scorecard globale, valutazioni per progetto, snapshot di tendenza
- **Badge di qualità ovunque** — dettagli missioni, board progetto, fasi workflow, dashboard principale
- **Nessun LLM richiesto** — tutte le metriche calcolate deterministicamente con strumenti open source (radon, bandit, semgrep, coverage.py, pa11y, madge)

### 4 missioni distribuite automaticamente per progetto
Ogni progetto riceve automaticamente 4 missioni operative:
- **MCO/TMA** — manutenzione continua: monitoraggio stato, triage incidenti (P0-P4), fix TDD, validazione non-regressione
- **Sicurezza** — scansioni SAST settimanali, audit dipendenze, monitoraggio CVE, code review
- **Debito tecnico** — riduzione mensile del debito: audit complessità, prioritizzazione WSJF, sprint di refactoring
- **Auto-guarigione** — pipeline autonoma degli incidenti: rilevamento 5xx → creazione missione TMA → diagnosi agenti → fix codice → validazione

### Miglioramento continuo
- **Workflow quality-improvement** — scansione → identificazione dimensioni peggiori → pianificazione e attuazione miglioramenti
- **Workflow retrospective-quality** — retro sprint con ROTI, incidenti, metriche di qualità → azioni
- **Workflow skill-evolution** — analisi performance agenti → aggiornamento prompt → evoluzione competenze
- **Ciclo di feedback** — metriche → analisi → miglioramento → nuova scansione → tracciamento progressi

### Prospettive SAFe e onboarding
- **9 prospettive di ruolo SAFe** — dashboard adattivo, barra laterale e KPI per ruolo
- **Assistente di onboarding** — flusso a 3 fasi per i nuovi utenti con selezione di ruolo e progetto
- **Selezione della prospettiva** — cambiare il ruolo SAFe in qualsiasi momento dall'intestazione

### Auto-guarigione e auto-riparazione
- **TMA Heartbeat** — monitoraggio continuo dello stato con creazione automatica degli incidenti
- **Agenti di auto-riparazione** — diagnosi e risoluzione autonoma degli errori comuni
- **Escalation ticket** — gli incidenti irrisolti creano ticket tracciati con notifiche

### Memoria a 4 livelli e RLM
- **Conoscenza persistente** — livelli di memoria sessione, pattern, progetto e globale con FTS5
- **RLM Deep Search** — ciclo di esplorazione ricorsiva (fino a 10 iterazioni) per analisi complessa della codebase
- **Contesto progetto caricato automaticamente** — CLAUDE.md, SPECS.md, VISION.md iniettati in ogni prompt degli agenti

### Guardia di qualità avversariale
- **L0 deterministico** — rilevamento immediato di slop, mock, build false, allucinazioni
- **L1 semantico** — valutazione della qualità degli output di esecuzione basata su LLM
- **Rifiuto forzato** — allucinazioni e incoerenze di stack vengono sempre bloccate

### Agenti Mercato
- **Mercato basato su token** con offerte di agenti, trasferimenti, prestiti e draft di agenti liberi
- **Valutazione di mercato** — prezzi automatici degli agenti basati su competenze e performance
- **Sistema wallet** — economia dei token per progetto con storico delle transazioni

### Autenticazione e sicurezza
- **Autenticazione basata su JWT** con login/registrazione/refresh/logout
- **RBAC** — ruoli: Admin, Project Manager, Developer, Viewer
- **OAuth** — SSO login con GitHub e Azure AD
- **Pannello admin** — interfaccia di gestione utenti (`/admin/users`)
- **Modalità demo** — pulsante "Skip" con un clic per accesso immediato

### Auto-documentazione
- **Retrospettive sprint** — note retro generate da LLM con ciclo di apprendimento
- **Riepiloghi di fase** — documentazione automatica dei risultati delle fasi della missione
- **Sincronizzazione Confluence** — integrazione wiki bidirezionale

### Provider LLM
- **Multi-provider** con catena di fallback automatica
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Modalità demo** per esplorare l'interfaccia senza chiavi API

### Miglioramenti della piattaforma
- Dashboard metriche DORA con tracciamento dei costi LLM
- Sincronizzazione Jira bidirezionale
- Suite di test E2E Playwright (11 file spec)
- Internazionalizzazione (EN/FR)
- Notifiche in tempo reale (Slack, email, webhook)
- Pipeline del sistema di design nei workflow (UX → Dev → Review)
- Visualizzazione 3D del mondo degli agenti

### Darwin — Selezione evolutiva del team
- **Selezione Thompson Sampling** — selezione probabilistica del team agente+pattern tramite `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type)`
- **Tracciamento fitness granulare** — punteggio separato per contesto: un team bravo nella migrazione Angular può essere scarso con le nuove funzionalità Angular
- **Fallback per similarità** — cold start tramite corrispondenza di prefissi tecnologici (`angular_19` → `angular_*` → `generic`)
- **Ritiro morbido** — i team deboli ricevono `weight_multiplier=0.1`, depriorizzati ma recuperabili
- **Sistema OKR / KPI** — obiettivi e indicatori per dominio e tipo di fase; 8 seed standard
- **A/B shadow test** — run paralleli automatici con punteggi di fitness vicini (delta < 10) o probabilità del 10%
- **Dashboard team** su `/teams` — classifica con badge, modifica OKR, curve evolutive, storico selezioni, risultati A/B
- **Opt-in non distruttivo** — `agent_id: "skill:developer"` attiva Darwin; gli ID espliciti rimangono invariati

## Novità in v2.2.0 (Feb 2026)

### OpenTelemetry e Distributed Tracing
- **Integrazione OTEL** — SDK OpenTelemetry con esportatore OTLP/HTTP verso Jaeger
- **Middleware di tracing ASGI** — ogni richiesta HTTP viene tracciata con span, latenza e stato
- **Dashboard tracing** su `/analytics` — statistiche delle richieste, grafici di latenza, tabella delle operazioni
- **Jaeger UI** — esplorazione completa dei trace distribuiti sulla porta 16686

### Analisi degli errori della pipeline
- **Classificazione degli errori** — categorizzazione degli errori basata su Python (setup_failed, llm_provider, timeout, phase_error, ecc.)
- **Heatmap degli errori di fase** — identifica quali fasi della pipeline falliscono più frequentemente
- **Motore di raccomandazioni** — suggerimenti attuabili basati sui pattern di errore
- **Pulsante Resume-All** — ripresa massiva con un clic delle esecuzioni in pausa dal dashboard

### Watchdog continuo
- **Ripresa automatica** — riprendere automaticamente le esecuzioni in pausa in batch (5/batch, ogni 5 minuti, max 10 contemporaneamente)
- **Recupero sessione** — rileva sessioni inattive da >30 minuti, le segna per il retry
- **Pulizia sessioni fallite** — pulire le sessioni zombie che bloccano il progresso della pipeline
- **Rilevamento blocchi** — le missioni bloccate in una fase per >60 minuti vengono riavviate automaticamente

### Resilienza delle fasi
- **Retry per fase** — contatore retry configurabile (default 3x) con backoff esponenziale per fase
- **skip_on_failure** — le fasi possono essere marcate come opzionali in modo che la pipeline possa continuare
- **Checkpointing** — le fasi completate vengono salvate, la ripresa intelligente salta il lavoro già fatto
- **Timeout di fase** — limite di 10 minuti per evitare blocchi infiniti

### Validazione build in sandbox
- **Verifica post-codice** — eseguire automaticamente build/lint dopo le fasi di generazione del codice
- **Rilevamento automatico del sistema di build** — npm, cargo, go, maven, python, docker
- **Iniezione degli errori** — gli errori di build vengono iniettati nel contesto degli agenti per l'auto-correzione

### Miglioramenti UI della qualità
- **Radar chart** — visualizzazione radar Chart.js delle dimensioni di qualità su `/quality`
- **Badge di qualità** — cerchio colorato con punteggio per l'intestazione del progetto (`/api/dashboard/quality-badge`)
- **Scorecard della missione** — metriche di qualità nella barra laterale dei dettagli della missione (`/api/dashboard/quality-mission`)

### Routing LLM multi-modello
- **3 modelli specializzati** — `gpt-5.2` per compiti di reasoning intenso, `gpt-5.1-codex` per codice/test, `gpt-5-mini` per compiti leggeri
- **Routing basato sul ruolo** — gli agenti ricevono automaticamente il modello corretto in base ai tag (`reasoner`, `architect`, `developer`, `tester`, `doc_writer`...)
- **Configurabile in tempo reale** — matrice di routing modificabile in Impostazioni → LLM senza riavvio

### Darwin LLM — Thompson Sampling sui modelli
- **A/B test sui modelli** — gli stessi team (agente + pattern) competono con diversi LLM; il modello migliore si afferma automaticamente per contesto
- **Distribuzione Beta** — `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type, llm_model)`
- **Scheda LLM A/B** su `/teams` — classifica fitness per modello e storico dei test
- **Catena di priorità** — Darwin LLM → configurazione DB → valori predefiniti (degradazione graduale)

### Impostazioni — Scheda LLM
- **Griglia provider** — stato attivo/inattivo con indicazioni sulle chiavi API mancanti
- **Matrice di routing** — pesante/leggero per categoria (reasoning, produzione/codice, attività, redazione)
- **Area A/B Darwin LLM** — visualizzazione in tempo reale degli esperimenti sui modelli in corso

## Novità in v2.7.0 (2026)

### Sistema di gestione della conoscenza
- **4 nuovi agenti** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **Team ART-Knowledge** — Agile Release Train dedicato alle operazioni sulla conoscenza
- **Workflow notturno `knowledge-maintenance`** — curatela automatica, deduplicazione, scoring di freschezza
- **Dashboard memory health** — metriche di salute della conoscenza nella scheda Metriche
- **Badge knowledge health** — visibile nella pagina delle impostazioni

### Memory Intelligence
- **Punteggio di rilevanza** — formula `Confidenza × Attualità × Boost accessi` per il retrieval ponderato
- **Tracciamento degli accessi** — campi `access_count` e `last_read_at` per ogni voce di memoria
- **Pulizia automatica** — le voci obsolete vengono rimosse a ogni esecuzione notturna

### Monitoraggio dei costi LLM
- **Costi per missione** — visualizzati nell'intestazione della scheda Timeline della missione
- **Sommati automaticamente** — aggregati dalla tabella `llm_traces`

### Timeline della missione
- **Scheda Timeline swimlane** — in Mission Control, mostra le fasi degli agenti come tracce orizzontali
- **Durata delle fasi** — rappresentazione visuale del tempo per fase

### Punteggio di qualità
- **Campo `quality_score` su PhaseRun** — compilato dalla guardia avversariale dopo ogni fase

### Esportazione/importazione del progetto
- **Archivio ZIP** — contiene `project.json` + tutte le missioni + run + memoria

### Validazione degli input
- **Modelli Pydantic** — tutte le route POST/PATCH validate con schemi rigidi

### Linee guida di dominio BSCC
- **Linee guida architetturali di dominio** — Confluence/Solaris applicato per dominio di progetto

### Hub delle integrazioni nelle impostazioni
- **Integrazioni strumenti configurabili** — Jira, Confluence, SonarQube disponibili per tutti gli agenti

### Notifiche push del browser
- **Web Push API (VAPID)** — notifiche push native del browser per gli eventi delle missioni

## Novità in v3.0.0 (2026)

### Marketplace degli agenti
- **191 agenti catalogati** — ricerca full-text, filtri per ART/ruolo/competenze su `/marketplace`
- **Profili degli agenti** — vista dettagliata con strumenti, competenze e storico recente delle sessioni
- **Avvio con un clic** — avviare una sessione diretta con qualsiasi agente dalla sua pagina del profilo

### UI Replay della missione
- **Replay passo per passo** — ogni turno dell'agente e chiamata agli strumenti su `/missions/{id}/replay`
- **Costi e token per passo** — ripartizione granulare dei costi LLM per agente
- **Storico esportabile** — scaricare il replay come JSON per debugging e audit

### Dashboard metriche LLM
- **Monitoraggio in tempo reale di costi/latenza/provider** su `/metrics`
- **Spese per agente e missione** — identificare e ottimizzare gli agenti costosi
- **Confronto provider** — latenza P50/P95 e costi di diversi provider affiancati

### RBAC + Rate limiting
- **RBAC per workspace** — assegnazioni di ruoli per workspace, non solo a livello di piattaforma
- **Rate limiting per utente** — quote di token/richieste configurabili per ruolo
- **Audit trail** — tutte le modifiche RBAC registrate con attore, timestamp e dettagli

### Framework di valutazione degli agenti
- **Valutazione LLM-as-judge** — valutazione automatica rispetto a dataset d'oro su `/evals`
- **Benchmark degli agenti** — tracciare la qualità nel tempo e rilevare regressioni
- **Giudici configurabili** — utilizzare qualsiasi provider LLM come giudice di valutazione

### Tool Builder
- **Creazione strumenti senza codice** su `/tool-builder` — strumenti HTTP, SQL e shell
- **Attivazione immediata** — gli strumenti sono disponibili agli agenti immediatamente dopo il salvataggio
- **Template di parametri** — definire schemi di input con tipi e validazione

### Workspace multi-tenant
- **Namespace isolati** su `/workspaces` — dati, agenti e memoria separati per workspace
- **Deployment per client** — onboardare più clienti senza interferenze reciproche
- **RBAC per workspace** — assegnazioni di ruoli granulari per namespace

### Hot reload YAML degli agenti
- **Aggiornamenti agenti live** — modificare i file YAML e ricaricarli senza riavviare la piattaforma
- **Nessun downtime** — le missioni in corso continuano a utilizzare la definizione dell'agente precedente

## Contribuire

Le contribuzioni sono benvenute! Si prega di leggere [CONTRIBUTING.md](CONTRIBUTING.md) per le linee guida.

## Licenza

Questo progetto è concesso in licenza sotto la licenza AGPL v3 — vedere il file [LICENSE](LICENSE) per i dettagli.

## Supporto

- Live: https://sf.macaron-software.com
- Issues: https://github.com/macaron-software/software-factory/issues
- Discussioni: https://github.com/macaron-software/software-factory/discussions
