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

Software Factory is an autonomous multi-agent platform that orchestrates the entire software development lifecycle using 145 specialized AI agents working together.

### Key Features

- **145 specialized agents** — architects, developers, testers, SRE, security analysts
- **12 orchestration patterns** — solo, parallel, hierarchical, network, adversarial-pair
- **SAFe-aligned lifecycle** — Portfolio → Epic → Feature → Story
- **Auto-heal** — autonomous incident detection and self-repair
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

- **158 AI agents** organized in teams
- **Built-in tools**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**


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
