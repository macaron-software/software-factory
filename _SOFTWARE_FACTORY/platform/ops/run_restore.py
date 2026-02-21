#!/usr/bin/env python3
"""Wrapper to run restore.py without 'platform' package import conflict."""
import os, sys
from pathlib import Path

script = Path(__file__).resolve().parent / "restore.py"
factory_root = script.parents[1]

clean_path = [p for p in sys.path if not p.endswith("/platform/ops") and not p.endswith("/platform")]
sys.path = clean_path

if not os.environ.get("DATABASE_URL"):
    env_file = Path.home() / ".config" / "factory" / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip()

g = {"__file__": str(script), "__name__": "__main__"}
exec(compile(script.read_text(), str(script), "exec"), g)
