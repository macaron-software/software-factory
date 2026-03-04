# Software Factory — Tech References & Inspirations

All external projects, tools, and concepts that shaped the SF architecture.
Organized by integration status: ✅ integrated · 🔄 ported/adapted · 📚 studied · 🔭 watch list.

---

## ✅ Integrated (code exists, module in registry or bundled)

| Tool | URL | Where in SF | Notes |
|------|-----|-------------|-------|
| **RTK** (Rust Token Killer) | https://github.com/macaron-software/rtk | `platform/tools/__init__.py` → `rtk_run`, `rtk_wrap` · registry: `rtk` | Token compression 40-90%. Used in `git_tools.py`, metrics in `rtk_compression_stats` DB table |
| **Infisical** | https://github.com/Infisical/infisical | `platform/tools/infisical_tools.py` · registry: `infisical` | Secrets vault: `get_secret`, `list_secrets`, `set_secret`, `rotate_secret`. Agents use elevated role |
| **Trivy** | https://github.com/aquasecurity/trivy · https://blog.stephane-robert.info/post/trivy-depot-github-vide/ | `platform/tools/sast_tools.py` → `TrivyScanTool`, `TrivyImageTool` · registry: `trivy` | CVE scan for repos + Docker images. Runs alongside semgrep in `sast_check` |
| **Scrapy** | https://github.com/scrapy/scrapy | registry: `scrapy` | Foundation for custom knowledge scrapers. `pip install scrapy` |
| **agent-browser** (browser-cli) | https://github.com/vercel-labs/agent-browser | `platform/tools/browser_tools.py` · registry: `browser-cli` | Rust CLI + Playwright/Chromium. Accessibility tree snapshots, LLM-friendly refs |
| **Playwright MCP** | https://github.com/microsoft/playwright-mcp | `platform/mcps/store.py` · registry: `playwright-mcp` | Playwright as MCP server via MCP LRM bus |
| **GSD** (get-shit-done) | https://github.com/gsd-build/get-shit-done | registry: `gsd` | Context engineering: prevents context rot, meta-prompting, progressive summarization |
| **mflux** | https://github.com/filipstrand/mflux | registry: `mflux` · `platform/db/migrations.py` (image provider) | Local FLUX image gen on Apple Silicon (M1/M2/M3/M4) via MLX. No API key |
| **Redis** | https://redis.io · https://github.com/redis/redis | `platform/agents/store.py`, `platform/rate_limit.py` · registry: `redis` | Cache backend + rate-limit store. `REDIS_URL` env var |
| **The Component Gallery** | https://component.gallery | `mcp_lrm/component_gallery_scraper.py` · registry: `component-gallery` | 60 UI components × 50+ design systems. 2676 implementations |

---

## 🔄 Ported / Adapted (concepts implemented, not direct dependency)

| Source | URL | Where in SF | What was ported |
|--------|-----|-------------|-----------------|
| **Airweave Error Monitoring Agent** | https://github.com/airweave-ai/error-monitoring-agent | `platform/ops/error_clustering.py` + `platform/ops/error_state.py` · `skills/error-monitoring.md` · registry: `error-monitoring` | Error fingerprinting, severity auto-triage, clustering pipeline, agent-triggered remediation |
| **Landlock LSM** | https://landlock.io · https://landlock.io/rust-landlock/landlock/#use-cases | `platform/tools/sandbox.py` · `platform/tools/sandbox/landlock-runner` | Kernel-level filesystem sandbox for agent shell commands. Restricts each agent to its project workspace |

---

## 📚 Studied — Patterns applied, not a direct dependency

| Source | URL | Patterns extracted |
|--------|-----|--------------------|
| **Ralph** (Claude Code context mgmt) | https://github.com/frankbria/ralph-claude-code | Context compression patterns for long sessions → informed GSD module + agent prompt_builder |
| **Agentation.dev** | https://agentation.dev/ | Agentic workflow patterns (site intermittently down). Concepts referenced in orchestration patterns |
| **D3.js** | https://github.com/d3/d3 | Data visualization library. Not a SF module but studied for potential metrics/dashboard charts |

---

## 🔭 Watch List — Not yet integrated, high potential

| Tool | URL | Category | Why |
|------|-----|----------|-----|
| **Shannon** (AI pentester) | https://github.com/KeygraphHQ/shannon | Security | Autonomous AI penetration testing agent. Docker-based. Potential integration as a pentest skill orchestrator alongside Trivy |
| **Pentagi** | https://github.com/vxcontrol/pentagi | Security | Full multi-agent pentest platform (recon, exploit, report). Could inspire a dedicated security team pattern in SF |
| **SeedVR2** (via mflux) | https://github.com/filipstrand/mflux?tab=readme-ov-file#%EF%B8%8F-seedvr2 | AI / Image | Video generation on Apple Silicon. Extension of mflux for video workflows |
| **Semgrep** | https://semgrep.dev | Security | Already called in `sast_tools.py` via `_run_semgrep()`. Could add to registry when `semgrep` binary detection is reliable |

---

## Notes

- Tools in **watch list** are referenced in `skills/` or have issues/PRs tracking them
- The **registry.yaml** (`platform/modules/registry.yaml`) contains only tools with actual code backing them
- This file is the source of truth for "what did we look at and why"
- Update this file when adding new integrations or moving tools from watch → integrated
