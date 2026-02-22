# Macaron Platform — Disaster Recovery Runbook

## Architecture Overview

```
┌─ Azure francecentral ──────────────────────────┐
│  VM: vm-macaron (D4as_v5, 4vCPU, 16GB)        │
│    └─ Docker: platform + nginx + certbot       │
│  PG: macaron-platform-pg (B1ms, PG17+pgvector) │
│  Blob: macaronbackups (GRS → francesouth)      │
│  Snapshots: vm-macaron-snap-* (incremental)    │
└─────────────────────────────────────────────────┘
┌─ Local Mac ────────────────────────────────────┐
│  SQLite DBs: data/*.db (7 files, ~90MB)        │
│  API keys: ~/.config/factory/*.key             │
│  Source: git repo (_MACARON-SOFTWARE)           │
└─────────────────────────────────────────────────┘
```

## RTO / RPO Targets

| Resource | RPO (max data loss) | RTO (recovery time) |
|----------|--------------------|--------------------|
| PostgreSQL | 24h (daily dump) + 7d PITR | 15 min |
| SQLite (local) | 24h (daily backup) | 5 min |
| VM | 7d (weekly snapshot) | 30 min |
| Secrets | 24h | 5 min |
| Source code | 0 (git) | 0 |

## Daily Backup (Automated)

### What runs
```bash
# Cron on local Mac (3AM UTC daily)
0 3 * * * /path/to/_SOFTWARE_FACTORY/platform/ops/run_backup.sh >> /var/log/macaron-backup.log 2>&1

# Cron weekly (Sunday 2AM) — includes VM snapshot
0 2 * * 0 /path/to/_SOFTWARE_FACTORY/platform/ops/run_backup.sh --tier weekly >> /var/log/macaron-backup.log 2>&1
```

### What gets backed up
| Data | Size | Destination | Retention |
|------|------|-------------|-----------|
| 7 SQLite DBs | ~25MB gz | `db-backups/daily/YYYYMMDD/` | 90 days |
| PG dump (33 tables) | ~0.7MB gz | `pg-dumps/daily/YYYYMMDD/` | 90 days |
| Secrets (API keys) | ~1KB | `secrets/daily/YYYYMMDD/` | 90 days |
| VM snapshot | 30GB disk | Azure Managed Disk | 4 snapshots |

### Verification
```bash
# Check backup health
python3 platform/ops/run_health.py

# List all backups
python3 platform/ops/run_restore.py --list
```

---

## Recovery Procedures

### Scenario 1: PG Database Corruption

**Symptoms:** HTTP 500 on missions/agents pages, psycopg connection errors

```bash
# 1. Check PG connectivity
python3 platform/ops/run_health.py

# 2. Try Azure PITR first (last 7 days, fastest)
az postgres flexible-server restore \
  --resource-group RG-MACARON \
  --name macaron-platform-pg-restored \
  --source-server macaron-platform-pg \
  --restore-point-in-time "2026-02-20T10:00:00Z"

# 3. Or restore from our dump
python3 platform/ops/run_restore.py --pg-only --latest --dry-run  # preview
python3 platform/ops/run_restore.py --pg-only --latest            # execute

# 4. Verify
python3 platform/ops/run_health.py
```

### Scenario 2: SQLite Database Loss (Local)

```bash
# 1. List available backups
python3 platform/ops/run_restore.py --list

# 2. Preview restore
python3 platform/ops/run_restore.py --sqlite-only --latest --dry-run

# 3. Execute (creates *.pre-restore backup of current)
python3 platform/ops/run_restore.py --sqlite-only --latest

# 4. Or specific date
python3 platform/ops/run_restore.py --sqlite-only --date 20260220
```

### Scenario 3: VM Total Loss

```bash
# 1. Create new disk from latest snapshot
az disk create -n vm-macaron-restored \
  -g RG-MACARON \
  --source vm-macaron-snap-20260221

# 2. Create new VM from disk
az vm create -n vm-macaron-new -g RG-MACARON \
  --attach-os-disk vm-macaron-restored \
  --os-type Linux --size Standard_D4as_v5 \
  --public-ip-address vm-macaron-ip \
  --nsg vm-macaron-nsg

# 3. Or redeploy from scratch
ssh azureadmin@<new-ip>
git clone <repo>
cd _SOFTWARE_FACTORY
docker compose -f platform/docker-compose.yml up -d

# 4. Restore secrets on new VM
python3 platform/ops/run_restore.py --secrets-only --latest

# 5. Update DNS/IP references
```

### Scenario 4: API Keys Lost

```bash
# Restore from blob
python3 platform/ops/run_restore.py --secrets-only --latest

# Files restored:
# ~/.config/factory/*.key
# _SOFTWARE_FACTORY/.env
# platform/docker-compose.yml
```

### Scenario 5: Full Disaster (everything lost)

```bash
# 1. Git clone source code
git clone <repo-url> _MACARON-SOFTWARE
cd _MACARON-SOFTWARE/_SOFTWARE_FACTORY

# 2. Restore secrets first (need Azure CLI auth)
az login
python3 platform/ops/run_restore.py --secrets-only --latest

# 3. Restore SQLite databases
python3 platform/ops/run_restore.py --sqlite-only --latest

# 4. Restore/create PG
# Option A: Azure PITR (if server still exists)
# Option B: Restore from dump
python3 platform/ops/run_restore.py --pg-only --latest

# 5. VM from snapshot
python3 platform/ops/run_restore.py --from-snapshot vm-macaron-snap-20260221

# 6. Verify everything
python3 platform/ops/run_health.py
```

---

## Azure Resources

| Resource | Name | SKU | Location |
|----------|------|-----|----------|
| VM | vm-macaron | D4as_v5 (4c/16GB) | francecentral |
| PostgreSQL | macaron-platform-pg | B1ms | francecentral |
| Blob Storage | macaronbackups | Standard_GRS | francecentral→francesouth |
| Snapshots | vm-macaron-snap-* | Incremental | francecentral |

### Credentials
- Stored in `~/.config/factory/.env` (chmod 600) — NEVER hardcode in source
- VM SSH: `azureadmin@4.233.64.30` / `$VM_PASS`
- PG: `$DATABASE_URL`
- Web: basic auth `macaron:macaron`
- LLM: Azure OpenAI `ascii-ui-openai` / gpt-5-mini / 100 req/min

## Monitoring

```bash
# One-shot check
python3 platform/ops/run_health.py

# Continuous (5min interval)
python3 platform/ops/run_health.py --watch

# JSON for alerting pipeline
python3 platform/ops/run_health.py --json

# Checks performed:
# 1. VM HTTP 200 (curl with basic auth)
# 2. PG connectivity (psycopg + row counts)
# 3. Docker containers on VM (SSH)
# 4. Disk usage on VM (SSH, alert >85%)
# 5. Backup freshness (Azure Blob, alert >26h)
```

## Lifecycle Policies

- **Daily backups**: auto-deleted after 90 days
- **Weekly backups**: auto-deleted after 365 days
- **VM snapshots**: 4 most recent kept
- **PG PITR**: 7 days (Azure native)
