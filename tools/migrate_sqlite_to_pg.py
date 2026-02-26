#!/usr/bin/env python3
"""Migrate data from SQLite platform.db → PostgreSQL.

Usage:
    python3 tools/migrate_sqlite_to_pg.py [--dry-run]

Requires:
    DATABASE_URL env var pointing to PG instance
    SQLite DB at data/platform.db (relative to repo root)
"""

import os
import sys
import re
import sqlite3
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(REPO_ROOT))

# Allow override via env var (e.g. inside Docker container data/ is at /app/data/)
_env_sqlite = os.environ.get("SQLITE_PATH", "")
if _env_sqlite:
    SQLITE_PATH = Path(_env_sqlite)
else:
    candidates = [
        REPO_ROOT / "data" / "platform.db",
        Path("/app/data/platform.db"),
        Path("/app/macaron_platform/data/platform.db"),
    ]
    SQLITE_PATH = next((p for p in candidates if p.exists()), candidates[0])

# Tables to skip (SQLite-only internals / FTS shadow tables)
_SKIP_PATTERN = re.compile(
    r"(_fts(_config|_data|_docsize|_idx)?$|^sqlite_sequence$|^messages_fts)"
)


def _skip(table: str) -> bool:
    return bool(_SKIP_PATTERN.search(table))


def get_pg_conn():
    import psycopg

    url = os.environ.get("DATABASE_URL", "")
    if not url.startswith(("postgresql://", "postgres://")):
        sys.exit("ERROR: DATABASE_URL not set or not a postgresql:// URL")
    return psycopg.connect(url)


def migrate(dry_run: bool = False):
    if not SQLITE_PATH.exists():
        sys.exit(f"ERROR: SQLite DB not found at {SQLITE_PATH}")

    sq = sqlite3.connect(str(SQLITE_PATH))
    sq.row_factory = sqlite3.Row
    sq_cur = sq.cursor()

    # Get all tables with data
    sq_cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    all_tables = [r[0] for r in sq_cur.fetchall()]
    tables = [t for t in all_tables if not _skip(t)]

    pg = get_pg_conn()
    pg.autocommit = False

    total_inserted = 0
    errors = []

    for table in tables:
        sq_cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = sq_cur.fetchone()[0]
        if count == 0:
            continue

        sq_cur.execute(f"SELECT * FROM {table} LIMIT 1")
        cols = [d[0] for d in sq_cur.description]

        # Check if table exists in PG
        with pg.cursor() as pc:
            pc.execute(
                "SELECT COUNT(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name=%s",
                (table,),
            )
            if pc.fetchone()[0] == 0:
                print(f"  SKIP {table} (not in PG schema)")
                continue

        sq_cur.execute(f"SELECT * FROM {table}")
        rows = sq_cur.fetchall()

        col_list = ", ".join(f'"{c}"' for c in cols)
        placeholders = ", ".join(["%s"] * len(cols))
        # Use ON CONFLICT DO NOTHING to be idempotent
        sql = (
            f'INSERT INTO "{table}" ({col_list}) VALUES ({placeholders}) '
            f"ON CONFLICT DO NOTHING"
        )

        if dry_run:
            print(f"  [DRY] {table}: {count} rows → would insert")
            continue

        try:
            with pg.cursor() as pc:
                # Temporarily defer FK constraints for orphaned legacy data
                pc.execute("SET session_replication_role = replica")

                # Strip NUL bytes (PG text fields reject \x00)
                def _clean(v):
                    if isinstance(v, str):
                        return v.replace("\x00", "")
                    return v

                data = [tuple(_clean(v) for v in row) for row in rows]
                pc.executemany(sql, data)
                pc.execute("SET session_replication_role = DEFAULT")
            pg.commit()
            print(f"  ✓ {table}: {count} rows")
            total_inserted += count
        except Exception as e:
            pg.rollback()
            err = f"  ✗ {table}: {e}"
            print(err)
            errors.append(err)

    sq.close()
    pg.close()

    print(
        f"\n{'DRY RUN — ' if dry_run else ''}Migrated: {total_inserted} rows across {len(tables)} tables"
    )
    if errors:
        print(f"\nErrors ({len(errors)}):")
        for e in errors:
            print(e)
        sys.exit(1)
    else:
        print("Migration complete ✓")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    migrate(dry_run=args.dry_run)
