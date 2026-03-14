"""Code simplification endpoint — parallel 3-agent analysis of a git diff."""

from __future__ import annotations

import asyncio
import json
import logging

from fastapi import Depends,  APIRouter
from fastapi.responses import JSONResponse
from ....auth.middleware import require_auth

router = APIRouter()
logger = logging.getLogger(__name__)

AXES = ("reuse", "quality", "efficiency")

# ── Prompts for each analysis axis ───────────────────────────────────────────

_SYSTEM = """You are a senior software engineer performing a focused code review.
Analyze ONLY the git diff provided. Return a JSON array of findings.

Each finding:
{
  "file": "path/to/file.py",
  "line": 42,           // approximate line in the NEW file (0 if unknown)
  "category": "...",    // axis-specific (see instructions)
  "severity": "high|medium|low",
  "message": "One sentence description of the issue",
  "suggestion": "Concrete fix or refactoring recommendation"
}

Rules:
- Return ONLY valid JSON (array). No markdown, no prose.
- Skip cosmetic/style issues (spacing, quotes). Focus on substance.
- If nothing to report, return [].
- Max 10 findings per analysis.
"""

_PROMPTS = {
    "reuse": (
        "AXIS: Code Reuse & Duplication\n"
        "Find: duplicated logic that could be extracted, identical patterns repeated 2+ times, "
        "helper functions that already exist elsewhere being re-implemented, "
        "copy-pasted blocks with minor variations.\n"
        "Category values: 'duplication' | 'extractable' | 'reimplemented'"
    ),
    "quality": (
        "AXIS: Code Quality & Readability\n"
        "Find: unclear variable/function names, functions doing too many things (SRP violation), "
        "dead code added in this diff, overly complex conditionals, missing error handling.\n"
        "Category values: 'naming' | 'complexity' | 'dead-code' | 'error-handling' | 'structure'"
    ),
    "efficiency": (
        "AXIS: Efficiency & Performance\n"
        "Find: unnecessary loops or re-computation, N+1 query patterns, "
        "redundant operations (sorting already-sorted data, etc.), "
        "memory leaks (unclosed resources), unnecessarily blocking I/O.\n"
        "Category values: 'n+1' | 'redundant-op' | 'memory' | 'blocking-io' | 'complexity'"
    ),
}


async def _analyze_axis(diff: str, axis: str) -> list[dict]:
    """Run one analysis axis against the diff."""
    from ....llm.client import LLMMessage, get_llm_client

    prompt = _PROMPTS[axis]
    user_msg = f"{prompt}\n\nGIT DIFF:\n```\n{diff[:12000]}\n```"

    try:
        client = get_llm_client()
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=user_msg)],
            system_prompt=_SYSTEM,
            temperature=0.1,
            max_tokens=2048,
        )
        content = resp.content.strip()
        # Strip markdown fences if present
        if content.startswith("```"):
            content = content.split("```", 2)[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.rsplit("```", 1)[0]
        findings = json.loads(content)
        if not isinstance(findings, list):
            return []
        # Annotate each finding with its axis
        for f in findings:
            f["axis"] = axis
        return findings
    except Exception as e:
        logger.warning("simplify axis=%s error: %s", axis, e)
        return []


@router.post("/api/simplify", dependencies=[Depends(require_auth())])
async def simplify_code(request: dict):
    """Analyze a git diff with 3 parallel agents (reuse, quality, efficiency).

    Body: {diff: str, project?: str, focus?: ["reuse", "quality", "efficiency"]}
    Returns: {findings: [...], stats: {total, by_axis, by_severity}}
    """
    diff = request.get("diff", "").strip()
    focus = request.get("focus") or list(AXES)

    if not diff:
        return JSONResponse({"error": "diff is required"}, status_code=400)

    if len(diff) > 60000:
        diff = diff[:60000]  # Truncate very large diffs

    # Run selected axes in parallel
    axes = [a for a in focus if a in _PROMPTS]
    if not axes:
        return JSONResponse({"error": "no valid focus axes"}, status_code=400)

    results = await asyncio.gather(*[_analyze_axis(diff, ax) for ax in axes])

    all_findings = []
    for findings in results:
        all_findings.extend(findings)

    # Sort: high → medium → low, then by file
    _sev_order = {"high": 0, "medium": 1, "low": 2}
    all_findings.sort(
        key=lambda f: (_sev_order.get(f.get("severity", "low"), 2), f.get("file", ""))
    )

    # Stats
    by_axis = {}
    by_severity = {"high": 0, "medium": 0, "low": 0}
    for f in all_findings:
        ax = f.get("axis", "unknown")
        by_axis[ax] = by_axis.get(ax, 0) + 1
        sev = f.get("severity", "low")
        by_severity[sev] = by_severity.get(sev, 0) + 1

    return JSONResponse(
        {
            "findings": all_findings,
            "stats": {
                "total": len(all_findings),
                "by_axis": by_axis,
                "by_severity": by_severity,
            },
        }
    )
