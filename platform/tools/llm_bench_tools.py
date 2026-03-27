"""AC LLM Bench — verify each model responds correctly with adapted parameters.

Tests 8 capabilities per model:
  basic-text, json-output, code-generation, reasoning-quality,
  long-output, no-think-leak, structured-json, minimal-prompt

Usage:
    from platform.tools.llm_bench_tools import run_llm_bench, run_all_llm_bench
    result = await run_llm_bench("gpt-5-mini", "azure-openai")
    all_results = await run_all_llm_bench()
"""
# Ref: feat-evals

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

BENCH_DIR = Path(__file__).resolve().parent.parent / "agents" / "benchmarks"
BENCH_FILE = "llm-models.yaml"


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class LLMCheckResult:
    spec: str
    passed: bool
    notes: str = ""


@dataclass
class LLMCaseResult:
    case_id: str
    model: str
    provider: str
    passed: bool
    checks_passed: int = 0
    checks_total: int = 0
    check_details: list[dict] = field(default_factory=list)
    output_excerpt: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    error: str = ""


@dataclass
class LLMBenchResult:
    model: str
    provider: str
    cases: list[LLMCaseResult] = field(default_factory=list)
    pass_rate: float = 0.0
    total_tokens: int = 0
    total_latency_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "model": self.model,
            "provider": self.provider,
            "pass_rate": round(self.pass_rate, 2),
            "cases_passed": sum(1 for c in self.cases if c.passed),
            "cases_total": len(self.cases),
            "total_tokens": self.total_tokens,
            "total_latency_ms": self.total_latency_ms,
            "cases": [
                {
                    "id": c.case_id,
                    "passed": c.passed,
                    "checks": f"{c.checks_passed}/{c.checks_total}",
                    "tokens": c.tokens_in + c.tokens_out,
                    "latency_ms": c.latency_ms,
                    "error": c.error or None,
                    "details": c.check_details,
                }
                for c in self.cases
            ],
        }


# ── Check runner ──────────────────────────────────────────────────────────────


def _run_check(spec: str, output: str) -> LLMCheckResult:
    """Run a single deterministic check against LLM output."""
    if ":" not in spec:
        if spec.strip().lower() == "valid_json":
            try:
                json.loads(output)
                return LLMCheckResult(spec, True, "Valid JSON ✓")
            except (json.JSONDecodeError, TypeError):
                # Try to extract JSON from markdown fences
                m = re.search(r"```(?:json)?\s*\n(.*?)```", output, re.DOTALL)
                if m:
                    try:
                        json.loads(m.group(1))
                        return LLMCheckResult(spec, True, "Valid JSON (in fence) ✓")
                    except Exception:
                        pass
                return LLMCheckResult(spec, False, f"Invalid JSON ✗")
        return LLMCheckResult(spec, False, f"Unknown check: {spec}")

    kind, _, arg = spec.partition(":")
    kind, arg = kind.strip().lower(), arg.strip()

    if kind == "has_keyword":
        ok = arg.lower() in output.lower()
        return LLMCheckResult(spec, ok, f"'{arg}' {'found ✓' if ok else 'NOT found ✗'}")

    if kind == "not_contains":
        ok = arg.lower() not in output.lower()
        return LLMCheckResult(spec, ok, f"'{arg}' {'absent ✓' if ok else 'PRESENT ✗'}")

    if kind == "regex":
        ok = bool(re.search(arg, output, re.IGNORECASE | re.DOTALL))
        return LLMCheckResult(spec, ok, f"Pattern '{arg[:40]}' {'matched ✓' if ok else 'NOT matched ✗'}")

    if kind == "not_regex":
        ok = not bool(re.search(arg, output, re.IGNORECASE | re.DOTALL))
        return LLMCheckResult(spec, ok, f"Pattern '{arg[:40]}' {'absent ✓' if ok else 'MATCHED ✗'}")

    if kind == "length_min":
        n = int(arg)
        ok = len(output) >= n
        return LLMCheckResult(spec, ok, f"len={len(output)} {'≥' if ok else '<'} {n}")

    if kind == "length_max":
        n = int(arg)
        ok = len(output) <= n
        return LLMCheckResult(spec, ok, f"len={len(output)} {'≤' if ok else '>'} {n}")

    if kind == "json_has_key":
        try:
            raw = output
            m = re.search(r"```(?:json)?\s*\n(.*?)```", output, re.DOTALL)
            if m:
                raw = m.group(1)
            data = json.loads(raw)
            ok = arg in data if isinstance(data, dict) else False
            return LLMCheckResult(spec, ok, f"Key '{arg}' {'present ✓' if ok else 'missing ✗'}")
        except Exception as e:
            return LLMCheckResult(spec, False, f"JSON parse error: {e}")

    if kind == "not_empty":
        ok = len(output.strip()) > 0
        return LLMCheckResult(spec, ok, "Output non-empty ✓" if ok else "Output EMPTY ✗")

    return LLMCheckResult(spec, False, f"Unknown check kind: {kind}")


# ── Bench loader ──────────────────────────────────────────────────────────────


def _load_bench() -> dict:
    """Load the LLM bench YAML definition."""
    path = BENCH_DIR / BENCH_FILE
    if not path.exists():
        raise FileNotFoundError(f"LLM bench not found: {path}")
    return yaml.safe_load(path.read_text())


# ── Per-model runner ──────────────────────────────────────────────────────────


async def run_llm_bench(
    model: str,
    provider: str,
    cases_filter: list[str] | None = None,
) -> LLMBenchResult:
    """Run LLM bench for a specific model/provider combo.

    Args:
        model: Model name (e.g. "gpt-5-mini", "MiniMax-M2.7")
        provider: Provider name (e.g. "azure-openai", "minimax")
        cases_filter: Optional list of case IDs to run (runs all if None)

    Returns:
        LLMBenchResult with per-case pass/fail details
    """
    from ..llm.client import LLMClient, LLMMessage

    bench = _load_bench()
    eval_cases = bench.get("eval_cases", [])
    if cases_filter:
        eval_cases = [c for c in eval_cases if c["id"] in cases_filter]

    client = LLMClient()
    result = LLMBenchResult(model=model, provider=provider)

    logger.info("AC LLM bench: %s/%s — %d cases", provider, model, len(eval_cases))

    for case in eval_cases:
        case_id = case["id"]
        prompt = case["input"]
        checks = case.get("checks", [])
        system = case.get("system_prompt", "You are a helpful assistant.")

        logger.info("  Case %s ...", case_id)
        t0 = time.monotonic()

        try:
            messages = [
                LLMMessage(role="system", content=system),
                LLMMessage(role="user", content=prompt),
            ]
            kwargs: dict[str, Any] = {
                "messages": messages,
                "provider": provider,
                "model": model,
                "max_tokens": case.get("max_tokens", 4096),
            }
            if case.get("temperature") is not None:
                kwargs["temperature"] = case["temperature"]

            resp = await client.chat(**kwargs)
            elapsed = int((time.monotonic() - t0) * 1000)
            output = resp.content or ""

            check_results = [_run_check(spec, output) for spec in checks]
            passed_count = sum(1 for cr in check_results if cr.passed)

            case_result = LLMCaseResult(
                case_id=case_id,
                model=model,
                provider=provider,
                passed=passed_count == len(check_results),
                checks_passed=passed_count,
                checks_total=len(check_results),
                check_details=[
                    {"spec": cr.spec, "passed": cr.passed, "notes": cr.notes}
                    for cr in check_results
                ],
                output_excerpt=output[:500],
                tokens_in=resp.tokens_in,
                tokens_out=resp.tokens_out,
                latency_ms=elapsed,
            )

        except Exception as e:
            elapsed = int((time.monotonic() - t0) * 1000)
            logger.error("  Case %s FAILED: %s", case_id, e)
            case_result = LLMCaseResult(
                case_id=case_id,
                model=model,
                provider=provider,
                passed=False,
                error=str(e)[:300],
                latency_ms=elapsed,
            )

        status = "✓" if case_result.passed else "✗"
        logger.info(
            "  Case %s %s (%d/%d checks, %dms)",
            case_id, status,
            case_result.checks_passed, case_result.checks_total,
            case_result.latency_ms,
        )
        result.cases.append(case_result)

    # Aggregate
    if result.cases:
        result.pass_rate = sum(1 for c in result.cases if c.passed) / len(result.cases)
        result.total_tokens = sum(c.tokens_in + c.tokens_out for c in result.cases)
        result.total_latency_ms = sum(c.latency_ms for c in result.cases)

    logger.info(
        "AC LLM bench %s/%s: %.0f%% (%d/%d passed, %d tokens, %dms)",
        provider, model,
        result.pass_rate * 100,
        sum(1 for c in result.cases if c.passed),
        len(result.cases),
        result.total_tokens,
        result.total_latency_ms,
    )
    return result


# ── All-models runner ─────────────────────────────────────────────────────────

BENCH_MODELS = [
    {"model": "gpt-5-mini", "provider": "azure-openai"},
    {"model": "gpt-5.2", "provider": "azure-openai"},
    {"model": "gpt-5.2-codex", "provider": "azure-openai"},
    {"model": "MiniMax-M2.7", "provider": "minimax"},
]


async def run_all_llm_bench() -> dict:
    """Run LLM bench across all configured models. Returns summary dict."""
    results = {}
    for entry in BENCH_MODELS:
        model, provider = entry["model"], entry["provider"]
        try:
            r = await run_llm_bench(model, provider)
            results[model] = r.to_dict()
        except Exception as e:
            logger.error("Model %s/%s bench failed: %s", provider, model, e)
            results[model] = {
                "model": model,
                "provider": provider,
                "pass_rate": 0.0,
                "error": str(e)[:200],
            }

    logger.info("\n=== AC LLM Bench Summary ===")
    for model, data in results.items():
        rate = data.get("pass_rate", 0)
        passed = data.get("cases_passed", 0)
        total = data.get("cases_total", 0)
        logger.info("  %s: %.0f%% (%d/%d)", model, rate * 100, passed, total)

    return results
