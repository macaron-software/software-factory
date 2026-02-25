# Deployment Guide

## 3 Environments

### 1. Azure Production (4.233.64.30)

| Property | Value |
|----------|-------|
| VM | D4as_v5 (4 CPU, 16 GB), francecentral |
| SSH | `macaron@4.233.64.30` |
| Web | http://4.233.64.30 (nginx basic auth) |
| LLM | Azure OpenAI / gpt-5-mini |
| Container | `deploy-platform-1` |
| Compose | `/opt/macaron/platform/deploy/docker-compose-vm.yml` |
| Build context | `/opt/macaron` |
| Module | `macaron_platform` (⚠️ NOT `platform`) |
| Patches | `/opt/macaron/patches/` → applied at startup |
| Tracing | OTEL → Jaeger `:16686` |
| DB | PostgreSQL (macaron-platform-pg.postgres.database.azure.com) + SQLite |

**Deploy process:**
```bash
# 1. rsync from push repo to VM
rsync -avz /tmp/gh_push_ops/software-factory/{platform,cli,skills,dashboard,mcp_lrm,projects}/ macaron@4.233.64.30:/home/macaron/

# 2. Update patches
ssh macaron@4.233.64.30 "sudo cp /home/macaron/platform/web/routes/*.py /opt/macaron/patches/"

# 3. Restart
ssh macaron@4.233.64.30 "sudo docker restart deploy-platform-1"
```

### 2. OVH Demo (54.36.183.124)

| Property | Value |
|----------|-------|
| VPS | OVH VPS, Debian |
| SSH | `debian@54.36.183.124` |
| Web | http://54.36.183.124 |
| LLM | Demo mode (mock, no API key needed) |
| Container | `software-factory-platform-1` |
| Image | `software-factory-platform:v2` |
| Code | `/opt/software-factory/` |
| DB | SQLite only |

**Deploy process:**
```bash
rsync -avz --delete /tmp/gh_push_ops/software-factory/ debian@54.36.183.124:/opt/software-factory/
ssh debian@54.36.183.124 "cd /opt/software-factory && sudo docker compose up -d --build"
```

### 3. Local Development

| Property | Value |
|----------|-------|
| URL | http://localhost:8099 (platform) / :8080 (dashboard) |
| LLM | MiniMax / MiniMax-M2.5 |
| Module | `platform` (standard Python package) |
| DB | SQLite (`data/platform.db`) |
| No Docker | Direct uvicorn |

**Run locally:**
```bash
# Platform (NEVER --reload, ALWAYS --ws none)
python3 -m uvicorn platform.server:app --host 0.0.0.0 --port 8099 --ws none --log-level warning

# Dashboard
python3 -m dashboard.server

# Tests
python3 -m pytest tests/ -v
```

## Docker Quick Start

```bash
git clone https://github.com/macaron-software/software-factory.git
cd software-factory
make setup    # install deps, init DB
make run      # start Docker containers
# → http://localhost:8090
```

For demo mode (no LLM key): `PLATFORM_LLM_PROVIDER=demo make run`

## 🇫🇷 [Guide de déploiement (FR)](Deployment-Guide‐FR) · 🇪🇸 [ES](Deployment-Guide‐ES) · 🇩🇪 [DE](Deployment-Guide‐DE)
