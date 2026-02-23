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
- **Auto-heal** — autonomous incident detection and self-repair with real-time notifications
- **DORA metrics** — deployment frequency, lead time, MTTR, change failure rate
- **Multilingual** — auto-detects browser language (8 locales: en, fr, es, it, de, pt, ja, zh)
- **Custom AI providers** — GUI to configure any OpenAI-compatible LLM with encrypted API keys
- **Real-time analytics** — live performance dashboards with Chart.js visualizations
- **In-app notifications** — bell icon with dropdown for TMA tickets, incidents, and system alerts

## Screenshots

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/pt/dashboard.png" width="100%"></td>
<td width="33%"><strong>Swagger API</strong><br><img src="docs/screenshots/pt/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/pt/cli.png" width="100%"></td>
</tr>
</table>

## Quick Start

A imagem Docker inclui: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env       # Configurar chaves LLM (ver abaixo)
docker-compose up -d
```

Open http://localhost:8090

### Configurar provedor LLM

A plataforma requer pelo menos **um provedor LLM** para gerar código real. Sem chave API, funciona em **modo demo**.

```bash
cp .env.example .env
# Editar .env e adicionar chaves API
```

| Provedor         | Variável de ambiente                             | Gratuito |
| ---------------- | ------------------------------------------------ | -------- |
| **MiniMax**      | `MINIMAX_API_KEY`                                | ✅       |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | ❌       |
| **NVIDIA NIM**   | `NVIDIA_API_KEY`                                 | ✅       |

Definir `PLATFORM_LLM_PROVIDER` como provedor principal. Configuração também em **Settings** (`/settings`).

## Features

- **158 AI agents** organized in teams
- **Ferramentas integradas**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **Complete CLI** — 40+ commands
- **REST API** — 94 documented endpoints
- **MCP Server** — 23 tools
- **License AGPL v3**

## Testes

```bash
# Testes unitários
pytest tests/

# Testes E2E (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
