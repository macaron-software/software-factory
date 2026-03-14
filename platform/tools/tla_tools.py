"""TLA+ formal verification tools.

Provides two agent-callable tools:
  tla_check  -- run the TLC model checker on a specification
  tla_list   -- list available TLA+ specs and their invariants

Container path for TLC JAR: /app/tools/tla2tools.jar
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Resolve formal/ directory relative to this file's location in the repo.
# Layout: platform/tools/tla_tools.py  ->  platform/formal/
_FORMAL_DIR = Path(__file__).resolve().parent.parent / "formal"

# TLC JAR discovery order:
#   1. TLA2TOOLS_JAR env var
#   2. /app/tools/tla2tools.jar  (container default)
#   3. <repo>/tools/tla2tools.jar  (local dev)
_TLC_JAR_CANDIDATES = [
    os.environ.get("TLA2TOOLS_JAR", ""),
    "/app/tools/tla2tools.jar",
    str(Path(__file__).resolve().parent.parent.parent / "tools" / "tla2tools.jar"),
]


def _find_tlc_jar() -> Optional[str]:
    """Return path to tla2tools.jar or None."""
    for candidate in _TLC_JAR_CANDIDATES:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def _parse_cfg_invariants(cfg_path: Path) -> list[str]:
    """Extract INVARIANTS and PROPERTIES entries from a .cfg file."""
    invariants: list[str] = []
    if not cfg_path.exists():
        return invariants
    section: Optional[str] = None
    for line in cfg_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.upper() in ("INVARIANT", "INVARIANTS"):
            section = "invariant"
            continue
        if stripped.upper() in ("PROPERTY", "PROPERTIES"):
            section = "property"
            continue
        if stripped.upper().startswith(("SPECIFICATION", "CONSTANT", "CONSTANTS")):
            section = None
            continue
        if section and stripped and not stripped.startswith("\\*"):
            invariants.append(stripped)
    return invariants


def _parse_constants(cfg_path: Path) -> dict[str, str]:
    """Extract CONSTANTS key = value pairs from a .cfg file."""
    constants: dict[str, str] = {}
    if not cfg_path.exists():
        return constants
    in_constants = False
    for line in cfg_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.upper() in ("CONSTANT", "CONSTANTS"):
            in_constants = True
            continue
        if stripped.upper().startswith(("SPECIFICATION", "INVARIANT", "PROPERTY")):
            in_constants = False
            continue
        if in_constants and "=" in stripped:
            key, _, val = stripped.partition("=")
            constants[key.strip()] = val.strip()
    return constants


# ------------------------------------------------------------------
# tla_list
# ------------------------------------------------------------------

async def run_tla_list(args: dict) -> str:
    """List all TLA+ specs in platform/formal/ with their invariants."""
    if not _FORMAL_DIR.is_dir():
        return "No formal/ directory found."

    tla_files = sorted(_FORMAL_DIR.glob("*.tla"))
    if not tla_files:
        return "No .tla specifications found in platform/formal/."

    lines: list[str] = ["Spec | Invariants | Constants"]
    lines.append("--- | --- | ---")
    for tla in tla_files:
        cfg = tla.with_suffix(".cfg")
        invs = _parse_cfg_invariants(cfg)
        consts = _parse_constants(cfg)
        const_str = ", ".join(f"{k}={v}" for k, v in consts.items()) or "-"
        inv_str = ", ".join(invs) or "(none)"
        lines.append(f"{tla.stem} | {inv_str} | {const_str}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# tla_check
# ------------------------------------------------------------------

async def run_tla_check(args: dict) -> str:
    """Run TLC model checker on a TLA+ specification.

    Args (dict keys):
        spec_path: filename relative to platform/formal/ (e.g. "NodeStateMachine.tla")
        invariant: optional specific invariant name to check
    """
    spec_path_arg = args.get("spec_path", "")
    if not spec_path_arg:
        return "Error: spec_path is required (e.g. 'NodeStateMachine.tla')."

    # Resolve spec file
    spec_file = _FORMAL_DIR / spec_path_arg
    if not spec_file.exists():
        # Try appending .tla
        spec_file = _FORMAL_DIR / (spec_path_arg + ".tla")
    if not spec_file.exists():
        available = [f.name for f in _FORMAL_DIR.glob("*.tla")]
        return f"Error: spec not found: {spec_path_arg}. Available: {available}"

    cfg_file = spec_file.with_suffix(".cfg")
    if not cfg_file.exists():
        return f"Error: configuration file not found: {cfg_file.name}"

    # Find TLC JAR
    tlc_jar = _find_tlc_jar()
    if not tlc_jar:
        return (
            "Error: TLC JAR (tla2tools.jar) not found. "
            "Set TLA2TOOLS_JAR env var or place it at /app/tools/tla2tools.jar. "
            "Download: https://github.com/tlaplus/tlaplus/releases"
        )

    # If a specific invariant is requested, create a temporary cfg
    invariant_filter = args.get("invariant", "")
    effective_cfg = cfg_file
    tmp_cfg: Optional[Path] = None
    if invariant_filter:
        tmp_cfg = spec_file.with_name(f"_tmp_{spec_file.stem}.cfg")
        consts = _parse_constants(cfg_file)
        cfg_lines = ["SPECIFICATION Spec", ""]
        if consts:
            cfg_lines.append("CONSTANTS")
            for k, v in consts.items():
                cfg_lines.append(f"    {k} = {v}")
            cfg_lines.append("")
        # Determine if it's an invariant or property (heuristic: starts with Eventually/liveness => property)
        all_invs = _parse_cfg_invariants(cfg_file)
        if invariant_filter in all_invs:
            # Check in the .tla for temporal operator to classify
            tla_text = spec_file.read_text()
            pattern = rf"^{re.escape(invariant_filter)}\s*==\s*<>"
            if re.search(pattern, tla_text, re.MULTILINE):
                cfg_lines.append("PROPERTIES")
            else:
                cfg_lines.append("INVARIANTS")
            cfg_lines.append(f"    {invariant_filter}")
        else:
            cfg_lines.append("INVARIANTS")
            cfg_lines.append(f"    {invariant_filter}")
        tmp_cfg.write_text("\n".join(cfg_lines))
        effective_cfg = tmp_cfg

    # Run TLC
    cmd = [
        "java", "-jar", tlc_jar,
        "-config", str(effective_cfg),
        "-workers", "auto",
        "-cleanup",
        str(spec_file),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_FORMAL_DIR),
        )
    except FileNotFoundError:
        return "Error: Java runtime not found. TLC requires Java 11+."
    except subprocess.TimeoutExpired:
        return "Error: TLC timed out after 120 seconds. Try reducing constants in .cfg."
    finally:
        if tmp_cfg and tmp_cfg.exists():
            tmp_cfg.unlink()

    stdout = result.stdout
    stderr = result.stderr

    # Parse TLC output
    if result.returncode == 0 and "Model checking completed" in stdout:
        # Extract stats
        states_match = re.search(r"(\d+)\s+states generated", stdout)
        distinct_match = re.search(r"(\d+)\s+distinct states", stdout)
        states = states_match.group(1) if states_match else "?"
        distinct = distinct_match.group(1) if distinct_match else "?"
        return (
            f"All invariants hold for {spec_file.stem}. "
            f"({states} states generated, {distinct} distinct states explored)"
        )

    # Check for invariant violations
    violation_match = re.search(r"Invariant\s+(\w+)\s+is violated", stdout)
    if violation_match:
        inv_name = violation_match.group(1)
        # Extract counterexample trace
        trace_start = stdout.find("Error: Invariant")
        trace = stdout[trace_start:trace_start + 2000] if trace_start >= 0 else ""
        return f"VIOLATION: Invariant {inv_name} violated in {spec_file.stem}.\n\n{trace}"

    # Check for property violations (liveness)
    prop_match = re.search(r"Temporal properties were violated", stdout)
    if prop_match:
        trace_start = stdout.find("Error:")
        trace = stdout[trace_start:trace_start + 2000] if trace_start >= 0 else ""
        return f"VIOLATION: Temporal property violated in {spec_file.stem}.\n\n{trace}"

    # Generic error
    error_output = stderr if stderr else stdout[-2000:]
    return f"TLC returned exit code {result.returncode} for {spec_file.stem}.\n\n{error_output}"


# ------------------------------------------------------------------
# Tool schema definitions (for LLM function calling)
# ------------------------------------------------------------------

TLA_CHECK_SCHEMA = {
    "name": "tla_check",
    "description": (
        "Run the TLC model checker on a TLA+ specification from platform/formal/. "
        "Returns 'All invariants hold' with state count, or a counterexample trace on violation."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "spec_path": {
                "type": "string",
                "description": "Specification filename relative to platform/formal/ (e.g. 'NodeStateMachine.tla')",
            },
            "invariant": {
                "type": "string",
                "description": "Optional: check only this specific invariant or property name",
            },
        },
        "required": ["spec_path"],
    },
}

TLA_LIST_SCHEMA = {
    "name": "tla_list",
    "description": "List all available TLA+ specifications in platform/formal/ with their invariants and constants.",
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
    },
}
