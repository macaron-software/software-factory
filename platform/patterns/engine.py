"""Pattern Execution Engine — runs pattern graphs with real agents.

Takes a PatternDef (graph of agent nodes + edges), resolves agents,
and executes them according to the pattern type (sequential, parallel,
loop, hierarchical, network/debate, wave).

All agent execution goes through the existing AgentExecutor + LLMClient.
Messages are stored in the session for WhatsApp-style display.

Context Rot Mitigation: older agent outputs are compressed to key points
to keep the context window fresh for each agent (inspired by GSD).

Wave Dependencies: nodes are grouped into waves based on dependency edges.
Agents within a wave run in parallel, waves run sequentially.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Prevent RecursionError in deep async pattern chains
sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))

from ..agents.executor import ExecutionContext, ExecutionResult, get_executor
from ..agents.store import AgentDef, get_agent_store
from ..memory.manager import get_memory_manager
from ..projects.manager import get_project_store
from ..sessions.store import MessageDef, get_session_store
from ..skills.library import get_skill_library
from .store import PatternDef

logger = logging.getLogger(__name__)

# Context rot mitigation: max chars of accumulated context per agent
CONTEXT_BUDGET = 6000
# Max chars to keep from each older agent's output when compressing
COMPRESSED_OUTPUT_SIZE = 400


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    VETOED = "vetoed"
    FAILED = "failed"


@dataclass
class NodeState:
    node_id: str
    agent_id: str
    agent: AgentDef | None = None
    status: NodeStatus = NodeStatus.PENDING
    result: ExecutionResult | None = None
    output: str = ""


@dataclass
class PatternRun:
    """Runtime state of a pattern execution."""

    pattern: PatternDef
    session_id: str
    project_id: str = ""
    project_path: str = ""  # workspace filesystem path for tools
    phase_id: str = ""  # mission phase_id for SSE routing
    nodes: dict[str, NodeState] = field(default_factory=dict)
    iteration: int = 0
    max_iterations: int = 5
    finished: bool = False
    success: bool = False
    error: str = ""
    flow_step: str = ""


# SSE push (import from runner to share the same queues)
from ..sessions.runner import _push_sse


async def _sse(run: PatternRun, event: dict):
    """Push SSE event with automatic phase_id injection."""
    if run.phase_id and "phase_id" not in event:
        event["phase_id"] = run.phase_id
    await _push_sse(run.session_id, event)


# Protocol that makes agents produce trackable PRs/deliverables
_PR_PROTOCOL = """[IMPORTANT — Team Protocol]
You are part of a team working together. Address your colleague directly.
When you produce deliverables or action items, list them as:
- [PR] Short title — description
Example: [PR] Update Angular deps — Upgrade @angular/core from 16.2 to 17.3
Each [PR] will be tracked in the project dashboard."""

# Decompose protocol — telegraphic
_DECOMPOSE_PROTOCOL = """ROLE: Tech Lead. DECOMPOSE work, do NOT code.

WORKFLOW:
1. list_files → understand project structure
2. deep_search(query="build tools, SDK, dependencies") → check build environment
3. Output [SUBTASK N] lines

ENVIRONMENT CHECK (MANDATORY before decomposing):
- Android/Kotlin: Use android_build() tools (NOT generic build). SDK is in android-builder container.
- iOS/Swift: Verify swift toolchain available.
- Web: Check node/npm availability.
- If SDK/toolchain missing: first subtask MUST be environment setup.

FORMAT:
[SUBTASK 1]: Create path/to/file — description
[SUBTASK 2]: Create path/to/file — description

RULES:
- 1-2 files per subtask. Specific paths. NO code. NO veto.
- Use correct file extensions for the stack (Kotlin=.kt, Swift=.swift, NO mixing).
- NEVER mix languages (no Swift files in Android project, no Kotlin in iOS).
- ALWAYS include a subtask for DEPENDENCY MANIFEST: requirements.txt, package.json, go.mod, or Cargo.toml.
- ALWAYS include a subtask for Dockerfile if the project will be deployed.
- Last subtask MUST be: "Run build verification and fix any errors"."""

# Execution protocol — telegraphic, code_write focused
_EXEC_PROTOCOL = """ROLE: Developer. You MUST call code_write. No code_write = FAILURE.

WORKFLOW:
1. EXPLORE FIRST: list_files + code_read existing files → understand what exists already
2. deep_search(query="architecture, patterns, existing code") → discover project structure
3. memory_search(query="conventions, decisions, design-system") → learn past decisions + design tokens
4. THEN code_write per file → REAL build → git_commit

TOOL: code_write(path="src/module.ts", content="full source code here")

RULES:
- ALWAYS read existing code BEFORE writing. Do NOT recreate files that exist.
- code_write EACH file. 30+ lines per file. No stubs. No placeholders. No fake scripts.
- Use paths matching the project stack (src/ for web, app/ for mobile). Auto-resolved.
- FOLLOW THE STACK DECIDED IN ARCHITECTURE PHASE. Do NOT switch language.
- Do NOT describe changes. DO them via code_write.
- NEVER create fake build scripts (gradlew, Makefile) that do nothing.

UI/UX CONSTRAINTS (MANDATORY for frontend code):
- IMPORT design tokens: @import './styles/tokens.css' or import '../styles/tokens.css'
- ALL colors via CSS custom properties: var(--color-primary), var(--color-text), etc.
- ALL font sizes via tokens: var(--font-size-sm), var(--font-size-md), etc.
- ALL spacing via tokens: var(--spacing-sm), var(--spacing-md), etc.
- NO hardcoded hex colors (#fff, #333), NO hardcoded px font-sizes, NO inline styles
- WCAG AA accessibility: aria-label on icons, aria-describedby on forms, role attributes
- Semantic HTML: <nav>, <main>, <article>, <section>, <header>, <footer>. NOT <div> soup.
- Responsive: mobile-first, use CSS grid/flexbox, test 320px→1440px
- Focus management: :focus-visible styles, skip-to-content link, keyboard navigation
- Loading/error/empty states for EVERY data-dependent component

DEPENDENCY MANIFESTS (MANDATORY — generate BEFORE build):
- Go: code_write go.mod with module name + deps, then build(command="cd {project} && go mod tidy")
- Python: code_write requirements.txt with ALL imports (fastapi, uvicorn, pydantic, etc.)
- Node.js/TS: code_write package.json with scripts + deps, then build(command="npm install")
- Rust: code_write Cargo.toml with [dependencies] section
- Docker: code_write Dockerfile with correct base image + COPY + RUN install
- NEVER leave deps empty. List EVERY import your code uses. Missing deps = build failure.

BUILD VERIFICATION (MANDATORY — run AFTER writing code):
- Web/Node.js: build(command="npm install && npm run build")
- Python: build(command="python3 -m py_compile file.py")
- Go: build(command="go vet ./...")
- Rust: build(command="cargo check")
- Android/Kotlin: android_build() — compiles via Gradle in real SDK container
- Android tests: android_test() — runs real unit tests
- Swift/iOS: build(command="swift build") — only for iOS/macOS projects
- Docker: build(command="docker build -t test .")
- If build fails, FIX the code and retry. Do NOT commit broken code.
- Do NOT use generic build() for Android — use android_build() instead.

COMPLETION CHECKLIST (before git_commit):
1. All source files written via code_write
2. Dependency manifest exists and is complete (requirements.txt / package.json / go.mod / Cargo.toml)
3. Dockerfile exists (if project uses Docker)
4. Build command ran successfully
5. git_commit with meaningful message"""

# Validation protocol — telegraphic
_QA_PROTOCOL = """ROLE: QA Engineer. You MUST run actual tests, not just read code.

WORKFLOW:
1. list_files → find test files and source files
2. Run REAL tests using the correct tools:
   - Android/Kotlin: android_build() → android_test() → android_lint()
   - Android E2E: android_emulator_test() — boots real emulator, runs instrumented tests
   - Python: build(command="python3 -m pytest tests/")
   - Node.js: build(command="npm test")
   - Playwright: playwright_test(spec="tests/e2e.spec.js")
3. For web projects: TAKE REAL SCREENSHOTS:
   - browser_screenshot() → captures real browser rendering
   - Minimum 2 screenshots: home page + key interaction
4. code_read source files → check for obvious bugs
5. Deliver verdict based on ACTUAL test results + screenshots

RULES:
- NEVER use generic build() for Android — use android_build() and android_test() instead.
- You MUST call build/test tools at least once. Reading code alone is NOT testing.
- For web projects, you MUST call browser_screenshot at least once.
- Verify REAL compilation output — if build tool returns empty output, it's a fake wrapper.
- [APPROVE] only if build/tests pass. [VETO] if build fails or critical bugs found.
- Include actual tool output in your verdict (exit codes, error messages).
- Sprints are incremental. Missing features ≠ VETO. Broken build = VETO.
- DO NOT fabricate screenshots or build scripts."""

# Review protocol — telegraphic
_REVIEW_PROTOCOL = """ROLE: Reviewer. Verify claims via tools.

DO: code_read files → code_search references → build(command="...") to verify.
VERDICT: [APPROVE] or [REQUEST_CHANGES] with specific file:line issues.
You MUST call build tool to verify the code compiles before approving."""

# CI/CD protocol — MUST run real commands
_CICD_PROTOCOL = """ROLE: DevOps / CI-CD Engineer. You MUST run real build+test commands.

WORKFLOW:
1. list_files → understand project structure
2. Verify dependency manifests exist:
   - If missing requirements.txt/package.json/go.mod → code_write them FIRST
   - If Dockerfile missing → code_write a proper multi-stage Dockerfile
3. Run actual build:
   - build(command="docker build -t app .") if Dockerfile exists
   - build(command="npm install && npm run build") for Node.js
   - build(command="pip install -r requirements.txt && python -m py_compile app/main.py") for Python
   - build(command="go build ./...") for Go
   - build(command="cargo build") for Rust
4. Run tests:
   - build(command="npm test") or build(command="pytest")
5. Write docker-compose.yml if multi-service project
6. Report REAL results with exit codes

RULES:
- You MUST call build tool with real commands. Writing YAML files is NOT CI/CD.
- If docker build fails, report the actual error — do NOT invent success.
- Include actual command output in your report.
- [APPROVE] only if build succeeds. [VETO] if build fails.
- ALWAYS verify dependency manifests are complete before building."""

# Research protocol for ideation/discussion — agents can READ docs, search memory, but NOT write code
_RESEARCH_PROTOCOL = """[DISCUSSION MODE — MANDATORY]

You are an EXPERT contributing to a team discussion. Your job is to DELIVER YOUR ANALYSIS NOW.

CRITICAL RULES:
- NEVER say "let me consult/check/analyze first" — deliver your verdict immediately
- USE deep_search(query="...") to explore the project codebase and understand what exists
- USE memory_search(query="...") to recall past decisions, architecture, conventions
- USE list_files + code_read to inspect actual project files
- But do NOT write code or create files — this is a discussion phase
- Give your DECISION, RECOMMENDATION or ANALYSIS with specifics
- Name technologies, numbers, risks, trade-offs
- If this is a GO/NOGO committee: state your verdict clearly (GO, NOGO, or CONDITIONAL GO + conditions)
- @mention colleagues when addressing them
- React to what others said, don't repeat
- 200-400 words, structured with headers if needed
- End with a clear actionable conclusion"""


def _auto_create_tickets_from_results(results: str, ctx, source: str = "qa"):
    """Auto-create TMA tickets from E2E/build results that contain failures."""
    import uuid

    try:
        from ..db.migrations import get_db
    except Exception:
        return

    # Detect failures in results
    fail_lines = []
    for line in results.split("\n"):
        line_lower = line.lower()
        if any(kw in line_lower for kw in ("fail", "error:", "timeout", "not responding")):
            if "npm install: OK" not in line and "0 failures" not in line_lower:
                fail_lines.append(line.strip())

    if not fail_lines:
        return

    mission_id = getattr(ctx, "mission_run_id", "") or ""
    agent_id = ctx.agent.id if ctx.agent else source
    try:
        db = get_db()
        for i, fail in enumerate(fail_lines[:5]):  # max 5 tickets per run
            tid = str(uuid.uuid4())[:8]
            title = fail[:120] if len(fail) > 10 else f"Auto-detected {source} failure #{i + 1}"
            severity = "high" if "error" in fail.lower() else "medium"
            db.execute(
                "INSERT INTO support_tickets (id, mission_id, title, description, severity, category, reporter, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, 'open')",
                (
                    tid,
                    mission_id,
                    title,
                    f"Auto-created from {source} results:\n{fail}",
                    severity,
                    "auto-qa",
                    agent_id,
                ),
            )
        db.commit()
        db.close()
        logger.info("Auto-created %d TMA tickets from %s results", len(fail_lines[:5]), source)
    except Exception as e:
        logger.warning("Failed to auto-create tickets: %s", e)


def _auto_persist_backlog(result: str, ctx, mission_id: str):
    """Auto-parse PM output to persist features/stories in the product backlog.

    MiniMax M2.5 won't call create_feature tool reliably, so we parse
    structured tables from PM output (Epic/Story markdown tables).
    """
    import re
    import uuid

    try:
        from ..db.migrations import get_db
    except Exception:
        return

    # Extract epics — two formats:
    # Format 1: | **E1** | Title | Priority |
    # Format 2: | **E1** Title | Desc | Status |  (title in same cell as Exx)
    epic_pattern = re.compile(
        r"\|\s*\*\*(?:E\d+|Epic\s*\d*)\*\*\s*(?:\|?\s*)(.+?)\s*\|\s*(.+?)\s*\|",
        re.IGNORECASE,
    )
    # Extract stories: | US-E1-01 : Title | Estimation | Dependency |
    story_pattern = re.compile(
        r"\|\s*(US-[\w-]+)\s*[:\s]+(.+?)\s*\|\s*(\d+)\s*\|",
        re.IGNORECASE,
    )

    epics_found = epic_pattern.findall(result)
    stories_found = story_pattern.findall(result)

    if not epics_found and not stories_found:
        return

    try:
        db = get_db()
        feature_ids = {}

        # Create features from epics
        priority_map = {
            "p0": 1,
            "p1": 3,
            "p2": 5,
            "p3": 7,
            "haute": 1,
            "high": 1,
            "moyen": 3,
            "medium": 3,
            "basse": 7,
            "low": 7,
        }
        for i, (name, extra) in enumerate(epics_found):
            fid = f"feat-{uuid.uuid4().hex[:6]}"
            # Try to find priority in extra column
            prio_match = re.search(
                r"P\d+|haute?|high|moyen|medium|basse?|low", extra, re.IGNORECASE
            )
            prio_clean = prio_match.group(0).lower() if prio_match else "p2"
            priority = priority_map.get(prio_clean, 5)
            name_clean = name.strip().rstrip("|").strip()
            if not name_clean or len(name_clean) < 3:
                continue
            db.execute(
                "INSERT OR IGNORE INTO features (id, epic_id, name, description, priority, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'backlog', datetime('now'))",
                (fid, mission_id, name_clean, "Auto-extracted from PM decomposition", priority),
            )
            feature_ids[f"E{i + 1}"] = fid

        # Create user stories
        for story_id, title, points in stories_found:
            sid = f"us-{uuid.uuid4().hex[:6]}"
            # Link to parent feature via story ID prefix (US-E1-xx → E1)
            epic_ref = re.match(r"US-(E\d+)", story_id, re.IGNORECASE)
            feat_id = feature_ids.get(epic_ref.group(1), "") if epic_ref else ""
            db.execute(
                "INSERT OR IGNORE INTO user_stories (id, feature_id, title, story_points, status, created_at) "
                "VALUES (?, ?, ?, ?, 'backlog', datetime('now'))",
                (sid, feat_id, f"{story_id}: {title.strip()}", int(points)),
            )

        db.commit()
        db.close()
        logger.info(
            "Auto-persisted backlog: %d features, %d stories for mission %s",
            len(epics_found),
            len(stories_found),
            mission_id,
        )
    except Exception as e:
        logger.warning("Failed to auto-persist backlog: %s", e)


def _auto_extract_requirements(description: str, mission_id: str):
    """Extract requirements from mission description for AO traceability.

    Decomposes both top-level numbered requirements AND their sub-items.
    Input: '1. **Portail usager** : inscription, choix du VAE, paiement'
    Output: REQ-xxxx-01 (parent) + REQ-xxxx-01.1, 01.2, 01.3 (sub-reqs)
    """
    import re

    try:
        from ..db.migrations import get_db
    except Exception:
        return

    # Match numbered items: "1. **Title**: desc" OR "1. Title: desc"
    req_pattern = re.compile(
        r"(\d+)\.\s*\*{0,2}([^*:\n]+?)\*{0,2}\s*[:：]\s*(.+?)(?=\n\d+\.\s|\Z)",
        re.DOTALL,
    )
    reqs = req_pattern.findall(description)
    if not reqs:
        return

    try:
        db = get_db()
        db.execute("""CREATE TABLE IF NOT EXISTS requirements (
            id TEXT PRIMARY KEY,
            mission_id TEXT NOT NULL,
            parent_id TEXT DEFAULT '',
            req_number TEXT,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT DEFAULT 'identified',
            covered_by TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now'))
        )""")

        total = 0
        prefix = mission_id[:4]
        for num, title, desc in reqs:
            parent_id = f"REQ-{prefix}-{num.zfill(2)}"
            # Insert parent requirement
            db.execute(
                "INSERT OR IGNORE INTO requirements (id, mission_id, parent_id, req_number, title, description) "
                "VALUES (?, ?, '', ?, ?, ?)",
                (parent_id, mission_id, num, title.strip(), desc.strip()[:500]),
            )
            total += 1

            # Decompose sub-items from description (comma/semicolon separated)
            desc_clean = desc.strip()
            # Remove parenthetical content for cleaner splitting
            desc_no_parens = re.sub(r"\([^)]*\)", "", desc_clean)
            sub_items = [
                s.strip()
                for s in re.split(r"[,;]", desc_no_parens)
                if s.strip() and len(s.strip()) > 3
            ]

            for j, sub in enumerate(sub_items, 1):
                sub_id = f"REQ-{prefix}-{num.zfill(2)}.{j}"
                # Clean up sub-item: remove leading articles, trailing whitespace
                sub_clean = re.sub(
                    r"^(le |la |les |l\'|un |une |des |du )", "", sub.strip(), flags=re.IGNORECASE
                ).strip()
                if len(sub_clean) < 3:
                    continue
                db.execute(
                    "INSERT OR IGNORE INTO requirements (id, mission_id, parent_id, req_number, title, description) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sub_id, mission_id, parent_id, f"{num}.{j}", sub_clean, ""),
                )
                total += 1

        db.commit()
        db.close()
        logger.info(
            "Extracted %d AO requirements (%d top + sub) for mission %s",
            total,
            len(reqs),
            mission_id,
        )
    except Exception as e:
        logger.warning("Failed to extract requirements: %s", e)


def _build_team_context(run: PatternRun, current_node: str, to_agent_id: str) -> str:
    """Build team awareness: who's on the team, what's the communication flow."""
    parts = []
    current = run.nodes.get(current_node)
    if not current or not current.agent:
        return ""

    # List team members
    team = []
    for nid, ns in run.nodes.items():
        if ns.agent and nid != current_node:
            status = ""
            if ns.status == NodeStatus.COMPLETED and ns.output:
                status = " (has already contributed)"
            team.append(f"  - {ns.agent.name} ({ns.agent.role}){status}")
    if team:
        parts.append("[Your team]:\n" + "\n".join(team))

    # Who are you addressing?
    if to_agent_id and to_agent_id not in ("all", "session"):
        target = None
        for ns in run.nodes.values():
            if ns.agent and ns.agent.id == to_agent_id:
                target = ns.agent
                break
        if target:
            parts.append(f"[You are addressing]: {target.name} ({target.role})")

    return "\n".join(parts)


async def run_pattern(
    pattern: PatternDef,
    session_id: str,
    initial_task: str,
    project_id: str = "",
    project_path: str = "",
    phase_id: str = "",
) -> PatternRun:
    """Execute a pattern graph in a session. Returns the run state."""
    run = PatternRun(
        pattern=pattern,
        session_id=session_id,
        project_id=project_id,
        project_path=project_path,
        phase_id=phase_id,
        max_iterations=pattern.config.get("max_iterations", 5),
    )

    # Resolve agents for each node — Thompson Sampling when multiple candidates exist
    agent_store = get_agent_store()
    _task_domain = project_id or ""
    for node in pattern.agents:
        nid = node["id"]
        agent_id = node.get("agent_id") or ""
        agent = None
        if agent_id:
            agent = agent_store.get(agent_id)
            # If not found by exact id, try Thompson role-based selection
            if agent is None:
                try:
                    from ..agents.selection import select_agent_for_role
                    agent = select_agent_for_role(agent_id, task_domain=_task_domain, project_id=project_id or "")
                except Exception:
                    pass
        run.nodes[nid] = NodeState(node_id=nid, agent_id=agent_id, agent=agent)

    # Determine pattern leader (first agent in the pattern)
    first_node = pattern.agents[0] if pattern.agents else None
    pattern_leader = (first_node.get("agent_id") or "") if first_node else ""

    # Log pattern start — target the leader, not broadcast
    store = get_session_store()
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="system",
            to_agent=pattern_leader or "all",
            message_type="system",
            content=f"Pattern **{pattern.name}** started ({pattern.type})",
        )
    )
    await _sse(
        run,
        {
            "type": "pattern_start",
            "pattern_id": pattern.id,
            "pattern_name": pattern.name,
        },
    )

    try:
        import sys

        # Prevent recursion errors from deep async/httpx stacks during concurrent LLM calls
        if sys.getrecursionlimit() < 3000:
            sys.setrecursionlimit(3000)

        ptype = pattern.type
        if ptype == "solo":
            await _impl_solo(_engine_proxy, run, initial_task)
        elif ptype == "sequential":
            await _impl_sequential(_engine_proxy, run, initial_task)
        elif ptype == "parallel":
            await _impl_parallel(_engine_proxy, run, initial_task)
        elif ptype == "loop":
            await _impl_loop(_engine_proxy, run, initial_task)
        elif ptype == "hierarchical":
            await _impl_hierarchical(_engine_proxy, run, initial_task)
        elif ptype == "network":
            await _impl_network(_engine_proxy, run, initial_task)
        elif ptype == "router":
            await _impl_router(_engine_proxy, run, initial_task)
        elif ptype == "aggregator":
            await _impl_aggregator(_engine_proxy, run, initial_task)
        elif ptype == "wave":
            await _impl_wave(_engine_proxy, run, initial_task)
        elif ptype == "human-in-the-loop":
            await _impl_human_in_the_loop(_engine_proxy, run, initial_task)
        else:
            await _impl_sequential(_engine_proxy, run, initial_task)

        run.finished = True
        has_vetoes = any(n.status == NodeStatus.VETOED for n in run.nodes.values())
        all_ok = all(
            n.status in (NodeStatus.COMPLETED, NodeStatus.PENDING) for n in run.nodes.values()
        )
        run.success = all_ok and not has_vetoes
    except Exception as e:
        run.finished = True
        run.error = str(e)
        has_vetoes = False
        logger.error("Pattern %s failed: %s", pattern.name, e, exc_info=True)

    # Log pattern end
    if run.success:
        status = "COMPLETED"
    elif has_vetoes:
        status = "NOGO — vetoes non résolus"
    else:
        status = f"FAILED: {run.error}"
    store.add_message(
        MessageDef(
            session_id=session_id,
            from_agent="system",
            to_agent=pattern_leader or "all",
            message_type="system",
            content=f"Pattern **{pattern.name}** {status}",
        )
    )
    await _sse(
        run,
        {
            "type": "pattern_end",
            "success": run.success,
            "error": run.error,
        },
    )

    return run


async def _execute_node(
    run: PatternRun,
    node_id: str,
    task: str,
    context_from: str = "",
    to_agent_id: str = "",
    protocol_override: str = "",
) -> str:
    """Execute a single node: call its agent with the task, store messages."""
    state = run.nodes.get(node_id)
    if not state or not state.agent:
        return f"[Node {node_id} has no agent assigned]"

    state.status = NodeStatus.RUNNING
    agent = state.agent
    store = get_session_store()

    # Push thinking status
    await _sse(
        run,
        {
            "type": "agent_status",
            "agent_id": agent.id,
            "node_id": node_id,
            "status": "thinking",
        },
    )

    # Build context
    ctx = await _build_node_context(agent, run)

    # Build team-aware context
    team_info = _build_team_context(run, node_id, to_agent_id)
    full_task = ""
    if team_info:
        full_task += f"{team_info}\n\n"
    if context_from:
        # Sanitize agent output to prevent cross-agent prompt injection
        try:
            from ..security.sanitize import sanitize_agent_output

            context_from = sanitize_agent_output(context_from, agent_id=to_agent_id)
        except ImportError:
            pass
        full_task += f"[Message from colleague]:\n{context_from}\n\n"
    full_task += f"[Your task]:\n{task}\n\n"

    # Inject protocol — override takes precedence over role-based detection
    if protocol_override:
        full_task += protocol_override
    else:
        # Inject protocol based on PHASE PATTERN, not agent rank
        pattern_type = run.pattern.type
        discussion_patterns = ("network", "human-in-the-loop")
        role_lower = (agent.role or "").lower()
        has_project = bool(run.project_id)

        if pattern_type in discussion_patterns or not has_project:
            full_task += _RESEARCH_PROTOCOL
        elif "devops" in role_lower or "sre" in role_lower or "pipeline" in role_lower:
            full_task += _CICD_PROTOCOL
            full_task += "\n\n" + _PR_PROTOCOL
        elif (
            "dev" in role_lower
            or "fullstack" in role_lower
            or "backend" in role_lower
            or "frontend" in role_lower
        ):
            full_task += _EXEC_PROTOCOL
            full_task += "\n\n" + _PR_PROTOCOL
        elif "qa" in role_lower or "test" in role_lower:
            full_task += _QA_PROTOCOL
            full_task += "\n\n" + _PR_PROTOCOL
            # Auto-run E2E tests for QA agents (LLM can't call tools reliably)
            if ctx.project_path:
                try:
                    from ..agents.tool_runner import _tool_run_e2e_tests

                    e2e_result = await _tool_run_e2e_tests({}, ctx)
                    full_task += f"\n\n## E2E Test Results (auto-executed)\n{e2e_result}"
                    # Auto-create TMA tickets for failures found
                    _auto_create_tickets_from_results(e2e_result, ctx, "qa")
                except Exception as e:
                    full_task += f"\n\n## E2E Tests: Error running auto-tests: {e}"
        elif "ux" in role_lower or "design" in role_lower:
            full_task += _EXEC_PROTOCOL
            # Auto-create design system scaffold if it doesn't exist
            if ctx.project_path:
                try:
                    import os

                    styles_dir = os.path.join(ctx.project_path, "src", "styles")
                    tokens_path = os.path.join(styles_dir, "tokens.css")
                    if not os.path.exists(tokens_path):
                        full_task += """

## Design System Status: NOT YET CREATED
The project has NO design system yet. You MUST create it NOW using code_write.
Create these files:
1. src/styles/tokens.css — CSS custom properties (colors, typography, spacing, radius, shadows)
2. src/styles/base.css — CSS reset, responsive grid, accessibility defaults
3. src/styles/components.css — Base component styles (btn, card, form, badge, alert, nav)

This is BLOCKING: developers cannot start without your design tokens."""
                    else:
                        full_task += (
                            "\n\n## Design System Status: EXISTS — review and improve if needed."
                        )
                except Exception:
                    pass
        elif "lead" in role_lower or "architect" in role_lower:
            full_task += _REVIEW_PROTOCOL
            full_task += "\n\n" + _PR_PROTOCOL
        else:
            full_task += _RESEARCH_PROTOCOL

    # Execute with streaming SSE
    executor = get_executor()
    result = None

    await _sse(
        run,
        {
            "type": "stream_start",
            "agent_id": agent.id,
            "agent_name": agent.name,
            "node_id": node_id,
            "pattern_type": run.pattern.type,
            "to_agent": to_agent_id or "all",
            "iteration": run.iteration,
            "flow_step": run.flow_step,
        },
    )

    import re as _re

    in_think = False
    in_tool_call = False
    think_chunks = 0
    delta_count = 0
    try:
        async for kind, value in executor.run_streaming(ctx, full_task):
            if kind == "delta":
                delta_count += 1
                delta = value
                # Filter <think> blocks
                if "<think>" in delta:
                    in_think = True
                if "</think>" in delta:
                    in_think = False
                    continue
                # Filter <minimax:tool_call> artifacts
                if "<minimax:tool_call>" in delta or "<tool_call>" in delta:
                    in_tool_call = True
                if "</minimax:tool_call>" in delta or "</tool_call>" in delta:
                    in_tool_call = False
                    continue
                if in_think:
                    think_chunks += 1
                    if think_chunks % 20 == 0:
                        await _sse(
                            run,
                            {
                                "type": "stream_thinking",
                                "agent_id": agent.id,
                            },
                        )
                elif not in_tool_call:
                    if delta_count <= 3:
                        logger.warning(
                            "STREAM_DELTA agent=%s count=%d len=%d",
                            agent.id,
                            delta_count,
                            len(delta),
                        )
                    await _sse(
                        run,
                        {
                            "type": "stream_delta",
                            "agent_id": agent.id,
                            "delta": delta,
                        },
                    )
            elif kind == "tool":
                # Agent is calling a tool — send activity SSE so UI shows progress
                await _sse(
                    run,
                    {
                        "type": "stream_thinking",
                        "agent_id": agent.id,
                        "tool_name": value,
                    },
                )
            elif kind == "result":
                result = value
        logger.warning(
            "STREAM_DONE agent=%s deltas=%d think=%d", agent.id, delta_count, think_chunks
        )
    except Exception as exc:
        logger.error("Streaming failed for %s, falling back: %s", agent.id, exc)
        result = await executor.run(ctx, full_task)

    if result is None:
        result = await executor.run(ctx, full_task)

    # Strip <think> and tool-call artifacts from final content
    content = result.content or ""
    if "<think>" in content:
        content = _re.sub(r"<think>.*?</think>\s*", "", content, flags=_re.DOTALL).strip()
    if "<minimax:tool_call>" in content or "<tool_call>" in content:
        content = _re.sub(
            r"<minimax:tool_call>.*?</minimax:tool_call>\s*", "", content, flags=_re.DOTALL
        ).strip()
        content = _re.sub(r"<tool_call>.*?</tool_call>\s*", "", content, flags=_re.DOTALL).strip()
    if content != (result.content or ""):
        result = ExecutionResult(
            content=content,
            agent_id=result.agent_id,
            model=result.model,
            provider=result.provider,
            tokens_in=result.tokens_in,
            tokens_out=result.tokens_out,
            duration_ms=result.duration_ms,
            tool_calls=result.tool_calls,
            delegations=result.delegations,
            error=result.error,
        )

    state.result = result
    state.output = content

    # Auto-persist backlog when PM produces epic/story decomposition
    role_lower = (agent.role or agent.id or "").lower()
    if ("product" in role_lower or "pm" in role_lower) and (
        "Épic" in content or "Epic" in content or "US-" in content or "Story" in content
    ):
        mission_id = run.session_id  # fallback
        if hasattr(ctx, "mission_run_id") and ctx.mission_run_id:
            mission_id = ctx.mission_run_id
        else:
            # Try to get mission_id from session config
            try:
                sess = get_session_store().get(run.session_id)
                if sess and sess.config:
                    mission_id = sess.config.get("mission_id", mission_id)
            except Exception:
                pass
        _auto_persist_backlog(content, ctx, mission_id)

    # Detect VETO/NOGO/APPROVE — must be explicit decisions, not mentions
    msg_type = "text"
    content_upper = content.upper()
    # Only detect NOGO as explicit status declarations, not mentions in text
    is_veto = (
        "[VETO]" in content
        or "[NOGO]" in content_upper
        or "STATUT: NOGO" in content_upper
        or "STATUT : NOGO" in content_upper
        or "DÉCISION: NOGO" in content_upper
        or "DÉCISION : NOGO" in content_upper
        or "DECISION: NOGO" in content_upper
        or "DECISION : NOGO" in content_upper
        or "\nNOGO\n" in content_upper
        or content_upper.strip() == "NOGO"
    )
    is_approve = (
        "[APPROVE]" in content
        or "STATUT: GO" in content_upper
        or "STATUT : GO" in content_upper
        or "DÉCISION: GO" in content_upper
        or "DÉCISION : GO" in content_upper
        or "DECISION: GO" in content_upper
        or "DECISION : GO" in content_upper
    )
    if is_approve and not is_veto:
        msg_type = "approve"
        state.status = NodeStatus.COMPLETED
    elif is_veto:
        msg_type = "veto"
        state.status = NodeStatus.VETOED
        logger.warning("VETO detected from %s: %s", agent.id, content[:200])
    elif result.error:
        msg_type = "system"
        state.status = NodeStatus.FAILED
    else:
        state.status = NodeStatus.COMPLETED

    # ── Adversarial Guard with retry loop ──
    # If rejected, re-run agent with feedback (max 1 retry = 2 attempts total)
    # Coordinators and discussion patterns skip L1 (expensive LLM check)
    # Discussion patterns: agents brainstorm, quality varies — L1 wastes rate-limited calls
    MAX_ADVERSARIAL_RETRIES = 1  # 1 retry = 2 attempts total for execution patterns
    is_coordinator = protocol_override and "DECOMPOSE" in protocol_override
    _discussion_patterns = {"network", "human-in-the-loop", "debate", "aggregator"}
    is_discussion = run.pattern.type in _discussion_patterns
    skip_l1 = is_coordinator or is_discussion
    guard_result = None
    cumulative_tool_calls = list(result.tool_calls or [])  # accumulate across retries
    if content and not result.error and state.status == NodeStatus.COMPLETED:
        for _adv_attempt in range(MAX_ADVERSARIAL_RETRIES + 1):
            try:
                from ..agents.adversarial import run_guard

                guard_result = await run_guard(
                    content=content,
                    task=task,
                    agent_role=agent.role or "",
                    agent_name=agent.name,
                    tool_calls=cumulative_tool_calls,
                    pattern_type=run.pattern.type,
                    enable_l1=not skip_l1,
                )
            except Exception as guard_err:
                logger.warning("Adversarial guard error: %s", guard_err)
                break  # on error, don't block

            if guard_result.passed:
                if guard_result.issues:
                    logger.info(
                        "ADVERSARIAL WARN [%s] score=%d: %s",
                        agent.name,
                        guard_result.score,
                        "; ".join(guard_result.issues[:3]),
                    )
                break  # approved

            # Severity tiers: 5-6 = pass with warning, 7-8 = retry, 9-10 = hard reject
            # BUT: HALLUCINATION/SLOP/STACK_MISMATCH keywords always force retry (never soft-pass)
            has_critical_flags = any(
                "HALLUCINATION" in i or "SLOP" in i or "STACK_MISMATCH" in i
                for i in guard_result.issues
            )
            if guard_result.score <= 6 and not has_critical_flags:
                logger.info(
                    "ADVERSARIAL SOFT-PASS [%s] score=%d (≤6 = warning): %s",
                    agent.name,
                    guard_result.score,
                    "; ".join(guard_result.issues[:3]),
                )
                content = (
                    f"[ADVERSARIAL WARNING — score {guard_result.score}/10]\n"
                    + "\n".join(f"- {i}" for i in guard_result.issues[:3])
                    + "\n\n"
                    + content
                )
                break  # pass with warning appended

            # Rejected — retry with feedback if attempts remain
            logger.warning(
                "ADVERSARIAL REJECT [%s] attempt=%d score=%d: %s",
                agent.name,
                _adv_attempt + 1,
                guard_result.score,
                "; ".join(guard_result.issues[:3]),
            )
            await _sse(
                run,
                {
                    "type": "adversarial",
                    "agent_id": agent.id,
                    "agent_name": agent.name,
                    "passed": False,
                    "score": guard_result.score,
                    "level": guard_result.level,
                    "issues": guard_result.issues[:5],
                    "node_id": node_id,
                    "retry": _adv_attempt + 1,
                },
            )

            if _adv_attempt < MAX_ADVERSARIAL_RETRIES:
                # Re-run agent with rejection feedback
                feedback = "\n".join(f"- {i}" for i in guard_result.issues[:5])
                retry_task = (
                    f"[ADVERSARIAL FEEDBACK — ton output précédent a été REJETÉ]\n"
                    f"Problèmes:\n{feedback}\n\n"
                    f"Corrige ces problèmes. Même tâche:\n{task}"
                )
                if protocol_override:
                    retry_task += "\n\n" + protocol_override

                await _sse(
                    run,
                    {
                        "type": "agent_status",
                        "agent_id": agent.id,
                        "node_id": node_id,
                        "status": "thinking",
                    },
                )

                try:
                    retry_result = await executor.run(ctx, retry_task)
                    retry_content = retry_result.content or ""
                    # Strip think/tool artifacts
                    if "<think>" in retry_content:
                        retry_content = _re.sub(
                            r"<think>.*?</think>\s*", "", retry_content, flags=_re.DOTALL
                        ).strip()
                    if "<minimax:tool_call>" in retry_content or "<tool_call>" in retry_content:
                        retry_content = _re.sub(
                            r"<minimax:tool_call>.*?</minimax:tool_call>\s*",
                            "",
                            retry_content,
                            flags=_re.DOTALL,
                        ).strip()
                        retry_content = _re.sub(
                            r"<tool_call>.*?</tool_call>\s*", "", retry_content, flags=_re.DOTALL
                        ).strip()
                    # Use retry output
                    result = retry_result
                    content = retry_content
                    state.result = result
                    state.output = content
                    # Accumulate tool_calls from retry
                    cumulative_tool_calls.extend(retry_result.tool_calls or [])
                    logger.info(
                        "ADVERSARIAL RETRY [%s] attempt=%d — re-running agent",
                        agent.name,
                        _adv_attempt + 2,
                    )
                except Exception as retry_err:
                    logger.error("Adversarial retry failed for %s: %s", agent.id, retry_err)
                    break
            else:
                # No retries — pass with rejection warning (forward progress > perfection)
                state.status = NodeStatus.COMPLETED
                msg_type = "agent"
                rejection = (
                    f"[ADVERSARIAL WARNING — {guard_result.level}] "
                    f"Score: {guard_result.score}/10\n"
                    + "\n".join(f"- {i}" for i in guard_result.issues[:3])
                    + "\n\n"
                )
                content = rejection + content
                # Track rejection in agent scores + update quality_score
                try:
                    from ..db.migrations import get_db
                    import time as _time

                    db = get_db()
                    db.execute(
                        """INSERT INTO agent_scores (agent_id, epic_id, rejected, iterations, quality_score)
                           VALUES (?, ?, 1, ?, 0.1)
                           ON CONFLICT(agent_id, epic_id)
                           DO UPDATE SET
                             rejected = rejected + 1,
                             iterations = iterations + ?,
                             quality_score = ROUND(
                               CAST(accepted AS REAL) / MAX(accepted + rejected + 1, 1), 3
                             )""",
                        (
                            agent.id,
                            run.project_id or "",
                            MAX_ADVERSARIAL_RETRIES + 1,
                            MAX_ADVERSARIAL_RETRIES + 1,
                        ),
                    )
                    db.commit()
                    db.close()
                except Exception:
                    pass
                # Create platform_incident for adversarial rejections (DORA tracking)
                # Auto-close if agent already has >=3 open quality_rejection incidents
                try:
                    from ..missions.feedback import create_platform_incident
                    from ..db.migrations import get_db as _get_db

                    _db = _get_db()
                    open_count = _db.execute(
                        """SELECT COUNT(*) FROM platform_incidents
                           WHERE agent_id=? AND error_type='quality_rejection' AND status='open'""",
                        (agent.id,),
                    ).fetchone()[0]
                    if open_count >= 3:
                        # Auto-close oldest batch — they won't be fixed individually
                        _db.execute(
                            """UPDATE platform_incidents
                               SET status='auto_closed',
                                   error_detail = error_detail || ' [auto-closed: Thompson escalation handles recurrence]'
                               WHERE agent_id=? AND error_type='quality_rejection'
                               AND status='open'""",
                            (agent.id,),
                        )
                        _db.commit()
                        logger.info(
                            "Auto-closed %d open quality_rejection incidents for %s (Thompson escalation active)",
                            open_count, agent.id,
                        )
                    else:
                        create_platform_incident(
                            title=f"Adversarial rejection: {agent.name}",
                            severity="P3",
                            source="adversarial_guard",
                            error_type="quality_rejection",
                            error_detail=f"Agent {agent.name} output rejected (score {guard_result.score}/10, {guard_result.level}). "
                            f"Issues: {'; '.join(guard_result.issues[:5])}",
                            mission_id=run.project_id or "",
                            agent_id=agent.id,
                        )
                    _db.close()
                except Exception:
                    pass

    # Push final guard result to frontend
    if guard_result and guard_result.passed:
        await _sse(
            run,
            {
                "type": "adversarial",
                "agent_id": agent.id,
                "agent_name": agent.name,
                "passed": True,
                "score": guard_result.score,
                "level": guard_result.level,
                "issues": guard_result.issues[:5],
                "node_id": node_id,
            },
        )

    store.add_message(
        MessageDef(
            session_id=run.session_id,
            from_agent=agent.id,
            to_agent=to_agent_id or "all",
            message_type=msg_type,
            content=content,
            metadata={
                "model": result.model,
                "provider": result.provider,
                "tokens_in": result.tokens_in,
                "tokens_out": result.tokens_out,
                "duration_ms": result.duration_ms,
                "node_id": node_id,
                "pattern_id": run.pattern.id,
                "pattern_type": run.pattern.type,
                "phase_id": run.phase_id,
                "tool_calls": result.tool_calls if result.tool_calls else None,
            },
        )
    )

    # Compute activity counts for UI badges
    tcs = result.tool_calls or []
    edit_count = sum(1 for tc in tcs if tc.get("name") in ("code_edit", "code_write"))
    read_count = sum(
        1 for tc in tcs if tc.get("name") in ("code_read", "code_search", "list_files")
    )

    await _sse(
        run,
        {
            "type": "stream_end",
            "agent_id": agent.id,
            "content": content,
            "message_type": msg_type,
            "to_agent": to_agent_id or "all",
            "flow_step": run.flow_step,
        },
    )

    await _sse(
        run,
        {
            "type": "message",
            "from_agent": agent.id,
            "to_agent": to_agent_id or "all",
            "content": content,
            "message_type": msg_type,
            "pattern_type": run.pattern.type,
            "node_id": node_id,
            "edits": edit_count,
            "reads": read_count,
            "tool_count": len(tcs),
        },
    )

    await _sse(
        run,
        {
            "type": "agent_status",
            "agent_id": agent.id,
            "status": "idle",
        },
    )

    # Store key insights in project memory + notify frontend
    if run.project_id and content and not result.error:
        try:
            mem = get_memory_manager()
            import re as _re2

            # Strip tool call artifacts, JSON blobs, and filler
            clean = _re2.sub(r'\{["\'](?:path|name|command|args)["\'].*?\}', "", content)
            clean = _re2.sub(r"\[TOOL_CALL\].*?\[/TOOL_CALL\]", "", clean, flags=_re2.DOTALL)
            clean = _re2.sub(
                r"(?:Now |)(?:Calling|Searching|Looking|Reading|Inspecting)\s+\w+.*?(?:\n|\.\.\.)",
                "",
                clean,
            )
            clean = _re2.sub(
                r"(?:J'examine|Je vais|Let me|I'll inspect|I'll check|I will now).*?\n", "", clean
            )
            clean = clean.strip()

            # Skip adversarial warnings/rejections — these aren't decisions
            if clean.startswith("[ADVERSARIAL") or "ADVERSARIAL WARNING" in clean[:100]:
                raise ValueError("adversarial output, not a decision")

            if len(clean) < 20:
                raise ValueError("content too short after cleaning")

            # Extract structured facts from agent output
            _FACT_KEYWORDS = (
                "decision:",
                "choix:",
                "stack:",
                "architecture:",
                "action:",
                "conclusion:",
                "recommandation:",
                "verdict:",
                "risque:",
                "blocage:",
                "résultat:",
                "created:",
                "wrote:",
                "approve",
                "veto",
                "go ",
                "nogo",
                "request_changes",
            )
            facts = []
            for line in clean.split("\n"):
                line_s = line.strip()
                if not line_s or len(line_s) < 15:
                    continue
                if (
                    line_s.startswith("[PR]")
                    or line_s.startswith("- [")
                    or any(kw in line_s.lower() for kw in _FACT_KEYWORDS)
                ):
                    facts.append(line_s)
            # Compact summary: facts first, then truncated clean text
            if facts:
                summary = "\n".join(facts[:8])
            else:
                paragraphs = [p.strip() for p in clean.split("\n\n") if len(p.strip()) > 40]
                summary = paragraphs[0][:300] if paragraphs else clean[:300]

            # Use semantic category based on agent role
            role_lower = (agent.role or "").lower()
            if "archi" in role_lower:
                cat = "architecture"
            elif "qa" in role_lower or "test" in role_lower:
                cat = "quality"
            elif "dev" in role_lower or "lead" in role_lower:
                cat = "development"
            elif "secu" in role_lower:
                cat = "security"
            elif "devops" in role_lower or "sre" in role_lower or "pipeline" in role_lower:
                cat = "infrastructure"
            elif "product" in role_lower or "business" in role_lower or "po" in role_lower:
                cat = "product"
            elif "ux" in role_lower or "design" in role_lower:
                cat = "design"
            else:
                cat = "decisions"
            mem.project_store(
                run.project_id,
                key=f"{agent.name}: {run.flow_step or run.pattern.type}",
                value=summary,
                category=cat,
                source=agent.id,
            )

            # Also store in pattern memory (session-level, for agents in same session)
            mem.pattern_store(
                run.session_id,
                key=f"{agent.name}:{cat}",
                value=summary[:500],
                category=cat,
                author=agent.id,
            )

            await _sse(
                run,
                {
                    "type": "memory_stored",
                    "category": cat,
                    "key": f"{agent.name}: {run.flow_step or 'contribution'}",
                    "value": summary[:200],
                    "agent_id": agent.id,
                },
            )
            # Record as tool_call for monitoring (auto-store counts as memory_store)
            try:
                from ..db.migrations import get_db as _get_db2

                _db2 = _get_db2()
                _db2.execute(
                    "INSERT INTO tool_calls (agent_id, session_id, tool_name, parameters_json, result_json, success, timestamp) "
                    "VALUES (?, ?, 'memory_store', ?, ?, 1, datetime('now'))",
                    (
                        agent.id,
                        run.session_id,
                        json.dumps({"key": f"{agent.name}:{cat}", "category": cat, "auto": True})[
                            :1000
                        ],
                        f"Auto-stored: {summary[:200]}",
                    ),
                )
                _db2.commit()
            except Exception:
                pass
        except Exception:
            pass

    # Track agent performance score with real quality_score
    try:
        from ..db.migrations import get_db

        db = get_db()
        # Compute quality signals: output length, tools used
        _output_len = len(content) if content else 0
        _tools_used = len(cumulative_tool_calls) if cumulative_tool_calls else 0
        # quality bonus: longer output + tools used = better score signal
        _quality_bonus = min(0.1, _tools_used * 0.02 + min(_output_len / 5000, 0.05))
        db.execute(
            """INSERT INTO agent_scores (agent_id, epic_id, accepted, iterations, quality_score)
               VALUES (?, ?, 1, 1, ?)
               ON CONFLICT(agent_id, epic_id)
               DO UPDATE SET
                 accepted = accepted + 1,
                 iterations = iterations + 1,
                 quality_score = ROUND(MIN(1.0,
                   CAST(accepted + 1 AS REAL) / MAX(accepted + rejected + 1, 1) + ?
                 ), 3)""",
            (agent.id, run.project_id, 0.5 + _quality_bonus, _quality_bonus),
        )
        db.commit()
        db.close()
    except Exception:
        pass

    return content


async def _build_node_context(agent: AgentDef, run: PatternRun) -> ExecutionContext:
    """Build execution context for a node's agent."""
    store = get_session_store()
    history = store.get_messages(run.session_id, limit=30)
    history_dicts = [
        {"from_agent": m.from_agent, "content": m.content, "message_type": m.message_type}
        for m in history
    ]

    project_context = ""
    vision = ""
    project_path = ""
    if run.project_id:
        try:
            proj_store = get_project_store()
            project = proj_store.get(run.project_id)
            if project:
                vision = project.vision[:3000] if project.vision else ""
                project_path = getattr(project, "path", "") or ""
                mem = get_memory_manager()
                # Load role-relevant categories first, then recent entries
                role_lower = (agent.role or "").lower()
                _ROLE_CATS = {
                    "archi": ["architecture", "infrastructure"],
                    "dev": ["development", "architecture"],
                    "lead": ["development", "architecture", "quality"],
                    "qa": ["quality", "development"],
                    "test": ["quality", "development"],
                    "secu": ["security", "architecture"],
                    "devops": ["infrastructure", "security"],
                    "product": ["product", "design"],
                    "ux": ["design", "product"],
                    "po": ["product", "development"],
                }
                # Pick categories matching agent role
                cats = []
                for key, val in _ROLE_CATS.items():
                    if key in role_lower:
                        cats = val
                        break
                entries = []
                seen_ids = set()
                # Role-specific entries first
                for cat in cats:
                    for e in mem.project_get(run.project_id, category=cat, limit=5):
                        eid = e.get("id")
                        if eid not in seen_ids:
                            entries.append(e)
                            seen_ids.add(eid)
                # Then recent entries from any category
                for e in mem.project_get(run.project_id, limit=10):
                    eid = e.get("id")
                    if eid not in seen_ids:
                        entries.append(e)
                        seen_ids.add(eid)
                if entries:
                    project_context = "\n".join(
                        f"[{e['category']}] {e['key']}: {e['value'][:200]}" for e in entries[:15]
                    )
        except Exception:
            pass

    # Inject pattern memory (session-level: what other agents decided in THIS session)
    try:
        mem = get_memory_manager()
        pattern_entries = mem.pattern_get(run.session_id, limit=15)
        if pattern_entries:
            # Only include entries from OTHER agents (not self)
            other_entries = [e for e in pattern_entries if e.get("author_agent") != agent.id]
            if other_entries:
                session_mem = "\n".join(
                    f"[{e.get('type', 'ctx')}] {e['key']}: {e['value'][:200]}"
                    for e in other_entries[:10]
                )
                project_context += (
                    f"\n\n## Decisions from this session (other agents)\n{session_mem}"
                )
    except Exception:
        pass

    # For missions: prefer workspace_path (actual code) over project registry path
    if run.project_path:
        project_path = run.project_path

    skills_prompt = ""
    if agent.skills:
        try:
            lib = get_skill_library()
            parts = []
            for sid in agent.skills[:5]:
                skill = lib.get(sid)
                if skill and skill.get("content"):
                    parts.append(f"### {skill['name']}\n{skill['content'][:1500]}")
            skills_prompt = "\n\n".join(parts)
        except Exception:
            pass

    # Inject global lessons from past epics (cross-epic learning)
    lessons_prompt = ""
    try:
        mem = get_memory_manager()
        lessons = mem.global_get(category="lesson", limit=8) or []
        lessons += mem.global_get(category="improvement", limit=4) or []
        if lessons:
            lesson_lines = []
            for l in lessons:
                val = l.get("value", "") if isinstance(l, dict) else str(l)
                if val:
                    lesson_lines.append(f"- {val[:150]}")
            if lesson_lines:
                lessons_prompt = (
                    "\n## Lessons from past epics\n"
                    "Apply these learnings from previous projects:\n" + "\n".join(lesson_lines[:10])
                )
    except Exception:
        pass

    # Inject SI blueprint for architecture/devops/security agents
    si_prompt = ""
    role_lower = (agent.role or "").lower()
    si_roles = ("architect", "devops", "sre", "security", "lead")
    if any(r in role_lower for r in si_roles) and run.project_id:
        try:
            import yaml as _yaml

            bp_path = Path(__file__).resolve().parents[2] / "data" / "si_blueprints"
            # Try project_id first, then check if there's a parent project
            for bp_name in (run.project_id,):
                bp_file = bp_path / f"{bp_name}.yaml"
                if bp_file.exists():
                    with open(bp_file) as _f:
                        bp = _yaml.safe_load(_f)
                    si_prompt = (
                        "\n## SI Blueprint (target infrastructure)\n"
                        f"Cloud: {bp.get('cloud', {}).get('provider', '?')} / {bp.get('cloud', {}).get('region', '')}\n"
                        f"Compute: {bp.get('compute', {}).get('type', '?')}\n"
                        f"CI/CD: {bp.get('cicd', {}).get('provider', '?')}\n"
                    )
                    if bp.get("databases"):
                        si_prompt += (
                            f"Databases: {', '.join(d.get('type', '') for d in bp['databases'])}\n"
                        )
                    if bp.get("conventions"):
                        si_prompt += f"Deploy: {bp['conventions'].get('deploy', '?')}, Secrets: {bp['conventions'].get('secrets', '?')}\n"
                    if bp.get("constraints"):
                        si_prompt += "Constraints: " + " | ".join(bp["constraints"][:5]) + "\n"
                    if bp.get("existing_services"):
                        si_prompt += "Existing services:\n"
                        for svc in bp["existing_services"][:5]:
                            si_prompt += f"  - {svc.get('name', '')}: {svc.get('url', '')} ({svc.get('proto', '')})\n"
                    break
        except Exception:
            pass

    has_project = bool(run.project_id)
    # Tools: every agent gets their configured tools when there's a project workspace
    # No rank gating — a CTO can search the web, a DSI can read project files
    tools_for_agent = has_project and bool(project_path)

    # Role-based tool filtering — each agent only sees tools relevant to their role
    from ..agents.tool_schemas import _get_tools_for_agent

    allowed_tools = _get_tools_for_agent(agent) if tools_for_agent else None

    # Enrich project_context with lessons and SI blueprint
    if lessons_prompt:
        project_context += "\n" + lessons_prompt
    if si_prompt:
        project_context += "\n" + si_prompt

    return ExecutionContext(
        agent=agent,
        session_id=run.session_id,
        project_id=run.project_id,
        project_path=project_path,
        history=history_dicts,
        project_context=project_context,
        skills_prompt=skills_prompt,
        vision=vision,
        tools_enabled=tools_for_agent,
        allowed_tools=allowed_tools,
    )


# ── Pattern Runners ─────────────────────────────────────────────

# Imports from extracted pattern implementations
from .impls.aggregator import run_aggregator as _impl_aggregator
from .impls.hierarchical import run_hierarchical as _impl_hierarchical
from .impls.human_in_the_loop import run_human_in_the_loop as _impl_human_in_the_loop
from .impls.loop import run_loop as _impl_loop
from .impls.network import run_network as _impl_network
from .impls.parallel import run_parallel as _impl_parallel
from .impls.router import run_router as _impl_router
from .impls.sequential import run_sequential as _impl_sequential
from .impls.solo import run_solo as _impl_solo
from .impls.wave import run_wave as _impl_wave


class _EngineProxy:
    """Thin proxy exposing module-level engine functions as instance methods.

    Passed as 'engine' to extracted pattern implementations so they can call
    engine._execute_node(), engine._ordered_nodes(), etc.
    """

    @staticmethod
    async def _execute_node(
        run, node_id, task, context_from="", to_agent_id="", protocol_override=""
    ):
        return await _execute_node(
            run,
            node_id,
            task,
            context_from=context_from,
            to_agent_id=to_agent_id,
            protocol_override=protocol_override,
        )

    @staticmethod
    def _ordered_nodes(pattern):
        return _ordered_nodes(pattern)

    @staticmethod
    def _node_agent_id(run, node_id):
        return _node_agent_id(run, node_id)

    @staticmethod
    def _build_compressed_context(accumulated, budget=CONTEXT_BUDGET):
        return _build_compressed_context(accumulated, budget)

    @staticmethod
    def _compute_waves(pattern):
        return _compute_waves(pattern)


_engine_proxy = _EngineProxy()


def _ordered_nodes(pattern: PatternDef) -> list[str]:
    """Return node IDs in topological order based on edges."""
    node_ids = [n["id"] for n in pattern.agents]
    # Build adjacency from sequential/parallel edges
    incoming = {nid: set() for nid in node_ids}
    for edge in pattern.edges:
        if edge.get("type") in ("sequential", "parallel"):
            incoming[edge["to"]].add(edge["from"])

    ordered = []
    remaining = set(node_ids)
    while remaining:
        # Find nodes with no unresolved incoming
        ready = [n for n in remaining if not (incoming[n] - set(ordered))]
        if not ready:
            # Cycle detected, just add remaining
            ordered.extend(remaining)
            break
        ordered.extend(sorted(ready))
        remaining -= set(ready)
    return ordered


def _node_agent_id(run: PatternRun, node_id: str) -> str:
    """Get the agent ID assigned to a node."""
    state = run.nodes.get(node_id)
    return state.agent.id if state and state.agent else node_id


def _compress_output(text: str, max_chars: int = COMPRESSED_OUTPUT_SIZE) -> str:
    """Compress an agent's output to key points for context rot mitigation.

    Keeps: first paragraph, lines with decisions/actions/key markers.
    Discards: verbose analysis, repeated context, filler.
    """
    if len(text) <= max_chars:
        return text
    lines = text.split("\n")
    kept = []
    char_count = 0
    # Always keep first non-empty paragraph
    for line in lines:
        if line.strip():
            kept.append(line)
            char_count += len(line)
            break
    # Then scan for high-signal lines
    signal_markers = (
        "decision",
        "choix",
        "stack",
        "conclusion",
        "recommand",
        "action",
        "verdict",
        "valide",
        "approve",
        "reject",
        "veto",
        "[pr]",
        "architecture",
        "technologie",
        "priorit",
        "- ",
        "* ",
        "1.",
        "2.",
        "3.",
    )
    for line in lines[1:]:
        stripped = line.strip().lower()
        if not stripped:
            continue
        if any(m in stripped for m in signal_markers) or stripped.startswith("#"):
            kept.append(line)
            char_count += len(line)
            if char_count >= max_chars:
                break
    result = "\n".join(kept)
    if len(result) > max_chars:
        result = result[:max_chars] + "..."
    return result


def _build_compressed_context(accumulated: list[str], budget: int = CONTEXT_BUDGET) -> str:
    """Build context string with compression for older outputs.

    Last agent's output stays full. Earlier outputs are compressed
    to fit within the budget — preventing context rot.
    """
    if not accumulated:
        return ""
    if len(accumulated) == 1:
        return accumulated[0][:budget]

    last = accumulated[-1]
    older = accumulated[:-1]

    # Reserve half budget for last output, half for compressed older
    last_budget = budget // 2
    older_budget = budget - last_budget

    last_text = last[:last_budget]

    # Compress older outputs to fit
    per_agent = max(200, older_budget // len(older))
    compressed = []
    for entry in older:
        # Entry format: "[AgentName]:\n{output}"
        header_end = entry.find("\n")
        if header_end > 0:
            header = entry[:header_end]
            body = _compress_output(entry[header_end + 1 :], per_agent)
            compressed.append(f"{header}\n{body}")
        else:
            compressed.append(_compress_output(entry, per_agent))

    return "\n\n---\n\n".join(compressed) + "\n\n---\n\n" + last_text


def _compute_waves(pattern: PatternDef) -> list[list[str]]:
    """Compute dependency waves for parallel execution.

    Groups nodes into waves: all nodes in a wave have their dependencies
    satisfied by previous waves. Nodes within a wave run in parallel.

    Returns: [[wave1_nodes], [wave2_nodes], ...]
    """
    node_ids = [n["id"] for n in pattern.agents]
    if not node_ids:
        return []

    # Build dependency graph from edges
    incoming = {nid: set() for nid in node_ids}
    for edge in pattern.edges:
        src, dst = edge.get("from"), edge.get("to")
        if src in incoming and dst in incoming:
            incoming[dst].add(src)

    waves = []
    done = set()
    remaining = set(node_ids)

    while remaining:
        # Nodes whose dependencies are all in 'done'
        wave = [n for n in remaining if incoming[n] <= done]
        if not wave:
            # Cycle — put all remaining in one final wave
            waves.append(sorted(remaining))
            break
        wave.sort()
        waves.append(wave)
        done.update(wave)
        remaining -= set(wave)

    return waves
