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

**Fábrica de Software Multi-Agente — Agentes IA autônomos orquestrando o ciclo de vida completo do produto**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[Recursos](#recursos) · [Início Rápido](#início-rápido) · [Capturas](#capturas-de-tela) · [Arquitetura](#arquitetura) · [Contribuir](#contribuir)

</div>

---

## O que é isso?

Macaron é uma **plataforma multi-agente autônoma** que orquestra todo o ciclo de vida do desenvolvimento de software — da ideação ao deploy — usando agentes IA especializados trabalhando juntos.

Pense nisso como uma **fábrica de software virtual** onde 94 agentes IA colaboram por meio de workflows estruturados, seguindo a metodologia SAFe, práticas TDD e gates de qualidade automatizados.

### Destaques

- **94 agentes especializados** — arquitetos, desenvolvedores, testadores, SREs, analistas de segurança, product owners
- **12 padrões de orquestração** — solo, paralelo, hierárquico, rede, adversarial-pair, human-in-the-loop
- **Ciclo de vida alinhado ao SAFe** — Portfolio → Epic → Feature → Story com cadência PI
- **Auto-reparação** — detecção de incidentes, triagem e reparação autônomos
- **Segurança primeiro** — proteção contra injeção, RBAC, limpeza de segredos, pool de conexões
- **Métricas DORA** — frequência de deploy, lead time, MTTR, taxa de falha

## Capturas de tela

<table>
<tr>
<td width="50%">
<strong>Portfolio — Comitê Estratégico e Governança</strong><br>
<img src="docs/screenshots/pt/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI Board — Planejamento de Incrementos de Programa</strong><br>
<img src="docs/screenshots/pt/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Agentes — 94 Agentes IA Especializados</strong><br>
<img src="docs/screenshots/pt/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>Workshop de Ideação — Brainstorming com IA</strong><br>
<img src="docs/screenshots/pt/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>Controle de Missão — Monitoramento de execução em tempo real</strong><br>
<img src="docs/screenshots/pt/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>Monitoramento — Saúde do sistema e métricas</strong><br>
<img src="docs/screenshots/pt/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## Início Rápido

### Opção 1: Docker (Recomendado)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### Opção 2: Docker Compose (Manual)

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### Opção 3: Desenvolvimento local

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### Verificar instalação

```bash
curl http://localhost:8090/api/health
```

## Contribuir

Contribuições são bem-vindas! Consulte [CONTRIBUTING.md](CONTRIBUTING.md) para as diretrizes.

## Licença

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**Construído com amor por [Macaron Software](https://github.com/macaron-software)**

[Reportar bug](https://github.com/macaron-software/software-factory/issues) · [Solicitar recurso](https://github.com/macaron-software/software-factory/issues)

</div>
