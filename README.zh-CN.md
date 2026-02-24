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

### 方式一：Docker（推荐）

Docker 镜像包含：**Node.js 20**、**Playwright + Chromium**、**bandit**、**semgrep**、**ripgrep**。

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # 复制 .env.example → .env（编辑添加 LLM 密钥）
make run     # 构建并启动平台
```

### 方式二：本地安装

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # 创建配置文件（添加 LLM 密钥 — 见下方）
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make dev
```

打开 http://localhost:8090 — 首次启动时会显示**引导向导**。
选择您的 SAFe 角色或点击 **"Skip (Demo)"**。

### 配置 LLM 提供商

没有 API 密钥时，以 **demo 模式** 运行（模拟响应 — 方便探索界面）。

编辑 `.env` 并添加 **一个** API 密钥：

```bash
# 选项 A：MiniMax（免费 — 推荐入门）
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# 选项 B：Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# 选项 C：NVIDIA NIM（免费）
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

重启：`make run`（Docker）或 `make dev`（本地）

| 提供商 | 环境变量 | 模型 | 免费 |
|--------|----------|------|------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 | ✅ |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini | ❌ |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 | ❌ |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 | ✅ |

也可以在仪表板的 **Settings** 页面（`/settings`）配置。

## Features

- **161 AI agents** organized in teams
- **Built-in tools**: `code_write`, `build`, `test`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**

## 质量指标 — 工业化监控

确定性质量扫描（无需LLM），10个维度如同生产线管理：

**复杂度** · **UT覆盖率** · **E2E覆盖率** · **安全性** · **可访问性** · **性能** · **文档** · **架构** · **可维护性** · **对抗验证**

工作流阶段质量门禁（PASS/FAIL徽章） · `/quality`仪表板 · 任务、项目和工作流显示质量徽章。

### 每个项目4个自动任务

| 任务 | 频率 | 描述 |
|------|------|------|
| **MCO/TMA** | 持续 | 健康监控、事件分级(P0-P4)、TDD修复 |
| **安全** | 每周 | SAST扫描、依赖审计、CVE监控 |
| **技术债务** | 每月 | 复杂度审计、WSJF优先级、重构冲刺 |
| **自愈** | 持续 | 5xx检测→TMA任务→Agent诊断→代码修复→验证 |

### 持续改进

3个内置工作流：**quality-improvement**（扫描→改进计划）、**retrospective-quality**（含指标的Sprint回顾）、**skill-evolution**（Agent提示词优化）。


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
