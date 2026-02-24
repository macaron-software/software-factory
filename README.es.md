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

**Fábrica de Software Multi-Agente — Agentes IA autónomos orquestando el ciclo de vida completo del producto**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

</div>

---

## ¿Qué es esto?

Software Factory es una **plataforma multi-agente autónoma** que orquesta todo el ciclo de desarrollo de software — desde la ideación hasta el despliegue — usando agentes IA especializados trabajando juntos.

Piensa en ello como una **fábrica de software virtual** donde 158 agentes IA colaboran a través de flujos estructurados, siguiendo metodología SAFe, prácticas TDD y puertas de calidad automatizadas.

### Puntos clave

- **158 agentes especializados** — arquitectos, desarrolladores, testers, SRE, analistas de seguridad, product owners
- **12 patrones de orquestación** — solo, paralelo, jerárquico, red, adversarial-pair, human-in-the-loop
- **Ciclo de vida SAFe** — Portfolio → Epic → Feature → Story con cadencia PI
- **Auto-reparación** — detección autónoma de incidentes, triage y auto-reparación
- **Seguridad prioritaria** — guardia inyección de prompt, RBAC, enmascaramiento secretos
- **Métricas DORA** — frecuencia despliegue, lead time, MTTR, tasa fallo cambios

## Capturas de pantalla

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/es/dashboard.png" width="100%"></td>
<td width="33%"><strong>API Swagger</strong><br><img src="docs/screenshots/es/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/es/cli.png" width="100%"></td>
</tr>
</table>

## Inicio rápido

### Opción 1: Docker (Recomendado)

La imagen Docker incluye: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # crea .env desde .env.example (editar con tu clave LLM)
make run     # construye e inicia la plataforma
```

### Opción 2: Instalación local

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # crear config (añadir clave LLM — ver abajo)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt
make dev
```

Abrir http://localhost:8090 — en el primer inicio aparece el **asistente de onboarding**.
Elige tu rol SAFe o haz clic en **"Skip (Demo)"**.

### Configurar un proveedor LLM

Sin clave API, la plataforma funciona en **modo demo** (respuestas simuladas — útil para explorar la interfaz).

Edita `.env` y añade **una** clave API:

```bash
# Opción A: MiniMax (gratuito — recomendado para empezar)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-tu-clave-aquí

# Opción B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=tu-clave
AZURE_OPENAI_ENDPOINT=https://tu-recurso.openai.azure.com

# Opción C: NVIDIA NIM (gratuito)
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-tu-clave-aquí
```

Luego reiniciar: `make run` (Docker) o `make dev` (local)

| Proveedor | Variable de entorno | Modelos | Gratuito |
|-----------|--------------------|---------|-----------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 | ✅ |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini | ❌ |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 | ❌ |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 | ✅ |

Configuración también disponible en **Settings** (`/settings`).

## Características

- **158 agentes IA** organizados en equipos
- **Herramientas integradas**: `code_write`, `build`, `local_ci`, `sast_scan`, `playwright_test`, `create_ticket`, `git_commit`
- **CLI completa** — 40+ comandos
- **API REST** — 94 endpoints documentados
- **Servidor MCP** — 23 herramientas
- **Licencia AGPL v3**


## Pruebas

```bash
# Tests unitarios
pytest tests/

# Tests E2E (Playwright)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test
```
