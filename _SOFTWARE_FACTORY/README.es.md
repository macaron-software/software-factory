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
- **Auto-reparación** — detección autónoma de incidentes, triage y auto-reparación con notificaciones en tiempo real
- **Seguridad prioritaria** — guardia inyección de prompt, RBAC, enmascaramiento secretos
- **Métricas DORA** — frecuencia despliegue, lead time, MTTR, tasa fallo cambios
- **Multilingüe** — detección automática del idioma del navegador (8 idiomas: en, fr, es, it, de, pt, ja, zh)
- **Proveedores de IA personalizados** — interfaz para configurar cualquier LLM compatible con OpenAI con cifrado de claves API
- **Analítica en tiempo real** — paneles de rendimiento en vivo con visualizaciones Chart.js
- **Notificaciones integradas** — icono de campana con menú desplegable para tickets TMA, incidentes y alertas del sistema

## Capturas de pantalla

<table>
<tr>
<td width="33%"><strong>Dashboard</strong><br><img src="docs/screenshots/es/dashboard.png" width="100%"></td>
<td width="33%"><strong>API Swagger</strong><br><img src="docs/screenshots/es/swagger.png" width="100%"></td>
<td width="33%"><strong>CLI</strong><br><img src="docs/screenshots/es/cli.png" width="100%"></td>
</tr>
</table>

## Inicio rápido

La imagen Docker incluye: **Node.js 20**, **Playwright + Chromium**, **bandit**, **semgrep**, **ripgrep**.

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env       # Configurar claves LLM (ver abajo)
docker-compose up -d
```

Abrir http://localhost:8090

### Configurar un proveedor LLM

La plataforma requiere al menos **un proveedor LLM** para generar código real. Sin clave API, funciona en **modo demo**.

```bash
cp .env.example .env
# Editar .env y añadir claves API
```

| Proveedor        | Variable de entorno                              | Gratuito |
| ---------------- | ------------------------------------------------ | -------- |
| **MiniMax**      | `MINIMAX_API_KEY`                                | ✅       |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | ❌       |
| **NVIDIA NIM**   | `NVIDIA_API_KEY`                                 | ✅       |

Establecer `PLATFORM_LLM_PROVIDER` como proveedor principal. Configuración también disponible en **Settings** (`/settings`).

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
