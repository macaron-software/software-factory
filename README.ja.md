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

**マルチエージェントソフトウェアファクトリー — 製品ライフサイクル全体を統括する自律AIエージェント**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[Live Demo: sf.macaron-software.com](https://sf.macaron-software.com)** — 「Skip (Demo)」をクリックして探索

[Features](#features) · [Quick Start](#quick-start) · [Screenshots](#screenshots) · [Architecture](#architecture) · [Contributing](#contributing)

</div>

---

## これは何か？

Software Factory は**自律型マルチエージェントプラットフォーム**で、専門AIエージェントが連携して、アイデア出しからデプロイまでのソフトウェア開発ライフサイクル全体を統括します。

161のAIエージェントが構造化されたワークフローを通じて協働する**仮想ソフトウェアファクトリー**と考えてください。SAFe方法論、TDDプラクティス、自動品質ゲートに従います。

### 主な特徴

- **161の専門エージェント** — アーキテクト、開発者、テスター、SRE、セキュリティアナリスト、プロダクトオーナー
- **10のオーケストレーションパターン** — ソロ、シーケンシャル、パラレル、階層、ネットワーク、ループ、ルーター、アグリゲーター、ウェーブ、ヒューマン・イン・ザ・ループ
- **SAFe準拠のライフサイクル** — Portfolio → Epic → Feature → Story（PIケイデンス付き）
- **自動修復** — 自律的なインシデント検出、トリアージ、セルフリペア
- **LLM回復力** — マルチプロバイダーフォールバック、ジッター付きリトライ、レート制限認識、環境駆動モデル設定
- **OpenTelemetryオブザーバビリティ** — Jaegerによる分散トレーシング、パイプライン分析ダッシュボード
- **継続的ウォッチドッグ** — 一時停止ランの自動再開、古いセッションの回復、失敗のクリーンアップ
- **セキュリティファースト** — プロンプトインジェクションガード、RBAC、シークレットスクラビング、コネクションプーリング
- **DORAメトリクス** — デプロイ頻度、リードタイム、MTTR、変更失敗率

## スクリーンショット

<table>
<tr>
<td width="50%">
<strong>Dashboard — Adaptive SAFe Perspective</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — Strategic Backlog & WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI Board — Program Increment Planning</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>Ideation Workshop — AI-Powered Brainstorming</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — Agile Release Trains & Agent Teams</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>Ceremonies — Workflow Templates & Patterns</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Monitoring — DORA Metrics & System Health</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>Onboarding — SAFe Role Selection Wizard</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ホーム — CTO Jarvis / ビジネスアイデア / プロジェクトアイデア タブ</strong><br>
<img src="docs/screenshots/en/home.png" alt="ホーム" width="100%">
</td>
<td width="50%">
<strong>CTO Jarvis — 戦略的AIアドバイザー</strong><br>
<img src="docs/screenshots/en/jarvis.png" alt="CTO Jarvis" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ビジネスアイデア — 6エージェント・マーケティングチーム</strong><br>
<img src="docs/screenshots/en/mkt_ideation.png" alt="ビジネスアイデア" width="100%">
</td>
<td width="50%">
<strong>プロジェクトアイデア — マルチエージェント技術チーム</strong><br>
<img src="docs/screenshots/en/ideation_projet.png" alt="プロジェクトアイデア" width="100%">
</td>
</tr>
</table>

## クイックスタート

### オプション 1: Docker（推奨）

Dockerイメージには以下が含まれます: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**。

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # copies .env.example → .env (edit it to add your LLM API key)
make run     # builds & starts the platform
```

http://localhost:8090 を開き — APIキーなしで探索するには **「Skip (Demo)」** をクリック。

### オプション 2: ローカルインストール

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # create your config (edit to add LLM key — see Step 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Start platform
make dev
# or manually: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

http://localhost:8090 を開きます — 初回起動時に**オンボーディングウィザード**が表示されます。
SAFeロールを選択するか、**「Skip (Demo)」**をクリックしてすぐに探索できます。

### ステップ 3: LLMプロバイダーの設定

APIキーなしでは、プラットフォームは**デモモード**で動作します — エージェントはモック回答で応答します。
UIの探索には便利ですが、エージェントは実際のコードや分析を生成しません。

実際のAIエージェントを有効にするには、`.env`を編集して**1つの**APIキーを追加してください：

```bash
# Option A: MiniMax (recommended for getting started)
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

Then restart: `make run` (Docker) or `make dev` (local)

| Provider | Env Variable | Models |
|----------|-------------|--------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

プライマリが失敗した場合、プラットフォームは他の設定済みプロバイダーに自動フォールバックします。
ダッシュボードの**設定**ページ（`/settings`）からプロバイダーを設定することもできます。

## はじめに — 最初のプロジェクト

インストール後、アイデアから実働プロジェクトへの手順：

### パス A: アイデアから始める（アイデアワークショップ）

1. **Open the Ideation page** — go to `/ideation` (or click "Ideation" in the sidebar)
2. **Describe your idea** — e.g. *"Enterprise carpooling app with real-time matching"*
3. **Watch agents discuss** — 5 specialized agents (Product Manager, Business Analyst, Architect, UX Designer, Security) analyze your idea in real-time via SSE streaming
4. **Create a project from the result** — click **"Create an Epic from this idea"**. The platform will:
   - Create a new **project** with generated `VISION.md` and CI/CD scaffolding
   - Create an **epic** with features and user stories broken down by the PO agent
   - Auto-provision **TMA** (maintenance), **Security**, and **Tech Debt** missions

You now have a full SAFe backlog ready to execute.

### パス B: プロジェクトを手動で作成

1. Go to `/projects` and click **"New Project"**
2. Fill in: name, description, tech stack, repository path
3. The platform auto-creates:
   - A **Product Manager agent** assigned to the project
   - A **TMA mission** (continuous maintenance — monitors health, creates incidents)
   - A **Security mission** (weekly security audits — SAST, dependency checks)
   - A **Tech Debt mission** (monthly debt reduction — planned)

### 次に: エピックとフィーチャーの作成

- From the **Portfolio** page (`/portfolio`), create epics with WSJF prioritization
- From an epic, add **features** and break them into **user stories**
- Use the **PI Board** (`/pi-board`) to plan program increments and assign features to sprints

### ミッションの実行

- Click **"Start"** on any mission to launch agent execution
- Choose an **orchestration pattern** (hierarchical, network, parallel...)
- Watch agents work in real-time from **Mission Control**
- Agents use their tools (code_read, git, build, test, security scan) autonomously

### TMA とセキュリティ — 常時稼働

These are **automatically enabled** for every project — no configuration needed:

| Mission | Type | Schedule | What it does |
|---------|------|----------|-------------|
| **TMA** | Program | Continuous | Health monitoring, incident detection, auto-repair, ticket creation |
| **Security** | Review | Weekly | SAST scans (bandit/semgrep), dependency audit, secret detection |
| **Tech Debt** | Reduction | Monthly | Code quality analysis, refactoring recommendations |
| **Self-Healing** | Program | Continuous | Auto-detection of 5xx/crashes → TMA mission → agent diagnosis → code fix → validation |

All four are created with the project. TMA, Security, and Self-Healing start as **active**, Tech Debt starts as **planning** (activate when ready).

## 機能

### 161の専門AIエージェント

エージェントは実際のソフトウェア組織を反映したチームに編成されています：

| Team | Agents | Role |
|------|--------|------|
| **Product** | Product Manager, Business Analyst, PO | SAFe planning, WSJF prioritization |
| **Architecture** | Solution Architect, Tech Lead, System Architect | Architecture decisions, design patterns |
| **Development** | Backend/Frontend/Mobile/Data Engineers | TDD implementation per stack |
| **Quality** | QA Engineers, Security Analysts, Test Automation | Testing, security audits, penetration testing |
| **Design** | UX Designer, UI Designer | User experience, visual design |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD, monitoring, infrastructure |
| **Management** | Scrum Master, RTE, Agile Coach | Ceremonies, facilitation, impediment removal |

### 10のオーケストレーションパターン

- **Solo** — single agent for simple tasks
- **Sequential** — pipeline of agents executing in order
- **Parallel** — multiple agents working simultaneously
- **Hierarchical** — manager delegating to sub-agents
- **Network** — agents collaborating peer-to-peer
- **Loop** — agent iterates until condition met
- **Router** — single agent routes to specialist based on input
- **Aggregator** — multiple inputs merged by a single aggregator
- **Wave** — parallel within waves, sequential across waves
- **Human-in-the-loop** — agent proposes, human validates

### SAFe準拠のライフサイクル

完全な Portfolio → Epic → Feature → Story 階層：

- **Strategic Portfolio** — portfolio canvas, strategic themes, value streams
- **Program Increment** — PI planning, objectives, dependencies
- **Team Backlog** — user stories, tasks, acceptance criteria
- **Sprint Execution** — daily standups, sprint reviews, retrospectives

### セキュリティとコンプライアンス

- **Authentication** — JWT-based auth with RBAC
- **Prompt injection guard** — detect and block malicious prompts
- **Secret scrubbing** — automatic redaction of sensitive data
- **CSP (Content Security Policy)** — hardened headers
- **Rate limiting** — per-user API quotas
- **Audit logging** — comprehensive activity logs

### DORAメトリクスとモニタリング

- **Deployment frequency** — how often code reaches production
- **Lead time** — commit to deploy duration
- **MTTR** — mean time to recovery from incidents
- **Change failure rate** — percentage of failed deployments
- **Real-time dashboards** — Chart.js visualizations
- **Prometheus metrics** — /metrics endpoint

### 品質メトリクス — 産業レベルモニタリング

10次元の決定論的品質スキャン（LLM不使用）、生産ラインのように：

| Dimension | Tools | What it measures |
|-----------|-------|-----------------|
| **Complexity** | radon, lizard | Cyclomatic complexity, cognitive complexity |
| **Unit Test Coverage** | coverage.py, nyc | Line/branch coverage percentage |
| **E2E Test Coverage** | Playwright | Test file count, spec coverage |
| **Security** | bandit, semgrep | SAST findings by severity (critical/high/medium/low) |
| **Accessibility** | pa11y | WCAG 2.1 AA violations |
| **Performance** | Lighthouse | Core Web Vitals scores |
| **Documentation** | interrogate | README, changelog, API docs, docstring coverage |
| **Architecture** | madge, jscpd, mypy | Circular deps, code duplication, type errors |
| **Maintainability** | custom | File size distribution, large file ratio |
| **Adversarial** | built-in | Incident rate, adversarial rejection rate |

**Quality gates on workflow phases** — each workflow phase shows a quality badge (PASS/FAIL/PENDING) based on dimension thresholds configured per gate type:

| Gate Type | Threshold | Used in |
|-----------|-----------|---------|
| `always` | 0% | Analysis, planning phases |
| `no_veto` | 50% | Implementation, sprint phases |
| `all_approved` | 70% | Review, release phases |
| `quality_gate` | 80% | Deploy, production phases |

**Quality dashboard** at `/quality` — global scorecard, per-project scores, trend snapshots.
Quality badges visible on mission detail, project board, workflow phases, and the main dashboard.

### 継続的改善ワークフロー

自己改善のための3つの組み込みワークフロー：

| Workflow | Purpose | Agents |
|----------|---------|--------|
| **quality-improvement** | Scan metrics → identify worst dimensions → plan & execute improvements | QA Lead, Dev, Architect |
| **retrospective-quality** | End-of-sprint retro: collect ROTI, incidents, quality data → action items | Scrum Master, QA, Dev |
| **skill-evolution** | Analyze agent performance → update system prompts → evolve skills | Brain, Lead Dev, QA |

These workflows create a **feedback loop**: metrics → analysis → improvement → re-scan → track progress.

### 組み込みエージェントツール

Dockerイメージにはエージェントが自律的に動作するために必要なすべてが含まれています：

| Category | Tools | Description |
|----------|-------|-------------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | Read, write, and search project files |
| **Build** | `build`, `test`, `local_ci` | Run builds, tests, and local CI pipelines (npm/pip/cargo auto-detected) |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | Version control with agent branch isolation |
| **Security** | `sast_scan`, `dependency_audit`, `secrets_scan` | SAST via bandit/semgrep, CVE audit, secret detection |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright E2E tests and screenshots (Chromium included) |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | Create incidents/tickets for TMA tracking |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | Container deployment and CI/CD status |
| **Memory** | `memory_store`, `memory_search`, `deep_search` | Persistent project memory across sessions |

### 自動修復とセルフリペア (TMA)

自律的なインシデント検出、トリアージ、セルフリペアサイクル：

- **Heartbeat monitoring** — continuous health checks on all running missions and services
- **Incident auto-detection** — HTTP 5xx, timeout, agent crash → automatic incident creation
- **Triage & classification** — severity (P0-P3), impact analysis, root cause hypothesis
- **Self-repair** — agents autonomously diagnose and fix issues (code patches, config changes, restarts)
- **Ticket creation** — unresolved incidents automatically create tracked tickets for human review
- **Escalation** — P0/P1 incidents trigger Slack/Email notifications to on-call team
- **Retrospective loop** — post-incident learnings stored in memory, injected into future sprints

### SAFeパースペクティブとオンボーディング

実際のSAFe組織を反映するロールベースのアダプティブUI：

- **9 SAFe perspectives** — Portfolio Manager, RTE, Product Owner, Scrum Master, Developer, Architect, QA/Security, Business Owner, Admin
- **Adaptive dashboard** — KPIs, quick actions, and sidebar links change per selected role
- **Onboarding wizard** — 3-step first-time user flow (choose role → choose project → start)
- **Perspective selector** — switch SAFe role anytime from the topbar dropdown
- **Dynamic sidebar** — only shows navigation relevant to the current perspective

### 4層メモリとRLMディープサーチ

インテリジェントな検索を備えたセッション間の永続的な知識：

- **Session memory** — conversation context within a single session
- **Pattern memory** — learnings from orchestration pattern execution
- **Project memory** — per-project knowledge (decisions, conventions, architecture)
- **Global memory** — cross-project organizational knowledge (FTS5 full-text search)
- **Auto-loaded project files** — CLAUDE.md, SPECS.md, VISION.md, README.md injected into every LLM prompt (max 8K)
- **RLM Deep Search** — Recursive Language Model (arXiv:2512.24601) — iterative WRITE-EXECUTE-OBSERVE-DECIDE loop with up to 10 exploration iterations

### エージェントメルカート（移籍市場）

チーム構成のためのトークンベースのエージェントマーケットプレイス：

- **Agent listings** — list agents for transfer with asking price
- **Free agent pool** — unassigned agents available for drafting
- **Transfers & loans** — buy, sell, or loan agents between projects
- **Market valuation** — automatic agent valuation based on skills, experience, and performance
- **Wallet system** — per-project token wallets with transaction history
- **Draft system** — claim free agents for your project

### 敵対的品質ガード

偽のコードやプレースホルダーコードの通過をブロックする2層品質ゲート：

- **L0 Deterministic** — instant detection of slop (lorem ipsum, TBD), mocks (NotImplementedError, TODO), fake builds, hallucinations, stack mismatches
- **L1 LLM Semantic** — separate LLM reviews output quality for execution patterns
- **Scoring** — score < 5 passes, 5-6 soft-pass with warning, 7+ rejected
- **Force reject** — hallucination, slop, stack mismatch, fake builds always rejected regardless of score

### 自動ドキュメント生成とWiki

ライフサイクル全体を通じた自動ドキュメント生成：

- **Sprint retrospectives** — LLM-generated retro notes stored in DB and memory, injected into next sprint prompts (learning loop)
- **Phase summaries** — each mission phase produces an LLM-generated summary of decisions and outcomes
- **Architecture Decision Records** — architecture patterns automatically document design decisions in project memory
- **Project context files** — auto-loaded instruction files (CLAUDE.md, SPECS.md, CONVENTIONS.md) serve as living documentation
- **Confluence sync** — bidirectional sync with Confluence wiki pages for enterprise documentation
- **Swagger auto-docs** — 94 REST endpoints auto-documented at `/docs` with OpenAPI schema

## 4つのインターフェース

### 1. Webダッシュボード (HTMX + SSE)

Main UI at http://localhost:8090:

- **Real-time multi-agent conversations** with SSE streaming
- **PI Board** — program increment planning
- **Mission Control** — execution monitoring
- **Agent Management** — view, configure, monitor agents
- **Incident Dashboard** — auto-heal triage
- **Mobile responsive** — works on tablets and phones

### 2. CLI (`sf`)

フル機能のコマンドラインインターフェース：

```bash
# Install (add to PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Browse
sf status                              # Platform health
sf projects list                       # All projects
sf missions list                       # Missions with WSJF scores
sf agents list                         # 145 agents
sf features list <epic_id>             # Epic features
sf stories list --feature <id>         # User stories

# Work
sf ideation "e-commerce app in React"  # Multi-agent ideation (streamed)
sf missions start <id>                 # Start mission run
sf metrics dora                        # DORA metrics

# Monitor
sf incidents list                      # Incidents
sf llm stats                           # LLM usage (tokens, cost)
sf chaos status                        # Chaos engineering
```

**22 command groups** · Dual mode: API (live server) or DB (offline) · JSON output (`--json`) · Spinner animations · Markdown table rendering

### 3. REST API + Swagger

94 API endpoints auto-documented at `/docs` (Swagger UI):

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

### 4. MCPサーバー（Model Context Protocol）

24 MCP tools for AI agent integration (port 9501):

```bash
# Start MCP server
python3 -m platform.mcp_platform.server

# Tools available:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## アーキテクチャ

### プラットフォーム概要

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

### パイプラインフロー

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

### オブザーバビリティ

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

### デプロイ

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

## プロジェクト設定

プロジェクトは `projects/*.yaml` で定義されます：

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

## ディレクトリ構造

```
├── platform/                # Agent Platform (152 Python files)
│   ├── server.py            # FastAPI app, port 8090
│   ├── agents/              # Agent loop, executor, store
│   ├── a2a/                 # Agent-to-agent messaging bus
│   ├── patterns/            # 10 orchestration patterns
│   ├── missions/            # SAFe mission lifecycle
│   ├── sessions/            # Conversation runner + SSE
│   ├── web/                 # Routes + Jinja2 templates
│   ├── mcp_platform/        # MCP server (23 tools)
│   └── tools/               # Agent tools (code, git, deploy)
│
├── cli/                     # CLI 'sf' (6 files, 2100+ LOC)
│   ├── sf.py                # 22 command groups, 40+ subcommands
│   ├── _api.py              # httpx REST client
│   ├── _db.py               # sqlite3 offline backend
│   ├── _output.py           # ANSI tables, markdown rendering
│   └── _stream.py           # SSE streaming with spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm charts, Docker, K8s
├── tests/                   # E2E Playwright tests
├── skills/                  # Agent skills library
├── projects/                # Project YAML configurations
└── data/                    # SQLite database
```

## テスト

```bash
# Run all tests
make test

# E2E tests (Playwright — requires install first)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Unit tests
pytest tests/

# Chaos engineering
python3 tests/test_chaos.py

# Endurance tests
python3 tests/test_endurance.py
```

## デプロイ

### Docker

Dockerイメージには以下が含まれます: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**。
Agents can build projects, run E2E tests with screenshots, and perform SAST security scans out of the box.

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### 環境変数

完全なリストは [`.env.example`](.env.example) を参照。主要な変数：

```bash
# LLM Provider (required for real agents)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API key

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

## 適応型インテリジェンス — GA · RL · Thompsonサンプリング · OKR

プラットフォームは3つの補完的なAIエンジンによって自己最適化します。

### Thompsonサンプリング — 確率的チーム選択
- コンテキスト `(agent_id, pattern_id, technology, phase_type)` ごとに `Beta(wins+1, losses+1)` を保持
- 細粒度の適合度スコア — コンテキストごとに独立したスコア、クロスコンテキスト汚染なし
- コールドスタートフォールバック：技術プレフィックスチェーン（`angular_19` → `angular_*` → `generic`）
- ソフトリタイア：弱いチームに `weight_multiplier=0.1` を設定、回復可能
- 自動A/Bシャドウ実行；中立エバリュエーターが勝者を決定
- **Darwin LLM**：Thompsonサンプリングをコンテキストごとのモデル選択に拡張

### 遺伝的アルゴリズム — ワークフロー進化
- ゲノム = PhaseSpec（pattern, agents, gate）の順序付きリスト
- 個体群：40ゲノム、最大30世代、エリート保存=2、突然変異率=15%、トーナメント k=3
- 適合度：フェーズ成功率 × エージェント適合度 × (1 − 拒否率) × リードタイムボーナス
- 上位3提案を `evolution_proposals` に保存して人間のレビュー後に適用
- 手動トリガー：`POST /api/evolution/run/{wf_id}` — Workflows → Evolutionタブで確認
- 夜間スケジューラー；5ミッション未満の場合はスキップ

### 強化学習 — ミッション中のパターン適応
- Q学習ポリシー（`platform/agents/rl_policy.py`）
- アクション：keep、switch_parallel、switch_sequential、switch_hierarchical、switch_debate、add_agent、remove_agent
- 状態：`(wf_id, phase_position, rejection_pct, quality_score)` をバケット化
- Qアップデート：α=0.1、γ=0.9、ε=0.1 — `rl_experience` テーブルでオフラインバッチ処理
- 信頼度 ≥ 70% かつ状態訪問 ≥ 3 回のときのみ発動；グレースフルデグラデーション対応

### OKR / KPIシステム
- 8つのデフォルトシード：code/migration、security/audit、architecture/design、testing、docs
- OKR達成度はGA適合度とRL報酬シグナルに直接フィードバック
- `/teams` でインライン編集、緑/黄/赤のステータス表示
- 設定からプロジェクトごとのOKR上書き設定が可能

---

## v2.1.0 の新機能 (2026年2月)

### 品質メトリクス — 産業レベルモニタリング
- **10 deterministic dimensions** — complexity, coverage (UT/E2E), security, accessibility, performance, documentation, architecture, maintainability, adversarial
- **Quality gates on workflow phases** — PASS/FAIL badges per phase with configurable thresholds (always/no_veto/all_approved/quality_gate)
- **Quality dashboard** at `/quality` — global scorecard, per-project scores, trend snapshots
- **Quality badges everywhere** — mission detail, project board, workflow phases, main dashboard
- **No LLM required** — all metrics computed deterministically using open-source tools (radon, bandit, semgrep, coverage.py, pa11y, madge)

### プロジェクトごとの4つの自動プロビジョニングミッション
Every project automatically gets 4 operational missions:
- **MCO/TMA** — continuous maintenance: health monitoring, incident triage (P0-P4), TDD fix, non-regression validation
- **Security** — weekly SAST scans, dependency audit, CVE watch, code review
- **Tech Debt** — monthly debt reduction: complexity audit, WSJF prioritization, refactoring sprints
- **Self-Healing** — autonomous incident pipeline: 5xx detection → TMA mission creation → agent diagnosis → code fix → validation

### 継続的改善
- **quality-improvement workflow** — scan → identify worst dimensions → plan & execute improvements
- **retrospective-quality workflow** — sprint retro with ROTI, incidents, quality metrics → action items
- **skill-evolution workflow** — analyze agent performance → update prompts → evolve skills
- **Feedback loop** — metrics → analysis → improvement → re-scan → track progress

### SAFeパースペクティブとオンボーディング
- **9 SAFe role perspectives** — adaptive dashboard, sidebar, and KPIs per role
- **Onboarding wizard** — 3-step first-time user flow with role and project selection
- **Perspective selector** — switch SAFe role from topbar at any time

### 自動修復とセルフリペア
- **TMA heartbeat** — continuous health monitoring with auto-incident creation
- **Self-repair agents** — autonomous diagnosis and fix for common failures
- **Ticket escalation** — unresolved incidents create tracked tickets with notifications

### 4層メモリとRLM
- **Persistent knowledge** — session, pattern, project, and global memory layers with FTS5
- **RLM deep search** — recursive exploration loop (up to 10 iterations) for complex codebase analysis
- **Auto-loaded project context** — CLAUDE.md, SPECS.md, VISION.md injected into every agent prompt

### 敵対的品質ガード
- **L0 deterministic** — instant detection of slop, mocks, fake builds, hallucinations
- **L1 semantic** — LLM-based quality review for execution outputs
- **Force reject** — hallucination and stack mismatch always blocked

### Agent Mercato
- **Token-based marketplace** with agent listings, transfers, loans, and free agent draft
- **Market valuation** — automatic agent pricing based on skills and performance
- **Wallet system** — per-project token economy with transaction history

### 認証とセキュリティ
- **JWT-based auth** with login/register/refresh/logout
- **RBAC** — admin, project_manager, developer, viewer roles
- **OAuth** — GitHub and Azure AD SSO login
- **Admin panel** — user management UI (`/admin/users`)
- **Demo mode** — one-click "Skip" button for instant access

### 自動ドキュメント生成
- **Sprint retrospectives** — LLM-generated retro notes with learning loop
- **Phase summaries** — automatic documentation of mission phase outcomes
- **Confluence sync** — bidirectional wiki integration

### LLMプロバイダー
- **Multi-provider** with automatic fallback chain
- MiniMax M2.5, Azure OpenAI GPT-5-mini, Azure AI Foundry, NVIDIA NIM
- **Demo mode** for UI exploration without API keys

### プラットフォームの改善
- DORA metrics dashboard with LLM cost tracking
- Jira bidirectional sync
- Playwright E2E test suite (11 spec files)
- Internationalization (EN/FR)
- Real-time notifications (Slack, Email, Webhook)
- Design System pipeline in workflows (UX → dev → review)
- 3D Agent World visualization

### Darwin — 進化的チーム選択
- **Thompson Samplingによる選択** — `Beta(wins+1, losses+1)` を用いた確率的 agent+pattern チーム選択（次元: `agent_id, pattern_id, 技術, フェーズタイプ`）
- **細粒度フィットネス追跡** — コンテキストごとに独立したスコア：Angularマイグレーション得意チームがAngular新機能に強いとは限らない
- **類似度フォールバック** — 技術プレフィックスマッチングでコールドスタートを解決（`angular_19` → `angular_*` → `generic`）
- **ソフト引退** — 低パフォーマンスチームは `weight_multiplier=0.1` で優先度を下げるが削除しない
- **OKR / KPIシステム** — ドメインとフェーズタイプごとの目標と指標；8つのデフォルトシード
- **A/Bシャドウテスト** — 2チームの適応度スコア差が10未満、または10%の確率で自動並列実行
- **Teamsダッシュボード** `/teams` — champion/rising/declining/retiredバッジ付きランキング、インラインOKR編集、進化チャート、選択履歴、A/B結果
- **ノンブレーキングオプトイン** — パターンで `agent_id: "skill:developer"` を使うとDarwinが有効化；明示的IDは変更なし

## v2.2.0 の新機能 (2026年2月)

### OpenTelemetryと分散トレーシング
- **OTEL integration** — OpenTelemetry SDK with OTLP/HTTP exporter to Jaeger
- **ASGI tracing middleware** — every HTTP request traced with spans, latency, status
- **Tracing dashboard** at `/analytics` — request stats, latency charts, operation table
- **Jaeger UI** — full distributed trace exploration at port 16686

### パイプライン障害分析
- **Failure classification** — Python-based error categorization (setup_failed, llm_provider, timeout, phase_error, etc.)
- **Phase failure heatmap** — identify which pipeline phases fail most often
- **Recommendations engine** — actionable suggestions based on failure patterns
- **Resume All button** — one-click mass-resume of paused runs from the dashboard

### 継続的ウォッチドッグ
- **Auto-resume** — automatically resume paused runs in batches (5/batch, every 5 min, max 10 concurrent)
- **Stale session recovery** — detect sessions inactive >30 min, mark as interrupted for retry
- **Failed session cleanup** — clean zombie sessions blocking pipeline progress
- **Stall detection** — missions stuck in a phase >60 min get automatic retry

### フェーズ回復力
- **Per-phase retry** — configurable retry count (default 3x) with exponential backoff per phase
- **skip_on_failure** — phases can be marked optional, allowing pipeline to continue
- **Checkpointing** — completed phases saved, smart resume skips finished work
- **Phase timeout** — 10-minute cap prevents infinite hangs

### サンドボックスビルド検証
- **Post-code build check** — after code generation phases, automatically run build/lint
- **Auto-detect build system** — npm, cargo, go, maven, python, docker
- **Error injection** — build failures injected into agent context for self-correction

### 品質UI改善
- **Radar chart** — Chart.js radar visualization of quality dimensions on `/quality`
- **Quality badge** — colored score circle for project headers (`/api/dashboard/quality-badge`)
- **Mission scorecard** — quality metrics in mission detail sidebar (`/api/dashboard/quality-mission`)

### マルチモデル LLM ルーティング
- **3 つの専門モデル** — `gpt-5.2` は重い推論向け、`gpt-5.1-codex` はコード/テスト向け、`gpt-5-mini` は軽タスク向け
- **ロールベースルーティング** — エージェントはタグ（`reasoner`、`architect`、`developer`、`tester`、`doc_writer`…）に基づき自動的に適切なモデルを受け取る
- **ライブ設定可能** — 設定 → LLM からルーティングマトリックスを再起動不要で編集

### Darwin LLM — モデルへの Thompson Sampling
- **モデル A/B テスト** — 同チーム（エージェント + パターン）が異なる LLM で競い、コンテキストごとに最良モデルが自動的に決定
- **ベータ分布** — `Beta(wins+1, losses+1)` per `(agent_id, pattern_id, technology, phase_type, llm_model)`
- **/teams の LLM A/B タブ** — モデルごとのフィットネスランキングと A/B テスト履歴
- **優先チェーン** — Darwin LLM → DB 設定 → デフォルト値（グレースフルデグラデーション）

### 設定 — LLM タブ
- **プロバイダーグリッド** — アクティブ/非アクティブ状態と API キー欠落のヒント表示
- **ルーティングマトリックス** — カテゴリ別（推論・本番/コード・タスク・文書作成）の重い/軽いモデル設定
- **Darwin LLM A/B セクション** — 進行中のモデル実験のライブビュー

## v2.3.0 の新機能 (2026年2月)

### ナビゲーションの再構成 — ホーム + ダッシュボード
- **ホームページ** (`/`) — 3つのタブ: CTO Jarvis · ビジネスアイデア · プロジェクトアイデア
- **ダッシュボード** (`/portfolio`) — 3つのタブ: 概要 · CTO · ビジネス
- **シンプルなサイドバー** — 2つのエントリのみ: ホームとダッシュボード
- **Feather SVGアイコン** — 絵文字を一貫したベクターアイコンに置き換え

### CTO Jarvis — 戦略的AIアドバイザー
- **永続的チャットパネル** — ホームページ専用タブ
- **永続的メモリ** — 技術的な決定とセッションコンテキストを会話間で保持
- **CTOレベルのアドバイザー** — アーキテクチャの意思決定、技術選択のサポート
- **プラットフォーム認識** — ポートフォリオ、プロジェクト、エージェントチームの現状を把握

### ビジネスアイデア — 6エージェントのマーケティングチーム
- **ルート** `/mkt-ideation` — ホームページのビジネスアイデアタブからアクセス可能
- **CMO Sophie Laurent** — 5名の専門マーケティングエキスパートを率いるチームリーダー
- **完全なマーケティングプランJSON** — SWOT、TAM/SAM/SOM、ブランド戦略、GTM、KPI、予算
- **エージェントグラフ** — アバター写真、コラボレーションエッジ、詳細ポップオーバーのig-nodeビジュアライゼーション

### PostgreSQL移行 + 40インデックス
- **SQLite → PostgreSQL移行** — スキーマとデータの完全な移行スクリプト
- **ネイティブPostgreSQL FTS** — `tsvector/tsquery`がFTS5を置き換え、より高性能でスケーラブル
- **40以上のPGインデックス** — すべてのホットクエリパスの包括的なカバレッジ
- **Darwin Teams** — コンテキスト（技術+フェーズ）ごとのエージェントチーム選択のThompsonサンプリング

## 貢献

貢献を歓迎します！ガイドラインについては [CONTRIBUTING.md](CONTRIBUTING.md) をお読みください。

## ライセンス

このプロジェクトはAGPL v3ライセンスの下でライセンスされています - 詳細は[LICENSE](LICENSE)ファイルを参照してください。

## サポート

- Live Demo: https://sf.macaron-software.com
- Issues: https://github.com/macaron-software/software-factory/issues
- Discussions: https://github.com/macaron-software/software-factory/discussions
