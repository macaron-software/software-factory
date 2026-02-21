#!/usr/bin/env python3
"""Macaron Platform — Full Restore from Azure Blob Storage.

Usage:
    python3 -m platform.ops.restore --list                    # List available backups
    python3 -m platform.ops.restore --latest                  # Restore latest daily
    python3 -m platform.ops.restore --date 20260221           # Restore specific date
    python3 -m platform.ops.restore --pg-only --latest        # PG only
    python3 -m platform.ops.restore --dry-run --latest        # Preview only
    python3 -m platform.ops.restore --from-snapshot snap-name # Restore VM from snapshot

Restores:
  1. SQLite databases → data/*.db
  2. PostgreSQL → psql < dump.sql
  3. Secrets → ~/.config/factory/*.key + .env
  4. VM → from Azure disk snapshot (new VM)

⚠️ DESTRUCTIVE: Overwrites existing data. Use --dry-run first.
"""

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STORAGE_ACCOUNT = "macaronbackups"


def _get_factory_root() -> Path:
    """Resolve factory root — works from any cwd."""
    try:
        candidate = Path(__file__).resolve().parents[2]
        if (candidate / "data").is_dir():
            return candidate
    except NameError:
        pass
    for p in [Path.cwd(), Path.cwd().parent]:
        if (p / "data" / "platform.db").exists():
            return p
    return Path.cwd()


FACTORY_ROOT = _get_factory_root()
DATA_DIR = FACTORY_ROOT / "data"
KEYS_DIR = Path.home() / ".config" / "factory"
PG_URL = os.environ.get("DATABASE_URL", "")


def _run(cmd: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, shell=True, check=check, capture_output=capture, text=True)


def _az_list_blobs(container: str, prefix: str = "") -> list[dict]:
    """List blobs in container."""
    cmd = (
        f"az storage blob list --account-name {STORAGE_ACCOUNT} "
        f"--container-name {container} "
        f"{'--prefix ' + prefix if prefix else ''} "
        f"--query \"[].{{name:name,size:properties.contentLength,modified:properties.lastModified}}\" "
        f"-o json --only-show-errors"
    )
    result = _run(cmd, check=False)
    if result.returncode == 0:
        return json.loads(result.stdout)
    return []


def _az_download(container: str, blob_name: str, dest: str) -> bool:
    """Download blob to local path."""
    cmd = (
        f"az storage blob download --account-name {STORAGE_ACCOUNT} "
        f"--container-name {container} --name {blob_name} "
        f"--file {dest} --only-show-errors"
    )
    result = _run(cmd, check=False)
    return result.returncode == 0


def list_backups():
    """List all available backups."""
    print("\n📋 Available Backups\n")

    for container in ["db-backups", "pg-dumps", "secrets"]:
        blobs = _az_list_blobs(container)
        if blobs:
            print(f"  {container}/ ({len(blobs)} files)")
            # Group by tier
            tiers = {}
            for b in blobs:
                tier = b["name"].split("/")[0]
                tiers.setdefault(tier, []).append(b)
            for tier, items in sorted(tiers.items()):
                latest = sorted(items, key=lambda x: x["name"], reverse=True)[0]
                size_mb = (latest.get("size") or 0) / (1024 * 1024)
                print(f"    {tier}: {len(items)} backups, latest={latest['name']} ({size_mb:.1f}MB)")
        else:
            print(f"  {container}/ (empty)")

    # Snapshots
    result = _run(
        "az snapshot list -g RG-MACARON --query \"[?starts_with(name,'vm-macaron-snap-')]"
        ".{name:name,time:timeCreated,size:diskSizeGb}\" -o json",
        check=False,
    )
    if result.returncode == 0:
        snaps = json.loads(result.stdout)
        print(f"\n  vm-snapshots/ ({len(snaps)} snapshots)")
        for s in sorted(snaps, key=lambda x: x["time"], reverse=True)[:5]:
            print(f"    {s['name']} — {s['time'][:19]}")

    print()


def _find_latest_blobs(container: str, date_filter: str = "") -> list[dict]:
    """Find latest blobs, optionally filtered by date prefix."""
    blobs = _az_list_blobs(container, prefix=f"daily/{date_filter}")
    if not blobs:
        blobs = _az_list_blobs(container, prefix=f"weekly/{date_filter}")
    if not blobs:
        blobs = _az_list_blobs(container, prefix=f"monthly/{date_filter}")
    return sorted(blobs, key=lambda x: x["name"], reverse=True)


def restore_sqlite(date_filter: str = "", dry_run: bool = False) -> int:
    """Restore SQLite databases from backup."""
    print("📦 Restoring SQLite databases...")
    blobs = _find_latest_blobs("db-backups", date_filter)
    if not blobs:
        print("  ❌ No SQLite backups found")
        return 0

    # Group by date (take latest set)
    latest_prefix = "/".join(blobs[0]["name"].split("/")[:2])
    latest_blobs = [b for b in blobs if b["name"].startswith(latest_prefix)]
    print(f"  Found {len(latest_blobs)} files from {latest_prefix}")

    count = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        for blob in latest_blobs:
            db_name = blob["name"].split("/")[-1].replace(".gz", "")
            dest_gz = Path(tmpdir) / f"{db_name}.gz"
            dest_db = DATA_DIR / db_name

            if dry_run:
                print(f"  [DRY-RUN] Would restore {blob['name']} → {dest_db}")
                count += 1
                continue

            if _az_download("db-backups", blob["name"], str(dest_gz)):
                # Decompress
                dest_tmp = Path(tmpdir) / db_name
                with gzip.open(dest_gz, "rb") as f_in, open(dest_tmp, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

                # Backup current before overwrite
                if dest_db.exists():
                    bak = dest_db.with_suffix(".db.pre-restore")
                    shutil.copy2(dest_db, bak)

                shutil.move(str(dest_tmp), str(dest_db))
                print(f"  ✅ {db_name} restored")
                count += 1

    return count


def restore_postgresql(date_filter: str = "", dry_run: bool = False) -> bool:
    """Restore PostgreSQL from dump."""
    print("🐘 Restoring PostgreSQL...")
    pg_url = PG_URL
    if not pg_url:
        print("  ⏭ No DATABASE_URL set, skipping PG restore")
        return False

    blobs = _find_latest_blobs("pg-dumps", date_filter)
    if not blobs:
        print("  ❌ No PG dumps found")
        return False

    latest = blobs[0]
    print(f"  Using: {latest['name']}")

    if dry_run:
        print(f"  [DRY-RUN] Would restore {latest['name']} to PostgreSQL")
        return True

    with tempfile.TemporaryDirectory() as tmpdir:
        dest_gz = Path(tmpdir) / "dump.sql.gz"
        dest_sql = Path(tmpdir) / "dump.sql"

        if not _az_download("pg-dumps", latest["name"], str(dest_gz)):
            print("  ❌ Download failed")
            return False

        # Decompress
        with gzip.open(dest_gz, "rb") as f_in, open(dest_sql, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)

        # Execute SQL statements via psycopg
        print("  ⚠ Executing restore statements...")
        try:
            import psycopg

            if "connect_timeout" not in pg_url:
                sep = "&" if "?" in pg_url else "?"
                pg_url += f"{sep}connect_timeout=10"
            conn = psycopg.connect(pg_url, autocommit=True)

            sql_text = dest_sql.read_text()
            stmts = [s.strip() for s in sql_text.split("\n") if s.strip() and not s.strip().startswith("--")]
            ok, err = 0, 0
            for stmt in stmts:
                try:
                    conn.execute(stmt)
                    ok += 1
                except Exception:
                    err += 1

            conn.close()
            print(f"  ✅ PostgreSQL restored ({ok} statements OK, {err} conflicts/skipped)")
            return True
        except ImportError:
            print("  ❌ psycopg not installed")
            return False


def restore_secrets(date_filter: str = "", dry_run: bool = False) -> bool:
    """Restore secrets from backup."""
    print("🔐 Restoring secrets...")
    blobs = _find_latest_blobs("secrets", date_filter)
    if not blobs:
        print("  ❌ No secrets backups found")
        return False

    latest = blobs[0]
    if dry_run:
        print(f"  [DRY-RUN] Would restore {latest['name']} to {KEYS_DIR}")
        return True

    with tempfile.TemporaryDirectory() as tmpdir:
        dest = Path(tmpdir) / "secrets.tar.gz"
        if not _az_download("secrets", latest["name"], str(dest)):
            return False

        extract_dir = Path(tmpdir) / "extracted"
        extract_dir.mkdir()
        _run(f'tar -xzf "{dest}" -C "{extract_dir}"', check=False)

        # Restore keys
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        for f in extract_dir.iterdir():
            if f.name == ".env":
                target = FACTORY_ROOT / ".env"
            elif f.name == "docker-compose.yml":
                target = FACTORY_ROOT / "platform" / "docker-compose.yml"
            else:
                target = KEYS_DIR / f.name
            shutil.copy2(f, target)
            print(f"  ✅ {f.name} → {target}")

    return True


def restore_vm_from_snapshot(snapshot_name: str, dry_run: bool = False) -> bool:
    """Restore VM from Azure disk snapshot (creates new VM)."""
    print(f"💾 Restoring VM from snapshot: {snapshot_name}")

    if dry_run:
        print("  [DRY-RUN] Would create new disk from snapshot and swap VM OS disk")
        return True

    # Create new disk from snapshot
    disk_name = f"vm-macaron-restored-{snapshot_name}"
    result = _run(
        f"az disk create -n {disk_name} -g RG-MACARON "
        f"--source {snapshot_name} --query name -o tsv",
        check=False,
    )
    if result.returncode != 0:
        print(f"  ❌ Failed to create disk: {result.stderr[:200]}")
        return False

    print(f"  ✅ Disk created: {disk_name}")
    print(f"  ⚠ To swap: az vm update -n vm-macaron -g RG-MACARON --os-disk {disk_name}")
    print(f"  ⚠ Then: az vm start -n vm-macaron -g RG-MACARON")
    return True


def run_full_restore(date_filter: str = "", dry_run: bool = False):
    """Full restore pipeline."""
    print(f"\n{'='*60}")
    print(f"🔄 MACARON FULL RESTORE {'[DRY-RUN]' if dry_run else ''}")
    print(f"{'='*60}\n")

    if not dry_run:
        print("⚠️  WARNING: This will OVERWRITE existing data!")
        print("    Current databases will be backed up as *.pre-restore")
        confirm = input("    Type 'RESTORE' to confirm: ")
        if confirm != "RESTORE":
            print("    Aborted.")
            return

    results = {}
    results["sqlite"] = restore_sqlite(date_filter, dry_run)
    results["pg"] = restore_postgresql(date_filter, dry_run)
    results["secrets"] = restore_secrets(date_filter, dry_run)

    print(f"\n{'='*60}")
    print(f"📊 RESTORE SUMMARY {'[DRY-RUN]' if dry_run else ''}")
    print(f"  SQLite DBs: {results['sqlite']} files")
    print(f"  PostgreSQL: {'✅' if results['pg'] else '⏭'}")
    print(f"  Secrets: {'✅' if results['secrets'] else '⏭'}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="Macaron Platform Restore")
    parser.add_argument("--list", action="store_true", help="List available backups")
    parser.add_argument("--latest", action="store_true", help="Restore latest backup")
    parser.add_argument("--date", help="Restore from specific date (YYYYMMDD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without restoring")
    parser.add_argument("--sqlite-only", action="store_true")
    parser.add_argument("--pg-only", action="store_true")
    parser.add_argument("--secrets-only", action="store_true")
    parser.add_argument("--from-snapshot", help="Restore VM from snapshot name")
    args = parser.parse_args()

    if args.list:
        list_backups()
        return

    if args.from_snapshot:
        restore_vm_from_snapshot(args.from_snapshot, args.dry_run)
        return

    date_filter = args.date or ""

    if not args.latest and not args.date:
        parser.print_help()
        return

    if args.sqlite_only:
        restore_sqlite(date_filter, args.dry_run)
    elif args.pg_only:
        restore_postgresql(date_filter, args.dry_run)
    elif args.secrets_only:
        restore_secrets(date_filter, args.dry_run)
    else:
        run_full_restore(date_filter, args.dry_run)


if __name__ == "__main__":
    main()
