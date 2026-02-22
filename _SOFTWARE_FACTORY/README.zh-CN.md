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

# Macaron 软件工厂

**多智能体软件工厂 — 自主 AI 智能体编排完整产品生命周期**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

[功能特性](#功能特性) · [快速开始](#快速开始) · [截图](#截图) · [架构](#架构) · [贡献](#贡献)

</div>

---

## 这是什么？

Macaron 是一个**自主多智能体平台**，编排整个软件开发生命周期——从构思到部署——使用协同工作的专业 AI 智能体。

将其想象为一个**虚拟软件工厂**，94 个 AI 智能体通过结构化工作流协作，遵循 SAFe 方法论、TDD 实践和自动化质量门。

### 核心亮点

- **94 个专业智能体** — 架构师、开发人员、测试人员、SRE、安全分析师、产品负责人
- **12 种编排模式** — 单独、并行、层级、网络、对抗对、人在回路
- **SAFe 对齐的生命周期** — Portfolio → Epic → Feature → Story，PI 节奏
- **自我修复** — 自主事件检测、分评和修复
- **安全优先** — 注入防护、RBAC、密钥清洗、连接池
- **DORA 指标** — 部署频率、前置时间、MTTR、变更失败率

## 截图

<table>
<tr>
<td width="50%">
<strong>投资组合 — 战略委员会与治理</strong><br>
<img src="docs/screenshots/zh/portfolio.png" alt="Portfolio" width="100%">
</td>
<td width="50%">
<strong>PI 板 — 程序增量规划</strong><br>
<img src="docs/screenshots/zh/pi_board.png" alt="PI Board" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>智能体 — 94 个专业 AI 智能体</strong><br>
<img src="docs/screenshots/zh/agents.png" alt="Agents" width="100%">
</td>
<td width="50%">
<strong>构思工作坊 — AI 驱动的头脑风暴</strong><br>
<img src="docs/screenshots/zh/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>任务控制 — 实时执行监控</strong><br>
<img src="docs/screenshots/zh/mission_control.png" alt="Mission Control" width="100%">
</td>
<td width="50%">
<strong>监控 — 系统健康与指标</strong><br>
<img src="docs/screenshots/zh/monitoring.png" alt="Monitoring" width="100%">
</td>
</tr>
</table>

## 快速开始

### 方式 1：Docker（推荐）

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

make setup
# Edit .env with your LLM API key

make run
```

Open **http://localhost:8090**

### 方式 2：Docker Compose（手动）

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

cp .env.example .env
# Edit .env with your LLM API key

docker compose up -d
```

### 方式 3：本地开发

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory

python3 -m venv .venv
source .venv/bin/activate
pip install -r platform/requirements.txt

export OPENAI_API_KEY=sk-...

make dev
```

### 验证安装

```bash
curl http://localhost:8090/api/health
```

## 贡献

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解指南。

## 许可证

**GNU Affero General Public License v3.0** — [LICENSE](LICENSE)

---

<div align="center">

**用爱构建 by [Macaron Software](https://github.com/macaron-software)**

[报告错误](https://github.com/macaron-software/software-factory/issues) · [功能请求](https://github.com/macaron-software/software-factory/issues)

</div>
