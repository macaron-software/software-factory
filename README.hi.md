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

**बहु-एजेंट सॉफ्टवेयर फैक्टरी — स्वायत्त AI एजेंट संपूर्ण उत्पाद जीवनचक्र का संचालन करते हैं**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live: sf.macaron-software.com](https://sf.macaron-software.com)**

[विशेषताएं](#विशेषताएं) · [त्वरित शुरुआत](#त्वरित-शुरुआत) · [स्क्रीनशॉट](#स्क्रीनशॉट) · [आर्किटेक्चर](#आर्किटेक्चर) · [योगदान](#योगदान)

</div>

---

## यह क्या है?

Software Factory एक **स्वायत्त बहु-एजेंट प्लेटफॉर्म** है जो संपूर्ण सॉफ्टवेयर विकास चक्र का संचालन करती है — विचार से लेकर तैनाती तक — विशेष AI एजेंटों के माध्यम से जो मिलकर काम करते हैं।

एक **आभासी सॉफ्टवेयर फैक्टरी** की कल्पना करें जहाँ 191 AI एजेंट संरचित वर्कफ़्लो के माध्यम से सहयोग करते हैं, SAFe पद्धति का पालन करते हैं, TDD प्रथाओं को लागू करते हैं और स्वचालित गुणवत्ता गेट का उपयोग करते हैं।

### मुख्य विशेषताएं

- **191 विशेष एजेंट** — आर्किटेक्ट, डेवलपर, टेस्टर, SRE, सुरक्षा विश्लेषक, Product Owner
- **36 अंतर्निहित वर्कफ़्लो** — SAFe समारोह, गुणवत्ता गेट, रात्रि रखरखाव, सुरक्षा, ज्ञान प्रबंधन
- **ज्ञान प्रबंधन** — 4 समर्पित एजेंट, ART-Knowledge-Team, रात्रि `knowledge-maintenance` वर्कफ़्लो
- **Memory Intelligence** — प्रासंगिकता स्कोरिंग, पहुँच ट्रैकिंग, पुरानी प्रविष्टियों की स्वचालित सफाई
- **LLM लागत ट्रैकिंग** — प्रति मिशन लागत Timeline Tab हेडर में प्रदर्शित
- **Mission Timeline** — Swimlane Timeline Tab Mission Control में चरण अवधि दिखाता है
- **10 ऑर्केस्ट्रेशन पैटर्न** — Solo, Sequential, Parallel, Hierarchical, Network, Loop, Router, Aggregator, Wave, Human-in-the-Loop
- **SAFe-संरेखित जीवनचक्र** — Portfolio -> Epic -> Feature -> Story, PI Cadence के साथ
- **स्व-उपचार** — स्वायत्त घटना पहचान, ट्राइएज और स्व-मरम्मत
- **LLM लचीलापन** — Multi-Provider Fallback, Jitter-Retry, Rate-Limit प्रबंधन, पर्यावरण चर-नियंत्रित मॉडल कॉन्फ़िगरेशन
- **OpenTelemetry ऑब्जर्वेबिलिटी** — Jaeger के साथ Distributed Tracing, Pipeline Analytics Dashboard
- **निरंतर Watchdog** — रुके हुए Runs की स्वत: पुनर्शुरुआत, सत्र पुनर्प्राप्ति, विफल Runs की सफाई
- **सुरक्षा प्रथम** — Prompt Injection Guard, RBAC, Secret Scrubbing, Connection Pooling
- **DORA मेट्रिक्स** — Deployment Frequency, Lead Time, MTTR, Change Failure Rate

## स्क्रीनशॉट

<table>
<tr>
<td width="50%">
<strong>Dashboard — अनुकूली SAFe दृष्टिकोण</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — रणनीतिक Backlog और WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Program Increment योजना</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Ideation Workshop — AI-समर्थित Brainstorming</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Trains और एजेंट टीमें</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>समारोह — वर्कफ़्लो टेम्पलेट और पैटर्न</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoring — DORA मेट्रिक्स और सिस्टम स्वास्थ्य</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — SAFe भूमिका चयन सहायक</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>होमपेज — CTO Jarvis / Business Ideation / Project Ideation</strong><br>
<img src="docs/screenshots/en/home.png" alt="Homepage" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — रणनीतिक AI सलाहकार</strong><br>
<img src="docs/screenshots/en/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Business Ideation — 6-एजेंट Marketing टीम</strong><br>
<img src="docs/screenshots/en/mkt_ideation.png" alt="Business Ideation" width="100%">
</td>
<td width="50%">
<strong>Project Ideation — Multi-Agent Tech टीम</strong><br>
<img src="docs/screenshots/en/ideation_projet.png" alt="Project Ideation" width="100%">
</td>
</tr>
</table>

## त्वरित शुरुआत

### विकल्प 1: Docker (अनुशंसित)

Docker image में शामिल है: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**।

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # .env.example को .env में कॉपी करता है (अपना LLM API Key डालें)
make run     # प्लेटफॉर्म बनाता और शुरू करता है
```

http://localhost:8090 खोलें — बिना API Key के एक्सप्लोर करने के लिए **"Skip (Demo)"** पर क्लिक करें।

### विकल्प 2: स्थानीय इंस्टॉलेशन

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # कॉन्फ़िगरेशन बनाएं (LLM Key डालें — चरण 3 देखें)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# प्लेटफॉर्म शुरू करें
make dev
# या मैन्युअली: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

http://localhost:8090 खोलें — पहली बार शुरू करने पर **Onboarding Assistant** दिखाई देगा।
अपनी SAFe भूमिका चुनें या तुरंत शुरू करने के लिए **"Skip (Demo)"** पर क्लिक करें।

### चरण 3: LLM प्रदाता कॉन्फ़िगर करें

API Key के बिना प्लेटफॉर्म **Demo Mode** में चलता है — एजेंट अनुकरणीय उत्तर देते हैं।
यह इंटरफ़ेस एक्सप्लोर करने के लिए उपयोगी है, लेकिन एजेंट वास्तविक कोड या विश्लेषण नहीं बनाते।

वास्तविक AI एजेंट सक्षम करने के लिए, `.env` संपादित करें और **एक** API Key जोड़ें:

```bash
# विकल्प A: MiniMax (शुरुआत के लिए अनुशंसित)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# विकल्प B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# विकल्प C: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

फिर पुनः शुरू करें: `make run` (Docker) या `make dev` (स्थानीय)

| प्रदाता | पर्यावरण चर | मॉडल |
|---------|-------------|------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

प्राथमिक प्रदाता विफल होने पर प्लेटफॉर्म स्वचालित रूप से अन्य कॉन्फ़िगर किए गए प्रदाताओं पर स्विच करता है।
आप Dashboard की **Settings** पेज (`/settings`) के माध्यम से भी प्रदाता कॉन्फ़िगर कर सकते हैं।

## पहले कदम — आपका पहला प्रोजेक्ट

इंस्टॉलेशन के बाद, विचार से तैयार प्रोजेक्ट तक इस प्रकार पहुँचें:

### मार्ग A: CTO Jarvis से पूछें (सबसे तेज़ शुरुआत)

1. **होमपेज खोलें** (`/`) — प्लेटफॉर्म CTO Jarvis Tab में शुरू होता है
2. **अपना प्रोजेक्ट विचार टाइप करें** — जैसे *"React और Python के साथ एक कॉर्पोरेट Carpooling App के लिए प्रोजेक्ट बनाएं"*
3. **Jarvis (Gabriel Mercier, Strategic Orchestrator)** अनुरोध का विश्लेषण करता है, प्रोजेक्ट बनाता है, SAFe Backlog प्रोविज़न करता है और पहला मिशन शुरू करता है — एक ही बातचीत में

यह किसी भी नए प्रोजेक्ट के लिए **अनुशंसित प्रारंभ बिंदु** है।

### मार्ग B: प्रोजेक्ट मैन्युअली बनाएं

1. `/projects` पर जाएं और **"New Project"** पर क्लिक करें
2. भरें: नाम, विवरण, Tech Stack, Repository Path
3. प्लेटफॉर्म स्वचालित रूप से बनाता है:
   - प्रोजेक्ट को असाइन किया गया एक **Product Manager Agent**
   - एक **TMA Mission** (निरंतर रखरखाव — स्वास्थ्य की निगरानी, घटनाएं बनाता है)
   - एक **Security Mission** (साप्ताहिक सुरक्षा ऑडिट — SAST, dependency checks)
   - एक **Technical Debt Mission** (मासिक debt reduction — scheduled)

### फिर: Epics और Features बनाएं

- **Portfolio** पेज (`/portfolio`) पर WSJF प्राथमिकता के साथ Epics बनाएं
- एक Epic से **Features** जोड़ें और उन्हें **User Stories** में विभाजित करें
- Program Increments की योजना बनाने और Features को Sprints में असाइन करने के लिए **PI Board** (`/pi-board`) का उपयोग करें

### मिशन चलाएं

- एजेंट निष्पादन शुरू करने के लिए किसी भी मिशन पर **"Start"** क्लिक करें
- एक **ऑर्केस्ट्रेशन पैटर्न** चुनें (hierarchical, network, parallel...)
- **Mission Control** के माध्यम से वास्तविक समय में एजेंटों को देखें
- एजेंट स्वायत्त रूप से अपने उपकरणों का उपयोग करते हैं (code_read, git, build, test, security scan)

### TMA और Security — हमेशा सक्रिय

ये प्रत्येक प्रोजेक्ट के लिए **स्वचालित रूप से सक्षम** हैं — कोई कॉन्फ़िगरेशन आवश्यक नहीं:

| मिशन | प्रकार | शेड्यूल | क्या करता है |
|------|-------|---------|-------------|
| **TMA** | Program | निरंतर | स्वास्थ्य निगरानी, घटना पहचान, Auto-Repair, Ticket निर्माण |
| **Security** | Review | साप्ताहिक | SAST Scans (bandit/semgrep), Dependency Audit, Secret Detection |
| **Technical Debt** | Reduction | मासिक | Code Quality Analysis, Refactoring Recommendations |
| **Self-Healing** | Program | निरंतर | 5xx detection -> TMA Mission -> Agent Diagnosis -> Code Fix -> Validation |

सभी चार प्रोजेक्ट के साथ बनाए जाते हैं। TMA, Security और Self-Healing **active** के रूप में शुरू होते हैं, Technical Debt **planning** के रूप में शुरू होता है (तैयार होने पर सक्षम करें)।

## विशेषताएं

### 191 विशेष AI एजेंट

एजेंट वास्तविक सॉफ्टवेयर संगठनों को दर्शाने वाली टीमों में व्यवस्थित हैं:

| टीम | एजेंट | भूमिका |
|-----|-------|--------|
| **Product** | Product Manager, Business Analyst, PO | SAFe Planning, WSJF Prioritization |
| **Architecture** | Solution Architect, Tech Lead, System Architect | Architecture Decisions, Design Patterns |
| **Development** | Backend/Frontend/Mobile/Data Engineers | Stack-per TDD Implementation |
| **Quality** | QA Engineers, Security Analysts, Test Automation | Tests, Security Audits, Penetration Testing |
| **Design** | UX Designer, UI Designer | User Experience, Visual Design |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, Monitoring, Infrastructure |
| **Management** | Scrum Master, RTE, Agile Coach | Ceremonies, Facilitation, Obstacle Removal |

### 10 ऑर्केस्ट्रेशन पैटर्न

- **Solo** — सरल कार्यों के लिए एकल एजेंट
- **Sequential** — क्रम में एजेंटों की Pipeline
- **Parallel** — एक साथ काम करने वाले कई एजेंट
- **Hierarchical** — Manager उप-एजेंटों को delegate करता है
- **Network** — Peer-to-Peer सहयोग करने वाले एजेंट
- **Loop** — शर्त पूरी होने तक एजेंट iterate करता है
- **Router** — इनपुट के आधार पर एकल एजेंट विशेषज्ञों को रूट करता है
- **Aggregator** — एकत्रीकरणकर्ता द्वारा कई इनपुट संयुक्त होते हैं
- **Wave** — Waves के भीतर parallel, Waves में sequential
- **Human-in-the-Loop** — एजेंट सुझाव देता है, मानव सत्यापित करता है

### SAFe-संरेखित जीवनचक्र

पूर्ण Portfolio -> Epic -> Feature -> Story पदानुक्रम के साथ:

- **Strategic Portfolio** — Portfolio Canvas, Strategic Themes, Value Streams
- **Program Increment** — PI Planning, Goals, Dependencies
- **Team Backlog** — User Stories, Tasks, Acceptance Criteria
- **Sprint Execution** — Daily Standups, Sprint Reviews, Retrospectives

### सुरक्षा और अनुपालन

- **Authentication** — RBAC के साथ JWT-based Authentication
- **Prompt Injection Guard** — दुर्भावनापूर्ण Prompts का पहचान और अवरोध
- **Secret Scrubbing** — संवेदनशील डेटा का स्वचालित रिडेक्शन
- **CSP (Content Security Policy)** — हार्डेंड Headers
- **Rate Limiting** — प्रति उपयोगकर्ता API कोटा
- **Audit Logging** — व्यापक Activity Logs

### DORA मेट्रिक्स और Monitoring

- **Deployment Frequency** — कितनी बार कोड Production में जाता है
- **Lead Time** — Commit से Deployment तक का समय
- **MTTR** — घटनाओं के बाद औसत पुनर्प्राप्ति समय
- **Change Failure Rate** — विफल Deployments का प्रतिशत
- **Real-time Dashboards** — Chart.js विज़ुअलाइज़ेशन
- **Prometheus Metrics** — /metrics endpoint

### गुणवत्ता मेट्रिक्स — औद्योगिक Monitoring

एक उत्पादन लाइन की तरह 10 आयामों के साथ Deterministic Quality Scanning (LLM के बिना):

| आयाम | उपकरण | क्या मापा जाता है |
|------|-------|-----------------|
| **Complexity** | radon, lizard | Cyclomatic Complexity, Cognitive Complexity |
| **Unit Test Coverage** | coverage.py, nyc | Line/Branch Coverage Percentage |
| **E2E Test Coverage** | Playwright | Test File Count, Spec Coverage |
| **Security** | bandit, semgrep | SAST Findings by Severity (critical/high/medium/low) |
| **Accessibility** | pa11y | WCAG 2.1 AA Violations |
| **Performance** | Lighthouse | Core Web Vitals Scores |
| **Documentation** | interrogate | README, Changelog, API Docs, Docstring Coverage |
| **Architecture** | madge, jscpd, mypy | Circular Dependencies, Code Duplication, Type Errors |
| **Maintainability** | custom | File Size Distribution, Large File Ratio |
| **Adversarial** | built-in | Incident Rate, Adversarial Rejection Rate |

**वर्कफ़्लो चरणों पर Quality Gates** — प्रत्येक वर्कफ़्लो चरण एक Quality Badge (PASS/FAIL/PENDING) दिखाता है जो Gate Type के अनुसार कॉन्फ़िगर किए गए Dimension Thresholds पर आधारित है:

| Gate Type | Threshold | उपयोग |
|-----------|-----------|-------|
| `always` | 0% | Analysis, Planning Phases |
| `no_veto` | 50% | Implementation, Sprint Phases |
| `all_approved` | 70% | Review, Release Phases |
| `quality_gate` | 80% | Deploy, Production Phases |

**Quality Dashboard** `/quality` पर — Global Scorecard, Project-specific Ratings, Trend Snapshots।
Mission Details, Project Board, Workflow Phases और Main Dashboard पर Quality Badges दृश्यमान।

### निरंतर सुधार वर्कफ़्लो

तीन अंतर्निहित आत्म-सुधार वर्कफ़्लो:

| वर्कफ़्लो | उद्देश्य | एजेंट |
|----------|---------|-------|
| **quality-improvement** | मेट्रिक्स स्कैन -> सबसे खराब आयाम पहचानें -> सुधार योजना और कार्यान्वयन | QA Lead, Dev, Architect |
| **retrospective-quality** | Sprint Retro: ROTI, Incidents, Quality Data -> Actions | Scrum Master, QA, Dev |
| **skill-evolution** | Agent Performance विश्लेषण -> System Prompts अपडेट -> Skills विकसित करें | Brain, Lead Dev, QA |

ये वर्कफ़्लो एक **Feedback Loop** बनाते हैं: Metrics -> Analysis -> Improvement -> Rescan -> Track Progress।

### अंतर्निहित एजेंट उपकरण

Docker image में वह सब कुछ है जो एजेंटों को स्वायत्त रूप से काम करने की आवश्यकता है:

| श्रेणी | उपकरण | विवरण |
|--------|-------|-------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | Project files पढ़ें, लिखें और खोजें |
| **Build** | `build`, `test`, `local_ci` | Builds, Tests और local CI Pipelines चलाएं (npm/pip/cargo auto-detected) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | Agent Branch Isolation के साथ Version Control |
| **Security** | `sast_scan`, `dependency_audit`, `secrets_scan` | bandit/semgrep के माध्यम से SAST, CVE Audit, Secret Detection |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright E2E Tests और Screenshots (Chromium included) |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | TMA Tracking के लिए Incidents/Tickets बनाएं |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | Container Deployment और CI/CD Status |
| **Memory** | `memory_store`, `memory_search`, `deep_search` | Sessions में persistent Project Memory |

### स्व-उपचार और स्व-मरम्मत (TMA)

घटना पहचान, ट्राइएज और स्व-मरम्मत के लिए स्वायत्त चक्र:

- **Heartbeat Monitoring** — सभी चल रहे Missions और Services की निरंतर स्वास्थ्य जांच
- **Automatic Incident Detection** — HTTP 5xx, Timeout, Agent Crash -> स्वचालित Incident निर्माण
- **Triage और Classification** — Severity (P0-P3), Impact Analysis, Root Cause Hypothesis
- **Self-Repair** — एजेंट स्वायत्त रूप से समस्याओं का निदान और समाधान करते हैं (Code Patches, Config Changes, Restarts)
- **Ticket Creation** — अनसुलझी Incidents स्वचालित रूप से मानव समीक्षा के लिए tracked Tickets बनाती हैं
- **Escalation** — P0/P1 Incidents on-call Team को Slack/Email Notifications trigger करती हैं
- **Retrospective Loop** — Post-Incident Learnings Memory में संग्रहीत और future Sprints में inject किए जाते हैं

### SAFe Perspectives और Onboarding

वास्तविक SAFe संगठनों को दर्शाने वाला Role-based Adaptive Interface:

- **9 SAFe Perspectives** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Adaptive Dashboard** — चुनी गई भूमिका के अनुसार KPIs, Quick Actions और Sidebar Links बदलते हैं
- **Onboarding Assistant** — 3-step First-User Flow (Role चुनें -> Project चुनें -> Start)
- **Perspective Selector** — Header Dropdown के माध्यम से किसी भी समय SAFe Role बदलें
- **Dynamic Sidebar** — केवल वर्तमान Perspective के लिए प्रासंगिक Navigation दिखाता है

### 4-Layer Memory और RLM Deep Search

intelligent querying के साथ Sessions में persistent knowledge:

- **Session Memory** — एक Single Session में conversational context
- **Pattern Memory** — Orchestration Pattern execution से learnings
- **Project Memory** — project-specific knowledge (Decisions, Conventions, Architecture)
- **Global Memory** — cross-project organizational knowledge (FTS5 Full-text Search)
- **Auto-loaded Project Files** — CLAUDE.md, SPECS.md, VISION.md, README.md हर LLM Prompt में inject होते हैं (max 8K)
- **RLM Deep Search** — Recursive Language Model (arXiv:2512.24601) — iterative WRITE-EXECUTE-OBSERVE-DECIDE Cycle with up to 10 exploration iterations

### Agent Mercato (Transfer Market)

Team Assembly के लिए Token-based Agent Marketplace:

- **Agent Listings** — Transfer के लिए Asking Price के साथ Agents offer करें
- **Free Agent Pool** — Draft के लिए उपलब्ध Unassigned Agents
- **Transfers और Loans** — Projects के बीच Agents खरीदें, बेचें या उधार लें
- **Market Valuation** — Skills, Experience और Performance पर आधारित Automatic Agent Valuation
- **Wallet System** — Transaction History के साथ per-Project Token Wallets
- **Draft System** — अपने Project के लिए Free Agents का दावा करें

### Adversarial Quality Guard

नकली/Placeholder Code को पास होने से रोकने वाला Two-Layer Quality Gate:

- **L0 Deterministic** — Slop (Lorem Ipsum, TBD), Mocks (NotImplementedError, TODO), Fake Builds, Hallucinations, Stack Mismatches की तत्काल पहचान
- **L1 LLM Semantic** — Execution Patterns के लिए Separate LLM Output Quality का मूल्यांकन करता है
- **Scoring** — Score < 5 pass, 5-6 Soft Pass with Warning, 7+ rejected
- **Force Rejection** — Hallucinations, Slop, Stack Mismatches, Fake Builds Score की परवाह किए बिना हमेशा reject होते हैं

### Auto-Documentation और Wiki

पूरे जीवनचक्र में स्वचालित Documentation Generation:

- **Sprint Retrospectives** — LLM-generated Retro Notes, Memory में संग्रहीत और next Sprint Prompts में inject किए जाते हैं (Learning Loop)
- **Phase Summaries** — प्रत्येक Mission Phase Decisions और Outcomes का LLM-generated Summary बनाता है
- **Architecture Decision Records** — Architecture Patterns स्वचालित रूप से Project Memory में Design Decisions document करते हैं
- **Project Context Files** — Auto-loaded Instruction Files (CLAUDE.md, SPECS.md, CONVENTIONS.md) living documentation के रूप में काम करती हैं
- **Confluence Sync** — Enterprise Documentation के लिए Confluence Wiki Pages के साथ Bidirectional Sync
- **Swagger Auto-Docs** — `/docs` पर OpenAPI Schema के साथ 94 REST Endpoints स्वचालित रूप से documented

## चार इंटरफेस

### 1. Web Dashboard (HTMX + SSE)

http://localhost:8090 पर मुख्य इंटरफेस:

- **Real-time Multi-Agent Conversations** SSE Streaming के साथ
- **PI Board** — Program Increment Planning
- **Mission Control** — Execution Monitoring
- **Agent Management** — Agents देखें, कॉन्फ़िगर करें, monitor करें
- **Incident Dashboard** — Self-Healing Triage
- **Mobile-Responsive** — Tablets और Smartphones पर काम करता है

### 2. CLI (`sf`)

पूर्ण Command Line Interface:

```bash
# Installation (PATH में जोड़ें)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Browse
sf status                              # Platform Health
sf projects list                       # All Projects
sf missions list                       # Missions with WSJF Scores
sf agents list                         # 145 Agents
sf features list <epic_id>             # Epic Features
sf stories list --feature <id>         # User Stories

# Work
sf ideation "e-commerce app in React"  # Multi-Agent Ideation (streamed)
sf missions start <id>                 # Start Mission
sf metrics dora                        # DORA Metrics

# Monitor
sf incidents list                      # Incidents
sf llm stats                           # LLM Usage (tokens, cost)
sf chaos status                        # Chaos Engineering
```

**22 Command Groups** · Dual Mode: API (Live Server) या DB (Offline) · JSON Output (`--json`) · Spinner Animations · Markdown Table Rendering

### 3. REST API + Swagger

`/docs` (Swagger UI) पर स्वचालित रूप से documented 94 API Endpoints:

```bash
# Examples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

### 4. MCP Server (Model Context Protocol)

AI Agent Integration के लिए 24 MCP Tools (Port 9501):

```bash
# MCP Server शुरू करें
python3 -m platform.mcp_platform.server

# Available Tools:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## आर्किटेक्चर

### Platform Overview

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

### Pipeline प्रवाह

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

### ऑब्जर्वेबिलिटी

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

### Deployment

```
Docker (recommended) → http://localhost:8090
Local (Development)  → http://localhost:8090
Production           → own infrastructure
```

## प्रोजेक्ट कॉन्फ़िगरेशन

Projects `projects/*.yaml` में परिभाषित होते हैं:

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

## डायरेक्टरी संरचना

```
├── platform/                # Agent Platform (152 Python files)
│   ├── server.py            # FastAPI App, Port 8090
│   ├── agents/              # Agent Loop, Executor, Store
│   ├── a2a/                 # Agent-to-Agent Message Bus
│   ├── patterns/            # 10 Orchestration Patterns
│   ├── missions/            # SAFe Mission Lifecycle
│   ├── sessions/            # Conversation Runner + SSE
│   ├── web/                 # Routes + Jinja2 Templates
│   ├── mcp_platform/        # MCP Server (23 Tools)
│   └── tools/               # Agent Tools (Code, Git, Deploy)
│
├── cli/                     # CLI 'sf' (6 files, 2100+ LOC)
│   ├── sf.py                # 22 Command Groups, 40+ Subcommands
│   ├── _api.py              # httpx REST Client
│   ├── _db.py               # sqlite3 Offline Backend
│   ├── _output.py           # ANSI Tables, Markdown Rendering
│   └── _stream.py           # SSE Streaming with Spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm Charts, Docker, K8s
├── tests/                   # E2E Playwright Tests
├── skills/                  # Agent Skills Library
├── projects/                # Project YAML Configurations
└── data/                    # SQLite Database
```

## परीक्षण

```bash
# सभी Tests चलाएं
make test

# E2E Tests (Playwright — पहले installation की आवश्यकता है)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Unit Tests
pytest tests/

# Chaos Engineering
python3 tests/test_chaos.py

# Endurance Tests
python3 tests/test_endurance.py
```

## Deployment

### Docker

Docker image में शामिल है: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**।
Agents Projects build कर सकते हैं, Screenshots के साथ E2E Tests चला सकते हैं और तुरंत SAST Security Scans कर सकते हैं।

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### पर्यावरण चर

पूरी सूची के लिए [`.env.example`](.env.example) देखें। महत्वपूर्ण Variables:

```bash
# LLM Provider (real Agents के लिए आवश्यक)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API Key

# Authentication (optional)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# Integrations (optional)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## Adaptive Intelligence — GA · RL · Thompson Sampling · OKR

प्लेटफॉर्म तीन पूरक AI Engines के माध्यम से खुद को optimize करता है।

### Thompson Sampling — Probabilistic Team Selection
- `Beta(wins+1, losses+1)` प्रति `(agent_id, pattern_id, technology, phase_type)` Context
- Fine-grained Fitness Scoring — Context के अनुसार अलग Score, कोई cross-context Bleeding नहीं
- Cold-Start Fallback Tech Prefix Chain के माध्यम से (`angular_19` -> `angular_*` -> `generic`)
- Soft Retirement: weak Teams के लिए `weight_multiplier=0.1`, reversible
- Automatic A/B Shadow Runs; neutral Evaluator winner चुनता है
- **Darwin LLM**: Thompson Sampling को LLM Model selection per context तक extend करता है

### Genetic Algorithm — Workflow Evolution
- Genome = ordered list of PhaseSpec (pattern, agents, gate)
- Population: 40 Genomes, max 30 Generations, Elitism=2, Mutation Rate=15%, Tournament k=3
- Fitness: Phase Success Rate x Agent Fitness x (1 - Veto Rate) x Lead Time Bonus
- Top-3 Proposals `evolution_proposals` में मानव समीक्षा के लिए stored
- Manual Trigger: `POST /api/evolution/run/{wf_id}` — Workflows -> Evolution पर देखें
- Nightly Scheduler; < 5 Missions पर skip

### Reinforcement Learning — Mid-Mission Pattern Adaptation
- Q-Learning Policy (`platform/agents/rl_policy.py`)
- Actions: keep, switch_parallel, switch_sequential, switch_hierarchical, switch_debate, add_agent, remove_agent
- State: `(wf_id, phase_position, rejection_pct, quality_score)` bucketed
- Q-Update: alpha=0.1, gamma=0.9, epsilon=0.1 — Offline Batch on table `rl_experience`
- केवल Confidence >= 70% पर activate, >= 3 State Visits के साथ; graceful degradation

### OKR / KPI System
- 8 Standard Seeds: code/migration, security/audit, architecture/design, testing, docs
- OKR Fulfillment directly GA Fitness और RL Reward Signal में contribute करता है
- `/teams` पर Inline Editing green/yellow/red status के साथ
- Settings के माध्यम से Project-specific OKR Overrides

---

## v2.1.0 में नया (फरवरी 2026)

### गुणवत्ता मेट्रिक्स — औद्योगिक Monitoring
- **10 Deterministic Dimensions** — Complexity, Coverage (UT/E2E), Security, Accessibility, Performance, Documentation, Architecture, Maintainability, Adversarial
- **Workflow Phases पर Quality Gates** — configurable Thresholds के साथ per-Phase PASS/FAIL Badges (always/no_veto/all_approved/quality_gate)
- **Quality Dashboard** `/quality` पर — Global Scorecard, Project-specific Ratings, Trend Snapshots
- **Quality Badges everywhere** — Mission Details, Project Board, Workflow Phases, Main Dashboard
- **LLM की आवश्यकता नहीं** — सभी Metrics Open-Source Tools से deterministically calculated (radon, bandit, semgrep, coverage.py, pa11y, madge)

### प्रति प्रोजेक्ट 4 स्वचालित रूप से deployed Missions
प्रत्येक Project को स्वचालित रूप से 4 operational Missions मिलते हैं:
- **MCO/TMA** — continuous maintenance: health monitoring, Incident Triage (P0-P4), TDD Fix, Non-Regression Validation
- **Security** — weekly SAST Scans, Dependency Audit, CVE Monitoring, Code Review
- **Technical Debt** — monthly debt reduction: Complexity Audit, WSJF Prioritization, Refactoring Sprints
- **Self-Healing** — autonomous Incident Pipeline: 5xx detection -> TMA Mission creation -> Agent Diagnosis -> Code Fix -> Validation

### निरंतर सुधार
- **quality-improvement Workflow** — Scan -> worst Dimensions identify -> Improvements plan and implement
- **retrospective-quality Workflow** — Sprint Retro with ROTI, Incidents, Quality Metrics -> Actions
- **skill-evolution Workflow** — Agent Performance analyze -> Prompts update -> Skills develop
- **Feedback Loop** — Metrics -> Analysis -> Improvement -> Rescan -> Track Progress

### SAFe Perspectives और Onboarding
- **9 SAFe Role Perspectives** — per-Role adaptive Dashboard, Sidebar और KPIs
- **Onboarding Assistant** — Role और Project Selection के साथ 3-step First-User Flow
- **Perspective Selector** — Header के माध्यम से किसी भी समय SAFe Role बदलें

### स्व-उपचार और स्व-मरम्मत
- **TMA Heartbeat** — automatic Incident creation के साथ continuous health monitoring
- **Self-Repair Agents** — common Errors का autonomous diagnosis और fix
- **Ticket Escalation** — unresolved Incidents tracked Tickets के साथ Notifications बनाती हैं

### 4-Layer Memory और RLM
- **Persistent Knowledge** — FTS5 के साथ Session, Pattern, Project और Global Memory Layers
- **RLM Deep Search** — complex Codebase Analysis के लिए recursive exploration loop (up to 10 iterations)
- **Auto-loaded Project Context** — CLAUDE.md, SPECS.md, VISION.md हर Agent Prompt में inject होते हैं

### Adversarial Quality Guard
- **L0 Deterministic** — Slop, Mocks, Fake Builds, Hallucinations की तत्काल पहचान
- **L1 Semantic** — Execution Outputs के लिए LLM-based Quality Check
- **Force Rejection** — Hallucinations और Stack Mismatches हमेशा block होते हैं

### Agent Mercato
- **Token-based Marketplace** Agent Listings, Transfers, Loans और Free Agent Draft के साथ
- **Market Valuation** — Skills और Performance पर आधारित automatic Agent Pricing
- **Wallet System** — Transaction History के साथ per-Project Token Economy

### Authentication और Security
- **JWT-based Authentication** Login/Register/Refresh/Logout के साथ
- **RBAC** — Roles: Admin, Project Manager, Developer, Viewer
- **OAuth** — GitHub और Azure AD SSO Login
- **Admin Panel** — User Management Interface (`/admin/users`)
- **Demo Mode** — One-click "Skip" Button for instant access

### Auto-Documentation
- **Sprint Retrospectives** — Learning Loop के साथ LLM-generated Retro Notes
- **Phase Summaries** — Mission Phase Outcomes का automatic documentation
- **Confluence Sync** — Bidirectional Wiki Integration

### LLM Providers
- **Multi-Provider** automatic Fallback Chain के साथ
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Demo Mode** API Keys के बिना Interface Exploration के लिए

### Platform Improvements
- LLM Cost Tracking के साथ DORA Metrics Dashboard
- Bidirectional Jira Synchronization
- Playwright E2E Test Suite (11 Spec Files)
- Internationalization (EN/FR)
- Real-time Notifications (Slack, Email, Webhook)
- Design System Pipeline in Workflows (UX -> Dev -> Review)
- 3D Agent World Visualization

### Darwin — Evolutionary Team Selection
- **Thompson Sampling Selection** — `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type)` के माध्यम से probabilistic Agent+Pattern Team Selection
- **Granular Fitness Tracking** — per-Context separate Score: Angular Migration में अच्छा Team new Angular Features में poor हो सकता है
- **Similarity Fallback** — Tech Prefix Matching के माध्यम से Cold Start (`angular_19` -> `angular_*` -> `generic`)
- **Soft Retirement** — weak Teams को `weight_multiplier=0.1` मिलता है, deprioritized but recoverable
- **OKR / KPI System** — Objectives और Metrics per Domain और Phase Type; 8 Standard Seeds
- **A/B Shadow Tests** — close Fitness Scores (Delta < 10) या 10% Probability पर automatic parallel Runs
- **Teams Dashboard** `/teams` पर — Leaderboard with Badges, OKR Editing, Evolution Curves, Selection History, A/B Results
- **Non-breaking Opt-in** — `agent_id: "skill:developer"` Darwin activates; explicit IDs unchanged रहते हैं

## v2.2.0 में नया (फरवरी 2026)

### OpenTelemetry और Distributed Tracing
- **OTEL Integration** — Jaeger को OTLP/HTTP Exporter के साथ OpenTelemetry SDK
- **ASGI Tracing Middleware** — Spans, Latency और Status के साथ प्रत्येक HTTP Request traced
- **Tracing Dashboard** `/analytics` पर — Request Statistics, Latency Charts, Operations Table
- **Jaeger UI** — Port 16686 पर full Distributed Trace Exploration

### Pipeline Failure Analysis
- **Error Classification** — Python-based Error Categorization (setup_failed, llm_provider, timeout, phase_error, etc.)
- **Phase Error Heatmap** — कौन सी Pipeline Phases सबसे अधिक fail होती हैं की पहचान
- **Recommendation Engine** — Error Patterns पर आधारित actionable Suggestions
- **Resume-All Button** — Dashboard से paused Runs का One-Click Mass Resume

### निरंतर Watchdog
- **Auto-Resume** — paused Runs automatically batch में continue (5/Batch, every 5 min, max 10 concurrent)
- **Session Recovery** — >30 min inactive Sessions detect करता है, Retry के लिए mark करता है
- **Failed Session Cleanup** — Pipeline Progress block करने वाली Zombie Sessions clean करता है
- **Blockade Detection** — >60 min किसी Phase में stuck Missions automatically restart होती हैं

### Phase Resilience
- **Per-Phase Retry** — configurable Retry Counter (default 3x) with exponential Backoff per Phase
- **skip_on_failure** — Phases optional mark हो सकती हैं, Pipeline continue हो सकती है
- **Checkpointing** — completed Phases saved, intelligent Resume done work skip करता है
- **Phase Timeout** — 10-minute Limit infinite hanging रोकती है

### Sandbox Build Validation
- **Post-Code Build Check** — Code Generation Phases के बाद automatically Build/Lint run करें
- **Automatic Build System Detection** — npm, cargo, go, maven, python, docker
- **Error Injection** — Build Errors Agent Context में Self-correction के लिए inject होते हैं

### Quality UI Improvements
- **Radar Chart** — `/quality` पर Quality Dimensions का Chart.js Radar Visualization
- **Quality Badge** — Project Header के लिए colored Score Circle (`/api/dashboard/quality-badge`)
- **Mission Scorecard** — Mission Detail Sidebar में Quality Metrics (`/api/dashboard/quality-mission`)

### Multi-Model LLM Routing
- **3 Specialized Models** — heavy Reasoning Tasks के लिए `gpt-5.2`, Code/Tests के लिए `gpt-5.1-codex`, light Tasks के लिए `gpt-5-mini`
- **Role-based Routing** — Agents Tags के अनुसार automatically सही Model पाते हैं (`reasoner`, `architect`, `developer`, `tester`, `doc_writer`...)
- **Live-configurable** — Settings -> LLM में Routing Matrix restart के बिना editable

### Darwin LLM — Models पर Thompson Sampling
- **Model A/B Testing** — same Teams (Agent + Pattern) different LLMs के साथ compete; best Model automatically per Context पर जीतता है
- **Beta Distribution** — `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type, llm_model)`
- **LLM A/B Tab** on `/teams` — per-Model Fitness Rankings और Test History
- **Priority Chain** — Darwin LLM -> DB Config -> Defaults (graceful degradation)

### Settings — LLM Tab
- **Provider Grid** — missing API Keys के hints के साथ Active/Inactive Status
- **Routing Matrix** — per Category heavy/light (Reasoning, Production/Code, Tasks, Writing)
- **Darwin LLM A/B Section** — running Model Experiments का Live View

## v2.7.0 में नया (2026)

### Knowledge Management System
- **4 नए Agents** — `knowledge-manager`, `knowledge-curator`, `knowledge-seeder`, `wiki-maintainer`
- **ART-Knowledge-Team** — Knowledge Operations के लिए dedicated Agile Release Train
- **Nightly `knowledge-maintenance` Workflow** — automatic Curation, Deduplication, Freshness Scoring
- **Memory Health Dashboard** — Metrics Tab में Knowledge Health Metrics
- **Knowledge Health Badge** — Settings Page पर visible

### Memory Intelligence
- **Relevance Scoring** — weighted Retrieval के लिए `Confidence x Recency x Access Boost` formula
- **Access Tracking** — प्रत्येक Memory Entry के लिए `access_count` और `last_read_at` fields
- **Automatic Cleanup** — हर nightly Run पर stale Entries remove होती हैं

### LLM Cost Tracking
- **Cost per Mission** — Mission Timeline Tab Header में displayed
- **Automatically Summed** — `llm_traces` table से aggregated

### Mission Timeline
- **Swimlane Timeline Tab** — Mission Control में, Agent Phases को horizontal Lanes के रूप में दिखाता है
- **Phase Durations** — per-Phase Time का visual representation

### Quality Scoring
- **`quality_score` field on PhaseRun** — Adversarial Guard द्वारा प्रत्येक Phase के बाद populated

### Project Export/Import
- **ZIP Archive** — `project.json` + सभी Missions + Runs + Memory शामिल है

### Input Validation
- **Pydantic Models** — strict Schemas के साथ सभी POST/PATCH Routes validated

### BSCC Domain Guidelines
- **Domain Architecture Guidelines** — Confluence/Solaris per Project Domain enforced

### Settings Integration Hub
- **Configurable Tool Integrations** — सभी Agents के लिए Jira, Confluence, SonarQube available

### Browser Push Notifications
- **Web Push API (VAPID)** — Mission Events के लिए native Browser Push Notifications

## v3.0.0 में नया (2026)

### Agent Marketplace
- **191 Agents catalogued** — `/marketplace` पर Full-text Search, ART/Role/Skills द्वारा Filter
- **Agent Profiles** — Tools, Skills और recent Session History के साथ Detail View
- **One-Click Start** — Agent की Profile Page से direct Session शुरू करें

### Mission Replay UI
- **Step-by-Step Replay** — `/missions/{id}/replay` पर प्रत्येक Agent Turn और Tool Call
- **Cost और Tokens per Step** — per Agent granular LLM Cost Breakdown
- **Exportable History** — Debugging और Audit के लिए Replay JSON के रूप में download करें

### LLM Metrics Dashboard
- **Real-time Cost/Latency/Provider Monitoring** `/metrics` पर
- **Spending per Agent और Mission** — expensive Agents identify और optimize करें
- **Provider Comparison** — विभिन्न Providers के P50/P95 Latency और Cost side by side

### RBAC + Rate Limiting
- **Workspace-scoped RBAC** — platform-wide नहीं, per-Workspace Role Assignments
- **User-scoped Rate Limiting** — per-Role configurable Token/Request Quotas
- **Audit Trail** — Actor, Timestamp और Details के साथ सभी RBAC Changes logged

### Agent Evaluation Framework
- **LLM-as-Judge Scoring** — `/evals` पर Golden Datasets के विरुद्ध automatic Evaluation
- **Agent Benchmarks** — Time के साथ Quality track करें और Regressions detect करें
- **Configurable Judges** — कोई भी LLM Provider Evaluation Judge के रूप में use करें

### Tool Builder
- **No-Code Tool Creation** `/tool-builder` पर — HTTP, SQL और Shell Tools
- **Instant Activation** — Tools save के तुरंत बाद Agents के लिए available
- **Parameter Templates** — Types और Validation के साथ Input Schemas define करें

### Multi-Tenant Workspaces
- **Isolated Namespaces** `/workspaces` पर — per-Workspace separate Data, Agents और Memory
- **Per-Client Deployment** — mutual interference के बिना multiple Customers onboard करें
- **RBAC per Workspace** — per-Namespace granular Role Assignments

### YAML Agent Hot-Reload
- **Live Agent Updates** — YAML Files edit करें और Platform restart किए बिना reload करें
- **Zero Downtime** — running Missions previous Agent Definition use करती रहती हैं

## योगदान

हम contributions का स्वागत करते हैं! दिशानिर्देशों के लिए कृपया [CONTRIBUTING.md](CONTRIBUTING.md) पढ़ें।
