# Software Factory — Architecture 360°

> Plateforme d'agents IA collaboratifs pour projets logiciels.
> Macaron Software · v2026

---

## Vue d'ensemble

```
╔══════════════════════════════════════════════════════════════════════════════════════════════════╗
║                           SOFTWARE FACTORY — VUE 360°                                           ║
║                    Platform Agents Macaron  ·  v2026                                            ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│  HUMAIN / OPERATOR                                                                              │
│  ┌───────────┐  ┌──────────────┐  ┌───────────────────┐  ┌────────────────────┐               │
│  │  Browser  │  │  sf CLI      │  │  REST / SSE API   │  │  Dashboard :8080   │               │
│  │  (web UI) │  │  cli/sf.py   │  │  curl / httpx     │  │  dashboard/server  │               │
│  └─────┬─────┘  └──────┬───────┘  └────────┬──────────┘  └─────────┬──────────┘               │
└────────┼───────────────┼──────────────────┼─────────────────────────┼─────────────────────────┘
         │               │                  │                         │
         └───────────────┴──────────────────┴─────────────────────────┘
                                             │ HTTP / WebSocket / SSE
╔════════════════════════════════════════════╪════════════════════════════════════════════════════╗
║  PLATFORM  :8090 (prod) / :8099 (dev)      │                                                   ║
║  FastAPI  ·  platform/server.py            ▼                                                   ║
║  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   ║
║  │  WEB LAYER  ·  platform/web/routes/                                                     │   ║
║  │  agents · projects · workflows · missions · sessions · memory                           │   ║
║  │  workspaces · patterns · epics · ops · analytics · pages                                │   ║
║  └───────────────────────────────┬─────────────────────────────────────────────────────────┘   ║
║                                  │                                                             ║
║  ┌───────────────────────────────┴────────────────────────────────────────────────────┐        ║
║  │  AGENT RUNTIME                                                                     │        ║
║  │                                                                                    │        ║
║  │  ┌────────────────┐  ┌─────────────────┐  ┌──────────────────┐                   │        ║
║  │  │  AgentLoop     │  │  AgentExecutor  │  │  PromptBuilder   │                   │        ║
║  │  │  loop.py       │  │  executor.py    │  │  prompt_builder  │                   │        ║
║  │  │  RL-Policy     │  │  Tool dispatch  │  │  Skill inject    │                   │        ║
║  │  │  (Q-learning)  │  │  Guardrails     │  │  Memory inject   │                   │        ║
║  │  └────────────────┘  └─────────────────┘  └──────────────────┘                   │        ║
║  │                                                                                    │        ║
║  │  ┌──────────────────────────────────────────────────────────────────────────────┐ │        ║
║  │  │  ORCHESTRATION PATTERNS  ·  platform/patterns/   (15 patterns)              │ │        ║
║  │  │                                                                              │ │        ║
║  │  │  sequential  parallel  network  loop  router  aggregator  wave              │ │        ║
║  │  │  hierarchical  human_in_the_loop  solo                                      │ │        ║
║  │  │                                                                              │ │        ║
║  │  │  → engine.py: RL adapte les patterns mid-mission (Q-learning offline)       │ │        ║
║  │  └──────────────────────────────────────────────────────────────────────────────┘ │        ║
║  │                                                                                    │        ║
║  │  ┌──────────────────────────────────────────────────────────────────────────────┐ │        ║
║  │  │  AGENT-TO-AGENT BUS  ·  platform/a2a/                                       │ │        ║
║  │  │  bus.py · negotiation.py · veto.py · protocol.py · azure_bridge.py          │ │        ║
║  │  └──────────────────────────────────────────────────────────────────────────────┘ │        ║
║  └────────────────────────────────────────────────────────────────────────────────────┘        ║
║                                                                                                 ║
║  ┌────────────────────────────────────────────────────────────────────────────────────┐        ║
║  │  SAFe LIFECYCLE  ·  platform/missions/ · epics/ · agents/org.py                  │        ║
║  │                                                                                    │        ║
║  │  Portfolio → ART → Team → Epic → Feature → Story → Task                          │        ║
║  │                                                                                    │        ║
║  │  ┌─────────────┐  ┌────────────────┐  ┌──────────────────────┐                  │        ║
║  │  │  Product    │  │  PI Planning   │  │  Mission / Epic      │                  │        ║
║  │  │  Backlog    │  │  pi-planning   │  │  store.py            │                  │        ║
║  │  │  (E→F→US)   │  │  .yaml         │  │  WSJF ordering       │                  │        ║
║  │  └─────────────┘  └────────────────┘  └──────────────────────┘                  │        ║
║  │                                                                                    │        ║
║  │  Genetic Evolution: GAEngine → evolve workflow templates (nightly)                │        ║
║  │  RL Policy:         Q-learning on rl_experience → pattern recommendation          │        ║
║  └────────────────────────────────────────────────────────────────────────────────────┘        ║
║                                                                                                 ║
║  ┌────────────────────────────────────────────────────────────────────────────────────┐        ║
║  │  SKILLS  ·  skills/  (40 skills)       WORKFLOWS  ·  workflows/  (44 yamls)       │        ║
║  │                                                                                    │        ║
║  │  code-quality      tdd                 tma-autoheal         pi-planning            │        ║
║  │  security-audit    ux                  error-monitoring-    feature-sprint         │        ║
║  │  devops-pipeline   architecture-review   cycle [NEW]        ideation-to-prod       │        ║
║  │  error-monitoring  [NEW]  + 36 more    cicd-pipeline        monitoring-setup       │        ║
║  └────────────────────────────────────────────────────────────────────────────────────┘        ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Tools & Exécution

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  TOOLS & EXECUTION                                                                              ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  NATIVE TOOLS  ·  platform/tools/                                                        │  ║
║  │                                                                                           │  ║
║  │  code_tools    git_tools      deploy_tools    security_tools    sast_tools               │  ║
║  │  build_tools   lint_tools     compose_tools   chaos_tools       ast_tools                │  ║
║  │  jira_tools    plan_tools     web_tools       dep_tools         sandbox.py               │  ║
║  └──────────────────────────────────┬───────────────────────────────────────────────────────┘  ║
║                                     │                                                           ║
║  ┌──────────────────────────────────▼───────────────────────────────────────────────────────┐  ║
║  │  SANDBOX + ISOLATION LAYERS                                                              │  ║
║  │                                                                                           │  ║
║  │  Agent Tool Call                                                                         │  ║
║  │       │                                                                                  │  ║
║  │       ▼                                                                                  │  ║
║  │  ┌──────────────────────────────────────────────────────────────────────────┐           │  ║
║  │  │  RTK Proxy  (token compression 60-90%)                                   │           │  ║
║  │  │  rtk read / rtk git / rtk test / rtk err                                 │           │  ║
║  │  └─────────────────────┬────────────────────────────────────────────────────┘           │  ║
║  │                        │                                                                 │  ║
║  │       ┌────────────────┼────────────────────┐                                           │  ║
║  │       ▼                ▼                    ▼                                           │  ║
║  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────────────────┐               │  ║
║  │  │  Direct  │  │  Docker      │  │  Landlock (Linux kernel)            │               │  ║
║  │  │  exec    │  │  Sandbox     │  │  tools/sandbox/landlock-runner      │               │  ║
║  │  │ (local)  │  │  SANDBOX_    │  │  (Rust)                             │               │  ║
║  │  │          │  │  ENABLED=1   │  │  FS namespace isolation             │               │  ║
║  │  │          │  │  --net none  │  │  R/W accès restreint au workspace   │               │  ║
║  │  │          │  │  --memory    │  │  ref: landlock.io/rust-landlock     │               │  ║
║  │  │          │  │  512m        │  └─────────────────────────────────────┘               │  ║
║  │  └──────────┘  └──────────────┘                                                        │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                                 ║
║  SAST / SECURITY  ·  platform/tools/sast_tools.py  ·  security_tools.py                       ║
║  ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌────────────┐  ┌───────────────────┐     ║
║  │  Bandit    │  │  Semgrep   │  │  Trivy       │  │  Snyk      │  │  OWASP checks     │     ║
║  │  (Python)  │  │  (multi)   │  │  (container  │  │  (deps)    │  │  pentest scripts  │     ║
║  │            │  │            │  │   + repo)    │  │            │  │                   │     ║
║  └────────────┘  └────────────┘  └──────────────┘  └────────────┘  └───────────────────┘     ║
║                                                                                                 ║
║  SECURITY RUNTIME  ·  platform/security/                                                       ║
║  ┌───────────────────┐  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐       ║
║  │  PromptGuard      │  │  OutputValidator │  │  Sanitize      │  │  Guardrails      │       ║
║  │  (injection det.) │  │  (output safe?)  │  │  (XSS, SQLi…)  │  │  (destructive    │       ║
║  │  score 0-10       │  │                  │  │                │  │   action blocks) │       ║
║  │  block à ≥ 7      │  │                  │  │                │  │  audit_log table │       ║
║  └───────────────────┘  └──────────────────┘  └────────────────┘  └──────────────────┘       ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## LLM Layer

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  LLM LAYER  ·  platform/llm/                                                                   ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  LLMClient  ·  client.py                                                                 │  ║
║  │                                                                                           │  ║
║  │  PRIMARY                     FALLBACK CHAIN                                              │  ║
║  │  ─────────────────────────   ────────────────────────────────────────────────────────    │  ║
║  │  local-mlx (dev local)       local-mlx → minimax → azure-openai → azure-ai → ollama    │  ║
║  │  azure-openai (prod)                                                                     │  ║
║  │                                                                                           │  ║
║  │  PROVIDERS                                                                               │  ║
║  │  ┌────────────────┐  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────┐    │  ║
║  │  │ Local MLX      │  │ Azure OpenAI     │  │ Azure AI       │  │ MiniMax (CI)     │    │  ║
║  │  │ Qwen3.5-35B    │  │ gpt-5-mini       │  │ Foundry        │  │ MiniMax-M2.5     │    │  ║
║  │  │ :8080/v1       │  │ gpt-5 / gpt-5.2  │  │ gpt-5.2        │  │ (no GPU needed)  │    │  ║
║  │  └────────────────┘  └──────────────────┘  └────────────────┘  └──────────────────┘    │  ║
║  │                                                                                           │  ║
║  │  Thompson Sampling → auto-select best provider par perf historique                       │  ║
║  │  Rate limiter (6 req/min) · Cooldown 90s on 429                                          │  ║
║  │  LLM Cache (PostgreSQL) · Prompt Compressor (RTK-inspired, 40-70% token save)           │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Mémoire

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  MEMORY  ·  platform/memory/                                                                   ║
║                                                                                                 ║
║  Layer 1 — Session     in-memory dict, cleared après session                                  ║
║  Layer 2 — Project     PostgreSQL FTS (memory_entries table), persist par projet              ║
║  Layer 3 — Global      platform_settings + global full-text index                            ║
║  Layer 4 — Vector      vectors.py (embeddings, semantic search)                               ║
║                                                                                                 ║
║  compactor.py — prune/résume les vieilles entrées pour tenir dans la context window           ║
║  seeder.py    — pré-charge le contexte projet (VISION.md, conventions, etc.)                  ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Ops Engine

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  OPS ENGINE  ·  platform/ops/                                                                  ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  AUTO-HEAL PIPELINE  (airweave-ai/error-monitoring-agent MIT, adapté)                    │  ║
║  │                                                                                           │  ║
║  │  platform_incidents                                                                       │  ║
║  │       │                                                                                   │  ║
║  │       ▼                                                                                   │  ║
║  │  error_clustering.py ──── Stage 1: strict (error_type + source)                         │  ║
║  │  (ErrorClusterer)    ──── Stage 2: regex  (HTTP_4xx, TimeoutError…)                     │  ║
║  │                      ──── Stage 3: LLM    (semantic grouping)                            │  ║
║  │       │                                                                                   │  ║
║  │       ▼                                                                                   │  ║
║  │  error_state.py ─────────────── determine_status(sig) → NEW / REGRESSION / ONGOING      │  ║
║  │  (ErrorStateManager) ────────── should_alert_async()  → alert ou suppress?              │  ║
║  │                                                                                           │  ║
║  │  semantic_matcher.py ─────────── LLM: mute "HTTP 429 download" supprime aussi            │  ║
║  │  (SemanticMatcher)                         "HTTP 429 upload"  (même root cause)          │  ║
║  │       │                                                                                   │  ║
║  │       ▼                                                                                   │  ║
║  │  auto_heal.py ── _cluster_and_filter() → create_heal_epic() → launch_tma_workflow()     │  ║
║  │                                                                                           │  ║
║  │  PostgreSQL tables: error_signatures · error_mutes (via migrations.py)                  │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                                 ║
║  health.py  ·  chaos_endurance.py  ·  backup.py  ·  restore.py  ·  zombie_cleanup.py         ║
║  endurance_watchdog.py  ·  e2e_scheduler.py  ·  knowledge_scheduler.py                        ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## MCP Layer

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  MCP LAYER  ·  Model Context Protocol                                                          ║
║                                                                                                 ║
║  ┌────────────────────────────────────┐   ┌────────────────────────────────────────────────┐  ║
║  │  MCP LRM  :9500                    │   │  MCP Platform  (platform/mcp_platform/)        │  ║
║  │  mcp_lrm/server.py                 │   │  server.py  ·  server_sse.py                   │  ║
║  │                                    │   │  mlx_proxy.py · proxy_figma.py                 │  ║
║  │  MIT CSAIL arXiv:2512.24601        │   │  component_gallery_scraper.py                  │  ║
║  │  (Recursive Language Models)       │   │  guidelines_scraper.py                         │  ║
║  │                                    │   │  anonymizer.py · rlm_cache.py                  │  ║
║  │  Tools:                            │   │                                                │  ║
║  │  lrm_locate · lrm_summarize        │   │  Component Gallery (component.gallery)         │  ║
║  │  lrm_conventions · lrm_examples    │   │  Figma proxy (design tokens)                   │  ║
║  │  lrm_task_read · lrm_task_update   │   │  MLX local inference proxy                     │  ║
║  │  lrm_subtask_create · lrm_build    │   │                                                │  ║
║  └────────────────────────────────────┘   └────────────────────────────────────────────────┘  ║
║                                                                                                 ║
║  ┌────────────────────────────────────────────────────────────────────────────────────────┐    ║
║  │  MCP BRIDGE  ·  platform/tools/mcp_bridge.py                                          │    ║
║  │  + platform/mcps/  (manager.py · store.py)                                            │    ║
║  │                                                                                        │    ║
║  │  Serveurs MCP externes connectés aux agents :                                          │    ║
║  │  fetch · memory · playwright (browser automation) · custom MCPs                        │    ║
║  └────────────────────────────────────────────────────────────────────────────────────────┘    ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Intégrations & Inspirations

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  EXTERNAL INTEGRATIONS & INSPIRATIONS                                                          ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  TOKEN OPTIMIZATION                                                                      │  ║
║  │  RTK (Rust Token Killer)  ~/.local/bin/rtk  v0.22.2                                     │  ║
║  │  rtk read · rtk git · rtk test · rtk err · rtk docker · rtk grep                       │  ║
║  │  → wrappé automatiquement dans sandbox.py (RTK proxy)                                   │  ║
║  │  → 60-90% token savings sur outputs longs                                               │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  RESEARCH FOUNDATIONS                                                                    │  ║
║  │                                                                                          │  ║
║  │  arXiv:2512.24601 (MIT CSAIL)   Recursive Language Models                               │  ║
║  │    → mcp_lrm/ server · RLM Brain itératif (WRITE→EXECUTE→OBSERVE)                      │  ║
║  │    → FRACTAL decomposition (3 concerns) dans les agents                                 │  ║
║  │                                                                                          │  ║
║  │  KeygraphHQ/shannon             Information-theoretic prompt compression                │  ║
║  │    → platform/llm/prompt_compressor.py                                                  │  ║
║  │    → supprime les tokens redondants avant envoi au LLM                                  │  ║
║  │                                                                                          │  ║
║  │  anthropics/skills              Skill YAML pattern                                      │  ║
║  │    → skills/ (40 .md skills) — format adapté pour injection système                    │  ║
║  │    → skills_integration.py dans agents/                                                  │  ║
║  │                                                                                          │  ║
║  │  airweave-ai/error-monitoring-agent (MIT)                                               │  ║
║  │    → platform/ops/error_clustering.py  (clustering multi-étapes)                       │  ║
║  │    → platform/ops/error_state.py       (NEW/REGRESSION/ONGOING)                        │  ║
║  │    → platform/ops/semantic_matcher.py  (mutes sémantiques LLM)                         │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
║                                                                                                 ║
║  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  ║
║  │  SECURITY TOOLCHAIN                                                                      │  ║
║  │                                                                                          │  ║
║  │  Trivy (Aquasec)       scan images Docker + dépôts GitHub (vides ou non)               │  ║
║  │    ref: blog.stephane-robert.info/post/trivy-depot-github-vide/                         │  ║
║  │    → platform/tools/sast_tools.py                                                       │  ║
║  │                                                                                          │  ║
║  │  Landlock (Linux)      isolation FS niveau kernel sans root                             │  ║
║  │    ref: landlock.io/rust-landlock                                                        │  ║
║  │    → tools/sandbox/landlock-runner (Rust binary)                                        │  ║
║  │    → activé via LANDLOCK_ENABLED=1                                                      │  ║
║  │                                                                                          │  ║
║  │  agentation.dev        patterns d'agents (inspiration architecture A2A)                 │  ║
║  │    → platform/a2a/  (bus, negotiation, veto, protocol)                                  │  ║
║  │                                                                                          │  ║
║  │  component.gallery     scraping composants UI pour agents design                        │  ║
║  │    → platform/mcp_platform/component_gallery_scraper.py                                 │  ║
║  └──────────────────────────────────────────────────────────────────────────────────────────┘  ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Déploiements

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  DÉPLOIEMENTS                                                                                   ║
║                                                                                                 ║
║  LOCAL DEV                 OVH DEMO                    AZURE PROD                             ║
║  ──────────────────────    ─────────────────────────   ─────────────────────────────          ║
║  localhost:8099            http://<OVH_IP>             http://<AZURE_VM_IP>                   ║
║  localhost:8080 (dash)     SSH: debian@<ovh>           SSH: macaron@<azure>                   ║
║  No Docker, uvicorn        Docker Compose              Docker Compose (D4as_v5)               ║
║  LLM: local-mlx (Qwen3.5)     LLM: demo (mock)            LLM: Azure OpenAI gpt-5-mini           ║
║  PostgreSQL platform DB        software-factory-           nginx basic auth                       ║
║                            platform:v2                 OTEL → Jaeger :16686                   ║
║                                                        Module: macaron_platform               ║
║                                                                                                 ║
║  DOCKER IMAGES  ·  Dockerfile / Dockerfile.dev / Dockerfile.sf                                ║
║  ┌─────────────────────────────────────────────────────────────────────────────────────────┐   ║
║  │  platform container                                                                     │   ║
║  │  ├── uvicorn platform.server:app  (8090)                                               │   ║
║  │  ├── /workspace mount (repo cible)                                                     │   ║
║  │  └── env: LLM keys, SANDBOX_*, LANDLOCK_ENABLED                                       │   ║
║  │                                                                                         │   ║
║  │  sandbox containers (éphémères, SANDBOX_ENABLED=1)                                    │   ║
║  │  ├── python:3.12-slim  / node:20-slim / debian:slim                                   │   ║
║  │  ├── --network none  --memory 512m  --cpus 1                                          │   ║
║  │  └── /workspace RW, /tmp RW, tout le reste interdit                                   │   ║
║  └─────────────────────────────────────────────────────────────────────────────────────────┘   ║
║                                                                                                 ║
║  REPOS GIT                                                                                     ║
║  ~/_MACARON-SOFTWARE/          → GitHub  macaron-software/software-factory  (AGPL-3.0)        ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Flux complet — projet de A à Z

```
╔═════════════════════════════════════════════════════════════════════════════════════════════════╗
║  FLUX COMPLET — projet de A à Z                                                                ║
║                                                                                                 ║
║  Humain                                                                                        ║
║    │ "nouveau projet e-commerce"                                                               ║
║    ▼                                                                                           ║
║  sf CLI / Web UI                                                                               ║
║    │ POST /api/projects                                                                        ║
║    ▼                                                                                           ║
║  Platform (FastAPI)                                                                            ║
║    ├── Crée projet + VISION.md                                                                 ║
║    ├── Assigne Agent Lead (Brain ou lead-dev)                                                  ║
║    └── Initialise mémoire projet (PG full-text seeder)                                        ║
║    │                                                                                           ║
║    ▼                                                                                           ║
║  SAFe Lifecycle                                                                                ║
║    ├── PI Planning → Epics → Features → Stories (WSJF ordering)                              ║
║    └── ProductBacklog.py                                                                       ║
║    │                                                                                           ║
║    ▼                                                                                           ║
║  Workflow Engine (ideation-to-prod.yaml)                                                       ║
║    ├── Phase 1: ideation  [brain + ux-designer]  → pattern: network                          ║
║    ├── Phase 2: tdd       [lead-dev + tdd-agent] → pattern: loop (RED→GREEN→REFACTOR)        ║
║    ├── Phase 3: review    [adversarial + lead]   → pattern: human_in_the_loop                ║
║    ├── Phase 4: security  [sec-agent]            → Trivy + Semgrep + SAST                    ║
║    └── Phase 5: deploy    [devops-agent]         → Docker build → push → deploy               ║
║    │                                                                                           ║
║    ▼                                                                                           ║
║  Execution                                                                                     ║
║    ├── AgentLoop → PromptBuilder (skill inject + memory inject)                               ║
║    ├── LLMClient.chat() [Thompson Sampling → best provider]                                   ║
║    ├── Tool calls → [RTK proxy] → [sandbox/landlock] → result                                ║
║    ├── A2A bus: agent A → veto/negotiate → agent B                                            ║
║    └── PromptGuard (injection check) + Guardrails (destructive block)                        ║
║    │                                                                                           ║
║    ▼                                                                                           ║
║  Ops Loop (auto_heal every 60s)                                                               ║
║    ├── scan incidents → cluster (strict→regex→LLM) → NEW/REGRESSION/ONGOING                 ║
║    ├── SemanticMatcher: mutes sémantiques LLM                                                 ║
║    └── Alert → TMA epic → workflow tma-autoheal                                              ║
╚═════════════════════════════════════════════════════════════════════════════════════════════════╝
```

---

## Légende

| Sigle | Signification |
|-------|---------------|
| `[NEW]` | Ajouté lors du port airweave (cette session) |
| MIT | Licence open-source source |
| RTK | Rust Token Killer — compression proxy (60-90% token savings) |
| LRM | Recursive Language Models — arXiv:2512.24601 (MIT CSAIL) |
| SAFe | Scaled Agile Framework — Portfolio → ART → Team → Epic → Story |
| A2A | Agent-to-Agent — bus interne + Azure bridge |
| WSJF | Weighted Shortest Job First — priorisation backlog |
| FTS5 | Full-Text Search SQLite — mémoire agents (remplacé par PostgreSQL FTS en prod) |
| DORA | Metrics: deployment freq, lead time, MTTR, change failure rate |
| SAST | Static Application Security Testing |
| TMA | Tierce Maintenance Applicative — workflow auto-heal |
| MCP | Model Context Protocol |

---

## Anti-patterns identifiés & propositions

### 🔴 AP-1 — Q-learning pour la sélection de patterns

**Problème actuel**

```
RL Policy: Q-learning on rl_experience → pattern recommendation (offline)
```

Le Q-learning offline dans ce contexte accumule plusieurs problèmes structurels :

- **Reward sparse** : le signal de récompense n'arrive qu'en fin de mission (succès/échec), parfois plusieurs heures après l'action. L'agent ne peut pas associer causalement "j'ai choisi `parallel` au step 3" → "la mission a réussi".
- **Espace d'états mal défini** : comment encoder "migration PHP + 3 agents + deadline serrée" dans un vecteur d'état Q-table ? Le mapping est arbitraire.
- **Pas d'exploration** : en mode offline, l'agent réutilise des expériences passées sans pouvoir explorer de nouvelles combinaisons. Il converge vers le pattern "le plus vu" (souvent `sequential`), même si `parallel` serait meilleur.
- **Distribution shift** : les missions de sprint feature ont une distribution très différente des migrations. Un modèle Q unique se retrouve à faire des compromis sous-optimaux pour les deux.

**Proposition : Contextual Bandit + features explicites**

```
MissionRouter
  ├── features: {project_type, agent_count, estimated_steps, has_external_deps}
  ├── model:    LogisticRegression (sklearn, online updates)
  ├── explore:  ε-greedy (ε=0.1) → 10% random pattern / 90% best predicted
  ├── reward:   mission_duration_normalized * success_rate (immédiat après mission)
  └── persist:  table rl_experience (features + chosen_pattern + reward)
```

Avantages :
- Features lisibles et auditables (pas de black-box)
- Mise à jour online après chaque mission (pas offline)
- ε-greedy garantit l'exploration continue
- Modèle séparable par `project_type` → 1 classifieur par famille si besoin

Implémentation minimale (50 lignes) dans `platform/patterns/router.py`, appelé depuis `engine.py` à la place du Q-table actuel.

---

### 🟠 AP-2 — Genetic Algorithm sur les workflow templates (nightly)

**Problème actuel**

```
GAEngine → evolve workflow templates (nightly)
```

Un GA qui mute des fichiers YAML de workflows sans guardrails clairs est fragile :

- **Fitness function implicite** : durée ? token count ? coverage ? Si non définie formellement, le GA optimise quelque chose d'incohérent.
- **Mutations cassantes** : un YAML avec `phases: [ideation, tdd, review]` muté en `phases: [tdd, deploy]` passe le "fitness test" de durée (plus court) mais produit du code non relu ni sécurisé.
- **Baseline instable** : après une nuit de mutations, les workflows de production changent silencieusement. Debugger un comportement étrange 3 jours plus tard est très difficile.
- **Pas de canary** : les workflows mutés sont déployés directement sans validation sur un sous-ensemble de missions.

**Proposition : Évolution contrainte sur hyperparamètres uniquement**

Séparer ce qui est **stable** (structure logique) de ce qui est **optimisable** (paramètres numériques) :

```yaml
# workflow.yaml — structure IMMUABLE (ne jamais muter)
phases:
  - name: ideation
    agents: [brain, ux-designer]
    pattern: network

# workflow_params.yaml — SEULS ces paramètres sont évoluables
hyperparams:
  ideation.max_turns: {range: [3, 15], current: 8}
  tdd.loop_max_iter: {range: [2, 10], current: 5}
  review.timeout_s:  {range: [60, 600], current: 180}
```

Le GA ne touche qu'à `workflow_params.yaml`. Fitness function explicite :

```
fitness = 0.4 * success_rate
        + 0.3 * (1 / normalized_duration)
        + 0.2 * test_coverage
        + 0.1 * (1 / llm_token_count)
```

Gardrails obligatoires :
1. **Canary** : les paramètres mutés s'appliquent à 20% des nouvelles missions (flag `canary=True`)
2. **Rollback automatique** : si `success_rate(canary) < success_rate(stable) - 0.1` → rollback
3. **Freeze période** : pas de mutation pendant les 48h suivant un déploiement prod
4. **Audit trail** : chaque mutation enregistrée dans `workflow_evolution_log` avec diff + fitness avant/après

---

### 🟡 AP-3 — "Direct exec (local)" comme code path actif

**Problème actuel**

```
Direct exec (local) | Docker Sandbox | Landlock
```

Avoir `direct exec` comme option dans le code (même documentée "local only") crée un vecteur d'attaque :

- Un agent peut être prompt-injecté pour forcer `sandbox_mode=direct`
- En multi-tenant, une mission qui "pense" être en local peut se retrouver en prod sans isolation
- Le code path non-sandboxé reste testé, maintenu, et donc utilisable

**Proposition : Suppression du code path direct en faveur d'un "lightweight sandbox"**

```
# Au lieu de : direct exec (pour la rapidité locale)
# → sandbox Docker ultra-light avec partage de layers

docker run --rm
  --network none
  --memory 256m          # moitié du sandbox prod (512m)
  --cpus 0.5
  --volume $WORKSPACE:/workspace:rw
  --volume /tmp:/tmp:rw
  --read-only            # FS root read-only
  python:3.12-slim       # image pré-chargée localement
  $cmd
```

En local, l'image est déjà dans le cache Docker → overhead ~150ms vs direct exec ~0ms. Le gain sécurité (isolation réseau, FS, mémoire) justifie largement ce coût.

Si le Docker overhead est inacceptable en dev : activer Landlock uniquement (sans Docker), qui n'a quasiment aucun overhead (~5ms) et tourne sur Linux. Sur macOS dev, accepter le risque conscient et documenter explicitement l'env.

---

### Ce qui manque (backlog architecture)

| Priorité | Manquant | Impact |
|----------|----------|--------|
| 🔴 P0 | **Schéma DB PostgreSQL** — entités, FK, index, migrations versionées | Onboarding, débogage, évolution |
| 🔴 P0 | **Auth / multi-user model** — qui voit quoi, rôles, API keys | Sécurité multi-tenant |
| 🟠 P1 | **Context window management** — limite par agent, rolling window, compactor triggers | Stabilité sur longues missions |
| 🟠 P1 | **Circuit breakers LLM** — si azure-openai down 5min, ne pas retenter à chaque call | Latence & coût |
| 🟠 P1 | **Worker queue model** — `platform/workers/` (job queue PG) absent du diagramme | Compréhension du runtime async |
| 🟡 P2 | **SSE event schema** — liste des events émis, fréquence, backpressure model | Debugging frontend |
| 🟡 P2 | **Testing strategy** — 52 pytest + 82 Playwright, doubles LLM, mocking | CI/CD fiabilité |
| 🟡 P2 | **Cost tracking / budgets** — budget max LLM par projet pour éviter runaway missions | FinOps |

