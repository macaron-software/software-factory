#!/usr/bin/env python3
"""Wrapper to run backup.py without 'platform' package import conflict."""
import os, sys
from pathlib import Path

# Resolve paths
script = Path(__file__).resolve().parent / "backup.py"
factory_root = script.parents[1]

# Remove any path entries that would cause 'platform' package to shadow stdlib
clean_path = [p for p in sys.path if not p.endswith("/platform/ops") and not p.endswith("/platform")]
sys.path = clean_path

# Set DATABASE_URL if not already set
if not os.environ.get("DATABASE_URL"):
    os.environ["DATABASE_URL"] = (
        "postgresql://macaron:Macaron2026!Pg@macaron-platform-pg.postgres.database.azure.com"
        "/macaron_platform?sslmode=require"
    )

# Execute backup.py with proper __file__
g = {"__file__": str(script), "__name__": "__main__"}
exec(compile(script.read_text(), str(script), "exec"), g)
