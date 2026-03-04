# Software Factory — Tech References & Inspirations

Source de vérité pour tous les projets étudiés, portés, intégrés.
Mis à jour à chaque intégration. Détail compressé aussi dans `platform/CLAUDE.md`.

Statuts: ✅ intégré (code live) · 🔄 porté/adapté (concepts implémentés) · 📚 étudié · 🔭 watch list

---

## ✅ Intégré — Code live, module dans registry ou bundlé

| Tool | URL | Implémentation SF | Notes |
|------|-----|-------------------|-------|
| **RTK** | https://github.com/macaron-software/rtk | `tools/__init__.py` → `rtk_run/rtk_wrap` · `llm/prompt_compressor.py` · registry: `rtk` | Token compression 40-90%. Métriques dans `rtk_compression_stats` DB |
| **Infisical** | https://github.com/Infisical/infisical · https://infisical.com | `tools/infisical_tools.py` → `get/list/set/rotate_secret` · registry: `infisical` | Secrets vault. Write ops = rôle `secrets_manager` requis |
| **Redis** | https://redis.io · https://github.com/redis/redis | `agents/store.py` · `rate_limit.py` · `llm/cache.py` · registry: `redis` | Cache backend + rate-limit store. Var: `REDIS_URL` |
| **Trivy** | https://github.com/aquasecurity/trivy · https://blog.stephane-robert.info/post/trivy-depot-github-vide/ | `tools/sast_tools.py` → `TrivyScanTool` + `TrivyImageTool` · registry: `trivy` | CVE scan repos + images Docker. Tourne en parallèle avec semgrep dans `sast_check` |
| **Scrapy** | https://github.com/scrapy/scrapy | registry: `scrapy` | Framework scraping pour futurs scrapers modules documentaires |
| **agent-browser** | https://github.com/vercel-labs/agent-browser | `tools/browser_tools.py` · registry: `browser-cli` | Rust CLI + Playwright/Chromium. Accessibility tree @refs, LLM-friendly |
| **Playwright MCP** | https://github.com/microsoft/playwright-mcp | `mcps/store.py` · registry: `playwright-mcp` | Playwright en tant que MCP server via MCP LRM bus |
| **GSD** | https://github.com/gsd-build/get-shit-done | registry: `gsd` | Context engineering: anti-context-rot, meta-prompting, summarization progressive |
| **mflux** | https://github.com/filipstrand/mflux | registry: `mflux` · `db/migrations.py` (image provider) | FLUX local sur Apple Silicon (M1-M4) via MLX. Offline, no API key |
| **The Component Gallery** | https://component.gallery · https://github.com/inbn/component-gallery | `mcp_lrm/component_gallery_scraper.py` · registry: `component-gallery` | 60 composants × 50+ design systems, 2676 implémentations |

---

## 🔄 Porté / Adapté — Concepts implémentés, pas de dépendance directe

| Source | URL | Implémentation SF | Ce qui a été porté |
|--------|-----|-------------------|--------------------|
| **Pentagi** | https://github.com/vxcontrol/pentagi | `workflows/definitions/security-hacking.yaml` + 12 skills dans `skills/definitions/` | Architecture Orchestrator→Researcher→Developer→Executor → équipe RSSI complète. Workflow dit explicitement "Inspiré PentAGI". Red Team (recon/exploit) + Blue Team (threat model) + CISO gate + remediation TDD + deploy hotfix |
| **Shannon** | https://github.com/KeygraphHQ/shannon | `tools/security_pentest_tools.py` | Outils offensifs autonomes: recon_portscan (nmap), recon_subdomain (subfinder), recon_fingerprint (whatweb), pentest_fuzz_api (schemathesis), pentest_inject (SQLi/XSS/SSTI), pentest_auth, pentest_ssrf |
| **Ralph** | https://github.com/frankbria/ralph-claude-code | `agents/executor.py` → `_summarize_context()` · `llm/prompt_compressor.py` | Context rot prevention: keep header + last 6 msgs, summarize middle. Threshold: 20 msgs. Fallback: truncation simple |
| **Agentation.dev** | https://agentation.dev/ | `web/routes/tma.py` · `workflows/definitions/tma-maintenance.yaml` · `metrics/quality.py` | Annotations code → tickets TMA (bug/debt/security/performance). Workflow TMA: triage → root cause → TDD fix → validation → hotfix deploy. Quality scanner 10 dimensions |
| **Airweave Error Monitoring** | https://github.com/airweave-ai/error-monitoring-agent | `ops/error_clustering.py` · `ops/error_state.py` · `skills/error-monitoring.md` · registry: `error-monitoring` | Error fingerprinting, clustering par similarité, severity auto-triage, agent remediation |
| **Landlock LSM** | https://landlock.io · https://landlock.io/rust-landlock/landlock/#use-cases | `tools/sandbox.py` · `tools/sandbox/landlock-runner` (binary bundlé) | Kernel sandbox LSM pour isolation filesystem des agents shell. Config: `security.landlock_enabled`. Linux kernel ≥5.13 requis |

---

## 📚 Étudié — Patterns appliqués sans intégration directe

| Source | URL | Impact |
|--------|-----|----|
| **D3.js** | https://github.com/d3/d3 | Lib dataviz frontend. Patterns étudiés pour graphes metrics/cockpit |

---

## 🔭 Watch list — Haut potentiel, pas encore intégré

| Tool | URL | Catégorie | Pourquoi |
|------|-----|-----------|----------|
| **SeedVR2** (via mflux) | https://github.com/filipstrand/mflux#seedvr2 | AI / Vidéo | Vidéo gen Apple Silicon. Extension naturelle de mflux pour workflows vidéo |
| **Semgrep** | https://semgrep.dev | Security | Déjà appelé dans `sast_tools.py` via `_run_semgrep()` si installé. Candidat registry officiel |

---

## Équipes agents créées

| Inspiration | Équipe SF | Fichiers |
|-------------|-----------|----------|
| Pentagi | Équipe RSSI + Hackers (12 agents) | `skills/definitions/`: ciso, pentester-lead, security-researcher, exploit-dev, security-architect, threat-analyst, secops-engineer, qa-security, security-dev-lead, security-backend-dev, security-frontend-dev, devsecops |
| (organique) | TMA Maintenance (5 agents) | `skills/definitions/`: responsable_tma, dev_tma, lead_dev, dba, test_automation |

---

_Mettre à jour ce fichier à chaque nouvelle intégration ou étude d'un projet externe._
_Détail compressé dans `platform/CLAUDE.md` section "EXTERNAL INSPIRATIONS"._
