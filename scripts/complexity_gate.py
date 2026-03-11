#!/usr/bin/env python3
"""Deterministic code complexity gate.

Checks: cyclomatic complexity (CC), maintainability index (MI), lines of code (LOC).
Uses radon. Exit 0=pass, 1=violations (--strict only).

Usage:
    python scripts/complexity_gate.py [path]            # report mode
    python scripts/complexity_gate.py [path] --strict    # exit 1 on errors
    python scripts/complexity_gate.py [path] --json      # machine output
"""

import json
import subprocess
import sys
from pathlib import Path

# --- Thresholds ---
CC_WARN = 6      # per-function: 6-10 = warn (radon grade C)
CC_ERR = 11      # per-function: 11+  = error (radon grade D+)
LOC_WARN = 300   # per-file: 300-500 = warn
LOC_ERR = 500    # per-file: 500+    = error
MI_WARN = 20.0   # per-file: 10-20   = warn (lower = worse)
MI_ERR = 10.0    # per-file: <10     = error


def count_loc(path: Path) -> int:
    """Count non-blank non-comment Python lines."""
    n = 0
    for line in path.read_text(errors="replace").splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


def run_radon(cmd: list) -> dict:
    """Run radon CLI, return parsed JSON."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {}


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else "platform/"
    strict = "--strict" in sys.argv
    as_json = "--json" in sys.argv

    errors, warnings = [], []

    # Collect .py files (skip __pycache__, tests, migrations)
    py_files = sorted(
        f for f in Path(target).rglob("*.py")
        if "__pycache__" not in str(f)
    )

    # 1. LOC check
    for f in py_files:
        loc = count_loc(f)
        if loc > LOC_ERR:
            errors.append({"type": "LOC", "file": str(f), "value": loc, "limit": LOC_ERR})
        elif loc > LOC_WARN:
            warnings.append({"type": "LOC", "file": str(f), "value": loc, "limit": LOC_WARN})

    # 2. Cyclomatic complexity per function (show B+ = CC >= 6)
    cc_data = run_radon(["radon", "cc", target, "-j", "-n", "B", "-e", "*__pycache__*"])
    for filepath, blocks in cc_data.items():
        if not isinstance(blocks, list):
            continue
        for b in blocks:
            cc = b.get("complexity", 0)
            name = b.get("name", "?")
            lineno = b.get("lineno", 0)
            if cc >= CC_ERR:
                errors.append({"type": "CC", "file": filepath, "func": name,
                               "line": lineno, "value": cc, "limit": CC_ERR - 1})
            elif cc >= CC_WARN:
                warnings.append({"type": "CC", "file": filepath, "func": name,
                                 "line": lineno, "value": cc, "limit": CC_WARN - 1})

    # 3. Maintainability index per file
    mi_data = run_radon(["radon", "mi", target, "-j", "-e", "*__pycache__*"])
    for filepath, info in mi_data.items():
        mi = info.get("mi", 100.0) if isinstance(info, dict) else (
            info if isinstance(info, (int, float)) else 100.0
        )
        if isinstance(mi, (int, float)):
            if mi < MI_ERR:
                errors.append({"type": "MI", "file": filepath, "value": round(mi, 1), "limit": MI_ERR})
            elif mi < MI_WARN:
                warnings.append({"type": "MI", "file": filepath, "value": round(mi, 1), "limit": MI_WARN})

    # --- Output ---
    total = len(py_files)
    result = {
        "files_scanned": total,
        "errors": len(errors),
        "warnings": len(warnings),
        "details": {"errors": errors, "warnings": warnings},
    }

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'=' * 60}")
        print(f"COMPLEXITY GATE — {total} files scanned")
        print(f"Thresholds: CC fn>{CC_ERR - 1}=err >{CC_WARN - 1}=warn | "
              f"LOC>{LOC_ERR}=err >{LOC_WARN}=warn | MI<{MI_ERR}=err <{MI_WARN}=warn")
        print(f"{'=' * 60}")

        if errors:
            print(f"\nERRORS ({len(errors)}):")
            for e in sorted(errors, key=lambda x: (x["file"], x.get("line", 0))):
                if e["type"] == "CC":
                    print(f"  X CC  {e['file']}:{e['func']} L{e['line']} = {e['value']} (max {e['limit']})")
                elif e["type"] == "LOC":
                    print(f"  X LOC {e['file']} = {e['value']} lines (max {e['limit']})")
                else:
                    print(f"  X MI  {e['file']} = {e['value']} (min {e['limit']})")

        if warnings:
            shown = sorted(warnings, key=lambda x: (x["file"], x.get("line", 0)))[:30]
            print(f"\nWARNINGS ({len(warnings)}):")
            for w in shown:
                if w["type"] == "CC":
                    print(f"  ! CC  {w['file']}:{w['func']} L{w['line']} = {w['value']} (rec <{w['limit']})")
                elif w["type"] == "LOC":
                    print(f"  ! LOC {w['file']} = {w['value']} lines (rec <{w['limit']})")
                else:
                    print(f"  ! MI  {w['file']} = {w['value']} (rec >{w['limit']})")
            if len(warnings) > 30:
                print(f"  ... +{len(warnings) - 30} more")

        flagged = len({e["file"] for e in errors} | {w["file"] for w in warnings})
        clean = total - flagged
        print(f"\n{clean}/{total} files clean")

        if errors:
            print(f"\nRESULT: FAIL ({len(errors)} errors, {len(warnings)} warnings)")
        elif warnings:
            print(f"\nRESULT: WARN ({len(warnings)} warnings)")
        else:
            print(f"\nRESULT: PASS")

    sys.exit(1 if strict and errors else 0)


if __name__ == "__main__":
    main()
