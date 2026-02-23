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
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/ko/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/ko/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/ko/cli.png" width="100%"></td>
</tr>
</table>

## Quick Start

Docker 이미지 포함: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env       # LLM 키 설정 (아래 참조)
docker-compose up -d
```

Open http://localhost:8090

### LLM 제공업체 설정

플랫폼은 최소 **하나의 LLM 제공업체**가 필요합니다. API 키 없이는 **데모 모드**로 작동합니다.

```bash
cp .env.example .env
# .env를 편집하고 API 키 추가
```

| 제공업체         | 환경 변수                                        | 무료 |
| ---------------- | ------------------------------------------------ | ---- |
| **MiniMax**      | `MINIMAX_API_KEY`                                | ✅   |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | ❌   |
| **NVIDIA NIM**   | `NVIDIA_API_KEY`                                 | ✅   |

`PLATFORM_LLM_PROVIDER`를 기본 제공업체로 설정. 대시보드 **Settings**(`/settings`)에서도 설정 가능.

## Features

- **158 AI agents** organized in teams
- **Built-in tools**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**

## 테스트

```bash
# 유닛 테스트
pytest tests/

# E2E 테스트 (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
