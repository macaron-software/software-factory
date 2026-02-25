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

**Multi-Agent Software Factory — Autonomous AI agents orchestrating the full product lifecycle**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

</div>

---

## Overview

Software Factory is an autonomous multi-agent platform that orchestrates the entire software development lifecycle using 161 specialized AI agents working together.

### Key Features

- **161 specialized agents** — architects, developers, testers, SRE, security analysts
- **10 orchestration patterns** — solo, sequential, parallel, hierarchical, network, loop, router, aggregator, wave, human-in-the-loop
- **SAFe-aligned lifecycle** — Portfolio → Epic → Feature → Story
- **Auto-heal** — autonomous incident detection and self-repair
- **LLM resilience** — multi-provider fallback, jittered retry, rate-limit aware
- **OpenTelemetry observability** — distributed tracing with Jaeger, pipeline analytics
- **Continuous watchdog** — auto-resume paused runs, stale session recovery
- **DORA metrics** — deployment frequency, lead time, MTTR, change failure rate

## Screenshots

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/ja/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/ja/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/ja/cli.png" width="100%"></td>
</tr>
</table>

## Quick Start

### オプション 1: Docker（推奨）

Docker イメージ内蔵: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**。

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # .env.example → .env をコピー（LLMキーを編集）
make run     # ビルド＆起動
```

### オプション 2: ローカルインストール

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # 設定ファイル作成（LLMキーを追加 — 下記参照）
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make dev
```

http://localhost:8090 を開く — 初回起動時に**オンボーディングウィザード**が表示されます。
SAFeロールを選択するか、**「Skip (Demo)」**をクリック。

### LLMプロバイダーの設定

APIキーなしでは **デモモード** で動作します（模擬応答 — UIの探索に便利）。

`.env` を編集して **1つの** APIキーを追加:

```bash
# オプション A: MiniMax（無料 — 推奨）
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# オプション B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# オプション C: NVIDIA NIM（無料）
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

再起動: `make run`（Docker）または `make dev`（ローカル）

| プロバイダー | 環境変数 | モデル | 無料 |
|-------------|----------|--------|------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 | ✅ |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini | ❌ |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 | ❌ |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 | ✅ |

ダッシュボードの **Settings**（`/settings`）からも設定可能。

## Features

- **161 AI agents** organized in teams
- **Built-in tools**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**

## 品質メトリクス — 工業的モニタリング

決定論的品質スキャン（LLM不要）、10次元で生産ラインのように管理：

**複雑度** · **UTカバレッジ** · **E2Eカバレッジ** · **セキュリティ** · **アクセシビリティ** · **パフォーマンス** · **ドキュメント** · **アーキテクチャ** · **保守性** · **アドバーサリアル**

ワークフローフェーズに品質ゲート（PASS/FAILバッジ） · `/quality`ダッシュボード · ミッション・プロジェクト・ワークフローにバッジ表示。

### プロジェクトごとの4つの自動ミッション

| ミッション | 頻度 | 説明 |
|-----------|------|------|
| **MCO/TMA** | 継続的 | ヘルスモニタリング、インシデントトリアージ(P0-P4)、TDD修正 |
| **セキュリティ** | 毎週 | SASTスキャン、依存関係監査、CVE監視 |
| **技術的負債** | 毎月 | 複雑度監査、WSJF優先順位付け、リファクタリングスプリント |
| **セルフヒーリング** | 継続的 | 5xx検出→TMAミッション→エージェント診断→コード修正→検証 |

### 継続的改善

3つの組み込みワークフロー：**quality-improvement**（スキャン→改善計画）、**retrospective-quality**（メトリクス付きスプリントレトロ）、**skill-evolution**（エージェントプロンプト最適化）。


## Architecture

```
                     ┌──────────────────────┐
                     │  CLI (sf) / Web UI   │
                     │  REST API :8090      │
                     └──────────┬───────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │     FastAPI Server            │
                 │  Auth (JWT + RBAC + OAuth)    │
                 └──┬──────────┬────────────┬───┘
                    │          │            │
       ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
       │ Agent        │   │ Workflow │   │   Mission    │
       │  Engine      │   │  Engine  │   │    Layer     │
       │ 161 agents   │   │ 39 defs  │   │ SAFe cycle   │
       │ executor     │   │ 10 ptrns │   │ Portfolio    │
       └──────┬───────┘   │ phases   │   │ Epic/Feature │
              │           │ retry    │   └──────────────┘
              │           └────┬─────┘
              │                │
  ┌───────────┴────────────────┴───────────────┐
  │  Services + Operations                      │
  │  LLM (multi-provider fallback)              │
  │  Tools (code, git, deploy, security)        │
  │  Watchdog (auto-resume, stall detection)    │
  │  Quality (10 dimensions, radar, badge)      │
  │  OpenTelemetry (tracing > Jaeger)           │
  └───────────────────┬────────────────────────┘
                      │
           ┌──────────┴──────────┐
           │  SQLite + Memory    │
           │  4 layers + FTS5    │
           └─────────────────────┘
```

## What's New in v2.2.0 (Feb 2026)

### OpenTelemetry & Distributed Tracing
- **OTEL integration** — OpenTelemetry SDK with OTLP/HTTP exporter to Jaeger
- **Tracing dashboard** at `/analytics` — request stats, latency charts, operation table

### Pipeline Failure Analysis
- **Failure classification** — error categorization (setup_failed, llm_provider, timeout, phase_error)
- **Phase failure heatmap** — identify which phases fail most often
- **Resume All button** — one-click mass-resume of paused runs

### Continuous Watchdog
- **Auto-resume** — resume paused runs in batches (5/batch, every 5 min, max 10 concurrent)
- **Stale session recovery** — detect inactive sessions >30 min, mark for retry
- **Stall detection** — missions stuck >60 min in a phase get automatic retry

### Phase Resilience
- **Per-phase retry** — configurable retry (3x) with exponential backoff
- **skip_on_failure** — optional phases, pipeline continues on failure
- **Checkpointing** — completed phases saved, smart resume skips finished work

### Sandbox Build Validation
- **Post-code build check** — auto build/lint after code generation phases
- **Auto-detect build system** — npm, cargo, go, maven, python, docker

## テスト

```bash
# ユニットテスト
pytest tests/

# E2Eテスト (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
