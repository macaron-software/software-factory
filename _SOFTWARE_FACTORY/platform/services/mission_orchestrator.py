"""Mission orchestrator — core mission execution logic.

Extracted from web/routes/missions.py to keep route handlers thin.
"""
from __future__ import annotations

import asyncio
import logging
import traceback
from datetime import datetime

logger = logging.getLogger(__name__)


class MissionOrchestrator:
    """Drives mission execution: CDP orchestrates phases sequentially.

    Uses the REAL pattern engine (run_pattern) for each phase — agents
    think with LLM, stream their responses, and interact per pattern type.
    """

    def __init__(
        self,
        mission,
        workflow,
        run_store,
        agent_store,
        session_id: str,
        orch_id: str,
        orch_name: str,
        orch_role: str,
        orch_avatar: str,
        push_sse,
    ):
        self.mission = mission
        self.wf = workflow
        self.run_store = run_store
        self.agent_store = agent_store
        self.session_id = session_id
        self.orch_id = orch_id
        self.orch_name = orch_name
        self.orch_role = orch_role
        self.orch_avatar = orch_avatar
        self._push_sse = push_sse

    # ── helpers re-used by the phase loop ──

    async def _sse_orch_msg(self, content: str, phase_id: str = ""):
        await self._push_sse(self.session_id, {
            "type": "message",
            "from_agent": self.orch_id,
            "from_name": self.orch_name,
            "from_role": self.orch_role,
            "from_avatar": self.orch_avatar,
            "content": content,
            "phase_id": phase_id,
            "msg_type": "text",
        })

    # ── main entry point ──

    async def run_phases(self):
        """Execute phases sequentially using the real pattern engine.

        Error reloop: when QA or deploy fails, re-run dev→CI/CD→QA with
        error feedback injected (max 2 reloops to avoid infinite loops).
        """
        from ..models import PhaseStatus, MissionStatus
        from ..patterns.engine import run_pattern, NodeStatus
        from ..patterns.store import PatternDef
        # Late imports to avoid circular deps
        from ..web.routes.missions import (
            _build_phase_prompt,
            _detect_project_platform,
            _extract_features_from_phase,
            _run_post_phase_hooks,
            _auto_retrospective,
        )

        mission = self.mission
        wf = self.wf
        run_store = self.run_store
        agent_store = self.agent_store
        session_id = self.session_id

        workspace = mission.workspace_path or ""
        phases_done = 0
        phases_failed = 0
        phase_summaries = []
        reloop_count = 0
        MAX_RELOOPS = 2
        reloop_errors = []

        # Evidence gate: acceptance criteria for dev phases
        from ..services.evidence import get_criteria_for_workflow, run_evidence_checks, format_evidence_report
        wf_config = wf.config if hasattr(wf, 'config') and isinstance(wf.config, dict) else {}
        acceptance_criteria = get_criteria_for_workflow(wf.id, wf_config)
        if acceptance_criteria:
            logger.info("Evidence gate: %d acceptance criteria for workflow %s", len(acceptance_criteria), wf.id)

        i = 0
        while i < len(mission.phases):
            phase = mission.phases[i]
            wf_phase = wf.phases[i] if i < len(wf.phases) else None
            if not wf_phase:
                i += 1
                continue

            if phase.status in (PhaseStatus.DONE, PhaseStatus.DONE_WITH_ISSUES, PhaseStatus.SKIPPED):
                if phase.summary:
                    phase_summaries.append(f"## {wf_phase.name}\n{phase.summary}")
                i += 1
                continue

            cfg = wf_phase.config or {}
            aids = cfg.get("agent_ids", cfg.get("agents", []))
            pattern_type = wf_phase.pattern_id

            # Build CDP context: workspace state + previous phase summaries
            cdp_context = ""
            if mission.workspace_path:
                try:
                    import subprocess
                    ws = mission.workspace_path
                    file_count = subprocess.run(
                        ["find", ws, "-type", "f", "-not", "-path", "*/.git/*"],
                        capture_output=True, text=True, timeout=5
                    )
                    n_files = len(file_count.stdout.strip().split("\n")) if file_count.stdout.strip() else 0
                    git_log = subprocess.run(
                        ["git", "log", "--oneline", "-5"],
                        cwd=ws, capture_output=True, text=True, timeout=5
                    )
                    cdp_context = f"Workspace: {n_files} fichiers"
                    if git_log.stdout.strip():
                        cdp_context += f" | Git: {git_log.stdout.strip().split(chr(10))[0]}"
                except Exception:
                    pass

            prev_context = ""
            if phase_summaries:
                prev_context = "\n".join(
                    s if isinstance(s, str) else f"- Phase {s.get('name','?')}: {s.get('summary','')}"
                    for s in phase_summaries[-5:]
                )

            # CDP announces the phase
            detected_platform = _detect_project_platform(workspace) if workspace else ""
            platform_display = {
                "macos-native": "🖥️ macOS native (Swift/SwiftUI)",
                "ios-native": "📱 iOS native (Swift/SwiftUI)",
                "android-native": "🤖 Android native (Kotlin)",
                "web-docker": "🌐 Web (Docker)",
                "web-node": "🌐 Web (Node.js)",
                "web-static": "🌐 Web statique",
            }.get(detected_platform, "")
            cdp_announce = f"Lancement phase {i+1}/{len(mission.phases)} : **{wf_phase.name}** (pattern: {pattern_type})"
            if platform_display:
                cdp_announce += f"\nPlateforme détectée : {platform_display}"
            if cdp_context:
                cdp_announce += f"\n{cdp_context}"
            await self._sse_orch_msg(cdp_announce, phase.phase_id)
            await asyncio.sleep(0.5)

            # Snapshot message count before phase starts
            from ..sessions.store import get_session_store as _get_ss
            _ss_pre = _get_ss()
            _pre_phase_msg_count = len(_ss_pre.get_messages(session_id, limit=1000))

            # Update phase status
            phase.status = PhaseStatus.RUNNING
            phase.started_at = datetime.utcnow()
            phase.agent_count = len(aids)
            mission.current_phase = phase.phase_id
            run_store.update(mission)

            await self._push_sse(session_id, {
                "type": "phase_started",
                "mission_id": mission.id,
                "phase_id": phase.phase_id,
                "phase_name": wf_phase.name,
                "pattern": pattern_type,
                "agents": aids,
            })

            # Build PatternDef for this phase
            agent_nodes = [{"id": aid, "agent_id": aid} for aid in aids]

            leader = cfg.get("leader", "")
            if not leader and aids:
                ranked = sorted(aids, key=lambda a: agent_store.get(a).hierarchy_rank if agent_store.get(a) else 50)
                leader = ranked[0]

            edges = self._build_edges(pattern_type, aids, leader)

            phase_pattern = PatternDef(
                id=f"mission-{mission.id}-phase-{phase.phase_id}",
                name=wf_phase.name,
                type=pattern_type,
                agents=agent_nodes,
                edges=edges,
                config={"max_rounds": 2, "max_iterations": 3},
            )

            phase_task = _build_phase_prompt(wf_phase.name, pattern_type, mission.brief, i, len(mission.phases), prev_context, workspace_path=workspace)
            phase_task += f"\nMISSION_ID: {mission.id}"

            # Sprint loop
            phase_key_check = wf_phase.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
            is_dev_phase = "sprint" in phase_key_check or "dev" in phase_key_check or "features" in phase_key_check or "test" in phase_key_check
            is_retryable = is_dev_phase or "cicd" in phase_key_check or "qa" in phase_key_check or "architecture" in phase_key_check or "setup" in phase_key_check
            max_sprints = wf_phase.config.get("max_iterations", 5) if is_dev_phase else 1

            phase_success = False
            phase_error = ""
            current_sprint_id = None

            for sprint_num in range(1, max_sprints + 1):
                sprint_label = f"Sprint {sprint_num}/{max_sprints}" if max_sprints > 1 else ""

                # SAFe: Auto-create Sprint record for dev phases
                if is_dev_phase:
                    try:
                        from ..missions.store import get_mission_store, SprintDef
                        _ms = get_mission_store()
                        sprint = SprintDef(
                            mission_id=mission.id,
                            number=sprint_num,
                            name=f"Sprint {sprint_num}" + (f" — {wf_phase.name}" if sprint_num == 1 else ""),
                            goal=phase_task[:200] if sprint_num == 1 else f"Iteration {sprint_num} — correction et amélioration",
                            status="active",
                            started_at=datetime.utcnow().isoformat(),
                        )
                        sprint = _ms.create_sprint(sprint)
                        current_sprint_id = sprint.id
                        logger.info("SAFe Sprint created: %s (num=%d, mission=%s)", sprint.id, sprint_num, mission.id)
                    except Exception as e:
                        logger.warning("Sprint creation failed: %s", e)

                if max_sprints > 1:
                    await self._sse_orch_msg(f"Lancement {sprint_label} pour «{wf_phase.name}»", phase.phase_id)
                    await asyncio.sleep(0.5)
                    phase_task = _build_phase_prompt(wf_phase.name, pattern_type, mission.brief, i, len(mission.phases), prev_context, workspace_path=workspace)
                    phase_task += (
                        f"\n\n--- {sprint_label} ---\n"
                        f"C'est le sprint {sprint_num} sur {max_sprints} prévus.\n"
                    )
                    if sprint_num == 1:
                        phase_task += "Focus: mise en place structure projet, première feature MVP.\n"
                    elif sprint_num < max_sprints:
                        phase_task += "Focus: itérez sur les features suivantes du backlog, utilisez le code existant.\n"
                    else:
                        phase_task += "Focus: sprint final — finalisez, nettoyez, préparez le handoff CI/CD.\n"

                    # Inject backlog from earlier phases
                    if mission.id:
                        try:
                            from ..memory.manager import get_memory_manager
                            mem = get_memory_manager()
                            backlog_items = mem.project_get(mission.id, category="product")
                            arch_items = mem.project_get(mission.id, category="architecture")
                            if backlog_items or arch_items:
                                phase_task += "\n\n--- Backlog et architecture (phases précédentes) ---\n"
                                for item in (backlog_items or [])[:5]:
                                    phase_task += f"- [Backlog] {item.get('key', '')}: {item.get('value', '')[:200]}\n"
                                for item in (arch_items or [])[:5]:
                                    phase_task += f"- [Archi] {item.get('key', '')}: {item.get('value', '')[:200]}\n"
                        except Exception:
                            pass

                    # SAFe B1: Feature Pull
                    if is_dev_phase:
                        try:
                            from ..missions.product import get_product_backlog
                            pb = get_product_backlog()
                            features = pb.list_features(epic_id=mission.id)
                            if features:
                                phase_task += "\n\n--- Features Backlog (WSJF priorité) ---\n"
                                for fi, feat in enumerate(features[:8]):
                                    status_icon = {"backlog": "⏳", "ready": "📋", "in_progress": "🔄", "done": "✅"}.get(feat.status, "?")
                                    phase_task += f"{fi+1}. {status_icon} [{feat.story_points}SP] {feat.name}: {feat.description[:100]}\n"
                                    if feat.status == "backlog" and sprint_num == 1:
                                        pb.update_feature_status(feat.id, "in_progress")
                        except Exception:
                            pass

                    # SAFe D1: Learning Loop
                    if is_dev_phase and sprint_num > 1:
                        try:
                            from ..memory.manager import get_memory_manager
                            mem = get_memory_manager()
                            learnings = mem.global_search("retrospective sprint")
                            if learnings:
                                phase_task += "\n\n--- Learnings des sprints précédents ---\n"
                                for l in learnings[:3]:
                                    phase_task += f"- {l.get('value', '')[:200]}\n"
                        except Exception:
                            pass

                try:
                    # Phase timeout: 10 minutes max per phase execution
                    PHASE_TIMEOUT = 600
                    MAX_LLM_RETRIES = 2
                    LLM_RETRY_DELAY = 30  # seconds between retries on rate limit

                    for llm_attempt in range(1, MAX_LLM_RETRIES + 1):
                        try:
                            result = await asyncio.wait_for(
                                run_pattern(
                                    phase_pattern, session_id, phase_task,
                                    project_id=mission.project_id or mission.id,
                                    project_path=mission.workspace_path,
                                    phase_id=phase.phase_id,
                                ),
                                timeout=PHASE_TIMEOUT,
                            )
                            phase_success = result.success
                            if not phase_success:
                                failed_nodes = [
                                    n for n in result.nodes.values()
                                    if n.status not in (NodeStatus.COMPLETED, NodeStatus.PENDING)
                                ]
                                if result.error:
                                    phase_error = result.error
                                elif failed_nodes:
                                    errors = []
                                    for fn in failed_nodes:
                                        err = (fn.result.error if fn.result else "") or fn.output or ""
                                        errors.append(f"{fn.agent_id}: {err[:100]}")
                                    phase_error = "; ".join(errors)
                                else:
                                    phase_error = "Pattern returned success=False"
                                # Retry on rate limit errors
                                is_rate_limit = any(kw in phase_error.lower() for kw in ("rate limit", "429", "all llm providers failed", "throttl"))
                                if is_rate_limit and llm_attempt < MAX_LLM_RETRIES:
                                    logger.warning("Phase %s rate-limited (attempt %d/%d), waiting %ds...", phase.phase_id, llm_attempt, MAX_LLM_RETRIES, LLM_RETRY_DELAY)
                                    await self._sse_orch_msg(f"⏳ Rate limit — pause {LLM_RETRY_DELAY}s avant retry ({llm_attempt}/{MAX_LLM_RETRIES})…", phase.phase_id)
                                    await asyncio.sleep(LLM_RETRY_DELAY)
                                    continue
                            break  # Success or non-retryable error
                        except asyncio.TimeoutError:
                            if llm_attempt < MAX_LLM_RETRIES:
                                logger.warning("Phase %s timed out (attempt %d/%d), retrying...", phase.phase_id, llm_attempt, MAX_LLM_RETRIES)
                                await asyncio.sleep(LLM_RETRY_DELAY)
                                continue
                            logger.error("Phase %s timed out after %ds (all retries exhausted)", phase.phase_id, PHASE_TIMEOUT)
                            phase_error = f"Phase timed out after {PHASE_TIMEOUT}s"
                            break
                except Exception as exc:
                    logger.error("Phase %s pattern crashed: %s\n%s", phase.phase_id, exc, traceback.format_exc())
                    phase_error = str(exc)

                # SAFe B2: Sprint Review + Retro Auto
                if is_dev_phase and current_sprint_id:
                    try:
                        from ..missions.store import get_mission_store
                        _ms = get_mission_store()
                        sprint_status = "completed" if phase_success else "failed"
                        _ms.update_sprint_status(current_sprint_id, sprint_status)
                        try:
                            from ..llm.client import get_llm_client, LLMMessage
                            llm = get_llm_client()
                            retro_prompt = (
                                f"Sprint {sprint_num} {'réussi' if phase_success else 'échoué'}. "
                                f"Erreur: {phase_error[:300] if phase_error else 'none'}. "
                                f"Génère une rétrospective en 3 points: "
                                f"1) Ce qui a bien marché 2) Ce qui n'a pas marché 3) Action d'amélioration. "
                                f"2-3 phrases max par point."
                            )
                            retro_resp = await asyncio.wait_for(
                                llm.chat([LLMMessage(role="user", content=retro_prompt)], max_tokens=300, temperature=0.4),
                                timeout=30)
                            retro_text = (retro_resp.content or "").strip()
                            if retro_text:
                                _ms.update_sprint_retro(current_sprint_id, retro_text)
                                from ..memory.manager import get_memory_manager
                                mem = get_memory_manager()
                                mem.global_store(
                                    key=f"retro-sprint-{mission.id}-{sprint_num}",
                                    value=retro_text[:500],
                                    category="retrospective",
                                )
                                logger.info("SAFe Retro stored for sprint %d (mission %s)", sprint_num, mission.id)
                        except Exception as e:
                            logger.warning("Retro generation failed: %s", e)
                        # SAFe B3: Velocity tracking
                        if phase_success:
                            try:
                                import subprocess as _sp
                                ws = getattr(mission, 'workspace_path', '')
                                if ws:
                                    res = _sp.run(
                                        ["git", "diff", "--stat", "HEAD~1"],
                                        cwd=ws, capture_output=True, text=True, timeout=10,
                                    )
                                    files_changed = res.stdout.count("|") if res.returncode == 0 else 0
                                    velocity = max(1, files_changed)
                                    _ms.update_sprint_velocity(current_sprint_id, velocity, planned_sp=velocity)
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning("Sprint update failed: %s", e)

                if not phase_success:
                    if sprint_num < max_sprints:
                        retry_label = f"Itération {sprint_num}/{max_sprints}" if not is_dev_phase else sprint_label
                        remediation_msg = f"{retry_label} terminé avec des problèmes. Relance avec feedback correctif…"
                        await self._sse_orch_msg(remediation_msg, phase.phase_id)
                        await asyncio.sleep(0.8)
                        prev_context += f"\n- REJET itération {sprint_num}: {phase_error[:500]}"
                        phase_error = ""
                        continue
                    else:
                        break

                # ── Evidence Gate: check acceptance criteria after dev sprints ──
                if is_dev_phase and acceptance_criteria and workspace:
                    # Reset criteria for fresh check
                    for c in acceptance_criteria:
                        c.passed = False
                        c.detail = ""
                    all_passed, results = run_evidence_checks(workspace, acceptance_criteria)
                    evidence_report = format_evidence_report(results)
                    passed_count = sum(1 for c in results if c.passed)
                    total_count = len(results)

                    await self._push_sse(session_id, {
                        "type": "evidence_gate",
                        "mission_id": mission.id,
                        "phase_id": phase.phase_id,
                        "sprint_num": sprint_num,
                        "passed": passed_count,
                        "total": total_count,
                        "all_passed": all_passed,
                        "details": [{"id": c.id, "desc": c.description, "passed": c.passed, "detail": c.detail} for c in results],
                    })

                    if all_passed:
                        await self._sse_orch_msg(
                            f"Evidence Gate PASSED ({passed_count}/{total_count}) — tous les critères d'acceptation remplis.",
                            phase.phase_id,
                        )
                        logger.info("Evidence gate PASSED for %s sprint %d (%d/%d)", phase.phase_id, sprint_num, passed_count, total_count)
                        break  # All criteria met, exit sprint loop
                    else:
                        if sprint_num < max_sprints:
                            await self._sse_orch_msg(
                                f"Evidence Gate FAILED ({passed_count}/{total_count}) — critères manquants, relance sprint…",
                                phase.phase_id,
                            )
                            logger.warning("Evidence gate FAILED for %s sprint %d (%d/%d), looping", phase.phase_id, sprint_num, passed_count, total_count)
                            # Inject evidence feedback into next sprint prompt
                            prev_context += f"\n\n{evidence_report}"
                            continue  # Loop to next sprint
                        else:
                            await self._sse_orch_msg(
                                f"Evidence Gate FAILED ({passed_count}/{total_count}) — max sprints atteint.\n{evidence_report}",
                                phase.phase_id,
                            )
                            logger.error("Evidence gate FAILED for %s, max sprints exhausted", phase.phase_id)
                            phase_success = False
                            phase_error = f"Acceptance criteria not met: {passed_count}/{total_count}"
                            break

                if max_sprints > 1 and sprint_num < max_sprints:
                    await self._sse_orch_msg(f"{sprint_label} terminé. Passage au sprint suivant…", phase.phase_id)
                    await asyncio.sleep(0.8)

            # Human-in-the-loop checkpoint
            if pattern_type == "human-in-the-loop":
                phase.status = PhaseStatus.WAITING_VALIDATION
                run_store.update(mission)
                await self._push_sse(session_id, {
                    "type": "checkpoint",
                    "mission_id": mission.id,
                    "phase_id": phase.phase_id,
                    "question": f"Validation requise pour «{wf_phase.name}»",
                    "options": ["GO", "NOGO", "PIVOT"],
                })
                for _ in range(600):
                    await asyncio.sleep(1)
                    m = run_store.get(mission.id)
                    if m:
                        for p in m.phases:
                            if p.phase_id == phase.phase_id and p.status != PhaseStatus.WAITING_VALIDATION:
                                phase.status = p.status
                                break
                        if phase.status != PhaseStatus.WAITING_VALIDATION:
                            break
                if phase.status == PhaseStatus.WAITING_VALIDATION:
                    phase.status = PhaseStatus.DONE
                if phase.status == PhaseStatus.FAILED:
                    run_store.update(mission)
                    await self._push_sse(session_id, {
                        "type": "phase_failed",
                        "mission_id": mission.id,
                        "phase_id": phase.phase_id,
                    })
                    await self._sse_orch_msg("Epic arrêtée — décision NOGO.", phase.phase_id)
                    mission.status = MissionStatus.FAILED
                    run_store.update(mission)
                    return
            else:
                phase.status = PhaseStatus.DONE if phase_success else PhaseStatus.FAILED

            phase_success = (phase.status == PhaseStatus.DONE)

            phase.completed_at = datetime.utcnow()
            if phase_success:
                try:
                    from ..sessions.store import get_session_store
                    from ..llm.client import get_llm_client, LLMMessage
                    ss = get_session_store()
                    phase_msgs = ss.get_messages(session_id, limit=1000)
                    convo = []
                    for m in phase_msgs[_pre_phase_msg_count:]:
                        txt = (getattr(m, 'content', '') or '').strip()
                        if not txt or len(txt) < 20:
                            continue
                        agent = getattr(m, 'from_agent', '') or ''
                        if agent in ('system', 'user', 'chef_de_programme'):
                            continue
                        name = getattr(m, 'from_name', '') or agent
                        convo.append(f"{name}: {txt[:500]}")
                    if convo:
                        transcript = "\n\n".join(convo[-15:])
                        llm = get_llm_client()
                        resp = await asyncio.wait_for(llm.chat([
                            LLMMessage(role="user", content=f"Summarize this team discussion in 2-3 sentences. Focus on decisions made, key proposals, and conclusions. Be factual and specific. Answer in the same language as the discussion.\n\n{transcript[:4000]}")
                        ], max_tokens=200, temperature=0.3), timeout=45)
                        phase.summary = (resp.content or "").strip()[:500]
                    if not getattr(phase, 'summary', None):
                        phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                except Exception:
                    phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                phases_done += 1

                summary_text = f"[{wf_phase.name}] terminée"
                if mission.workspace_path:
                    try:
                        import subprocess as _sp
                        diff_stat = _sp.run(
                            ["git", "diff", "--stat", "HEAD~1"],
                            cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                        )
                        if diff_stat.stdout.strip():
                            summary_text += f" | Fichiers: {diff_stat.stdout.strip().split(chr(10))[-1]}"
                    except Exception:
                        pass
                try:
                    from ..memory.manager import get_memory_manager
                    mem = get_memory_manager()
                    if mission.project_id:
                        mem.project_store(
                            mission.project_id,
                            key=f"phase:{wf_phase.name}",
                            value=summary_text[:500],
                            category="phase-summary",
                            source="mission-control",
                        )
                except Exception:
                    pass
                phase_summaries.append(f"## {wf_phase.name}\n{summary_text[:200]}")
            else:
                phase.summary = f"Phase échouée — {phase_error[:200]}"
                phases_failed += 1
            run_store.update(mission)

            # Extract features from phase output into PO backlog
            if phase_success:
                asyncio.ensure_future(_extract_features_from_phase(
                    mission.id, session_id, phase.phase_id,
                    wf_phase.name, phase.summary or "",
                    _pre_phase_msg_count
                ))
                try:
                    from ..db.migrations import get_db as _gdb_feat
                    _fdb = _gdb_feat()
                    if phase.phase_id in ("dev-sprint",):
                        _fdb.execute("UPDATE features SET status='in_progress' WHERE epic_id=? AND status='backlog'", (mission.id,))
                        _fdb.commit()
                    elif phase.phase_id in ("qa-campaign", "qa-execution", "deploy-prod"):
                        _fdb.execute("UPDATE features SET status='done' WHERE epic_id=? AND status='in_progress'", (mission.id,))
                        _fdb.commit()
                    rows = _fdb.execute("SELECT name, status, priority, story_points FROM features WHERE epic_id=?", (mission.id,)).fetchall()
                    if rows:
                        _bl = [{"name":r[0],"priority":r[2],"story_points":r[3]} for r in rows if r[1]=="backlog"]
                        _sp = [{"name":r[0],"priority":r[2],"story_points":r[3]} for r in rows if r[1]=="in_progress"]
                        _dn = [{"name":r[0]} for r in rows if r[1]=="done"]
                        await self._push_sse(session_id, {
                            "type": "kanban_refresh",
                            "mission_id": mission.id,
                            "backlog": _bl, "sprint": _sp, "done": _dn,
                        })
                except Exception:
                    pass

            await self._push_sse(session_id, {
                "type": "phase_completed",
                "mission_id": mission.id,
                "phase_id": phase.phase_id,
                "success": phase_success,
            })

            # Feedback loop: activate TMA after deploy phase
            if phase_success and phase.phase_id in ("deploy-prod", "deploy", "tma-handoff"):
                try:
                    from ..missions.feedback import on_deploy_completed
                    if mission.project_id:
                        on_deploy_completed(mission.project_id, mission.id)
                except Exception as _fb_err:
                    logger.warning("Feedback on_deploy_completed failed: %s", _fb_err)

            # Feedback: create TMA incident on deploy failure
            if not phase_success and phase.phase_id in ("deploy-prod", "deploy"):
                try:
                    from ..missions.feedback import on_deploy_failed
                    if mission.project_id:
                        on_deploy_failed(mission.project_id, mission.id, phase_error or "Deploy phase failed")
                except Exception as _fb_err:
                    logger.warning("Feedback on_deploy_failed failed: %s", _fb_err)

            # Feedback loop: track TMA fix for recurring incident detection
            if phase_success and phase.phase_id in ("fix", "tma-fix", "validate"):
                if mission.type in ("bug", "program") and mission.project_id:
                    try:
                        from ..missions.feedback import on_tma_incident_fixed
                        incident_key = (mission.config or {}).get("incident_key", mission.name)
                        on_tma_incident_fixed(mission.project_id, incident_key)
                    except Exception as _fb_err:
                        logger.warning("Feedback on_tma_incident_fixed failed: %s", _fb_err)

            # CDP announces result
            if i < len(mission.phases) - 1:
                if phase_success:
                    cdp_msg = f"Phase «{wf_phase.name}» réussie. Passage à la phase suivante…"
                    await self._sse_orch_msg(cdp_msg, phase.phase_id)
                    await asyncio.sleep(0.8)
                else:
                    phase_gate = getattr(wf_phase, 'gate', 'always') or 'always'
                    phase_key = phase.phase_id.lower() if phase.phase_id else ""
                    is_execution_phase = any(k in phase_key for k in ("sprint", "dev", "cicd", "ci-cd", "pipeline"))
                    is_hitl_gate = phase_gate == "all_approved" and pattern_type in ("human-in-the-loop",)
                    is_blocking = phase_gate in ("all_approved", "no_veto") or is_execution_phase
                    short_err = phase_error[:200] if phase_error else "erreur inconnue"
                    if is_hitl_gate:
                        cdp_msg = f"Phase «{wf_phase.name}» échouée ({short_err}). Epic arrêtée — corrigez puis relancez via le bouton Réinitialiser."
                    elif is_blocking:
                        cdp_msg = f"Phase «{wf_phase.name}» échouée ({short_err}). Phase bloquante — correction nécessaire avant de continuer."
                    else:
                        cdp_msg = f"Phase «{wf_phase.name}» terminée avec des problèmes ({short_err}). Passage à la phase suivante malgré tout…"
                        phase.status = PhaseStatus.DONE_WITH_ISSUES
                        phases_done += 1
                        phases_failed -= 1
                        try:
                            from ..sessions.store import get_session_store
                            ss = get_session_store()
                            phase_msgs = ss.get_messages(session_id, limit=1000)
                            convo = []
                            for pm in phase_msgs[_pre_phase_msg_count:]:
                                txt = (getattr(pm, 'content', '') or '').strip()
                                if not txt or len(txt) < 20:
                                    continue
                                agent = getattr(pm, 'from_agent', '') or ''
                                if agent in ('system', 'user', 'chef_de_programme'):
                                    continue
                                name = getattr(pm, 'from_name', '') or agent
                                convo.append(f"{name}: {txt[:300]}")
                            if convo:
                                from ..llm.client import get_llm_client, LLMMessage
                                llm = get_llm_client()
                                transcript = "\n\n".join(convo[-10:])
                                resp = await asyncio.wait_for(llm.chat([
                                    LLMMessage(role="user", content=f"Résume cette discussion d'équipe en 2-3 phrases. Focus sur les décisions et conclusions. Même langue que la discussion.\n\n{transcript[:3000]}")
                                ], max_tokens=200, temperature=0.3), timeout=45)
                                new_summary = (resp.content or "").strip()[:500]
                                if new_summary and len(new_summary) > 20:
                                    phase.summary = new_summary
                                else:
                                    phase.summary = f"{len(aids)} agents ont travaillé ({pattern_type}) — terminée avec avertissements"
                            else:
                                phase.summary = f"{len(aids)} agents, pattern: {pattern_type}"
                        except Exception:
                            phase.summary = f"{len(aids)} agents ont travaillé ({pattern_type}) — terminée avec avertissements"
                    await self._sse_orch_msg(cdp_msg, phase.phase_id)
                    if is_hitl_gate:
                        mission.status = MissionStatus.FAILED
                        run_store.update(mission)
                        await self._push_sse(session_id, {
                            "type": "mission_failed",
                            "mission_id": mission.id,
                            "phase_id": phase.phase_id,
                            "error": short_err,
                        })
                        return
                    else:
                        await asyncio.sleep(0.8)

            # Post-phase hooks (non-blocking)
            if phase_success:
                async def _safe_hooks():
                    try:
                        await asyncio.wait_for(
                            _run_post_phase_hooks(
                                phase.phase_id, wf_phase.name, mission, session_id, self._push_sse
                            ), timeout=90
                        )
                    except Exception as hook_err:
                        logger.warning("Post-phase hooks timeout/error for %s: %s", phase.phase_id, hook_err)
                asyncio.create_task(_safe_hooks())

            # Error Reloop
            if not phase_success and reloop_count < MAX_RELOOPS:
                phase_key_rl = phase.phase_id.lower() if phase.phase_id else ""
                is_reloopable = any(k in phase_key_rl for k in ("qa", "deploy", "tma", "sprint", "dev", "cicd", "ci-cd", "pipeline"))
                if is_reloopable:
                    reloop_count += 1
                    reloop_errors.append(f"[Reloop {reloop_count}] Phase «{wf_phase.name}» failed: {phase_error[:300]}")
                    dev_idx = None
                    for j, wp_j in enumerate(wf.phases):
                        pk_j = wp_j.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
                        if "sprint" in pk_j or "dev" in pk_j:
                            dev_idx = j
                            break
                    if dev_idx is not None and dev_idx <= i:
                        reloop_msg = (
                            f"Reloop {reloop_count}/{MAX_RELOOPS} — Phase «{wf_phase.name}» échouée. "
                            f"Error: {phase_error[:200]}. "
                            f"Back to development sprint for correction…"
                        )
                        await self._sse_orch_msg(reloop_msg, phase.phase_id)
                        await asyncio.sleep(1)
                        reset_pids = []
                        for k in range(dev_idx, len(mission.phases)):
                            mission.phases[k].status = PhaseStatus.PENDING
                            mission.phases[k].summary = None
                            mission.phases[k].started_at = None
                            mission.phases[k].completed_at = None
                            reset_pids.append(mission.phases[k].phase_id)
                        run_store.update(mission)
                        await self._push_sse(session_id, {
                            "type": "reloop",
                            "mission_id": mission.id,
                            "reloop_count": reloop_count,
                            "max_reloops": MAX_RELOOPS,
                            "failed_phase": phase.phase_id,
                            "target_phase": mission.phases[dev_idx].phase_id,
                            "reset_phases": reset_pids,
                            "error": phase_error[:200],
                        })
                        error_feedback = "\n".join(reloop_errors)
                        prev_context += f"\n\n--- RELOOP FEEDBACK (erreurs à corriger) ---\n{error_feedback}\n"
                        i = dev_idx
                        continue

            i += 1

        # Mission complete
        phases_done = sum(1 for p in mission.phases if p.status == PhaseStatus.DONE)
        phases_with_issues = sum(1 for p in mission.phases if p.status == PhaseStatus.DONE_WITH_ISSUES)
        phases_failed = sum(1 for p in mission.phases if p.status == PhaseStatus.FAILED)
        total = phases_done + phases_with_issues + phases_failed
        if phases_failed == 0 and phases_with_issues == 0:
            mission.status = MissionStatus.COMPLETED
            reloop_info = f" ({reloop_count} reloop{'s' if reloop_count > 1 else ''})" if reloop_count > 0 else ""
            final_msg = f"Epic terminée avec succès — {phases_done}/{total} phases réussies{reloop_info}."
        else:
            mission.status = MissionStatus.COMPLETED if phases_done > 0 else MissionStatus.FAILED
            reloop_info = f" ({reloop_count} reloop{'s' if reloop_count > 1 else ''})" if reloop_count > 0 else ""
            issues_info = f", {phases_with_issues} avec avertissements" if phases_with_issues > 0 else ""
            final_msg = f"Epic terminée — {phases_done} réussies{issues_info}, {phases_failed} échouées sur {total} phases{reloop_info}."
        run_store.update(mission)
        await self._sse_orch_msg(final_msg)

        try:
            await _auto_retrospective(mission, session_id, phase_summaries, self._push_sse)
        except Exception as retro_err:
            logger.warning(f"Auto-retrospective failed: {retro_err}")

    def _build_edges(self, pattern_type: str, aids: list, leader: str) -> list:
        """Build edges for the pattern graph."""
        edges = []
        others = [a for a in aids if a != leader] if leader else aids

        if pattern_type == "network":
            if leader:
                for o in others:
                    edges.append({"from": leader, "to": o, "type": "delegate"})
            for idx_a, a in enumerate(others):
                for b in others[idx_a+1:]:
                    edges.append({"from": a, "to": b, "type": "bidirectional"})
            if leader:
                for o in others:
                    edges.append({"from": o, "to": leader, "type": "report"})

        elif pattern_type == "sequential":
            for idx_a in range(len(aids) - 1):
                edges.append({"from": aids[idx_a], "to": aids[idx_a+1], "type": "sequential"})
            if len(aids) > 2:
                edges.append({"from": aids[-1], "to": aids[0], "type": "feedback"})

        elif pattern_type == "hierarchical" and leader:
            for sub in others:
                edges.append({"from": leader, "to": sub, "type": "delegate"})
            workers = [a for a in others if (self.agent_store.get(a) or type('',(),{'hierarchy_rank':50})).hierarchy_rank >= 40]
            for idx_a, a in enumerate(workers):
                for b in workers[idx_a+1:]:
                    edges.append({"from": a, "to": b, "type": "bidirectional"})
            for sub in others:
                edges.append({"from": sub, "to": leader, "type": "report"})

        elif pattern_type == "aggregator" and aids:
            aggregator_id = leader or (aids[-1] if len(aids) > 1 else aids[0])
            contributors = [a for a in aids if a != aggregator_id]
            for a in contributors:
                edges.append({"from": a, "to": aggregator_id, "type": "report"})
            for idx_a, a in enumerate(contributors):
                for b in contributors[idx_a+1:]:
                    edges.append({"from": a, "to": b, "type": "bidirectional"})

        elif pattern_type == "router" and aids:
            router_id = leader or aids[0]
            specialists = [a for a in aids if a != router_id]
            for a in specialists:
                edges.append({"from": router_id, "to": a, "type": "route"})
                edges.append({"from": a, "to": router_id, "type": "report"})

        elif pattern_type == "human-in-the-loop" and aids:
            for o in others:
                edges.append({"from": o, "to": leader, "type": "report"})
            for idx_a, a in enumerate(others):
                for b in others[idx_a+1:]:
                    edges.append({"from": a, "to": b, "type": "bidirectional"})

        elif pattern_type == "loop" and len(aids) >= 2:
            edges.append({"from": aids[0], "to": aids[1], "type": "sequential"})
            edges.append({"from": aids[1], "to": aids[0], "type": "feedback"})

        elif pattern_type == "parallel" and aids:
            dispatcher = leader or aids[0]
            workers = [a for a in aids if a != dispatcher]
            for w in workers:
                edges.append({"from": dispatcher, "to": w, "type": "delegate"})
                edges.append({"from": w, "to": dispatcher, "type": "report"})

        return edges
