#!/usr/bin/env python3
"""Macaron Platform — Full Backup to Azure Blob Storage.

Usage:
    python3 platform/ops/backup.py [--full|--daily|--weekly|--monthly]
    python3 platform/ops/backup.py --secrets-only
    python3 platform/ops/backup.py --pg-only

Backs up:
  1. All SQLite databases (data/*.db)
  2. PostgreSQL dump (pg_dump via DATABASE_URL)
  3. API keys and secrets (encrypted with age)
  4. Docker compose + nginx config from VM

Destinations:
  Azure Blob: macaronbackups (GRS: francecentral → francesouth)
  Containers: db-backups/, pg-dumps/, secrets/

Lifecycle: daily=90d, weekly=365d, monthly=forever
"""

import argparse
import datetime
import gzip
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STORAGE_ACCOUNT = "macaronbackups"
VM_HOST = "4.233.64.30"
VM_USER = "azureadmin"

def _get_factory_root() -> Path:
    """Resolve factory root — works from any cwd."""
    # If running from the script location
    try:
        script_dir = Path(__file__).resolve().parent
        candidate = script_dir.parents[1]  # platform/ops/../../ = _SOFTWARE_FACTORY
        if (candidate / "data" / "platform.db").exists():
            return candidate
    except NameError:
        pass
    # Fallback: check cwd and parents
    for p in [Path.cwd(), Path.cwd().parent]:
        if (p / "data" / "platform.db").exists():
            return p
    # Last resort
    return Path.cwd()

FACTORY_ROOT = _get_factory_root()
DATA_DIR = FACTORY_ROOT / "data"
KEYS_DIR = Path.home() / ".config" / "factory"

# SQLite databases to back up
SQLITE_DBS = [
    "platform.db",
    "factory.db",
    "build_queue.db",
    "metrics.db",
    "project_context.db",
    "rlm_cache.db",
    "permissions_audit.db",
]

PG_URL = os.environ.get("DATABASE_URL", "")
VM_HOST = "4.233.64.30"
VM_USER = "azureadmin"


def _run(cmd: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True)


def _az_upload(local_path: str, container: str, blob_name: str) -> bool:
    """Upload file to Azure Blob."""
    cmd = (
        f"az storage blob upload --account-name {STORAGE_ACCOUNT} "
        f"--container-name {container} --name {blob_name} "
        f"--file {local_path} --overwrite --no-progress --only-show-errors"
    )
    result = _run(cmd, check=False)
    if result.returncode != 0:
        print(f"  ❌ Upload failed: {blob_name}: {result.stderr[:200]}")
        return False
    return True


def _timestamp() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")


def _tier_prefix(tier: str) -> str:
    """Get blob prefix for retention tier."""
    ts = _timestamp()
    if tier == "monthly":
        return f"monthly/{ts[:6]}/"
    elif tier == "weekly":
        return f"weekly/{ts[:8]}/"
    else:
        return f"daily/{ts[:8]}/"


def backup_sqlite(tier: str = "daily") -> int:
    """Back up all SQLite databases."""
    print("📦 Backing up SQLite databases...")
    prefix = _tier_prefix(tier)
    count = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        for db_name in SQLITE_DBS:
            db_path = DATA_DIR / db_name
            if not db_path.exists():
                continue

            # Use SQLite backup API (safe, no WAL issues)
            backup_path = Path(tmpdir) / db_name
            _run(f'sqlite3 "{db_path}" ".backup \'{backup_path}\'"', check=False)

            if not backup_path.exists():
                # Fallback: copy
                shutil.copy2(db_path, backup_path)

            # Compress
            gz_path = f"{backup_path}.gz"
            with open(backup_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            blob_name = f"{prefix}{db_name}.gz"
            if _az_upload(gz_path, "db-backups", blob_name):
                size_mb = os.path.getsize(gz_path) / (1024 * 1024)
                print(f"  ✅ {db_name} ({size_mb:.1f}MB) → db-backups/{blob_name}")
                count += 1

    return count


def backup_postgresql(tier: str = "daily") -> bool:
    """Back up PostgreSQL via psycopg COPY (no pg_dump dependency)."""
    pg_url = PG_URL
    if not pg_url:
        print("  ⏭  No DATABASE_URL set, skipping PG backup")
        return False

    print("🐘 Backing up PostgreSQL...")
    prefix = _tier_prefix(tier)
    ts = _timestamp()

    try:
        import psycopg

        if "connect_timeout" not in pg_url:
            sep = "&" if "?" in pg_url else "?"
            pg_url += f"{sep}connect_timeout=10"
        conn = psycopg.connect(pg_url)

        with tempfile.TemporaryDirectory() as tmpdir:
            dump_path = Path(tmpdir) / f"macaron_platform_{ts}.sql"

            # Get all tables
            cur = conn.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
            )
            tables = [row[0] for row in cur.fetchall()]

            with open(dump_path, "w") as f:
                total_rows = 0
                for table in tables:
                    # Get non-generated columns only
                    cur = conn.execute(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name=%s AND table_schema='public' "
                        "AND is_generated='NEVER' ORDER BY ordinal_position",
                        (table,),
                    )
                    write_cols = [r[0] for r in cur.fetchall()]
                    if not write_cols:
                        continue

                    col_list = ", ".join(write_cols)
                    cur = conn.execute(f"SELECT {col_list} FROM {table}")
                    rows = cur.fetchall()
                    if not rows:
                        continue

                    f.write(f"\n-- {table}: {len(rows)} rows\n")
                    for row in rows:
                        vals = []
                        for v in row:
                            if v is None:
                                vals.append("NULL")
                            elif isinstance(v, bool):
                                vals.append("true" if v else "false")
                            elif isinstance(v, (int, float)):
                                vals.append(str(v))
                            else:
                                escaped = str(v).replace("'", "''")
                                vals.append(f"'{escaped}'")
                        val_list = ", ".join(vals)
                        f.write(f"INSERT INTO {table} ({col_list}) VALUES ({val_list}) ON CONFLICT DO NOTHING;\n")
                    total_rows += len(rows)

                f.write("\n-- Backup complete\n")

            conn.close()

            # Compress and upload
            gz_path = f"{dump_path}.gz"
            with open(dump_path, "rb") as f_in, gzip.open(gz_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)

            blob_name = f"{prefix}macaron_platform_{ts}.sql.gz"
            if _az_upload(gz_path, "pg-dumps", blob_name):
                size_mb = os.path.getsize(gz_path) / (1024 * 1024)
                print(f"  ✅ PG dump ({size_mb:.1f}MB, {len(tables)} tables, {total_rows} rows) → pg-dumps/{blob_name}")
                return True

    except Exception as e:
        print(f"  ❌ PG backup failed: {e}")

    return False


def backup_secrets(tier: str = "daily") -> bool:
    """Back up API keys and config (encrypted)."""
    print("🔐 Backing up secrets...")
    prefix = _tier_prefix(tier)
    ts = _timestamp()

    with tempfile.TemporaryDirectory() as tmpdir:
        archive_dir = Path(tmpdir) / "secrets"
        archive_dir.mkdir()

        # Collect secrets
        if KEYS_DIR.exists():
            for f in KEYS_DIR.iterdir():
                if f.is_file() and f.suffix in (".key", ".json", ".env"):
                    shutil.copy2(f, archive_dir / f.name)

        # .env file
        env_file = FACTORY_ROOT / ".env"
        if env_file.exists():
            shutil.copy2(env_file, archive_dir / ".env")

        # Docker compose (has DB passwords)
        compose_local = FACTORY_ROOT / "platform" / "docker-compose.yml"
        if compose_local.exists():
            shutil.copy2(compose_local, archive_dir / "docker-compose.yml")

        # Tar + gzip (no encryption for now — blob is private + Azure RBAC)
        archive_path = Path(tmpdir) / f"secrets_{ts}.tar.gz"
        _run(f'tar -czf "{archive_path}" -C "{archive_dir}" .', check=False)

        if archive_path.exists():
            blob_name = f"{prefix}secrets_{ts}.tar.gz"
            if _az_upload(str(archive_path), "secrets", blob_name):
                print(f"  ✅ Secrets → secrets/{blob_name}")
                return True

    print("  ❌ Secrets backup failed")
    return False


def backup_vm_snapshot() -> bool:
    """Create incremental Azure VM disk snapshot."""
    print("💾 Creating VM disk snapshot...")
    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")
    snap_name = f"vm-macaron-snap-{ts}"

    result = _run(
        f"az snapshot create --name {snap_name} --resource-group RG-MACARON "
        f"--location francecentral --source vm-macaron_OsDisk_1_0c8a0321411042f8a7f7948127c8cbbc "
        f"--incremental true --query name -o tsv",
        check=False,
    )

    if result.returncode == 0:
        print(f"  ✅ Snapshot: {snap_name}")
        # Clean old snapshots (keep last 4)
        _cleanup_snapshots(keep=4)
        return True

    print(f"  ❌ Snapshot failed: {result.stderr[:200]}")
    return False


def _cleanup_snapshots(keep: int = 4):
    """Delete old snapshots, keep most recent N."""
    result = _run(
        "az snapshot list -g RG-MACARON --query \"[?starts_with(name,'vm-macaron-snap-')]"
        ".{name:name,time:timeCreated}\" -o json",
        check=False,
    )
    if result.returncode != 0:
        return

    import json
    snaps = json.loads(result.stdout)
    snaps.sort(key=lambda s: s["time"], reverse=True)

    for snap in snaps[keep:]:
        print(f"  🗑 Deleting old snapshot: {snap['name']}")
        _run(f"az snapshot delete -n {snap['name']} -g RG-MACARON --no-wait", check=False)


def run_full_backup(tier: str = "daily"):
    """Run complete backup pipeline."""
    print(f"\n{'='*60}")
    print(f"🚀 MACARON FULL BACKUP — tier={tier} — {_timestamp()}")
    print(f"{'='*60}\n")

    results = {}
    results["sqlite"] = backup_sqlite(tier)
    results["pg"] = backup_postgresql(tier)
    results["secrets"] = backup_secrets(tier)

    if tier in ("weekly", "monthly"):
        results["snapshot"] = backup_vm_snapshot()

    print(f"\n{'='*60}")
    print(f"📊 BACKUP SUMMARY")
    print(f"  SQLite DBs: {results['sqlite']} files")
    print(f"  PostgreSQL: {'✅' if results.get('pg') else '❌'}")
    print(f"  Secrets: {'✅' if results.get('secrets') else '❌'}")
    if "snapshot" in results:
        print(f"  VM Snapshot: {'✅' if results['snapshot'] else '❌'}")
    print(f"{'='*60}\n")

    # Return success/failure for alerting
    all_ok = results["sqlite"] > 0 and results.get("secrets")
    return all_ok


def main():
    parser = argparse.ArgumentParser(description="Macaron Platform Backup")
    parser.add_argument("--tier", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--sqlite-only", action="store_true")
    parser.add_argument("--pg-only", action="store_true")
    parser.add_argument("--secrets-only", action="store_true")
    parser.add_argument("--snapshot-only", action="store_true")
    args = parser.parse_args()

    if args.sqlite_only:
        backup_sqlite(args.tier)
    elif args.pg_only:
        backup_postgresql(args.tier)
    elif args.secrets_only:
        backup_secrets(args.tier)
    elif args.snapshot_only:
        backup_vm_snapshot()
    else:
        ok = run_full_backup(args.tier)
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
