"""Hierarchical pattern: manager decomposes, devs execute, QA validates."""
from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)


def _classify_agents(run, node_ids: list[str]) -> dict:
    """Classify nodes by role: manager, workers, qa, based on agent role/rank."""
    classified = {"manager": None, "workers": [], "qa": []}
    for nid in node_ids:
        ns = run.nodes.get(nid)
        if not ns or not ns.agent:
            continue
        role = (ns.agent.role or "").lower()
        rank = getattr(ns.agent, "hierarchy_rank", 50)
        if "qa" in role or "test" in role:
            classified["qa"].append(nid)
        elif "lead" in role or rank <= 20:
            # First lead/manager found — if we already have one, second is worker
            if classified["manager"] is None:
                classified["manager"] = nid
            else:
                classified["workers"].append(nid)
        elif "dev" in role or rank >= 40:
            classified["workers"].append(nid)
        else:
            # Chef de projet, securite, etc. — treat as manager or worker
            if classified["manager"] is None:
                classified["manager"] = nid
            else:
                classified["workers"].append(nid)
    return classified


def _parse_subtasks(text: str) -> list[str]:
    """Extract [SUBTASK N] items from manager output."""
    subtasks = []
    for line in text.split("\n"):
        if "[SUBTASK" in line.upper():
            subtask = line.split("]", 1)[-1].strip() if "]" in line else line
            if subtask:
                subtasks.append(subtask)
    return subtasks


async def run_hierarchical(engine, run, task: str):
    """Real team flow with inner dev loop and outer QA validation loop.

    Flow:
      1. Manager (lead_dev) decomposes work into sub-tasks for devs
      2. INNER LOOP: Devs execute in parallel → Manager reviews completeness
         - If incomplete: manager re-briefs devs with what's missing → devs continue
         - If complete: proceed to QA
      3. QA validates the completed work
      4. OUTER LOOP: If QA VETOs → Manager gets feedback → back to inner loop
      Max 3 outer iterations.
    """
    from ..engine import NodeStatus, _DECOMPOSE_PROTOCOL, _sse
    from ...sessions.store import get_session_store, MessageDef

    nodes = engine._ordered_nodes(run.pattern)
    if len(nodes) < 2:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    roles = _classify_agents(run, nodes)
    manager_id = roles["manager"] or nodes[0]
    worker_ids = roles["workers"]
    qa_ids = roles["qa"]

    # Fallback: if no workers found, all non-manager non-qa are workers
    if not worker_ids:
        worker_ids = [n for n in nodes if n != manager_id and n not in qa_ids]
    if not worker_ids:
        from .sequential import run_sequential
        return await run_sequential(engine, run, task)

    manager_agent = engine._node_agent_id(run, manager_id)

    # Build team roster
    worker_roster = []
    for wid in worker_ids:
        ws = run.nodes.get(wid)
        if ws and ws.agent:
            worker_roster.append(f"- {ws.agent.name} ({ws.agent.role})")

    max_outer = 5   # QA validation retries (build gate reloops up to max_outer-1)
    max_inner = 2   # Dev completeness retries
    veto_feedback = ""

    for outer in range(max_outer):
        # ── Reset statuses ──
        if outer > 0:
            for nid in nodes:
                run.nodes[nid].status = NodeStatus.PENDING
            store = get_session_store()
            store.add_message(MessageDef(
                session_id=run.session_id,
                from_agent="system", to_agent=manager_agent,
                message_type="system",
                content=f"QA loop {outer + 1}/{max_outer} — addressing VETO feedback",
            ))
            await _sse(run, {
                "type": "system",
                "content": f"QA validation loop {outer + 1}/{max_outer}",
            })

        # ── Step 1: Manager decomposes ──
        if outer == 0:
            # Get previous phase summaries for context
            prev_summaries = ""
            try:
                from ...missions.store import get_mission_run_store
                if run.session_id:
                    mr = get_mission_run_store().get(run.session_id)
                    if mr and mr.phases:
                        for ph in mr.phases:
                            if ph.status == "done" and ph.summary:
                                prev_summaries += f"- {ph.phase_name}: {ph.summary}\n"
            except Exception:
                pass

            decompose_prompt = f"Team: {len(worker_roster)} devs. "
            if prev_summaries:
                decompose_prompt += f"Context:\n{prev_summaries}\n"
            decompose_prompt += (
                f"list_files first, then output [SUBTASK N] lines.\n"
                f"1 subtask per dev, 1-3 files each, specific paths.\n\n"
                f"TASK: {task}"
            )
        else:
            decompose_prompt = (
                f"QA REJECTED (iter {outer + 1}). Feedback:\n{veto_feedback}\n\n"
                f"Re-assign fixes. Format: [SUBTASK N]: fix description\n\n{task}"
            )

        # Build targeted routing
        worker_agents = [engine._node_agent_id(run, w) for w in worker_ids]
        # For messages addressing multiple workers, use first worker (UI shows conversation)
        workers_target = worker_agents[0] if len(worker_agents) == 1 else ",".join(worker_agents)
        qa_agents = [engine._node_agent_id(run, q) for q in qa_ids]

        manager_output = await engine._execute_node(
            run, manager_id, decompose_prompt, to_agent_id=workers_target,
            protocol_override=_DECOMPOSE_PROTOCOL,
        )

        # Parse subtasks
        subtasks = _parse_subtasks(manager_output)
        if not subtasks or len(subtasks) < len(worker_ids):
            # Smart fallback: parse architecture summary for file names
            logger.warning("Subtask parsing got %d subtasks for %d workers — using smart fallback",
                           len(subtasks), len(worker_ids))
            # Extract file/module hints from architecture summary
            arch_text = prev_summaries + "\n" + task
            # Find patterns like Sources/Foo/Bar.swift, src/components/Foo.tsx, etc
            file_hints = re.findall(r'(?:Sources|src|lib|app)/[\w/]+\.(?:swift|ts|tsx|py|rs|kt)', arch_text, re.I)
            # Also extract module/class names from parenthetical lists
            names_in_parens = re.findall(r'\(([^)]+)\)', arch_text)
            class_names = []
            for group in names_in_parens:
                for name in re.findall(r'([A-Z]\w+)', group):
                    if name not in ("MVVM", "MVC", "API", "UI", "SPM", "NPM", "GET", "POST"):
                        class_names.append(name)
            # Build per-file subtask list
            subtask_items = []
            if file_hints:
                for fp in file_hints:
                    subtask_items.append(fp)
            elif class_names:
                for cn in class_names[:8]:
                    subtask_items.append(cn)
            # Distribute items across workers
            nw = len(worker_ids)
            subtasks = []
            if subtask_items:
                worker_files: dict[int, list[str]] = {i: [] for i in range(nw)}
                for idx, item in enumerate(subtask_items):
                    worker_files[idx % nw].append(item)
                for wi in range(nw):
                    files_str = ", ".join(worker_files[wi])
                    subtasks.append(
                        f"code_write EACH file: {files_str}\n"
                        f"30+ lines per file. Complete implementation, no stubs."
                    )
            else:
                for wi in range(nw):
                    role = "backend/core" if wi == 0 else ("frontend/UI" if wi == 1 else "tests")
                    subtasks.append(f"Implement {role}. code_write ALL needed files.")

        # ── Step 2: INNER LOOP — Devs work until lead says complete ──
        all_dev_work = ""
        for inner in range(max_inner):
            # Workers execute in parallel
            worker_tasks = []
            for i, wid in enumerate(worker_ids):
                st = subtasks[i] if i < len(subtasks) else subtasks[-1]
                if inner > 0:
                    st = f"INCOMPLETE. Lead feedback:\n{all_dev_work[:300]}\n\nContinue: {st}"
                elif outer > 0:
                    st = f"QA FIX (round {outer + 1}):\n{veto_feedback[:300]}\n\nTask: {st}"
                worker_tasks.append(
                    engine._execute_node(run, wid, st, context_from=manager_output, to_agent_id=manager_agent)
                )
            results = await asyncio.gather(*worker_tasks, return_exceptions=True)

            # Collect worker outputs
            combined_parts = []
            for i, r in enumerate(results):
                ws = run.nodes.get(worker_ids[i])
                name = ws.agent.name if ws and ws.agent else worker_ids[i]
                combined_parts.append(f"[{name}]:\n{r if isinstance(r, str) else str(r)}")
            all_dev_work = "\n\n---\n\n".join(combined_parts)

            # Manager reviews completeness — sends to QA if done, workers if not
            # Get actual file status for review context
            workspace_status = ""
            try:
                workspace = run.project_path or None
                if workspace:
                    import subprocess as _sp
                    git_r = _sp.run(["git", "diff", "--stat", "HEAD"], capture_output=True, text=True, cwd=workspace, timeout=5)
                    ls_r = _sp.run(["find", ".", "-not", "-path", "./.git/*", "-type", "f", "-name", "*.swift", "-o", "-name", "*.ts", "-o", "-name", "*.py", "-o", "-name", "*.rs"],
                                   capture_output=True, text=True, cwd=workspace, timeout=5)
                    workspace_status = f"\n\nACTUAL FILES in workspace:\n{ls_r.stdout[:500]}\nGit changes:\n{git_r.stdout[:500]}"
            except Exception:
                pass
            run.nodes[manager_id].status = NodeStatus.PENDING
            qa_target = qa_agents[0] if qa_agents else manager_agent
            review_output = await engine._execute_node(
                run, manager_id,
                f"Review completeness. [COMPLETE] or [INCOMPLETE] + missing items.\n"
                f"Work:\n{all_dev_work}{workspace_status}",
                context_from=all_dev_work, to_agent_id=qa_target,
            )

            if "[INCOMPLETE]" in review_output.upper():
                # Re-parse manager's updated subtasks for next inner iteration
                new_subtasks = _parse_subtasks(review_output)
                if new_subtasks:
                    subtasks = new_subtasks
                for wid in worker_ids:
                    run.nodes[wid].status = NodeStatus.PENDING
                logger.warning("Inner loop: lead says INCOMPLETE, iteration %d", inner + 1)
                continue
            else:
                # Lead says complete — move to QA
                break

        # ── Step 3: Preflight build gate — automatic build verification ──
        preflight_result = ""
        test_results = ""
        build_passed = True
        workspace = run.project_path or None
        if workspace:
            try:
                import subprocess as _sp
                import os as _os
                from collections import Counter as _Counter
                build_cmds = []
                test_cmds = []

                # ── Duplicate file detection (caused chocolat Swift build failure) ──
                try:
                    all_src_files = []
                    for root, dirs, files in _os.walk(workspace):
                        dirs[:] = [d for d in dirs if d not in ('.git', 'node_modules', 'DerivedData', '.build', '__pycache__', 'dist')]
                        for f in files:
                            if f.endswith(('.swift', '.ts', '.tsx', '.js', '.jsx', '.py', '.rs')):
                                all_src_files.append(f)
                    dupes = [name for name, cnt in _Counter(all_src_files).items() if cnt > 1]
                    if dupes:
                        dupe_list = ", ".join(dupes[:10])
                        preflight_result += f"[WARN] Duplicate filenames detected: {dupe_list}\n"
                except Exception:
                    pass

                # ── Detect project type and run appropriate build ──
                if _os.path.isfile(_os.path.join(workspace, "Package.swift")):
                    # Use /usr/bin/swift to avoid OpenStack Swift CLI conflict
                    _swift = "/usr/bin/swift" if _os.path.isfile("/usr/bin/swift") else "swift"
                    build_cmds.append(("swift build", f"{_swift} build 2>&1 | tail -30"))
                    test_cmds.append(("swift test", f"{_swift} test 2>&1 | tail -30"))
                if _os.path.isfile(_os.path.join(workspace, "Cargo.toml")):
                    build_cmds.append(("cargo check", "cargo check 2>&1 | tail -20"))
                    test_cmds.append(("cargo test", "cargo test 2>&1 | tail -30"))
                if _os.path.isfile(_os.path.join(workspace, "package.json")):
                    build_cmds.append(("npm install", "npm install --no-audit --no-fund 2>&1 | tail -10"))
                    # Check if build script exists
                    try:
                        import json as _json
                        with open(_os.path.join(workspace, "package.json")) as _f:
                            pkg = _json.load(_f)
                        if "build" in pkg.get("scripts", {}):
                            build_cmds.append(("npm build", "npm run build 2>&1 | tail -20"))
                        if "test" in pkg.get("scripts", {}):
                            test_cmds.append(("npm test", "npm test 2>&1 | tail -30"))
                    except Exception:
                        pass
                if _os.path.isfile(_os.path.join(workspace, "requirements.txt")):
                    build_cmds.append(("pip check", "pip install -r requirements.txt --dry-run 2>&1 | tail -5"))
                if _os.path.isfile(_os.path.join(workspace, "Dockerfile")):
                    build_cmds.append(("docker build", "docker build --no-cache -t preflight-test . 2>&1 | tail -20"))

                # Syntax checks for files without a build system
                if not build_cmds:
                    for ext, checker in [("*.py", "python3 -m py_compile"), ("*.js", "node --check")]:
                        check_r = _sp.run(
                            f'find . -not -path "./.git/*" -not -path "*/node_modules/*" -name "{ext}" -type f | head -5',
                            shell=True, capture_output=True, text=True, cwd=workspace, timeout=5
                        )
                        files = [f.strip() for f in check_r.stdout.strip().split("\n") if f.strip()]
                        for fpath in files:
                            build_cmds.append((f"syntax {fpath}", f"{checker} {fpath}"))

                # ── Run build checks ──
                preflight_parts = []
                any_failed = False
                for label, cmd in build_cmds[:8]:
                    try:
                        r = _sp.run(cmd, shell=True, capture_output=True, text=True,
                                    cwd=workspace, timeout=180, env={**_os.environ, "DOCKER_BUILDKIT": "1"})
                        status = "PASS" if r.returncode == 0 else "FAIL"
                        if r.returncode != 0:
                            any_failed = True
                        output = (r.stdout + r.stderr)[-500:].strip()
                        preflight_parts.append(f"[{status}] {label}: exit={r.returncode}\n{output}")
                    except Exception as e:
                        preflight_parts.append(f"[SKIP] {label}: {e}")

                # ── Run tests if build passed ──
                test_result_parts = []
                if not any_failed and test_cmds:
                    for label, cmd in test_cmds[:3]:
                        try:
                            r = _sp.run(cmd, shell=True, capture_output=True, text=True,
                                        cwd=workspace, timeout=180, env={**_os.environ})
                            status = "PASS" if r.returncode == 0 else "FAIL"
                            output = (r.stdout + r.stderr)[-500:].strip()
                            test_result_parts.append(f"[{status}] {label}: exit={r.returncode}\n{output}")
                        except Exception as e:
                            test_result_parts.append(f"[SKIP] {label}: {e}")

                preflight_result = "\n".join(preflight_parts)
                test_results = "\n".join(test_result_parts) if test_result_parts else ""
                build_passed = not any_failed

                if preflight_result:
                    status_label = "FAILED" if any_failed else "PASSED"
                    full_report = f"**Preflight Build Gate — {status_label}**\n```\n{preflight_result}\n```"
                    if test_results:
                        full_report += f"\n**Test Results:**\n```\n{test_results}\n```"
                    await _sse(run, {
                        "type": "message",
                        "from_agent": "system",
                        "content": full_report,
                        "message_type": "system",
                    })
                    store = get_session_store()
                    store.add_message(MessageDef(
                        session_id=run.session_id,
                        from_agent="system", to_agent="all",
                        message_type="system",
                        content=f"Preflight Build Gate — {status_label}\n{preflight_result}" + (f"\nTests:\n{test_results}" if test_results else ""),
                    ))
                    logger.info("Preflight gate: %s (%d build checks, %d test checks)", status_label, len(preflight_parts), len(test_result_parts))

                    # ── BLOCKING: if build failed, loop back to devs ──
                    if any_failed and outer < max_outer - 1:
                        veto_feedback = f"BUILD FAILED — fix these errors before proceeding:\n{preflight_result}"
                        await _sse(run, {
                            "type": "system",
                            "content": f"Build gate FAILED — looping back to dev (attempt {outer + 1}/{max_outer})",
                        })
                        logger.warning("Build gate FAILED — relooping to dev iteration %d", outer + 1)
                        continue  # Goes back to outer loop → resets all statuses → devs get error feedback

            except Exception as e:
                logger.warning("Preflight gate error: %s", e)
                preflight_result = f"Preflight skipped: {e}"

        # ── Step 4: QA validates (with preflight results) ──
        if not qa_ids:
            # No QA agent — phase done
            return

        qa_context = f"Lead review:\n{review_output[:300]}\nDev output:\n{all_dev_work[:500]}"
        if preflight_result:
            qa_context += f"\n\nPREFLIGHT BUILD RESULTS (build {'PASSED' if build_passed else 'FAILED'}):\n{preflight_result}"
        if test_results:
            qa_context += f"\n\nTEST RESULTS:\n{test_results}"

        for qid in qa_ids:
            run.nodes[qid].status = NodeStatus.PENDING
            await engine._execute_node(
                run, qid,
                f"Validate dev work. Run tests with build tool. [APPROVE] or [VETO] + reasons.\n"
                f"{qa_context}",
                context_from=review_output, to_agent_id=manager_agent,
            )

        # ── Step 5: Check QA verdicts ──
        vetoes = []
        for qid in qa_ids:
            ns = run.nodes[qid]
            if ns.status == NodeStatus.VETOED:
                agent_name = ns.agent.name if ns.agent else qid
                vetoes.append(f"[VETO by {agent_name}]: {(ns.output or '')[:500]}")

        if not vetoes:
            # QA approved — phase done
            return

        # QA rejected — build feedback for outer loop
        veto_feedback = "\n\n".join(vetoes)
        logger.warning("QA VETO at outer iteration %d: %d veto(s)", outer + 1, len(vetoes))

        store = get_session_store()
        store.add_message(MessageDef(
            session_id=run.session_id,
            from_agent="system", to_agent=manager_agent,
            message_type="system",
            content=f"QA rejected — {len(vetoes)} VETO(s). Feedback loop — re-assign corrections.",
        ))
        await _sse(run, {
            "type": "message",
            "from_agent": "system",
            "content": f"{len(vetoes)} VETO(s) — correction loop {outer + 1}/{max_outer}",
            "message_type": "system",
        })

    # Exhausted retries — if build never passed, raise to mark phase as FAILED
    if not build_passed:
        logger.warning("Hierarchical phase exhausted %d iterations — build NEVER passed", max_outer)
        raise RuntimeError(f"Build never passed after {max_outer} dev iterations")
    logger.warning("Hierarchical phase exhausted %d QA iterations with unresolved VETOs", max_outer)
