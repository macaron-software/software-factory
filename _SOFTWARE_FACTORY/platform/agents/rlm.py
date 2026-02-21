"""RLM — Recursive Language Model (MIT CSAIL arXiv:2512.24601).

Each project gets an RLM: a main LLM orchestrator that spawns sub-agent
exploration queries in parallel to deeply understand the codebase.

WRITE-EXECUTE-OBSERVE-DECIDE cycle:
1. WRITE: Main LLM generates 1-3 exploration queries
2. EXECUTE: Sub-agents run queries (file read, grep, structure analysis)
3. OBSERVE: Results accumulated as findings
4. DECIDE: Main LLM explores more or emits FINAL_ANSWER
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from typing import Optional

from ..llm.client import LLMMessage, get_llm_client

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 2
MAX_PARALLEL_QUERIES = 2
MAX_FINDINGS_CHARS = 4000


@dataclass
class RLMResult:
    """Result of an RLM deep search."""
    answer: str
    findings: list[str] = field(default_factory=list)
    iterations: int = 0
    total_queries: int = 0


class ProjectRLM:
    """RLM engine for a single project.

    Tier 0 (orchestrator): uses the project's configured LLM (e.g. GPT-5.2, MiniMax)
    Tier 1 (sub-agents): lightweight tool execution (grep, read, structure)
    """

    def __init__(self, project_id: str, project_path: str, project_name: str,
                 provider: str = "minimax", model: str = "MiniMax-M2.5"):
        self.project_id = project_id
        self.project_path = project_path
        self.project_name = project_name
        # RLM always uses MiniMax (fast, no rate limit) for its orchestrator
        self.provider = "minimax"
        self.model = "MiniMax-M2.5"
        self._llm = get_llm_client()

    async def search(self, query: str, context: str = "",
                     max_iterations: int = MAX_ITERATIONS,
                     on_progress: Optional[object] = None) -> RLMResult:
        """Deep recursive search on the project.

        The main LLM orchestrates the loop, sub-agents execute tool queries.
        on_progress: async callable(label: str) for streaming status updates.
        """
        findings: list[str] = []
        total_queries = 0
        print(f"[RLM] Starting search on '{self.project_name}': {query[:80]}", flush=True)

        async def _notify(label: str):
            if on_progress:
                try:
                    await on_progress(label)
                except Exception:
                    pass

        for i in range(max_iterations):
            await _notify(f"Deep search — iteration {i + 1}/{max_iterations}…")
            print(f"[RLM:{self.project_name}] Iteration {i + 1}/{max_iterations}", flush=True)

            # Last iteration → force synthesis, don't ask LLM to decide
            if i == max_iterations - 1 and findings:
                print(f"[RLM:{self.project_name}] Last iteration, forcing synthesis", flush=True)
                break

            # WRITE: Main LLM decides what to explore
            prompt = self._build_iteration_prompt(
                query=query,
                iteration=i,
                max_iterations=max_iterations,
                findings=findings,
                context=context,
            )

            print(f"[RLM:{self.project_name}] Calling LLM orchestrator...", flush=True)
            resp = await self._llm.chat(
                messages=[LLMMessage(role="user", content=prompt)],
                provider=self.provider or None,
                model=self.model or None,
                temperature=0.3,
                max_tokens=1000,
                system_prompt=f"You are the RLM for project '{self.project_name}'. Respond with ONLY valid JSON.",
            )

            if not resp or not resp.content:
                print(f"[RLM:{self.project_name}] Empty response, stopping", flush=True)
                break

            # PARSE: Extract decision
            decision = self._parse_response(resp.content)
            print(f"[RLM:{self.project_name}] Decision: {decision.get('action')}", flush=True)

            # FINAL_ANSWER → done
            if decision["action"] == "final":
                print(f"[RLM:{self.project_name}] FINAL_ANSWER at iteration {i + 1}", flush=True)
                return RLMResult(
                    answer=decision.get("answer", ""),
                    findings=findings,
                    iterations=i + 1,
                    total_queries=total_queries,
                )

            # EXECUTE: Run sub-agent queries in parallel
            queries = decision.get("queries", [])[:MAX_PARALLEL_QUERIES]
            if not queries:
                print(f"[RLM:{self.project_name}] No queries, stopping", flush=True)
                break

            total_queries += len(queries)
            await _notify(f"Exploring codebase ({len(queries)} queries)…")
            print(f"[RLM:{self.project_name}] Running {len(queries)} sub-agents...", flush=True)
            results = await asyncio.gather(*[
                self._execute_subagent(q) for q in queries
            ])

            # OBSERVE: Accumulate findings
            for q, result in zip(queries, results):
                q_text = q.get("query", str(q)) if isinstance(q, dict) else str(q)
                if result:
                    findings.append(f"[iter {i + 1}] Q: {q_text}\nA: {result[:2000]}")

            logger.info("[RLM:%s] %d findings (%d chars)",
                        self.project_name, len(findings),
                        sum(len(f) for f in findings))

        # Max iterations: force synthesis from findings
        await _notify(f"Synthesizing {len(findings)} findings…")
        answer = await self._force_final(query, findings)
        return RLMResult(
            answer=answer,
            findings=findings,
            iterations=max_iterations,
            total_queries=total_queries,
        )

    async def _execute_subagent(self, query: dict) -> Optional[str]:
        """Sub-agent: execute an exploration query using direct tools (no LLM).

        Sub-agents are deterministic — they run grep, read, find, etc.
        No LLM hallucination at this tier.
        """
        if isinstance(query, str):
            query = {"query": query}

        q_text = query.get("query", "")
        files = query.get("files", [])
        tool = query.get("tool", "auto")

        results = []

        # Tool dispatch based on query type
        if tool == "read" and files:
            for f in files[:5]:
                content = self._read_file(f)
                if content:
                    results.append(f"[FILE] {f}:\n{content}")

        elif tool == "grep" or (tool == "auto" and not files):
            # Extract search terms from query
            pattern = query.get("pattern", "")
            if not pattern:
                # Build pattern from query keywords
                words = [w for w in q_text.split() if len(w) > 3][:5]
                pattern = "|".join(words) if words else q_text
            glob_filter = query.get("glob", "")
            grep_result = self._grep(pattern, glob_filter)
            if grep_result:
                results.append(grep_result)

        elif tool == "structure":
            struct = self._get_structure(query.get("path", ""))
            if struct:
                results.append(struct)

        else:
            # Auto: try grep first, then targeted reads
            words = [w for w in q_text.split() if len(w) > 3][:5]
            if words:
                pattern = "|".join(words)
                grep_result = self._grep(pattern, query.get("glob", ""))
                if grep_result:
                    results.append(grep_result)

            # Read specific files if mentioned
            for f in files[:3]:
                content = self._read_file(f)
                if content:
                    results.append(f"[FILE] {f}:\n{content[:1000]}")

        return "\n\n".join(results) if results else None

    def _read_file(self, path: str, max_lines: int = 200) -> Optional[str]:
        """Read a file from the project."""
        full = os.path.join(self.project_path, path) if not os.path.isabs(path) else path
        try:
            with open(full, 'r', errors='replace') as f:
                lines = f.readlines()
            if len(lines) > max_lines:
                content = "".join(lines[:max_lines])
                content += f"\n... ({len(lines)} lines total, truncated)"
                return content
            return "".join(lines)
        except Exception:
            return None

    def _grep(self, pattern: str, glob_filter: str = "", max_results: int = 30) -> Optional[str]:
        """Ripgrep search across the project."""
        cmd = ["rg", "--no-heading", "-n", "-i", "--max-count", "3",
               "--max-filesize", "500K",
               "-g", "!.git", "-g", "!node_modules", "-g", "!target",
               "-g", "!__pycache__", "-g", "!*.min.js", "-g", "!*.lock",
               "-g", "!*.map"]
        if glob_filter:
            cmd.extend(["-g", glob_filter])
        cmd.extend([pattern, self.project_path])
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            lines = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
            if not lines:
                return None
            # Make paths relative
            rel_lines = []
            for line in lines[:max_results]:
                if line.startswith(self.project_path):
                    line = line[len(self.project_path):].lstrip("/")
                rel_lines.append(line)
            return f"grep '{pattern}' ({len(lines)} matches):\n" + "\n".join(rel_lines)
        except FileNotFoundError:
            # rg not available, fallback to grep -r
            try:
                cmd = ["grep", "-rn", "-i", "-m", "3", pattern, self.project_path]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                lines = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
                if lines:
                    return f"grep '{pattern}' ({len(lines)} matches):\n" + "\n".join(lines[:max_results])
            except Exception:
                pass
            return None
        except Exception:
            return None

    def _get_structure(self, subpath: str = "", depth: int = 3) -> Optional[str]:
        """Get directory tree structure."""
        root = os.path.join(self.project_path, subpath) if subpath else self.project_path
        if not os.path.isdir(root):
            return None
        lines = []
        for dirpath, dirs, files in os.walk(root):
            level = dirpath.replace(root, "").count(os.sep)
            if level >= depth:
                dirs.clear()
                continue
            # Skip noise
            dirs[:] = [d for d in sorted(dirs)
                       if d not in ('.git', 'node_modules', '__pycache__', 'target', '.build', '.next')]
            indent = "  " * level
            lines.append(f"{indent}{os.path.basename(dirpath)}/")
            for f in sorted(files)[:30]:
                lines.append(f"{'  ' * (level + 1)}{f}")
        return f"Structure ({subpath or '/'}):\n" + "\n".join(lines[:150])

    def _build_iteration_prompt(self, query: str, iteration: int,
                                max_iterations: int, findings: list[str],
                                context: str) -> str:
        """Build the prompt for the orchestrator LLM at each iteration."""
        # Truncate findings: keep recent verbatim, summarize older
        findings_text = "(none yet — first iteration)"
        if findings:
            all_text = "\n\n".join(findings)
            if len(all_text) > MAX_FINDINGS_CHARS:
                recent = "\n\n".join(findings[-4:])
                older = [f.split("\n")[0] for f in findings[:-4]]
                findings_text = ("OLDER (summary):\n" + "\n".join(older)
                                 + "\n\nRECENT (full):\n" + recent)
                findings_text = findings_text[-MAX_FINDINGS_CHARS:]
            else:
                findings_text = all_text

        # Push for convergence on later iterations
        urgency = ""
        if iteration >= max_iterations - 1:
            urgency = "\nTHIS IS THE LAST ITERATION. You MUST emit FINAL_ANSWER now with everything you know.\n"
        elif iteration >= max_iterations - 2:
            urgency = "\nOnly 1 iteration left after this. Emit FINAL_ANSWER unless you critically need more info.\n"
        elif findings:
            urgency = f"\nYou have {len(findings)} findings. If you can answer the query, emit FINAL_ANSWER now.\n"

        return f'''Project: "{self.project_name}" at {self.project_path}
Iteration {iteration + 1}/{max_iterations}.
{urgency}
USER QUERY: {query}

{f"PROJECT CONTEXT:\n{context[:2000]}" if context else ""}

FINDINGS SO FAR:
{findings_text}

Generate 1-3 exploration queries OR emit FINAL_ANSWER.

Sub-agent tools: "grep" (pattern + glob), "read" (files list), "structure" (path), "auto".

JSON response ONLY:
{{"action": "explore", "queries": [{{"query": "...", "tool": "grep|read|structure|auto", "pattern": "...", "glob": "...", "files": [...], "reason": "..."}}]}}

OR:
{{"action": "final", "answer": "Comprehensive answer with file paths, code excerpts, concrete facts."}}
'''

    def _parse_response(self, response: str) -> dict:
        """Parse orchestrator response into {action, queries/answer}."""
        cleaned = response.strip()
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'\s*```$', '', cleaned)
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict) and "action" in data:
                return data
        except json.JSONDecodeError:
            # Try to find JSON in response
            match = re.search(r'\{[^{}]*"action"\s*:', cleaned)
            if match:
                try:
                    # Find matching closing brace
                    start = match.start()
                    depth = 0
                    for idx in range(start, len(cleaned)):
                        if cleaned[idx] == '{':
                            depth += 1
                        elif cleaned[idx] == '}':
                            depth -= 1
                            if depth == 0:
                                return json.loads(cleaned[start:idx + 1])
                except Exception:
                    pass

        # Fallback: treat as explore with generic query
        logger.warning("[RLM] Failed to parse response, using fallback query")
        return {"action": "explore", "queries": [{"query": response[:200], "tool": "auto"}]}

    async def _force_final(self, query: str, findings: list[str]) -> str:
        """Force a final answer from accumulated findings (no extra LLM call)."""
        print(f"[RLM:{self.project_name}] Force final from {len(findings)} findings", flush=True)
        if not findings:
            return "No findings were collected during the search."
        # Return findings directly — the chat agent LLM will synthesize
        findings_text = "\n\n".join(findings[-6:])[-3000:]
        return f"**Deep search findings ({len(findings)} explorations):**\n\n{findings_text}"


# ── Singleton per project ──────────────────────────────────────

_rlm_cache: dict[str, ProjectRLM] = {}


def get_project_rlm(project_id: str, workspace_path: str = "") -> Optional[ProjectRLM]:
    """Get or create an RLM for a project.  Falls back to workspace_path."""
    cache_key = f"{project_id}:{workspace_path}" if workspace_path else project_id
    if cache_key in _rlm_cache:
        return _rlm_cache[cache_key]

    from ..projects.manager import get_project_store
    from ..agents.store import get_agent_store

    proj = get_project_store().get(project_id)
    project_path = ""
    project_name = project_id

    if proj:
        project_path = proj.path or ""
        project_name = proj.name or project_id

    # Fallback: use workspace_path if project has no path or isn't registered
    if not project_path and workspace_path:
        project_path = workspace_path

    if not project_path:
        return None

    # Use the project's lead agent LLM config
    provider, model = "", ""
    if proj and proj.lead_agent_id:
        agent = get_agent_store().get(proj.lead_agent_id)
        if agent:
            provider = agent.provider
            model = agent.model

    rlm = ProjectRLM(
        project_id=project_id,
        project_path=project_path,
        project_name=project_name,
        provider=provider,
        model=model,
    )
    _rlm_cache[cache_key] = rlm
    return rlm
