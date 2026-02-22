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
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/zh/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/zh/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/zh/cli.png" width="100%"></td>
</tr>
</table>

## Quick Start

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
docker-compose up -d
```

Open http://localhost:8099

### 配置 LLM 提供商

平台需要至少 **一个 LLM 提供商** 才能让 AI 代理生成真实代码。没有 API 密钥时，以 **demo 模式** 运行。

```bash
cp .env.example .env
# 编辑 .env 并添加 API 密钥
```

| 提供商 | 环境变量 | 免费 |
|--------|----------|------|
| **MiniMax** | `MINIMAX_API_KEY` | ✅ |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | ❌ |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | ✅ |

设置 `PLATFORM_LLM_PROVIDER` 为主提供商（`minimax`、`azure-openai`、`nvidia`）。
也可以在仪表板的 **Settings** 页面（`/settings`）配置。

## Features

- **145 AI agents** organized in teams
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**


## 测试

```bash
# 单元测试
pytest tests/

# E2E 测试 (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
