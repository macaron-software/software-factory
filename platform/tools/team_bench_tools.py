"""Team Bench Tools — eval harness for agent teams (pattern + composition).

Tests:
  - Which team configuration (agents + pattern) best handles a task
  - Combined output quality (deterministic checks + LLM judge on full output)
  - Darwin feedback per agent in the team (technology × phase_type)

YAML (platform/agents/benchmarks/teams/{team_id}.yaml):
  team_id: brain-dev-seq
  technology: generic
  phase_type: development
  description: Brain plans + Dev implements — sequential
  pattern:
    type: sequential
    agents:
      - id: brain      # agent_id in agents table
      - id: dev
  task: "Plan and implement validate_email() using TDD"
  checks:
    - has_keyword:def test_
    - has_keyword:def validate_email
    - tool_called:code_write
    - length_min:300
  expectations:
    - "Brain produces a clear plan/steps"
    - "Dev implements following the plan with TDD"
"""
# Ref: feat-art

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import yaml

from ..config import DATA_DIR, PLATFORM_ROOT
from .agent_bench_tools import (
    BenchCheckResult,
    _agent_judge,
    _cleanup_bench_workspace,
    _create_bench_workspace,
    _run_check,
)

logger = logging.getLogger(__name__)

TEAM_BENCH_RESULTS_DIR = DATA_DIR / "team_bench"
TEAM_BENCH_DEFS_DIR = PLATFORM_ROOT / "agents" / "benchmarks" / "teams"
TEAM_BENCH_PASS_THRESHOLD = 0.6


# ── Dataclasses ───────────────────────────────────────────────────────────────


@dataclass
class TeamBenchResult:
    team_id: str = ""
    technology: str = "generic"
    phase_type: str = "generic"
    pass_rate: float = 0.0
    avg_checks: float = 0.0
    avg_judge: float = 0.0
    avg_overall: float = 0.0
    combined_output_length: int = 0
    tool_calls_made: list[str] = field(default_factory=list)
    check_details: list[BenchCheckResult] = field(default_factory=list)
    judge_score: float | None = None
    judge_notes: str = ""
    darwin_updated: bool = False
    status: str = "ok"
    error: str = ""
    ran_at: str = ""
    duration_s: float = 0.0


# ── YAML loading ──────────────────────────────────────────────────────────────


def load_team_bench_def(team_id: str) -> dict:
    """Load team benchmark YAML. Raises FileNotFoundError if not found."""
    path = TEAM_BENCH_DEFS_DIR / f"{team_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Team bench YAML not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def list_team_benchmarks() -> list[dict[str, Any]]:
    """Scan team benchmark YAMLs, return metadata list."""
    TEAM_BENCH_DEFS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for path in sorted(TEAM_BENCH_DEFS_DIR.glob("*.yaml")):
        try:
            d = yaml.safe_load(path.read_text())
            last = _load_last_team_result(d.get("team_id", path.stem))
            results.append(
                {
                    "team_id": d.get("team_id", path.stem),
                    "bench_file": path.name,
                    "technology": d.get("technology", "generic"),
                    "phase_type": d.get("phase_type", "generic"),
                    "description": d.get("description", ""),
                    "pattern_type": d.get("pattern", {}).get("type", "sequential"),
                    "agents": [a["id"] for a in d.get("pattern", {}).get("agents", [])],
                    "checks_count": len(d.get("checks", [])),
                    "last_ran": last.get("ran_at") if last else None,
                    "last_pass_rate": last.get("pass_rate") if last else None,
                    "last_avg_overall": last.get("avg_overall") if last else None,
                    "last_status": last.get("status") if last else None,
                }
            )
        except Exception as e:
            logger.warning("team bench YAML parse error %s: %s", path.name, e)
    return results


def load_team_bench_result(team_id: str) -> dict | None:
    """Load last stored result for team_id."""
    return _load_last_team_result(team_id)


def team_bench_coverage_summary() -> dict[str, Any]:
    benchmarks = list_team_benchmarks()
    with_results = [b for b in benchmarks if b["last_ran"] is not None]
    return {
        "total_benchmarks": len(benchmarks),
        "with_results": len(with_results),
        "without_results": len(benchmarks) - len(with_results),
        "avg_pass_rate": (
            sum(b["last_pass_rate"] for b in with_results) / len(with_results)
            if with_results
            else 0.0
        ),
        "benchmarks": benchmarks,
    }


def _load_last_team_result(team_id: str) -> dict | None:
    TEAM_BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = TEAM_BENCH_RESULTS_DIR / f"{team_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _save_team_result(team_id: str, result: TeamBenchResult) -> None:
    TEAM_BENCH_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = TEAM_BENCH_RESULTS_DIR / f"{team_id}.json"
    data = {
        "team_id": result.team_id,
        "technology": result.technology,
        "phase_type": result.phase_type,
        "pass_rate": result.pass_rate,
        "avg_checks": result.avg_checks,
        "avg_judge": result.avg_judge,
        "avg_overall": result.avg_overall,
        "combined_output_length": result.combined_output_length,
        "tool_calls_made": result.tool_calls_made,
        "check_details": [
            {"spec": c.spec, "passed": c.passed, "notes": c.notes}
            for c in result.check_details
        ],
        "judge_score": result.judge_score,
        "judge_notes": result.judge_notes,
        "darwin_updated": result.darwin_updated,
        "status": result.status,
        "error": result.error,
        "ran_at": result.ran_at,
        "duration_s": result.duration_s,
    }
    path.write_text(json.dumps(data, indent=2))


# ── Bench runner ──────────────────────────────────────────────────────────────


async def run_team_bench(
    team_id: str,
    update_darwin: bool = True,
) -> TeamBenchResult:
    """Run team bench: construct PatternDef → run_pattern → checks + judge."""
    t0 = time.time()
    result = TeamBenchResult(
        team_id=team_id,
        ran_at=datetime.now(timezone.utc).isoformat(),
    )

    try:
        defn = load_team_bench_def(team_id)
    except FileNotFoundError as e:
        result.status = "error"
        result.error = str(e)
        return result

    result.technology = defn.get("technology", "generic")
    result.phase_type = defn.get("phase_type", "generic")
    task = defn.get("task", "")
    checks_specs = defn.get("checks", [])
    expectations = defn.get("expectations", [])
    pattern_cfg = defn.get("pattern", {})
    agent_ids = [a["id"] for a in pattern_cfg.get("agents", [])]

    bench_id = f"teambench-{team_id}-{uuid.uuid4().hex[:8]}"
    workspace = _create_bench_workspace(bench_id)
    # Inject workspace path so agents know where to write files
    task_with_ctx = f"{task}\n\nWorkspace: {workspace}\nWrite all files using code_write with paths relative to this workspace."

    try:
        # Run pattern with fixed agent list
        combined_output, tool_calls = await _run_team_pattern(
            pattern_cfg=pattern_cfg,
            agent_ids=agent_ids,
            task=task_with_ctx,
            workspace=workspace,
            bench_id=bench_id,
            technology=result.technology,
            phase_type=result.phase_type,
        )

        result.combined_output_length = len(combined_output)
        result.tool_calls_made = tool_calls

        # Deterministic checks on combined output
        check_results = [
            _run_check(spec, combined_output, tool_calls) for spec in checks_specs
        ]
        result.check_details = check_results
        checks_passed = sum(1 for c in check_results if c.passed)
        avg_checks = checks_passed / len(check_results) if check_results else 0.0
        result.avg_checks = round(avg_checks, 4)

        # LLM judge on combined output
        avg_judge = None
        if expectations and combined_output.strip():
            judge_result = await _agent_judge(
                agent_description=f"Team: {' + '.join(agent_ids)} ({pattern_cfg.get('type', 'sequential')})",
                prompt=task,
                output=combined_output,
                tool_calls=tool_calls,
                expectations=expectations,
            )
            if judge_result:
                avg_judge, judge_notes = judge_result
                result.judge_score = avg_judge
                result.judge_notes = judge_notes

        # Combined overall score
        if avg_judge is not None:
            avg_overall = avg_checks * 0.6 + avg_judge * 0.4
        else:
            avg_overall = avg_checks
        result.avg_overall = round(avg_overall, 4)
        result.avg_judge = round(avg_judge or 0.0, 4)
        result.pass_rate = 1.0 if avg_overall >= TEAM_BENCH_PASS_THRESHOLD else 0.0

        # Darwin feedback — record per agent
        if update_darwin and agent_ids:
            from .agent_bench_tools import _update_darwin_from_bench

            for agent_id in agent_ids:
                _update_darwin_from_bench(
                    agent_id=agent_id,
                    technology=result.technology,
                    phase_type=result.phase_type,
                    bench_score=avg_overall,
                )
            result.darwin_updated = True

    except Exception as e:
        logger.error("run_team_bench %s error: %s", team_id, e, exc_info=True)
        result.status = "error"
        result.error = str(e)
    finally:
        _cleanup_bench_workspace(workspace)

    result.duration_s = round(time.time() - t0, 2)
    _save_team_result(team_id, result)
    return result


async def _run_team_pattern(
    pattern_cfg: dict,
    agent_ids: list[str],
    task: str,
    workspace: str,
    bench_id: str,
    technology: str,
    phase_type: str,
) -> tuple[str, list[str]]:
    """Run agents sequentially with direct LLM calls (no executor/pattern engine).

    Each agent receives the task + accumulated output from prior agents.
    This avoids the executor's massive system prompt that triggers Azure
    content policy blocks on bench runs.
    """
    import asyncio

    from ..agents.store import get_agent_store
    from ..llm.client import LLMClient, LLMMessage

    agent_store = get_agent_store()
    client = LLMClient()

    combined_parts: list[str] = []
    all_tool_calls: list[str] = []

    for i, agent_id in enumerate(agent_ids):
        agent = agent_store.get(agent_id)
        if not agent:
            combined_parts.append(f"[Agent {agent_id} not found]")
            continue

        # Build system prompt: minimal (agent identity only)
        sys_prompt = f"You are {agent.name}, role: {agent.role}."
        if agent.description:
            sys_prompt += f" {agent.description}"
        sys_prompt += (
            "\nProvide thorough, actionable analysis. Be specific and concrete."
        )

        # Build user message: task + prior agents' output
        user_content = task
        if combined_parts:
            prior = "\n---\n".join(combined_parts)
            user_content = (
                f"Previous agents output:\n{prior}\n\n---\n\n"
                f"Your task (continue from above):\n{task}"
            )

        try:
            resp = await asyncio.wait_for(
                client.chat(
                    [LLMMessage(role="user", content=user_content)],
                    model=agent.model,
                    system_prompt=sys_prompt,
                    max_tokens=4096,
                ),
                timeout=240.0,
            )
            output = resp.content or ""
            # Collect tool calls if any
            for tc in resp.tool_calls or []:
                if tc.function_name:
                    all_tool_calls.append(tc.function_name)
        except asyncio.TimeoutError:
            output = f"[Agent {agent_id} timed out]"
        except Exception as e:
            output = f"[Agent {agent_id} error: {e}]"
            logger.warning("team bench agent %s failed: %s", agent_id, e)

        combined_parts.append(f"=== {agent.name} ({agent_id}) ===\n{output}")

    return "\n\n".join(combined_parts), all_tool_calls
