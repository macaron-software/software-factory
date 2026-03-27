"""Agent Bench Tools — deterministic + LLM-as-judge eval harness for SF agents.

Design principles:
  - PG only (get_db from migrations — no SQLite fallback, no second DB)
  - Isolated Docker workspace per bench run (Platform Bubble pattern)
    → agent tool calls (code_write, git, build…) run INSIDE a fresh container
    → bench container is ephemeral: created, used, destroyed
    → SF data and codebase are never touched
  - Darwin/Thompson feedback via existing team_fitness + agent_scores tables

New check types (beyond skill_eval):
  tool_called:<name>       agent must have called this tool at least once
  tool_not_called:<name>   agent must NOT have called this tool (specialization guard)
  tool_count_min:<n>       agent made >= N total tool calls

Benchmark YAML (platform/agents/benchmarks/{agent_id}.yaml):
  agent_id: dev
  technology: generic       # Darwin technology key
  phase_type: development   # Darwin phase_type
  description: Generic developer TDD discipline
  eval_cases:
    - id: tdd-email
      input: "Implement validate_email(email) using TDD"
      checks:
        - tool_called:code_write
        - has_keyword:def test_
        - tool_not_called:cargo
      expectations:
        - "Writes test first before implementation"
        - "No stubs or hardcoded returns"

Darwin feedback weight: 0.3 (bench is cheaper signal than real mission = 1.0)
"""
# Ref: feat-evals

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ..config import DATA_DIR, PLATFORM_ROOT

logger = logging.getLogger(__name__)

BENCH_RESULTS_DIR = DATA_DIR / "agent_bench"
BENCH_DEFS_DIR = PLATFORM_ROOT / "agents" / "benchmarks"
BENCH_SYNTHETIC_WEIGHT = 0.3  # vs real mission = 1.0
DEFAULT_TRIALS = 1
BENCH_PASS_THRESHOLD = 0.6
BENCH_CONTAINER_IMAGE = "python:3.12-slim"  # default isolation image

# Tools an agent is allowed to call during a bench run.
# Excludes bash, deploy_*, build_*, git_push, docker_* — anything that could
# touch production infrastructure or execute arbitrary host commands.
BENCH_SAFE_TOOLS: list[str] = [
    "code_write",
    "code_read",
    "code_edit",
    "code_search",
    "file_read",
    "file_write",
    "file_list",
    "read_file",
    "write_file",
    "edit_file",
    "list_files",
    "memory_read",
    "memory_write",
]


@contextlib.contextmanager
def _bench_sandbox_ctx(workspace: str):
    """Temporarily enable Docker sandbox isolation for a bench case.

    Patches sandbox.SANDBOX_ENABLED=True so that BashTool routes all
    subprocess calls through 'docker run --rm --network none -m 512m'.
    Falls back gracefully when Docker is unavailable.
    """
    try:
        from . import sandbox as _sb  # late import — module must exist

        prev_enabled = _sb.SANDBOX_ENABLED
        prev_volume = getattr(_sb, "SANDBOX_WORKSPACE_VOLUME", "")
        _sb.SANDBOX_ENABLED = True
        _sb.SANDBOX_WORKSPACE_VOLUME = workspace
        try:
            yield
        finally:
            _sb.SANDBOX_ENABLED = prev_enabled
            _sb.SANDBOX_WORKSPACE_VOLUME = prev_volume
    except ImportError:
        # sandbox module not available — yield unprotected (safe_tools still applies)
        yield


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class BenchCheckResult:
    spec: str
    label: str
    passed: bool
    notes: str = ""


@dataclass
class IterationRecord:
    """One attempt in an iterative refinement loop."""

    iteration: int
    score: float
    judge_notes: str
    output_excerpt: str = ""
    tokens: int = 0
    latency_ms: float = 0.0


@dataclass
class BenchCaseResult:
    case_id: str
    check_pass_rate: float = 0.0
    judge_score: float = -1.0
    overall: float = 0.0
    tool_calls_made: list[str] = field(default_factory=list)
    check_details: list[BenchCheckResult] = field(default_factory=list)
    judge_notes: str = ""
    output_excerpt: str = ""
    tokens: int = 0
    latency_ms: float = 0.0
    error: str = ""
    iterations: list[IterationRecord] = field(default_factory=list)
    iterations_used: int = 1


@dataclass
class AgentBenchResult:
    agent_id: str
    bench_file: str
    technology: str
    phase_type: str
    pass_rate: float = 0.0
    avg_checks: float = 0.0
    avg_judge: float = -1.0
    avg_overall: float = 0.0
    case_results: list[BenchCaseResult] = field(default_factory=list)
    cases_total: int = 0
    ran_at: str = ""
    duration_s: float = 0.0
    status: str = "ok"
    error: str = ""
    darwin_updated: bool = False
    workspace: str = ""  # temp docker workspace used


# ── YAML loaders ──────────────────────────────────────────────────────────────


def list_benchmarks() -> list[dict[str, Any]]:
    """All benchmark YAML files with last result metadata."""
    BENCH_DEFS_DIR.mkdir(parents=True, exist_ok=True)
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result = []
    for yf in sorted(BENCH_DEFS_DIR.glob("*.yaml")):
        try:
            fm = yaml.safe_load(yf.read_text()) or {}
        except Exception:
            continue
        agent_id = fm.get("agent_id", yf.stem)
        last = _load_last_result(agent_id)
        result.append(
            {
                "agent_id": agent_id,
                "bench_file": yf.name,
                "technology": fm.get("technology", "generic"),
                "phase_type": fm.get("phase_type", "generic"),
                "description": fm.get("description", ""),
                "eval_cases": len(fm.get("eval_cases", [])),
                "last_ran": last.get("ran_at") if last else None,
                "last_pass_rate": last.get("pass_rate") if last else None,
                "last_avg_overall": last.get("avg_overall") if last else None,
                "last_status": last.get("status") if last else None,
            }
        )
    return result


def load_bench_def(agent_id: str) -> dict:
    path = BENCH_DEFS_DIR / f"{agent_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"No benchmark for agent '{agent_id}' ({path})")
    return yaml.safe_load(path.read_text()) or {}


def load_bench_result(agent_id: str) -> dict | None:
    return _load_last_result(agent_id)


def bench_coverage_summary() -> dict[str, Any]:
    benchmarks = list_benchmarks()
    total = len(benchmarks)
    with_results = sum(1 for b in benchmarks if b.get("last_ran"))
    avg = sum(
        b["last_pass_rate"] for b in benchmarks if b.get("last_pass_rate") is not None
    ) / max(1, with_results)
    return {
        "total_benchmarks": total,
        "with_results": with_results,
        "without_results": total - with_results,
        "avg_pass_rate": round(avg, 3),
        "benchmarks": benchmarks,
    }


def _load_last_result(agent_id: str) -> dict | None:
    path = BENCH_RESULTS_DIR / f"{agent_id}.json"
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except Exception:
        return None


def _save_result(agent_id: str, result: AgentBenchResult) -> None:
    BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    data = {
        "agent_id": result.agent_id,
        "bench_file": result.bench_file,
        "technology": result.technology,
        "phase_type": result.phase_type,
        "pass_rate": round(result.pass_rate, 3),
        "avg_checks": round(result.avg_checks, 3),
        "avg_judge": round(result.avg_judge, 3),
        "avg_overall": round(result.avg_overall, 3),
        "cases_total": result.cases_total,
        "ran_at": result.ran_at,
        "duration_s": round(result.duration_s, 1),
        "status": result.status,
        "error": result.error,
        "darwin_updated": result.darwin_updated,
        "workspace": result.workspace,
        "case_results": [
            {
                "case_id": c.case_id,
                "check_pass_rate": c.check_pass_rate,
                "judge_score": c.judge_score,
                "overall": c.overall,
                "tool_calls_made": c.tool_calls_made,
                "check_details": [
                    {"spec": ch.spec, "passed": ch.passed, "notes": ch.notes}
                    for ch in c.check_details
                ],
                "judge_notes": c.judge_notes,
                "output_excerpt": c.output_excerpt[:500],
                "tokens": c.tokens,
                "latency_ms": round(c.latency_ms, 1),
                "error": c.error,
                "iterations_used": c.iterations_used,
                "iterations": [
                    {
                        "iteration": it.iteration,
                        "score": round(it.score, 3),
                        "judge_notes": it.judge_notes,
                        "tokens": it.tokens,
                        "latency_ms": round(it.latency_ms, 1),
                    }
                    for it in c.iterations
                ],
            }
            for c in result.case_results
        ],
    }
    (BENCH_RESULTS_DIR / f"{agent_id}.json").write_text(json.dumps(data, indent=2))


# ── Deterministic checks ──────────────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(
    r"\bTODO\b|\bFIXME\b|\bPLACEHOLDER\b|\bNOT IMPLEMENTED\b|\.\.\.", re.IGNORECASE
)


def _run_check(spec: str, output: str, tool_calls: list[str]) -> BenchCheckResult:
    """Run one deterministic check against output + list of tool names called."""
    if ":" not in spec:
        if spec.strip().lower() == "no_placeholder":
            ok = not bool(_PLACEHOLDER_RE.search(output))
            return BenchCheckResult(
                spec, spec, ok, "Clean" if ok else "Placeholder found"
            )
        return BenchCheckResult(spec, spec, False, f"Invalid spec: {spec!r}")

    kind, _, arg = spec.partition(":")
    kind, arg = kind.strip().lower(), arg.strip()

    try:
        if kind == "tool_called":
            ok = arg in tool_calls
            return BenchCheckResult(
                spec,
                spec,
                ok,
                f"tool '{arg}' {'called ✓' if ok else f'NOT called ✗ (called: {tool_calls[:6]})'}",
            )

        if kind == "tool_not_called":
            ok = arg not in tool_calls
            return BenchCheckResult(
                spec,
                spec,
                ok,
                f"tool '{arg}' {'absent ✓' if ok else 'CALLED ✗ (specialization violation)'}",
            )

        if kind == "tool_count_min":
            n = int(arg)
            ok = len(tool_calls) >= n
            return BenchCheckResult(
                spec, spec, ok, f"{len(tool_calls)} tool calls {'≥' if ok else '<'} {n}"
            )

        if kind == "has_keyword":
            ok = arg.lower() in output.lower()
            return BenchCheckResult(
                spec, spec, ok, f"Keyword '{arg}' {'found ✓' if ok else 'NOT found ✗'}"
            )

        if kind == "not_regex":
            ok = not bool(re.search(arg, output, re.IGNORECASE | re.DOTALL))
            return BenchCheckResult(
                spec,
                spec,
                ok,
                f"Pattern '{arg[:40]}' {'absent ✓' if ok else 'MATCHED ✗'}",
            )

        if kind == "regex":
            ok = bool(re.search(arg, output, re.IGNORECASE | re.DOTALL))
            return BenchCheckResult(
                spec,
                spec,
                ok,
                f"Pattern '{arg[:40]}' {'matched ✓' if ok else 'not matched ✗'}",
            )

        if kind == "length_min":
            n = int(arg)
            ok = len(output) >= n
            return BenchCheckResult(spec, spec, ok, f"len={len(output)} vs min={n}")

    except Exception as e:
        return BenchCheckResult(spec, spec, False, f"check error: {e}")

    return BenchCheckResult(spec, spec, False, f"Unknown check kind: {kind!r}")


# ── LLM judge ─────────────────────────────────────────────────────────────────


async def _agent_judge(
    agent_description: str,
    prompt: str,
    output: str,
    tool_calls: list[str],
    expectations: list[str],
) -> tuple[float, str]:
    """LLM-as-judge. Returns (score 0.0–1.0, notes string)."""
    if not expectations:
        return -1.0, "no expectations"

    from ..llm.client import LLMClient, LLMMessage

    exp_list = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(expectations))
    tools_line = f"Tools called: {tool_calls}" if tool_calls else "No tools called"
    judge_prompt = f"""You are an evaluator grading an AI agent's response.

AGENT: {agent_description[:200]}
TASK: {prompt}
OUTPUT: {output}
{tools_line}

EXPECTATIONS:
{exp_list}

Reply ONLY with this JSON:
{{"grades":[{{"id":1,"expectation":"...","passed":true/false,"evidence":"brief"}},...],
  "overall_notes":"2-3 sentence summary"}}

Rules: passed=true only when output ACTUALLY satisfies it. Stub/placeholder = FAIL.
"""

    def _parse(raw: str) -> tuple[float, str] | None:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        try:
            d = json.loads(raw)
        except Exception:
            return None
        grades = d.get("grades", [])
        if not grades:
            return None
        passed = sum(1 for g in grades if g.get("passed"))
        score = passed / len(grades)
        notes = d.get("overall_notes", "")
        failed = [g for g in grades if not g.get("passed")]
        if failed:
            notes += " | FAILED: " + "; ".join(
                g.get("evidence", "?") for g in failed[:2]
            )
        return score, notes

    try:
        client = LLMClient()
        _json_fmt = {"type": "json_object"}
        resp = await client.chat(
            [LLMMessage(role="user", content=judge_prompt)],
            temperature=0.1,
            model="gpt-5-mini",
            response_format=_json_fmt,
        )
        logger.info(
            "judge raw (%d chars): %.300s", len(resp.content or ""), resp.content or ""
        )
        parsed = _parse(resp.content)
        if parsed:
            return parsed
        # retry
        resp2 = await client.chat(
            [LLMMessage(role="user", content=judge_prompt + "\nIMPORTANT: JSON only.")],
            temperature=0.1,
            model="gpt-5-mini",
            response_format=_json_fmt,
        )
        logger.info("judge retry raw: %.300s", resp2.content or "")
        return _parse(resp2.content) or (0.5, "unparseable judge response")
    except Exception as e:
        logger.warning("judge failed: %s", e)
        return 0.5, f"judge error: {e}"


async def _taste_judge(
    taste_prompt: str,
    agent_description: str,
    task: str,
    output: str,
    expectations: list[str],
) -> tuple[float, str]:
    """Design taste judge — evaluates aesthetic quality with detailed feedback.

    Uses a custom taste_judge_prompt from the YAML that defines scoring dimensions
    (typography, spacing, color, hierarchy, etc). Returns granular feedback for
    the iteration loop.
    """
    from ..llm.client import LLMClient, LLMMessage

    exp_list = "\n".join(f"{i + 1}. {e}" for i, e in enumerate(expectations))
    prompt = f"""{taste_prompt}

AGENT: {agent_description[:200]}
TASK: {task}
OUTPUT:
{output}

EXPECTATIONS:
{exp_list}

Reply ONLY with this JSON:
{{"dimensions":[
  {{"name":"<dimension name>","score_10":<0-10>,"evidence":"what you observed","suggestion":"how to improve"}}
],
"expectations":[
  {{"id":<n>,"expectation":"...","passed":true/false,"evidence":"brief"}}
],
"overall_score_10":<0-10>,
"overall_notes":"2-3 sentence summary of strengths and weaknesses",
"post_mortem":"if score < 8: explain WHY the design falls short and what mental model is missing"}}

Rules:
- Score each dimension 0-10 (10 = best designs on the web, 5 = generic/mediocre, 0 = broken)
- overall_score_10 = weighted average biased toward weakest dimension (a chain is as strong as its weakest link)
- post_mortem is MANDATORY when overall < 8 — be brutally honest about what's wrong
- passed=true only when output ACTUALLY demonstrates the expectation, not just mentions it
"""

    def _parse(raw: str) -> tuple[float, str] | None:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
        try:
            d = json.loads(raw)
        except Exception:
            return None

        # Extract score (0-10 → 0.0-1.0)
        overall_10 = d.get("overall_score_10", 5)
        score = max(0.0, min(1.0, overall_10 / 10.0))

        # Build rich feedback notes for iteration
        notes_parts = []
        if d.get("overall_notes"):
            notes_parts.append(d["overall_notes"])

        dims = d.get("dimensions", [])
        weak_dims = [dm for dm in dims if dm.get("score_10", 10) < 8]
        if weak_dims:
            notes_parts.append(
                "WEAK DIMENSIONS: "
                + "; ".join(
                    f"{dm['name']}={dm.get('score_10', '?')}/10 → {dm.get('suggestion', '?')}"
                    for dm in weak_dims
                )
            )

        exps = d.get("expectations", [])
        failed_exps = [e for e in exps if not e.get("passed")]
        if failed_exps:
            notes_parts.append(
                "FAILED: " + "; ".join(e.get("evidence", "?") for e in failed_exps[:3])
            )

        if d.get("post_mortem"):
            notes_parts.append(f"POST-MORTEM: {d['post_mortem']}")

        # For overall score, also factor in expectation pass rate
        if exps:
            exp_pass_rate = sum(1 for e in exps if e.get("passed")) / len(exps)
            score = score * 0.6 + exp_pass_rate * 0.4

        return score, " | ".join(notes_parts)

    try:
        client = LLMClient()
        _json_fmt = {"type": "json_object"}
        resp = await client.chat(
            [LLMMessage(role="user", content=prompt)],
            temperature=0.2,
            model="gpt-5-mini",
            response_format=_json_fmt,
        )
        logger.info(
            "taste judge raw (%d chars): %.400s",
            len(resp.content or ""),
            resp.content or "",
        )
        parsed = _parse(resp.content)
        if parsed:
            return parsed
        # retry
        resp2 = await client.chat(
            [
                LLMMessage(
                    role="user", content=prompt + "\nIMPORTANT: JSON only, no markdown."
                )
            ],
            temperature=0.1,
            model="gpt-5-mini",
            response_format=_json_fmt,
        )
        return _parse(resp2.content) or (0.5, "unparseable taste judge")
    except Exception as e:
        logger.warning("taste judge failed: %s", e)
        return 0.5, f"taste judge error: {e}"


# ── Docker workspace isolation ────────────────────────────────────────────────


def _create_bench_workspace(bench_id: str) -> str:
    """Create a temp workspace dir for this bench run inside data/workspaces/ (allowed by code_tools).
    Returns absolute path.
    """
    ws = Path(DATA_DIR) / "workspaces" / bench_id
    ws.mkdir(parents=True, exist_ok=True)
    return str(ws)


def _cleanup_bench_workspace(workspace: str) -> None:
    """Remove the temp workspace after bench. Container was ephemeral, no docker cleanup needed."""
    import shutil

    try:
        if workspace and Path(workspace).exists():
            shutil.rmtree(workspace, ignore_errors=True)
    except Exception:
        pass


# ── Darwin / Thompson feedback (PG) ──────────────────────────────────────────


def _update_darwin_from_bench(
    agent_id: str, technology: str, phase_type: str, bench_score: float
) -> None:
    """Feed bench result into team_fitness (Darwin) and agent_scores (Thompson). PG only."""
    from ..db.migrations import get_db
    from ..patterns.team_selector import update_team_fitness

    won = bench_score >= BENCH_PASS_THRESHOLD
    bench_session = f"bench-{uuid.uuid4().hex[:8]}"

    try:
        with get_db() as db:
            # Darwin: synthetic run (pattern_id='bench' distinguishes from real missions)
            update_team_fitness(
                db,
                agent_id=agent_id,
                pattern_id="bench",
                technology=technology,
                phase_type=phase_type,
                won=won,
                iterations=1,
            )
            # Thompson: agent_scores
            try:
                db.execute(
                    "INSERT INTO agent_scores (agent_id, session_id, accepted, score, source) "
                    "VALUES (?, ?, ?, ?, 'bench')",
                    (agent_id, bench_session, won, bench_score),
                )
            except Exception:
                try:
                    db.execute(
                        "INSERT INTO agent_scores (agent_id, session_id, accepted, score) "
                        "VALUES (?, ?, ?, ?)",
                        (agent_id, bench_session, won, bench_score),
                    )
                except Exception as e2:
                    logger.warning("agent_scores insert failed: %s", e2)
        logger.info(
            "bench→Darwin: %s tech=%s phase=%s score=%.2f won=%s",
            agent_id,
            technology,
            phase_type,
            bench_score,
            won,
        )
    except Exception as e:
        logger.warning("Darwin bench update failed for %s: %s", agent_id, e)


# ── Main runner ───────────────────────────────────────────────────────────────


async def run_agent_bench(
    agent_id: str,
    trials: int = DEFAULT_TRIALS,
    update_darwin: bool = True,
    cleanup_workspace: bool = True,
    bench_file: str = "",
) -> AgentBenchResult:
    """Run the full bench for an agent in an isolated Docker workspace.

    Steps:
      1. Load YAML from platform/agents/benchmarks/{agent_id}.yaml
         (or bench_file if specified — allows multiple benches per agent)
      2. Load AgentDef from PG
      3. Create ephemeral workspace dir (bench uses it as project_path)
      4. For each eval_case:
           a. Run executor.run() with project_path = bench workspace
              → tool calls (code_write etc.) go into the isolated workspace
           b. Deterministic checks on output + tool_calls list
           c. LLM judge on qualitative expectations
      5. Aggregate
      6. Darwin/Thompson feedback → PG
      7. Persist result JSON
      8. Cleanup workspace
    """
    bench_name = bench_file or agent_id
    t0 = time.time()
    bench_id = f"bench-{bench_name}-{uuid.uuid4().hex[:8]}"
    workspace = _create_bench_workspace(bench_id)

    result = AgentBenchResult(
        agent_id=agent_id,
        bench_file=f"{bench_name}.yaml",
        technology="generic",
        phase_type="generic",
        ran_at=_now_iso(),
        workspace=workspace,
    )

    try:
        # ── Load bench def ────────────────────────────────────────────────────
        try:
            bench_def = load_bench_def(bench_name)
        except FileNotFoundError as e:
            result.status, result.error = "error", str(e)
            return result

        result.technology = bench_def.get("technology", "generic")
        result.phase_type = bench_def.get("phase_type", "generic")
        eval_cases = bench_def.get("eval_cases", [])
        agent_description = bench_def.get("description", f"Agent {agent_id}")

        if not eval_cases:
            result.status, result.error = "no_cases", "No eval_cases in benchmark YAML"
            return result

        result.cases_total = len(eval_cases)

        # ── Load agent from PG ────────────────────────────────────────────────
        from ..agents.store import get_agent_store

        store = get_agent_store()
        agent = store.get(agent_id)
        if agent is None:
            result.status = "error"
            result.error = f"Agent '{agent_id}' not found in PG agents table"
            return result

        # Optional provider override for bench (avoids content policy in prod LLM)
        llm_override = bench_def.get("llm_provider_override")
        if llm_override:
            import dataclasses

            _default_models = {
                "minimax": "MiniMax-M2.7",
                "azure-openai": "gpt-5-mini",
                "openai": "gpt-4o-mini",
            }
            override_model = bench_def.get(
                "llm_model_override",
                _default_models.get(llm_override, agent.model),
            )
            agent = dataclasses.replace(
                agent, provider=llm_override, model=override_model
            )
            logger.info(
                "bench %s: provider overridden → %s / %s",
                agent_id,
                llm_override,
                override_model,
            )

        # ── Iteration config (YAML-level defaults) ─────────────────────────
        max_iterations = bench_def.get("max_iterations", 1)
        target_score = bench_def.get("target_score", 0.9)
        taste_judge_prompt = bench_def.get("taste_judge_prompt", "")

        # ── Run cases ─────────────────────────────────────────────────────────
        case_results: list[BenchCaseResult] = []
        all_overalls, all_checks, all_judges = [], [], []

        for case in eval_cases:
            case_id = str(
                case.get("id")
                or case.get("prompt", "")[:30]
                or f"case-{len(case_results)}"
            )
            prompt = str(case.get("input") or case.get("prompt", ""))
            checks_spec: list[str] = case.get("checks", [])
            expectations: list[str] = (
                case.get("expectations") or case.get("expect") or []
            )
            # Per-case iteration override
            case_max_iter = case.get("max_iterations", max_iterations)
            case_target = case.get("target_score", target_score)

            cr = BenchCaseResult(case_id=case_id)
            total_tokens = 0
            total_latency = 0.0
            feedback_notes = ""

            for iteration in range(1, max(2, case_max_iter + 1)):
                try:
                    t_case = time.time()

                    from ..llm.client import LLMClient, LLMMessage

                    _bench_client = LLMClient()
                    _bench_system = f"You are {agent.name}, role: {agent.role}."
                    if agent.description:
                        _bench_system += f" {agent.description}"
                    _bench_system += "\nProvide thorough, actionable analysis. Be specific and concrete."

                    # Build prompt — include feedback from previous iteration
                    if feedback_notes and iteration > 1:
                        iter_prompt = (
                            f"{prompt}\n\n"
                            f"--- FEEDBACK FROM PREVIOUS ATTEMPT (iteration {iteration - 1}) ---\n"
                            f"{feedback_notes}\n"
                            f"--- END FEEDBACK ---\n\n"
                            f"Improve your response based on this feedback. "
                            f"Fix every issue mentioned. Aim for excellence."
                        )
                    else:
                        iter_prompt = prompt

                    _bench_resp = await asyncio.wait_for(
                        _bench_client.chat(
                            [LLMMessage(role="user", content=iter_prompt)],
                            model=agent.model,
                            system_prompt=_bench_system,
                            max_tokens=4096,
                        ),
                        timeout=240.0,
                    )

                    output = _bench_resp.content or ""
                    tool_calls = [
                        tc.function_name
                        for tc in (_bench_resp.tool_calls or [])
                        if tc.function_name
                    ]
                    iter_latency = (time.time() - t_case) * 1000
                    iter_tokens = (_bench_resp.tokens_in or 0) + (
                        _bench_resp.tokens_out or 0
                    )
                    total_tokens += iter_tokens
                    total_latency += iter_latency
                    cr.error = ""

                except asyncio.TimeoutError:
                    output, tool_calls = "", []
                    iter_latency, iter_tokens = 120_000.0, 0
                    cr.error = "timeout"
                    break
                except Exception as e:
                    output, tool_calls = "", []
                    cr.error = str(e)
                    logger.warning(
                        "bench case %s/%s iter %d failed: %s",
                        agent_id,
                        case_id,
                        iteration,
                        e,
                    )
                    break

                # Deterministic checks
                cr.tool_calls_made = tool_calls
                cr.check_details = [
                    _run_check(s, output, tool_calls) for s in checks_spec
                ]
                cr.check_pass_rate = (
                    sum(1 for c in cr.check_details if c.passed) / len(cr.check_details)
                    if cr.check_details
                    else 1.0
                )
                cr.output_excerpt = output[:600]

                # LLM judge
                if expectations and output.strip():
                    if taste_judge_prompt:
                        cr.judge_score, cr.judge_notes = await _taste_judge(
                            taste_judge_prompt,
                            agent_description,
                            prompt,
                            output,
                            expectations,
                        )
                    else:
                        cr.judge_score, cr.judge_notes = await _agent_judge(
                            agent_description,
                            prompt,
                            output,
                            cr.tool_calls_made,
                            expectations,
                        )
                else:
                    cr.judge_score, cr.judge_notes = -1.0, "no expectations"

                cr.overall = (
                    cr.check_pass_rate * 0.60 + cr.judge_score * 0.40
                    if cr.judge_score >= 0
                    else cr.check_pass_rate
                )

                # Record iteration
                cr.iterations.append(
                    IterationRecord(
                        iteration=iteration,
                        score=cr.overall,
                        judge_notes=cr.judge_notes,
                        output_excerpt=output[:300],
                        tokens=iter_tokens,
                        latency_ms=iter_latency,
                    )
                )
                cr.iterations_used = iteration

                # Check if target reached or single-pass mode
                if case_max_iter <= 1 or cr.overall >= case_target:
                    break

                # Prepare feedback for next iteration
                failed_checks = [ch for ch in cr.check_details if not ch.passed]
                feedback_parts = []
                if failed_checks:
                    feedback_parts.append(
                        "Failed checks: "
                        + "; ".join(f"{ch.spec}: {ch.notes}" for ch in failed_checks)
                    )
                if cr.judge_notes:
                    feedback_parts.append(f"Judge feedback: {cr.judge_notes}")
                feedback_parts.append(
                    f"Score: {cr.overall:.2f}/{case_target:.2f} — not good enough yet."
                )
                feedback_notes = "\n".join(feedback_parts)

                logger.info(
                    "bench %s/%s iter %d: score=%.2f (target=%.2f) — retrying",
                    agent_id,
                    case_id,
                    iteration,
                    cr.overall,
                    case_target,
                )
                await asyncio.sleep(1)  # rate limit between iterations

            cr.tokens = total_tokens
            cr.latency_ms = total_latency

            case_results.append(cr)
            all_overalls.append(cr.overall)
            all_checks.append(cr.check_pass_rate)
            if cr.judge_score >= 0:
                all_judges.append(cr.judge_score)

        # ── Aggregate ─────────────────────────────────────────────────────────
        result.case_results = case_results
        result.avg_checks = sum(all_checks) / len(all_checks) if all_checks else 0.0
        result.avg_judge = sum(all_judges) / len(all_judges) if all_judges else -1.0
        result.avg_overall = (
            sum(all_overalls) / len(all_overalls) if all_overalls else 0.0
        )
        result.pass_rate = (
            sum(1 for o in all_overalls if o >= BENCH_PASS_THRESHOLD)
            / len(all_overalls)
            if all_overalls
            else 0.0
        )
        result.duration_s = time.time() - t0
        result.status = "ok"

        # ── Darwin feedback → PG ──────────────────────────────────────────────
        if update_darwin:
            try:
                _update_darwin_from_bench(
                    agent_id, result.technology, result.phase_type, result.avg_overall
                )
                result.darwin_updated = True
            except Exception as e:
                logger.warning("darwin update failed: %s", e)

    finally:
        # ── Cleanup ───────────────────────────────────────────────────────────
        if cleanup_workspace:
            _cleanup_bench_workspace(workspace)
            result.workspace = ""

        _save_result(agent_id, result)

    logger.info(
        "bench done: %s pass_rate=%.0f%% avg_overall=%.2f cases=%d %.1fs",
        agent_id,
        result.pass_rate * 100,
        result.avg_overall,
        result.cases_total,
        result.duration_s,
    )
    return result


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
