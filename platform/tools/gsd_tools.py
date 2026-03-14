"""
GSD Tools — Get Shit Done meta-prompting and context compression.
=================================================================
SOURCE: https://github.com/gsd-build/get-shit-done (MIT)

WHY: GSD's core insight is that context rot kills agent productivity.
Instead of keeping everything in context, we:
  (1) compress past interactions into structured summaries preserving
      decisions/blockers/progress — reducing token usage by ~60-80%;
  (2) apply meta-prompting templates that guide the LLM toward
      spec-first, test-first, and security-first behavior.

PATTERNS APPLIED:
  - meta-prompting: structured prompt scaffolds that shape LLM behavior
  - progressive context compression: extract signal, discard noise
  - spec-driven development: spec before code, tests before implementation
"""
# Ref: feat-tool-builder

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING

from .registry import BaseTool

if TYPE_CHECKING:
    from ..models import AgentInstance

logger = logging.getLogger(__name__)

# Keyword sets for heuristic extraction
_DECISION_KW = re.compile(
    r"\b(decided|chosen|selected|will use|we use|using)\b", re.IGNORECASE
)
_BLOCKER_KW = re.compile(
    r"\b(blocked|cannot|failed|error|issue|problem)\b", re.IGNORECASE
)
_PROGRESS_KW = re.compile(
    r"\b(done|completed|implemented|created|added|fixed)\b", re.IGNORECASE
)
_NEXT_KW = re.compile(r"\b(next|TODO|should|need to|will|plan)\b", re.IGNORECASE)

_PATTERNS: dict[str, str] = {
    "spec-first": """\
## SPEC
{task_description}

### Inputs
- [ ] Define all inputs and their types

### Outputs
- [ ] Define expected outputs and formats

### Constraints
- [ ] List all constraints and invariants

## IMPLEMENTATION
- Follow the spec above exactly
- No features beyond what the spec defines

## VALIDATION
- [ ] Each spec requirement has a corresponding test
- [ ] Edge cases from constraints are covered
""",
    "test-first": """\
## TEST CASES
Task: {task_description}

### Happy Path
- [ ] Test case 1: (describe input → expected output)

### Edge Cases
- [ ] Empty / null input
- [ ] Boundary values

### Error Cases
- [ ] Invalid input types
- [ ] Out-of-range values

## IMPLEMENTATION CONTRACT
Implement ONLY what makes the tests above pass.
No speculative features.

## ACCEPTANCE
All tests green before merging.
""",
    "security-first": """\
## THREAT MODEL
Task: {task_description}

### Assets
- [ ] What data/resources need protection?

### Threats
- [ ] Who are the adversaries?
- [ ] What attack vectors exist?

### Trust Boundaries
- [ ] Where does untrusted data enter the system?

## MITIGATIONS
- [ ] Input validation for each untrusted source
- [ ] Least-privilege access
- [ ] No secrets in logs or error messages

## IMPLEMENTATION
Implement mitigations above before business logic.
Security is not an afterthought.
""",
    "context-budget": """\
## CONTEXT BUDGET
Task: {task_description}

### Budget Rules
- Max history: last 5 exchanges only
- Checkpoint every 10 turns: summarize → compress → continue
- Never re-read files already processed in this session

### Summary Checkpoint Format
```json
{{
  "decisions": [],
  "progress": [],
  "blockers": [],
  "next_steps": []
}}
```

### Current Context Allocation
- [ ] Task spec: ~200 tokens
- [ ] History summary: ~300 tokens
- [ ] Working memory: ~500 tokens
- [ ] Output budget: remaining

Compress aggressively. Signal over verbosity.
""",
}


class GsdSummarizeContextTool(BaseTool):
    name = "gsd_summarize_context"
    description = (
        "Compress a message history into a structured summary (decisions, blockers, progress, next steps). "
        "Heuristic-based — no LLM call. Reduces context token usage by ~60-80%. "
        "params: messages (list[{role, content}]), focus (str, optional, e.g. 'security'|'architecture'). "
        "Returns JSON: {summary, decisions, blockers, progress, next_steps, token_reduction}."
    )
    category = "productivity"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        messages = params.get("messages", [])
        if isinstance(messages, str):
            try:
                messages = json.loads(messages)
            except Exception:
                return json.dumps(
                    {"error": "messages must be a JSON list of {role, content}"}
                )

        focus = params.get("focus", "")

        decisions: list[str] = []
        blockers: list[str] = []
        progress: list[str] = []
        next_steps: list[str] = []
        summary = ""

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""

            if role == "assistant" and not summary:
                summary = content[:200].replace("\n", " ").strip()

            for line in content.splitlines():
                line = line.strip()
                if not line:
                    continue
                if _DECISION_KW.search(line) and len(decisions) < 5:
                    decisions.append(line[:150])
                if _BLOCKER_KW.search(line) and len(blockers) < 5:
                    blockers.append(line[:150])
                if _PROGRESS_KW.search(line) and len(progress) < 5:
                    progress.append(line[:150])
                if _NEXT_KW.search(line) and len(next_steps) < 5:
                    next_steps.append(line[:150])

        # Rough token estimation: ~4 chars per token
        total_chars = sum(len(m.get("content", "")) for m in messages)
        summary_chars = len(summary) + sum(
            len(s) for s in decisions + blockers + progress + next_steps
        )
        reduction_pct = (
            round((1 - summary_chars / total_chars) * 100) if total_chars > 0 else 0
        )

        if focus:
            summary = f"[Focus: {focus}] " + summary

        return json.dumps(
            {
                "summary": summary or "(no assistant messages found)",
                "decisions": decisions,
                "blockers": blockers,
                "progress": progress,
                "next_steps": next_steps,
                "token_reduction": f"estimated {reduction_pct}% reduction",
            }
        )


class GsdApplyPatternsTool(BaseTool):
    name = "gsd_apply_patterns"
    description = (
        "Return a structured meta-prompt template for a given development pattern. "
        "params: task_description (str), pattern (str, default 'spec-first', "
        "options: spec-first|test-first|security-first|context-budget). "
        "Returns a filled prompt template string ready to prepend to an agent prompt."
    )
    category = "productivity"

    async def execute(self, params: dict, agent: "AgentInstance" = None) -> str:
        task_description = params.get("task_description", "")
        pattern = params.get("pattern", "spec-first")

        if pattern not in _PATTERNS:
            pattern = "spec-first"

        template = _PATTERNS[pattern]
        try:
            filled = template.format(
                task_description=task_description or "(no description provided)"
            )
        except Exception as exc:
            logger.error("gsd_apply_patterns template error: %s", exc)
            filled = template

        return filled


def register_gsd_tools(registry) -> None:
    registry.register(GsdSummarizeContextTool())
    registry.register(GsdApplyPatternsTool())
    logger.debug("GSD tools registered (2 tools)")
