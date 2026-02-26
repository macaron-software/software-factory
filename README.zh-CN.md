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

**多智能体软件工厂 — 自主 AI 智能体编排完整产品生命周期**

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-green.svg)](https://fastapi.tiangolo.com/)

**[在线演示: sf.macaron-software.com](https://sf.macaron-software.com)** — 点击 "Skip (Demo)" 即可探索

[功能特性](#功能特性) · [快速开始](#快速开始) · [截图预览](#截图预览) · [架构设计](#架构设计) · [参与贡献](#参与贡献)

</div>

---

## 这是什么？

Software Factory 是一个**自主多智能体平台**，它编排整个软件开发生命周期 — 从构思到部署 — 使用专业化 AI 智能体协同工作。

可以将其视为一个**虚拟软件工厂**，其中 161 个 AI 智能体通过结构化工作流进行协作，遵循 SAFe 方法论、TDD 实践和自动化质量门控。

### 核心亮点

- **161 个专业智能体** — 架构师、开发者、测试工程师、SRE、安全分析师、产品负责人
- **10 种编排模式** — 单智能体、顺序、并行、层级、网络、循环、路由、聚合、波次、人机协作
- **SAFe 对齐生命周期** — Portfolio → Epic → Feature → Story，PI 节奏驱动
- **自动修复** — 自主事件检测、分类和自修复
- **LLM 弹性** — 多提供商回退、抖动重试、速率限制感知、环境驱动模型配置
- **OpenTelemetry 可观测性** — Jaeger 分布式追踪、流水线分析仪表盘
- **持续看门狗** — 自动恢复暂停运行、过期会话恢复、失败清理
- **安全优先** — 提示注入防护、RBAC、密钥清洗、连接池
- **DORA 指标** — 部署频率、前置时间、MTTR、变更失败率

## 截图预览

<table>
<tr>
<td width="50%">
<strong>仪表盘 — 自适应 SAFe 视角</strong><br>
<img src="docs/screenshots/en/dashboard.png" alt="Dashboard" width="100%">
</td>
<td width="50%">
<strong>Portfolio — 战略待办与 WSJF</strong><br>
<img src="docs/screenshots/en/portfolio.png" alt="Portfolio Dashboard" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>PI 看板 — 项目增量规划</strong><br>
<img src="docs/screenshots/en/pi_board.png" alt="PI Board" width="100%">
</td>
<td width="50%">
<strong>创意工坊 — AI 驱动的头脑风暴</strong><br>
<img src="docs/screenshots/en/ideation.png" alt="Ideation" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>ART — 敏捷发布列车与智能体团队</strong><br>
<img src="docs/screenshots/en/agents.png" alt="Agent Teams" width="100%">
</td>
<td width="50%">
<strong>仪式 — 工作流模板与模式</strong><br>
<img src="docs/screenshots/en/ceremonies.png" alt="Ceremonies" width="100%">
</td>
</tr>
<tr>
<td width="50%">
<strong>监控 — DORA 指标与系统健康</strong><br>
<img src="docs/screenshots/en/monitoring.png" alt="Monitoring" width="100%">
</td>
<td width="50%">
<strong>新手引导 — SAFe 角色选择向导</strong><br>
<img src="docs/screenshots/en/onboarding.png" alt="Onboarding" width="100%">
</td>
</tr>
</table>

## 快速开始

### 方式一：Docker（推荐）

Docker 镜像包含：**Node.js 20**、**Playwright + Chromium**、**bandit**、**semgrep**、**ripgrep**。

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup   # copies .env.example → .env (edit it to add your LLM API key)
make run     # builds & starts the platform
```

打开 http://localhost:8090 — 点击 **"Skip (Demo)"** 即可无需 API 密钥进行探索。

### 方式二：本地安装

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
cp .env.example .env                # create your config (edit to add LLM key — see Step 3)
python3 -m venv .venv && source .venv/bin/activate
pip install -r platform/requirements.txt

# Start platform
make dev
# or manually: PYTHONPATH=$(pwd) python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8090 --ws none
```

打开 http://localhost:8090 — 首次启动时将看到**新手引导向导**。
选择您的 SAFe 角色或点击 **"Skip (Demo)"** 立即开始探索。

### 步骤三：配置 LLM 提供商

如果没有 API 密钥，平台将以**演示模式**运行 — 智能体以模拟答案进行响应。
这对于探索 UI 很有用，但智能体不会生成真正的代码或分析结果。

要启用真正的 AI 智能体，请编辑 `.env` 并添加**一个** API 密钥：

```bash
# Option A: MiniMax (recommended for getting started)
PLATFORM_LLM_PROVIDER=minimax
MINIMAX_API_KEY=sk-your-key-here

# Option B: Azure OpenAI
PLATFORM_LLM_PROVIDER=azure-openai
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com

# Option C: NVIDIA NIM
PLATFORM_LLM_PROVIDER=nvidia
NVIDIA_API_KEY=nvapi-your-key-here
```

然后重启：`make run`（Docker）或 `make dev`（本地）

| Provider | Env Variable | Models |
|----------|-------------|--------|
| **MiniMax** | `MINIMAX_API_KEY` | MiniMax-M2.5 |
| **Azure OpenAI** | `AZURE_OPENAI_API_KEY` + `AZURE_OPENAI_ENDPOINT` | GPT-5-mini |
| **Azure AI Foundry** | `AZURE_AI_API_KEY` + `AZURE_AI_ENDPOINT` | GPT-5.2 |
| **NVIDIA NIM** | `NVIDIA_API_KEY` | Kimi K2 |

平台会自动回退到其他已配置的提供商（当主提供商失败时）。
您也可以在仪表盘的**设置**页面（`/settings`）中配置提供商。

## 入门指南 — 您的第一个项目

安装完成后，以下是从创意到可用项目的流程：

### 路径 A：从创意开始（创意工坊）

1. **打开创意页面** — 前往 `/ideation`（或点击侧边栏中的 "Ideation"）
2. **描述您的创意** — 例如 *"具有实时匹配功能的企业拼车应用"*
3. **观察智能体讨论** — 5 个专业智能体（产品经理、业务分析师、架构师、UX 设计师、安全专家）通过 SSE 流式传输实时分析您的创意
4. **从结果创建项目** — 点击 **"Create an Epic from this idea"**。平台将：
   - 创建一个新**项目**，包含生成的 `VISION.md` 和 CI/CD 脚手架
   - 创建一个**史诗**，由 PO 智能体分解为功能特性和用户故事
   - 自动配置 **TMA**（运维）、**安全** 和 **技术债务** 任务

现在您已拥有一个完整的 SAFe 待办事项列表，可以开始执行了。

### 路径 B：手动创建项目

1. 前往 `/projects` 并点击 **"New Project"**
2. 填写：名称、描述、技术栈、仓库路径
3. 平台自动创建：
   - 分配到项目的**产品经理智能体**
   - **TMA 任务**（持续运维 — 监控健康状态、创建事件）
   - **安全任务**（每周安全审计 — SAST、依赖检查）
   - **技术债务任务**（每月债务消减 — 规划中）

### 接下来：创建史诗和功能特性

- 从 **Portfolio** 页面（`/portfolio`），创建带有 WSJF 优先级的史诗
- 从史诗中添加**功能特性**，并将其分解为**用户故事**
- 使用 **PI 看板**（`/pi-board`）规划项目增量，将功能特性分配到冲刺中

### 运行任务

- 点击任意任务上的 **"Start"** 启动智能体执行
- 选择**编排模式**（层级、网络、并行...）
- 在**任务控制中心**实时观察智能体工作
- 智能体自主使用工具（code_read、git、build、test、安全扫描）

### TMA 与安全 — 始终在线

这些功能为每个项目**自动启用** — 无需配置：

| Mission | Type | Schedule | What it does |
|---------|------|----------|-------------|
| **TMA** | Program | Continuous | 健康监控、事件检测、自动修复、工单创建 |
| **Security** | Review | Weekly | SAST 扫描（bandit/semgrep）、依赖审计、密钥检测 |
| **Tech Debt** | Reduction | Monthly | 代码质量分析、重构建议 |
| **Self-Healing** | Program | Continuous | 自动检测 5xx/崩溃 → TMA 任务 → 智能体诊断 → 代码修复 → 验证 |

四个任务随项目一起创建。TMA、安全和自修复以**活跃**状态启动，技术债务以**规划**状态启动（准备好时激活）。

## 功能特性

### 161 个专业 AI 智能体

智能体按团队组织，镜像真实软件组织结构：

| Team | Agents | Role |
|------|--------|------|
| **Product** | Product Manager, Business Analyst, PO | SAFe 规划、WSJF 优先级排序 |
| **Architecture** | Solution Architect, Tech Lead, System Architect | 架构决策、设计模式 |
| **Development** | Backend/Frontend/Mobile/Data Engineers | 按技术栈 TDD 实现 |
| **Quality** | QA Engineers, Security Analysts, Test Automation | 测试、安全审计、渗透测试 |
| **Design** | UX Designer, UI Designer | 用户体验、视觉设计 |
| **DevOps** | DevOps Engineer, SRE, Platform Engineer | CI/CD、监控、基础设施 |
| **Management** | Scrum Master, RTE, Agile Coach | 仪式、促进、障碍移除 |

### 10 种编排模式

- **Solo** — 单智能体执行简单任务
- **Sequential** — 智能体按顺序依次执行的流水线
- **Parallel** — 多个智能体同时工作
- **Hierarchical** — 管理者向子智能体委派任务
- **Network** — 智能体点对点协作
- **Loop** — 智能体迭代执行直到满足条件
- **Router** — 单智能体根据输入路由到专家
- **Aggregator** — 多个输入由单个聚合器合并
- **Wave** — 波次内并行，波次间顺序执行
- **Human-in-the-loop** — 智能体提议，人类验证

### SAFe 对齐生命周期

完整的 Portfolio → Epic → Feature → Story 层级体系，包含：

- **战略 Portfolio** — 投资组合画布、战略主题、价值流
- **项目增量** — PI 规划、目标、依赖关系
- **团队待办** — 用户故事、任务、验收标准
- **冲刺执行** — 每日站会、冲刺评审、回顾

### 安全与合规

- **身份认证** — 基于 JWT 的认证，支持 RBAC
- **提示注入防护** — 检测并阻止恶意提示
- **密钥清洗** — 自动脱敏处理敏感数据
- **CSP（内容安全策略）** — 加固的响应头
- **速率限制** — 按用户的 API 配额
- **审计日志** — 全面的活动日志记录

### DORA 指标与监控

- **部署频率** — 代码到达生产环境的频率
- **前置时间** — 从提交到部署的时间
- **MTTR** — 事件恢复的平均时间
- **变更失败率** — 失败部署的百分比
- **实时仪表盘** — Chart.js 可视化
- **Prometheus 指标** — /metrics 端点

### 质量指标 — 工业化监控

确定性质量扫描（无需 LLM），涵盖 10 个维度，如同生产流水线：

| Dimension | Tools | What it measures |
|-----------|-------|-----------------|
| **Complexity** | radon, lizard | 圈复杂度、认知复杂度 |
| **Unit Test Coverage** | coverage.py, nyc | 行/分支覆盖率百分比 |
| **E2E Test Coverage** | Playwright | 测试文件数量、规格覆盖 |
| **Security** | bandit, semgrep | 按严重级别的 SAST 发现（严重/高/中/低） |
| **Accessibility** | pa11y | WCAG 2.1 AA 违规 |
| **Performance** | Lighthouse | Core Web Vitals 评分 |
| **Documentation** | interrogate | README、变更日志、API 文档、文档字符串覆盖 |
| **Architecture** | madge, jscpd, mypy | 循环依赖、代码重复、类型错误 |
| **Maintainability** | custom | 文件大小分布、大文件比例 |
| **Adversarial** | built-in | 事件率、对抗性拒绝率 |

**工作流阶段的质量门控** — 每个工作流阶段显示质量徽章（PASS/FAIL/PENDING），基于按门控类型配置的维度阈值：

| Gate Type | Threshold | Used in |
|-----------|-----------|---------|
| `always` | 0% | 分析、规划阶段 |
| `no_veto` | 50% | 实现、冲刺阶段 |
| `all_approved` | 70% | 评审、发布阶段 |
| `quality_gate` | 80% | 部署、生产阶段 |

**质量仪表盘**位于 `/quality` — 全局记分卡、项目分数、趋势快照。
质量徽章显示在任务详情、项目看板、工作流阶段和主仪表盘上。

### 持续改进工作流

三个用于自我改进的内置工作流：

| Workflow | Purpose | Agents |
|----------|---------|--------|
| **quality-improvement** | 扫描指标 → 识别最差维度 → 规划并执行改进 | QA Lead, Dev, Architect |
| **retrospective-quality** | 冲刺结束回顾：收集 ROTI、事件、质量数据 → 行动项 | Scrum Master, QA, Dev |
| **skill-evolution** | 分析智能体表现 → 更新系统提示 → 进化技能 | Brain, Lead Dev, QA |

这些工作流创建了一个**反馈循环**：指标 → 分析 → 改进 → 重新扫描 → 跟踪进度。

### 内置智能体工具

Docker 镜像包含智能体自主工作所需的一切：

| Category | Tools | Description |
|----------|-------|-------------|
| **Code** | `code_read`, `code_write`, `code_edit`, `code_search`, `list_files` | 读取、写入和搜索项目文件 |
| **Build** | `build`, `test`, `local_ci` | 运行构建、测试和本地 CI 流水线（自动检测 npm/pip/cargo） |
| **Git** | `git_commit`, `git_diff`, `git_log`, `git_status` | 版本控制，智能体分支隔离 |
| **Security** | `sast_scan`, `dependency_audit`, `secrets_scan` | 通过 bandit/semgrep 进行 SAST、CVE 审计、密钥检测 |
| **QA** | `playwright_test`, `browser_screenshot`, `screenshot` | Playwright 端到端测试和截图（包含 Chromium） |
| **Tickets** | `create_ticket`, `jira_search`, `jira_create` | 为 TMA 跟踪创建事件/工单 |
| **Deploy** | `docker_deploy`, `docker_status`, `github_actions` | 容器部署和 CI/CD 状态 |
| **Memory** | `memory_store`, `memory_search`, `deep_search` | 跨会话的持久化项目记忆 |

### 自动修复与自修复（TMA）

自主事件检测、分类和自修复循环：

- **心跳监控** — 对所有运行中的任务和服务进行持续健康检查
- **事件自动检测** — HTTP 5xx、超时、智能体崩溃 → 自动创建事件
- **分类与归类** — 严重级别（P0-P3）、影响分析、根因假设
- **自修复** — 智能体自主诊断并修复问题（代码补丁、配置变更、重启）
- **工单创建** — 未解决的事件自动创建跟踪工单供人工审查
- **升级** — P0/P1 事件触发 Slack/邮件通知给值班团队
- **回顾循环** — 事后复盘经验存储在记忆中，注入到后续冲刺

### SAFe 视角与新手引导

基于角色的自适应 UI，镜像真实 SAFe 组织：

- **9 个 SAFe 视角** — Portfolio 经理、RTE、产品负责人、Scrum Master、开发者、架构师、QA/安全、业务负责人、管理员
- **自适应仪表盘** — KPI、快捷操作和侧边栏链接随所选角色变化
- **新手引导向导** — 3 步首次用户流程（选择角色 → 选择项目 → 开始）
- **视角选择器** — 随时从顶部下拉菜单切换 SAFe 角色
- **动态侧边栏** — 仅显示与当前视角相关的导航

### 4 层记忆与 RLM 深度搜索

跨会话的持久化知识与智能检索：

- **会话记忆** — 单次会话内的对话上下文
- **模式记忆** — 编排模式执行中的经验学习
- **项目记忆** — 项目级知识（决策、约定、架构）
- **全局记忆** — 跨项目的组织级知识（FTS5 全文搜索）
- **自动加载项目文件** — CLAUDE.md、SPECS.md、VISION.md、README.md 注入到每次 LLM 提示中（最大 8K）
- **RLM 深度搜索** — 递归语言模型（arXiv:2512.24601）— 迭代 WRITE-EXECUTE-OBSERVE-DECIDE 循环，最多 10 次探索迭代

### 智能体交易市场（Mercato）

基于代币的智能体市场，用于团队组成：

- **智能体列表** — 列出待转让的智能体及要价
- **自由智能体池** — 未分配的可选秀智能体
- **转会与租借** — 在项目之间买入、卖出或租借智能体
- **市场估值** — 基于技能、经验和表现的自动智能体估值
- **钱包系统** — 每个项目的代币钱包及交易历史
- **选秀系统** — 为您的项目认领自由智能体

### 对抗性质量守卫

双层质量门控，阻止虚假/占位代码通过：

- **L0 确定性** — 即时检测虚假内容（lorem ipsum、TBD）、模拟代码（NotImplementedError、TODO）、假构建、幻觉、技术栈不匹配
- **L1 LLM 语义** — 独立 LLM 审查执行模式的输出质量
- **评分** — 分数 < 5 通过，5-6 软通过并带警告，7+ 拒绝
- **强制拒绝** — 幻觉、虚假内容、技术栈不匹配、假构建始终被拒绝，不论分数

### 自动文档与 Wiki

整个生命周期中的自动文档生成：

- **冲刺回顾** — LLM 生成的回顾笔记存储在数据库和记忆中，注入到下一个冲刺提示中（学习循环）
- **阶段摘要** — 每个任务阶段产生 LLM 生成的决策和结果摘要
- **架构决策记录** — 架构模式自动将设计决策记录在项目记忆中
- **项目上下文文件** — 自动加载的指令文件（CLAUDE.md、SPECS.md、CONVENTIONS.md）作为活文档
- **Confluence 同步** — 与 Confluence wiki 页面的双向同步，用于企业文档管理
- **Swagger 自动文档** — 94 个 REST 端点在 `/docs` 自动生成 OpenAPI 规范文档

## 四种接口

### 1. Web 仪表盘（HTMX + SSE）

主 UI 地址 http://localhost:8090：

- **实时多智能体对话**，SSE 流式传输
- **PI 看板** — 项目增量规划
- **任务控制中心** — 执行监控
- **智能体管理** — 查看、配置、监控智能体
- **事件仪表盘** — 自动修复分类
- **移动端响应** — 支持平板和手机

### 2. CLI (`sf`)

功能齐全的命令行界面：

```bash
# Install (add to PATH)
ln -s $(pwd)/cli/sf.py ~/.local/bin/sf

# Browse
sf status                              # Platform health
sf projects list                       # All projects
sf missions list                       # Missions with WSJF scores
sf agents list                         # 145 agents
sf features list <epic_id>             # Epic features
sf stories list --feature <id>         # User stories

# Work
sf ideation "e-commerce app in React"  # Multi-agent ideation (streamed)
sf missions start <id>                 # Start mission run
sf metrics dora                        # DORA metrics

# Monitor
sf incidents list                      # Incidents
sf llm stats                           # LLM usage (tokens, cost)
sf chaos status                        # Chaos engineering
```

**22 个命令组** · 双模式：API（在线服务器）或 DB（离线） · JSON 输出（`--json`） · 加载动画 · Markdown 表格渲染

### 3. REST API + Swagger

94 个 API 端点在 `/docs`（Swagger UI）自动文档化：

```bash
# Examples
curl http://localhost:8090/api/projects
curl http://localhost:8090/api/agents
curl http://localhost:8090/api/missions
curl -X POST http://localhost:8090/api/ideation \
  -H "Content-Type: application/json" \
  -d '{"prompt": "bike GPS tracker app"}'
```

Swagger UI: http://localhost:8090/docs

### 4. MCP 服务器（Model Context Protocol）

24 个 MCP 工具用于 AI 智能体集成（端口 9501）：

```bash
# Start MCP server
python3 -m platform.mcp_platform.server

# Tools available:
# platform_agents, platform_projects, platform_missions,
# platform_features, platform_sprints, platform_stories,
# platform_incidents, platform_llm, platform_search, ...
```

## 架构设计

### 平台概览

```
                        ┌──────────────────────┐
                        │   CLI (sf) / Web UI  │
                        │   REST API :8090     │
                        └──────────┬───────────┘
                                   │
                    ┌──────────────┴──────────────┐
                    │     FastAPI Server           │
                    │  Auth (JWT + RBAC + OAuth)   │
                    │  17 route modules            │
                    └──┬──────────┬────────────┬───┘
                       │          │            │
          ┌────────────┴┐   ┌────┴─────┐   ┌──┴───────────┐
          │ Agent Engine │   │ Workflow │   │   Mission    │
          │ 161 agents   │   │  Engine  │   │    Layer     │
          │ executor     │   │ 39 defs  │   │ SAFe cycle   │
          │ loop+retry   │   │ 10 ptrns │   │ Portfolio    │
          └──────┬───────┘   │ phases   │   │ Epic/Feature │
                 │           │ retry    │   │ Story/Sprint │
                 │           │ skip     │   └──────────────┘
                 │           │ ckpoint  │
                 │           └────┬─────┘
                 │                │
     ┌───────────┴────────────────┴───────────────┐
     │              Services                       │
     │  LLM Client (multi-provider fallback)       │
     │  Tools (code, git, deploy, memory, security)│
     │  MCP Bridge (fetch, memory, playwright)     │
     │  Quality Engine (10 dimensions)             │
     │  Notifications (Slack, Email, Webhook)      │
     └───────────────────┬─────────────────────────┘
                         │
     ┌───────────────────┴─────────────────────────┐
     │              Operations                      │
     │  Watchdog (auto-resume, stall detection)     │
     │  Auto-Heal (incident > triage > fix)         │
     │  OpenTelemetry (tracing + metrics > Jaeger)  │
     └───────────────────┬─────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │   SQLite + Memory   │
              │   4-layer memory    │
              │   FTS5 search       │
              └─────────────────────┘
```

### 流水线流程

```
Mission Created
     │
     ▼
┌─────────────┐     ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Select     │────▶│sequential│    │ parallel │    │hierarchic│
│  Pattern    │────▶│          │    │          │    │          │
└─────────────┘────▶│ adversar.│    │          │    │          │
                    └────┬─────┘    └────┬─────┘    └────┬─────┘
                         └───────────────┴───────────────┘
                                         │
                    ┌────────────────────────────────────────┐
                    │         Phase Execution                 │
                    │                                        │
                    │  Agent ──▶ LLM Call ──▶ Result         │
                    │                          │             │
                    │              ┌───success──┴──failure──┐│
                    │              ▼                        ▼│
                    │         Code phase?            Retries? │
                    │           │ yes                  │ yes │
                    │           ▼                      ▼     │
                    │     Sandbox Build         Retry w/     │
                    │     Validation            backoff      │
                    │           │                      │ no  │
                    │           ▼                      ▼     │
                    │     Quality Gate          skip_on_fail?│
                    │      │        │            │yes  │no   │
                    │    pass     fail            │     │     │
                    │      │        │             │     ▼     │
                    │      ▼        ▼             │   PAUSED  │
                    │  Checkpoint  PAUSED ◀───────┘     │     │
                    └──────┬─────────────────────────────┘    │
                           │                                  │
                    More phases? ──yes──▶ next phase          │
                           │ no                               │
                           ▼                    watchdog      │
                    Mission Completed     auto-resume ◀───────┘
```

### 可观测性

```
┌──────────────────────┐    ┌────────────────────────────────┐
│   OTEL Middleware     │    │     Continuous Watchdog         │
│   (every request)     │    │                                │
│   spans + metrics     │    │  health check    every 60s     │
│         │             │    │  stall detection  phases>60min │
│         ▼             │    │  auto-resume     5/batch 5min  │
│   OTLP/HTTP export    │    │  session recovery  >30min      │
│         │             │    │  failed cleanup   zombies      │
│         ▼             │    └────────────────────────────────┘
│   Jaeger :16686       │
└──────────────────────┘    ┌────────────────────────────────┐
                            │     Failure Analysis            │
┌──────────────────────┐    │                                │
│   Quality Engine      │    │  error classification          │
│   10 dimensions       │    │  phase heatmap                 │
│   quality gates       │    │  recommendations               │
│   radar chart         │    │  resume-all button             │
│   badge + scorecard   │    └────────────────────────────────┘
└──────────────────────┘
                            ┌────────────────────────────────┐
         All data ─────────▶│  Dashboard /analytics           │
                            │  tracing stats + latency chart  │
                            │  error doughnut + phase bars    │
                            │  quality radar + scorecard      │
                            └────────────────────────────────┘
```

### 部署架构

```
                          Internet
                     ┌───────┴────────┐
                     │                │
          ┌──────────▼─────┐  ┌───────▼────────┐
          │ Azure VM (Prod)│  │ OVH VPS (Demo) │
          │ sf.macaron-software.com   │  │ demo.macaron-software.com  │
          │                │  │                │
          │ Nginx :443     │  │ Nginx :443     │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Platform :8090 │  │ Platform :8090 │
          │ GPT-5-mini     │  │ MiniMax-M2.5   │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ Jaeger :16686  │  │ Jaeger :16686  │
          │   │            │  │   │            │
          │   ▼            │  │   ▼            │
          │ SQLite DB      │  │ SQLite DB      │
          │ /patches (ro)  │  │                │
          └────────────────┘  └────────────────┘
                     │                │
                     └───────┬────────┘
                             │
                    ┌────────▼────────┐
                    │ GitHub          │
                    │ macaron-software│
                    │ /software-factory│
                    └─────────────────┘
```

## 项目配置

项目定义在 `projects/*.yaml` 中：

```yaml
project:
  name: my-project
  root_path: /path/to/project
  vision_doc: CLAUDE.md

agents:
  - product_manager
  - solution_architect
  - backend_dev
  - qa_engineer

patterns:
  ideation: hierarchical
  development: parallel
  review: adversarial-pair

deployment:
  strategy: blue-green
  auto_prod: true
  health_check_url: /health

monitoring:
  prometheus: true
  grafana_dashboard: project-metrics
```

## 目录结构

```
├── platform/                # Agent Platform (152 Python files)
│   ├── server.py            # FastAPI app, port 8090
│   ├── agents/              # Agent loop, executor, store
│   ├── a2a/                 # Agent-to-agent messaging bus
│   ├── patterns/            # 10 orchestration patterns
│   ├── missions/            # SAFe mission lifecycle
│   ├── sessions/            # Conversation runner + SSE
│   ├── web/                 # Routes + Jinja2 templates
│   ├── mcp_platform/        # MCP server (23 tools)
│   └── tools/               # Agent tools (code, git, deploy)
│
├── cli/                     # CLI 'sf' (6 files, 2100+ LOC)
│   ├── sf.py                # 22 command groups, 40+ subcommands
│   ├── _api.py              # httpx REST client
│   ├── _db.py               # sqlite3 offline backend
│   ├── _output.py           # ANSI tables, markdown rendering
│   └── _stream.py           # SSE streaming with spinner
│
├── dashboard/               # Frontend HTMX
├── deploy/                  # Helm charts, Docker, K8s
├── tests/                   # E2E Playwright tests
├── skills/                  # Agent skills library
├── projects/                # Project YAML configurations
└── data/                    # SQLite database
```

## 测试

```bash
# Run all tests
make test

# E2E tests (Playwright — requires install first)
cd platform/tests/e2e
npm install
npx playwright install --with-deps chromium
npm test

# Unit tests
pytest tests/

# Chaos engineering
python3 tests/test_chaos.py

# Endurance tests
python3 tests/test_endurance.py
```

## 部署

### Docker

Docker 镜像包含：**Node.js 20**、**Playwright + Chromium**、**bandit**、**semgrep**、**ripgrep**。
智能体可以开箱即用地构建项目、运行端到端测试并截图、执行 SAST 安全扫描。

```bash
docker-compose up -d
```

### Kubernetes (Helm)

```bash
helm install software-factory ./deploy/helm/
```

### 环境变量

完整列表请参见 [`.env.example`](.env.example)。关键变量：

```bash
# LLM Provider (required for real agents)
PLATFORM_LLM_PROVIDER=minimax        # minimax | azure-openai | azure-ai | nvidia | demo
MINIMAX_API_KEY=sk-...               # MiniMax API key

# Authentication (optional)
GITHUB_CLIENT_ID=...                 # GitHub OAuth
GITHUB_CLIENT_SECRET=...
AZURE_AD_CLIENT_ID=...               # Azure AD OAuth
AZURE_AD_CLIENT_SECRET=...
AZURE_AD_TENANT_ID=...

# Integrations (optional)
JIRA_URL=https://your-jira.atlassian.net
ATLASSIAN_TOKEN=your-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
```

## v2.1.0 新特性（2026 年 2 月）

### 质量指标 — 工业化监控
- **10 个确定性维度** — 复杂度、覆盖率（UT/E2E）、安全、可访问性、性能、文档、架构、可维护性、对抗性
- **工作流阶段质量门控** — 按阶段的 PASS/FAIL 徽章，可配置阈值（always/no_veto/all_approved/quality_gate）
- **质量仪表盘**位于 `/quality` — 全局记分卡、项目分数、趋势快照
- **质量徽章无处不在** — 任务详情、项目看板、工作流阶段、主仪表盘
- **无需 LLM** — 所有指标使用开源工具确定性计算（radon、bandit、semgrep、coverage.py、pa11y、madge）

### 每个项目自动配置 4 个任务
每个项目自动获得 4 个运维任务：
- **MCO/TMA** — 持续运维：健康监控、事件分类（P0-P4）、TDD 修复、非回归验证
- **Security** — 每周 SAST 扫描、依赖审计、CVE 监控、代码审查
- **Tech Debt** — 每月债务消减：复杂度审计、WSJF 优先级排序、重构冲刺
- **Self-Healing** — 自主事件流水线：5xx 检测 → TMA 任务创建 → 智能体诊断 → 代码修复 → 验证

### 持续改进
- **quality-improvement 工作流** — 扫描 → 识别最差维度 → 规划并执行改进
- **retrospective-quality 工作流** — 冲刺回顾，包含 ROTI、事件、质量指标 → 行动项
- **skill-evolution 工作流** — 分析智能体表现 → 更新提示 → 进化技能
- **反馈循环** — 指标 → 分析 → 改进 → 重新扫描 → 跟踪进度

### SAFe 视角与新手引导
- **9 个 SAFe 角色视角** — 自适应仪表盘、侧边栏和每角色 KPI
- **新手引导向导** — 3 步首次用户流程，含角色和项目选择
- **视角选择器** — 随时从顶栏切换 SAFe 角色

### 自动修复与自修复
- **TMA 心跳** — 持续健康监控，自动创建事件
- **自修复智能体** — 自主诊断和修复常见故障
- **工单升级** — 未解决的事件创建跟踪工单并发送通知

### 4 层记忆与 RLM
- **持久化知识** — 会话、模式、项目和全局记忆层，FTS5 支持
- **RLM 深度搜索** — 递归探索循环（最多 10 次迭代），用于复杂代码库分析
- **自动加载项目上下文** — CLAUDE.md、SPECS.md、VISION.md 注入到每个智能体提示中

### 对抗性质量守卫
- **L0 确定性** — 即时检测虚假内容、模拟代码、假构建、幻觉
- **L1 语义** — 基于 LLM 的执行输出质量审查
- **强制拒绝** — 幻觉和技术栈不匹配始终被阻止

### 智能体交易市场
- **基于代币的市场**，含智能体列表、转会、租借和自由智能体选秀
- **市场估值** — 基于技能和表现的自动智能体定价
- **钱包系统** — 每个项目的代币经济和交易历史

### 身份认证与安全
- **基于 JWT 的认证**，支持登录/注册/刷新/注销
- **RBAC** — admin、project_manager、developer、viewer 角色
- **OAuth** — GitHub 和 Azure AD SSO 登录
- **管理面板** — 用户管理 UI（`/admin/users`）
- **演示模式** — 一键 "Skip" 按钮即时访问

### 自动文档
- **冲刺回顾** — LLM 生成的回顾笔记，带学习循环
- **阶段摘要** — 自动记录任务阶段结果
- **Confluence 同步** — 双向 Wiki 集成

### LLM 提供商
- **多提供商**支持自动回退链
- MiniMax M2.5、Azure OpenAI GPT-5-mini、Azure AI Foundry、NVIDIA NIM
- **演示模式**，无需 API 密钥即可探索 UI

### 平台改进
- DORA 指标仪表盘，含 LLM 成本追踪
- Jira 双向同步
- Playwright 端到端测试套件（11 个规格文件）
- 国际化（EN/FR）
- 实时通知（Slack、Email、Webhook）
- 工作流中的设计系统流水线（UX → 开发 → 评审）
- 3D 智能体世界可视化

### Darwin — 进化式团队选择
- **Thompson Sampling 选择** — 基于 `Beta(wins+1, losses+1)` 的概率性 agent+pattern 团队选择，维度：`(agent_id, pattern_id, 技术, 阶段类型)`
- **细粒度适应度追踪** — 每个上下文独立评分：擅长 Angular 迁移的团队未必擅长 Angular 新功能开发
- **相似度回退** — 冷启动通过技术前缀匹配处理（`angular_19` → `angular_*` → `generic`）
- **软退休机制** — 表现持续较差的团队获得 `weight_multiplier=0.1`，降优先级但可恢复
- **OKR / KPI 系统** — 按领域和阶段类型设置目标与指标；8 个默认种子
- **A/B 影子测试** — 当两个团队适应度分数接近（delta < 10）或 10% 概率时，自动触发并行影子运行
- **Teams 仪表板** `/teams` — 排行榜含 champion/rising/declining/retired 徽章、内联 OKR 编辑、Chart.js 进化曲线、选择历史、A/B 测试结果
- **非破坏性可选** — 在 pattern 中使用 `agent_id: "skill:developer"` 即可启用 Darwin；显式 ID 不受影响

## v2.2.0 新特性（2026 年 2 月）

### OpenTelemetry 与分布式追踪
- **OTEL 集成** — OpenTelemetry SDK，OTLP/HTTP 导出到 Jaeger
- **ASGI 追踪中间件** — 每个 HTTP 请求都带有 span、延迟、状态追踪
- **追踪仪表盘**位于 `/analytics` — 请求统计、延迟图表、操作表
- **Jaeger UI** — 在端口 16686 进行完整的分布式追踪探索

### 流水线故障分析
- **故障分类** — 基于 Python 的错误分类（setup_failed、llm_provider、timeout、phase_error 等）
- **阶段故障热力图** — 识别哪些流水线阶段最常失败
- **建议引擎** — 基于故障模式的可操作建议
- **全部恢复按钮** — 一键从仪表盘批量恢复暂停的运行

### 持续看门狗
- **自动恢复** — 自动批量恢复暂停的运行（每批 5 个，每 5 分钟，最多 10 个并发）
- **过期会话恢复** — 检测不活跃 > 30 分钟的会话，标记为中断以便重试
- **失败会话清理** — 清理阻塞流水线进度的僵尸会话
- **卡顿检测** — 在某阶段停留 > 60 分钟的任务自动重试

### 阶段弹性
- **逐阶段重试** — 可配置的重试次数（默认 3 次），每阶段指数退避
- **skip_on_failure** — 阶段可标记为可选，允许流水线继续执行
- **检查点** — 已完成阶段被保存，智能恢复跳过已完成的工作
- **阶段超时** — 10 分钟上限防止无限挂起

### 沙箱构建验证
- **代码后构建检查** — 代码生成阶段后自动运行构建/lint
- **自动检测构建系统** — npm、cargo、go、maven、python、docker
- **错误注入** — 构建失败注入到智能体上下文中以进行自我修正

### 质量 UI 增强
- **雷达图** — Chart.js 雷达可视化质量维度，位于 `/quality`
- **质量徽章** — 项目头部的彩色分数圆圈（`/api/dashboard/quality-badge`）
- **任务记分卡** — 任务详情侧边栏中的质量指标（`/api/dashboard/quality-mission`）

## 参与贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解贡献指南。

## 许可证

本项目基于 AGPL v3 许可证发布 - 详见 [LICENSE](LICENSE) 文件。

## 支持

- 在线演示: https://sf.macaron-software.com
- 问题反馈: https://github.com/macaron-software/software-factory/issues
- 讨论区: https://github.com/macaron-software/software-factory/discussions
