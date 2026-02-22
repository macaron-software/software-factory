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

# Macaron Software Factory

**Fábrica de Software Multi-Agente — Agentes IA autónomos orquestando el ciclo de vida completo del producto**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Características](#características) · [Inicio Rápido](#inicio-rápido) · [Capturas](#capturas-de-pantalla) · [Arquitectura](#arquitectura) · [Contribuir](#contribuir)

</div>

---

## ¿Qué es esto?

Macaron es una **plataforma multi-agente autónoma** que orquesta todo el ciclo de vida del desarrollo de software — desde la ideación hasta el despliegue — utilizando agentes IA especializados que trabajan juntos.

Piensálo como una **fábrica de software virtual** donde 94 agentes IA colaboran a través de flujos de trabajo estructurados, siguiendo la metodología SAFe, prácticas TDD y puertas de calidad automatizadas.

### Puntos clave

- **94 agentes especializados** — arquitectos, desarrolladores, testers, SREs, analistas de seguridad, product owners
- **12 patrones de orquestación** — solo, paralelo, jerárquico, red, adversarial-pair, human-in-the-loop
- **Ciclo de vida alineado con SAFe** — Portfolio → Epic → Feature → Story con cadencia PI
- **Auto-reparación** — detección de incidentes, triaje y reparación autónomos
- **Seguridad primero** — protección contra inyección, RBAC, limpieza de secretos, pool de conexiones
- **Métricas DORA** — frecuencia de despliegue, lead time, MTTR, tasa de fallos

## Capturas de pantalla

<table>
<tr>
<td width="50%">
<strong>Portfolio — Comité Estratégico y Gobernanza</strong><br>
<img src="docs/screenshots/es/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI Board — Planificación de Incrementos de Programa</strong><br>
<img src="docs/screenshots/es/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agentes — 94 Agentes IA Especializados</strong><br>
<img src="docs/screenshots/es/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>Taller de Ideación — Brainstorming con IA</strong><br>
<img src="docs/screenshots/es/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Control de Misión — Monitoreo de ejecución en tiempo real</strong><br>
<img src="docs/screenshots/es/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>Monitoreo — Salud del sistema y métricas</strong><br>
<img src="docs/screenshots/es/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## Inicio Rápido

### Opción 1: Docker (Recomendado)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### Opción 2: Docker Compose (Manual)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### Opción 3: Desarrollo local

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### Verificar instalación

```bash
curl http://localhost:8090/api/health
```

## Contribuir

¡Las contribuciones son bienvenidas! Consulta [CONTRIBUTING.md](CONTRIBUTING.md) para las directrices.

## Licencia

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**Construido con amor por [Macaron Software](https://github.com/macaron-software)**

[Reportar bug](https://github.com/macaron-software/software-factory/issues) · [Solicitar funcionalidad](https://github.com/macaron-software/software-factory/issues)

</div>
