#!/usr/bin/env python3
"""Wrapper to run health.py without 'platform' package import conflict."""
import sys
from pathlib import Path

script = Path(__file__).resolve().parent / "health.py"
clean_path = [p for p in sys.path if not p.endswith("/platform/ops") and not p.endswith("/platform")]
sys.path = clean_path

g = {"__file__": str(script), "__name__": "__main__"}
exec(compile(script.read_text(), str(script), "exec"), g)
