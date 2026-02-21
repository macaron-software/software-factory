"""Mission context builder — aggregates data for mission control page.

Extracted from web/routes/missions.py to keep route handlers thin.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class MissionContextBuilder:
    """Builds the template context dict for the Mission Control dashboard."""

    def __init__(self, mission_id: str):
        self.mission_id = mission_id

    async def build_context(self) -> dict | None:
        """Return a dict ready for template rendering, or None if mission not found."""
        from ..missions.store import get_mission_run_store
        from ..agents.store import get_agent_store
        from ..workflows.store import get_workflow_store
        from ..sessions.store import get_session_store
        from ..memory.manager import get_memory_manager
        from ..web.routes.helpers import _agent_map_for_template
        from ..web.routes.missions import _detect_project_platform

        mission_id = self.mission_id
        run_store = get_mission_run_store()
        mission = run_store.get(mission_id)
        if not mission:
            return None

        # Sub-missions hierarchy
        sub_missions = run_store.list_children_runs(mission_id)
        parent_mission = None
        if mission.parent_mission_id:
            parent_mission = run_store.get(mission.parent_mission_id)

        agents = get_agent_store().list_all()
        agent_map = _agent_map_for_template(agents)

        # Build phase→agents mapping + per-phase sub-graphs
        phase_agents = {}
        phase_graphs = {}
        wf = get_workflow_store().get(mission.workflow_id)
        if wf:
            phase_agents, phase_graphs = self._build_phase_graphs(wf, agents, agent_map)

        # Session messages
        messages, phase_messages = self._extract_messages(mission, wf, agent_map, get_session_store)

        # Screenshots
        phase_screenshots = self._extract_screenshots(phase_messages, mission)

        # Memory entries
        memories, memory_groups = self._load_memories(mission, get_memory_manager)

        # Tool-extracted data
        tool_commits, tool_prs, tool_features = self._extract_tool_data(mission, get_session_store)

        # Pull requests & workspace commits
        pull_requests, workspace_commits = self._load_git_data(mission, tool_prs, tool_commits)

        # SI Blueprint
        si_blueprint = self._load_si_blueprint(mission)

        # Global lessons
        lessons = self._load_lessons(get_memory_manager)

        # Result section
        result = self._build_result_section(mission, _detect_project_platform)

        # Workspace files
        workspace_files = self._scan_workspace_files(mission)

        # PO Kanban
        po_backlog, po_sprint, po_done = self._load_po_kanban(mission, tool_features)

        # QA data
        qa_data = self._load_qa_data(mission, phase_messages, wf)

        # Architecture tab
        archi = self._load_architecture_data(mission, phase_messages, wf)

        # Wiki tab
        wiki_pages, wiki_memories = self._load_wiki_data(mission, lessons, get_memory_manager)

        # Tab profiles
        tab_profile, support_tickets = self._build_tab_profile(mission, agent_map)

        return {
            "mission": mission,
            "agent_map": agent_map,
            "phase_agents": phase_agents,
            "phase_graphs": phase_graphs,
            "messages": messages,
            "phase_messages": phase_messages,
            "phase_screenshots": phase_screenshots,
            "memories": memories,
            "memory_groups": memory_groups,
            "pull_requests": pull_requests,
            "workspace_commits": workspace_commits,
            "si_blueprint": si_blueprint,
            "lessons": lessons,
            "features": tool_features,
            "session_id": mission.session_id or "",
            "result_screenshots": result["screenshots"],
            "result_build_cmd": result["build_cmd"],
            "result_run_cmd": result["run_cmd"],
            "result_launch_cmd": result["launch_cmd"],
            "result_deploy_url": result["deploy_url"],
            "result_project_type": result["project_type"],
            "workspace_files": workspace_files,
            "po_backlog": po_backlog,
            "po_sprint": po_sprint,
            "po_done": po_done,
            "agent_scores": qa_data["agent_scores"],
            "qa_pass_rate": qa_data["qa_pass_rate"],
            "qa_total_accepted": qa_data["qa_total_accepted"],
            "qa_total_rejected": qa_data["qa_total_rejected"],
            "qa_total_iterations": qa_data["qa_total_iterations"],
            "qa_test_files": qa_data["qa_test_files"],
            "qa_phase_results": qa_data["qa_phase_results"],
            "qa_coverage": qa_data["qa_coverage"],
            "archi_content": archi["content"],
            "archi_updated": archi["updated"],
            "archi_decisions": archi["decisions"],
            "archi_stack": archi["stack"],
            "wiki_pages": wiki_pages,
            "wiki_memories": wiki_memories,
            "orchestrator_id": mission.cdp_agent_id or "chef_de_programme",
            "tab_profile": tab_profile,
            "workflow_type": mission.workflow_id or "",
            "support_tickets": support_tickets,
            "sub_missions": sub_missions,
            "parent_mission": parent_mission,
            "page_title": f"Epic Control — {mission.workflow_name}",
        }

    # ── private helpers ──

    def _build_phase_graphs(self, wf, agents, agent_map):
        phase_agents = {}
        phase_graphs = {}
        global_graph = (wf.config or {}).get("graph", {})
        all_nodes = global_graph.get("nodes", [])
        all_edges = global_graph.get("edges", [])
        nid_to_agent = {n["id"]: n.get("agent_id", "") for n in all_nodes}
        agent_defs = {a.id: a for a in agents}

        for wp in wf.phases:
            cfg = wp.config or {}
            aids = cfg.get("agent_ids", cfg.get("agents", []))
            entries = []
            for a in aids:
                adef = agent_defs.get(a)
                am = agent_map.get(a, {})
                entries.append({
                    "id": a,
                    "name": am.get("name", a),
                    "role": am.get("role", ""),
                    "avatar_url": am.get("avatar_url", ""),
                    "color": am.get("color", "#8b949e"),
                    "tagline": getattr(adef, "tagline", "") or "" if adef else "",
                    "persona": getattr(adef, "persona", "") or "" if adef else "",
                    "motivation": getattr(adef, "motivation", "") or "" if adef else "",
                    "skills": getattr(adef, "skills", []) or [] if adef else [],
                    "tools": getattr(adef, "tools", []) or [] if adef else [],
                    "model": getattr(adef, "model", "") or "" if adef else "",
                    "provider": getattr(adef, "provider", "") or "" if adef else "",
                })
            phase_agents[wp.id] = entries

            agent_set = set(aids)
            p_nodes = [n for n in all_nodes if n.get("agent_id") in agent_set]
            p_node_ids = {n["id"] for n in p_nodes}
            p_edges = [e for e in all_edges if e["from"] in p_node_ids and e["to"] in p_node_ids]

            pattern_id = wp.pattern_id or ""
            if len(p_nodes) >= 2:
                self._auto_generate_edges(p_nodes, p_edges, pattern_id, agent_map)

            enriched_nodes = []
            for n in p_nodes:
                aid = n.get("agent_id", "")
                am = agent_map.get(aid, {})
                enriched_nodes.append({
                    "id": n["id"], "agent_id": aid,
                    "label": am.get("name", n.get("label", aid)),
                    "role": am.get("role", ""),
                    "avatar": am.get("avatar_url", ""),
                    "hierarchy_rank": am.get("hierarchy_rank", 50),
                })
            phase_graphs[wp.id] = {"nodes": enriched_nodes, "edges": p_edges}

        return phase_agents, phase_graphs

    def _auto_generate_edges(self, p_nodes, p_edges, pattern_id, agent_map):
        """Auto-generate rich multi-pattern edges."""
        pids = [n["id"] for n in p_nodes]
        ranked = sorted(p_nodes, key=lambda n: agent_map.get(n.get("agent_id",""), {}).get("hierarchy_rank", 50))
        leader_nid = ranked[0]["id"]

        C_HIER   = "#f59e0b"
        C_NET    = "#8b5cf6"
        C_SEQ    = "#3b82f6"
        C_LOOP   = "#ec4899"
        C_PAR    = "#10b981"
        C_GATE   = "#ef4444"
        C_AGG    = "#06b6d4"
        C_ROUTE  = "#f97316"

        def _add(f, t, **kw):
            if not any(e["from"] == f and e["to"] == t for e in p_edges):
                p_edges.append({"from": f, "to": t, **kw})

        if pattern_id == "network":
            for i, a in enumerate(pids):
                for b in pids[i+1:]:
                    _add(a, b, color=C_NET, label="")
                    _add(b, a, color=C_NET, label="")
            others = [p for p in pids if p != leader_nid]
            for a in others:
                _add(a, leader_nid, color=C_AGG, label="synthèse")

        elif pattern_id == "human-in-the-loop":
            advisors = [p for p in pids if p != leader_nid]
            for a in advisors:
                _add(a, leader_nid, color=C_HIER, label="avis")
            for i, a in enumerate(advisors):
                for b in advisors[i+1:]:
                    _add(a, b, color=C_NET, label="débat")
                    _add(b, a, color=C_NET, label="")
            if advisors:
                _add(leader_nid, advisors[0], color=C_GATE, label="GO/NOGO")

        elif pattern_id == "sequential":
            for i in range(len(pids) - 1):
                _add(pids[i], pids[i+1], color=C_SEQ, label="")
            if len(pids) >= 3:
                _add(pids[-1], pids[0], color=C_LOOP, label="feedback")

        elif pattern_id == "aggregator":
            aggregator = pids[-1]
            contributors = [p for p in pids if p != aggregator]
            for a in contributors:
                _add(a, aggregator, color=C_AGG, label="")
            for a in contributors:
                _add(aggregator, a, color=C_LOOP, label="review")
            for i, a in enumerate(contributors):
                for b in contributors[i+1:]:
                    _add(a, b, color=C_NET, label="")

        elif pattern_id == "hierarchical":
            team = [p for p in pids if p != leader_nid]
            for t in team:
                _add(leader_nid, t, color=C_HIER, label="")
            for t in team:
                _add(t, leader_nid, color=C_LOOP, label="review")
            for i, a in enumerate(team):
                for b in team[i+1:]:
                    _add(a, b, color=C_NET, label="")

        elif pattern_id == "parallel":
            workers = [p for p in pids if p != leader_nid]
            for w in workers:
                _add(leader_nid, w, color=C_PAR, label="")
            for w in workers:
                _add(w, leader_nid, color=C_AGG, label="résultat")
            for i, a in enumerate(workers):
                for b in workers[i+1:]:
                    _add(a, b, color=C_NET, label="")

        elif pattern_id == "loop":
            for i in range(len(pids)):
                f, t = pids[i], pids[(i+1) % len(pids)]
                _add(f, t, color=C_LOOP, label="")
                _add(t, f, color=C_LOOP, label="feedback")

        elif pattern_id == "router":
            specialists = [p for p in pids if p != leader_nid]
            for s in specialists:
                _add(leader_nid, s, color=C_ROUTE, label="route")
            for s in specialists:
                _add(s, leader_nid, color=C_AGG, label="résolu")
            for i, a in enumerate(specialists):
                for b in specialists[i+1:]:
                    _add(a, b, color=C_NET, label="")

        else:
            for i in range(len(pids) - 1):
                _add(pids[i], pids[i+1], color="#8b949e")

    def _extract_messages(self, mission, wf, agent_map, get_session_store):
        messages = []
        phase_messages: dict[str, list] = {}
        _agent_to_phase: dict[str, str] = {}
        if wf:
            for wp in wf.phases:
                cfg = wp.config or {}
                for aid in cfg.get("agent_ids", cfg.get("agents", [])):
                    _agent_to_phase.setdefault(aid, wp.id)
        _current_phase_infer = ""
        if mission.session_id:
            session_store = get_session_store()
            msgs = session_store.get_messages(mission.session_id, limit=500)
            for m in msgs:
                if m.from_agent == "system" and m.content:
                    for wp in (wf.phases if wf else []):
                        if wp.name and wp.name in m.content and "started" in m.content:
                            _current_phase_infer = wp.id
                            break
                if m.message_type == "system" and m.from_agent == "system":
                    continue
                _c = (m.content or "").strip()
                if not _c or _c.startswith(("<FunctionCall", "<tool_code", "[TOOL_CALL]{")):
                    continue
                ag = agent_map.get(m.from_agent)
                meta = {}
                if hasattr(m, "metadata") and m.metadata:
                    meta = m.metadata if isinstance(m.metadata, dict) else {}
                msg_dict = {
                    "from_agent": m.from_agent,
                    "to_agent": getattr(m, "to_agent", "") or "",
                    "content": m.content,
                    "message_type": m.message_type,
                    "timestamp": m.created_at if hasattr(m, "created_at") else "",
                    "metadata": meta,
                }
                messages.append(msg_dict)
                pid = meta.get("phase_id", "") or _current_phase_infer or _agent_to_phase.get(m.from_agent, "")
                if pid:
                    phase_messages.setdefault(pid, []).append(msg_dict)
        return messages, phase_messages

    def _extract_screenshots(self, phase_messages, mission):
        phase_screenshots: dict[str, list[str]] = {}
        for pid, pmsgs in phase_messages.items():
            shots = []
            for m in pmsgs:
                for match in re.finditer(r'\[SCREENSHOT:([^\]]+)\]', m.get("content", "")):
                    p = match.group(1).strip().lstrip("./")
                    shots.append(p)
            if shots:
                phase_screenshots[pid] = shots[:6]

        if mission.workspace_path:
            _ws_shots_dir = Path(mission.workspace_path) / "screenshots"
            if _ws_shots_dir.exists():
                _ws_shots = sorted(
                    [f"screenshots/{f.name}" for f in _ws_shots_dir.glob("*.png")
                     if f.stat().st_size > 1000],
                )
                if _ws_shots:
                    for pid in ("qa-campaign", "qa-execution", "test"):
                        if pid not in phase_screenshots:
                            phase_screenshots[pid] = _ws_shots[:6]
                            break
        return phase_screenshots

    def _load_memories(self, mission, get_memory_manager):
        memories = []
        _useful_cats = {"product", "architecture", "security", "development", "quality",
                        "phase-summary", "vision", "convention", "team",
                        "decisions", "infrastructure"}
        try:
            mem_mgr = get_memory_manager()
            proj_mems = mem_mgr.project_get(mission.id, limit=80) or []
            for pm in proj_mems:
                if not isinstance(pm, dict):
                    continue
                cat = pm.get("category", "")
                key = pm.get("key", "")
                if key.startswith("agent:"):
                    continue
                if cat in _useful_cats:
                    memories.append(pm)
        except Exception:
            pass

        memory_groups: dict = {}
        for pm in memories:
            c = pm.get("category", "general")
            memory_groups.setdefault(c, []).append(pm)
        return memories, memory_groups

    def _extract_tool_data(self, mission, get_session_store):
        tool_commits = []
        tool_prs = []
        tool_features = []
        try:
            session_store = get_session_store()
            all_msgs = session_store.get_messages(mission.session_id) if mission.session_id else []
            for m in all_msgs:
                content = m.content or ""
                if "git_commit" in content or "[TOOL_CALL]" in content:
                    for match in re.finditer(r'(?:git_commit|git commit)[^\n]*?["\']([^"\']{5,80})["\']', content):
                        tool_commits.append({"hash": f"{hash(match.group(1)) & 0xfffffff:07x}", "message": match.group(1)})
                    for match in re.finditer(r'(?:feat|fix|chore|refactor|test|docs)\([^)]+\):\s*(.{10,80})', content):
                        msg = match.group(0)
                        if msg not in [c["message"] for c in tool_commits]:
                            tool_commits.append({"hash": f"{hash(msg) & 0xfffffff:07x}", "message": msg})
                if "create_pull_request" in content.lower() or "[PR]" in content:
                    for match in re.finditer(r'\[PR\]\s*(.{5,80})', content):
                        tool_prs.append({"number": len(tool_prs) + 1, "title": match.group(1).strip(), "status": "Open"})
                if any(kw in content.lower() for kw in ("implement", "create ", "add ", "[pr]", "livrable")):
                    for match in re.finditer(r'\[PR\]\s*(.{5,100})', content):
                        feat = match.group(1).strip()
                        if feat not in tool_features:
                            tool_features.append(feat)
        except Exception:
            pass
        return tool_commits, tool_prs, tool_features

    def _load_git_data(self, mission, tool_prs, tool_commits):
        pull_requests = list(tool_prs)
        workspace_commits = list(tool_commits)
        if mission.workspace_path:
            import subprocess
            try:
                result = subprocess.run(
                    ["git", "branch", "-a", "--format=%(refname:short)"],
                    cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                )
                branches = [b.strip() for b in result.stdout.strip().split("\n") if b.strip() and b.strip() not in ("master", "main")]
                for i, branch in enumerate(branches[:10]):
                    status = "Open"
                    merged = subprocess.run(
                        ["git", "branch", "--merged", "HEAD", "--format=%(refname:short)"],
                        cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                    )
                    if branch in merged.stdout:
                        status = "Merged"
                    pull_requests.append({"number": i + 1, "title": branch, "status": status})
            except Exception:
                pass
            try:
                result = subprocess.run(
                    ["git", "log", "--oneline", "--no-decorate", "-15"],
                    cwd=mission.workspace_path, capture_output=True, text=True, timeout=5
                )
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        parts = line.strip().split(" ", 1)
                        workspace_commits.append({"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""})
            except Exception:
                pass
        return pull_requests, workspace_commits

    def _load_si_blueprint(self, mission):
        si_blueprint = None
        try:
            import yaml as _yaml
            bp_path = Path(__file__).resolve().parents[1] / "data" / "si_blueprints" / f"{mission.project_id}.yaml"
            if bp_path.exists():
                with open(bp_path) as _f:
                    si_blueprint = _yaml.safe_load(_f)
        except Exception:
            pass
        return si_blueprint

    def _load_lessons(self, get_memory_manager):
        lessons = []
        try:
            mem_mgr = get_memory_manager()
            global_mems = mem_mgr.global_get(category="lesson", limit=20) or []
            global_mems += mem_mgr.global_get(category="improvement", limit=10) or []
            for gm in global_mems:
                if isinstance(gm, dict):
                    lessons.append(gm)
        except Exception:
            pass
        return lessons

    def _build_result_section(self, mission, _detect_project_platform):
        result = {
            "screenshots": [], "build_cmd": "", "run_cmd": "",
            "launch_cmd": "", "deploy_url": "", "project_type": "",
        }
        ws_path = mission.workspace_path or ""
        if not ws_path:
            return result
        ws = Path(ws_path)
        if not ws.exists():
            return result

        # Collect screenshots
        for img_dir in [ws / "screenshots", ws]:
            if img_dir.exists():
                for ext in ("*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp"):
                    for img in sorted(img_dir.glob(ext)):
                        if img.stat().st_size > 5000:
                            rel = img.relative_to(ws)
                            result["screenshots"].append(str(rel))
        result["screenshots"] = result["screenshots"][:12]

        detected = _detect_project_platform(ws_path)
        brief_lower = (mission.brief or "").lower()
        brief_web_keywords = ("site web", "e-commerce", "webapp", "web app", "api rest",
                              "saas", "dashboard", "portail", "backoffice", "back-office",
                              "react", "vue", "angular", "svelte", "next.js", "django",
                              "flask", "fastapi", "express", "node.js", "docker")
        if any(kw in brief_lower for kw in brief_web_keywords):
            if detected in ("macos-native", "ios-native", "unknown"):
                detected = "web-docker" if "docker" in brief_lower else "web-node"
        result["project_type"] = detected

        if detected in ("macos-native", "ios-native"):
            if (ws / "Package.swift").exists():
                result["build_cmd"] = "swift build"
                result["run_cmd"] = "swift run"
                result["launch_cmd"] = "open -a Simulator && swift run"
            elif (ws / "project.yml").exists():
                scheme = "App"
                try:
                    import yaml as _y
                    proj = _y.safe_load((ws / "project.yml").read_text())
                    scheme = proj.get("name", "App")
                except Exception:
                    pass
                result["build_cmd"] = f"xcodegen generate && xcodebuild -scheme {scheme} -configuration Debug build"
                result["run_cmd"] = f"open build/Debug/{scheme}.app"
                result["launch_cmd"] = f"xcodegen generate && xcodebuild -scheme {scheme} -configuration Debug build && open build/Debug/{scheme}.app"
            else:
                result["build_cmd"] = "swift build"
                result["run_cmd"] = "swift run"
                result["launch_cmd"] = "open -a Simulator && swift run"
        elif detected == "android-native":
            result["build_cmd"] = "./gradlew assembleDebug"
            result["run_cmd"] = "./gradlew installDebug"
            result["launch_cmd"] = "adb shell am start -n com.app/.MainActivity"
        elif detected == "web-docker":
            if (ws / "docker-compose.yml").exists():
                result["build_cmd"] = "docker compose build"
                result["run_cmd"] = "docker compose up"
            else:
                result["build_cmd"] = "docker build -t app ."
                result["run_cmd"] = "docker run -p 8080:8080 app"
            result["deploy_url"] = "http://localhost:8080"
        elif detected == "web-node":
            result["build_cmd"] = "npm install && npm run build"
            result["run_cmd"] = "npm start"
            result["deploy_url"] = "http://localhost:3000"
        elif (ws / "Makefile").exists():
            result["build_cmd"] = "make build"
            result["run_cmd"] = "make run"

        if detected.startswith("web") and not result["deploy_url"]:
            for env_file in (ws / "environments.md", ws / ".env", ws / "deploy.md"):
                if env_file.exists():
                    try:
                        env_text = env_file.read_text()[:2000]
                        urls = re.findall(r'https?://[^\s\)\"\']+', env_text)
                        for u in urls:
                            if any(d in u for d in ("azurewebsites", "azure", "herokuapp", "vercel", "netlify", "localhost")):
                                result["deploy_url"] = u
                                break
                    except Exception:
                        pass

        return result

    def _scan_workspace_files(self, mission):
        workspace_files = []
        ws_path = mission.workspace_path or ""
        if not ws_path:
            return workspace_files
        ws = Path(ws_path)
        if not ws.exists():
            return workspace_files
        for root, dirs, files in os.walk(ws):
            level = root.replace(str(ws), "").count(os.sep)
            if level >= 3:
                dirs.clear()
                continue
            rel = os.path.relpath(root, ws)
            if rel == ".":
                rel = ""
            _ws_exclude = {"node_modules", ".git", ".next", "dist", "build", "vendor", "__pycache__", ".tox", "venv"}
            dirs[:] = [d for d in sorted(dirs) if not d.startswith(".") and d not in _ws_exclude][:20]
            for f in sorted(files)[:30]:
                if f.endswith(".bak"):
                    continue
                fpath = os.path.join(rel, f) if rel else f
                workspace_files.append({"path": fpath, "is_dir": False})
        return workspace_files[:100]

    def _load_po_kanban(self, mission, tool_features):
        po_backlog, po_sprint, po_done = [], [], []
        try:
            from ..db.migrations import get_db
            db = get_db()
            rows = db.execute("SELECT name, description, acceptance_criteria, priority, status, story_points, assigned_to FROM features WHERE epic_id=?", (self.mission_id,)).fetchall()
            for r in rows:
                feat = {"name": r[0], "description": r[1] or "", "acceptance_criteria": r[2] or "", "priority": r[3] or 5, "story_points": r[5] or 0, "assigned_to": r[6] or ""}
                if r[4] == "done":
                    po_done.append(feat)
                elif r[4] in ("in_progress", "sprint"):
                    po_sprint.append(feat)
                else:
                    po_backlog.append(feat)
        except Exception:
            pass
        if not po_backlog and not po_sprint and not po_done and tool_features:
            for f in tool_features:
                po_done.append({"name": f, "description": "", "acceptance_criteria": "", "priority": 5, "story_points": 0, "assigned_to": ""})
        if not po_backlog and not po_sprint and not po_done and mission:
            from ..models import PhaseStatus
            done_phases = {"deploy-prod", "qa-execution", "qa-campaign", "tma-router", "tma-fix"}
            sprint_phases = {"dev-sprint", "cicd"}
            for ph in mission.phases:
                if not getattr(ph, "summary", None):
                    continue
                feat = {"name": ph.summary[:80], "description": "", "acceptance_criteria": "",
                        "priority": 5, "story_points": 0, "assigned_to": ""}
                if ph.phase_id in done_phases and ph.status in (PhaseStatus.DONE,):
                    po_done.append(feat)
                elif ph.phase_id in sprint_phases:
                    po_sprint.append(feat)
                elif ph.status in (PhaseStatus.DONE, PhaseStatus.DONE_WITH_ISSUES):
                    po_done.append(feat)
        return po_backlog, po_sprint, po_done

    def _load_qa_data(self, mission, phase_messages, wf):
        agent_scores = []
        qa_total_accepted = 0
        qa_total_rejected = 0
        qa_total_iterations = 0
        try:
            from ..db.migrations import get_db as _gdb_qa
            db = _gdb_qa()
            rows = db.execute("SELECT agent_id, accepted, rejected, iterations, quality_score FROM agent_scores WHERE epic_id=?", (self.mission_id,)).fetchall()
            for r in rows:
                agent_scores.append({"agent_id": r[0], "accepted": r[1], "rejected": r[2], "iterations": r[3], "quality_score": r[4]})
                qa_total_accepted += r[1]
                qa_total_rejected += r[2]
                qa_total_iterations += r[3]
        except Exception:
            pass
        qa_pass_rate = round(qa_total_accepted / qa_total_iterations * 100) if qa_total_iterations > 0 else 0

        qa_test_files = []
        _qa_exclude = {"node_modules", ".git", ".next", "dist", "build", "vendor", "__pycache__", ".tox", "venv"}
        ws_path = mission.workspace_path or ""
        if ws_path and Path(ws_path).exists():
            ws = Path(ws_path)
            test_globs = ["**/test_*.py", "**/*_test.py", "**/*.test.ts", "**/*.test.js",
                          "**/*.spec.ts", "**/*.spec.js", "**/Tests/**/*.swift", "**/*Test.swift",
                          "**/*Test.kt", "**/*Test.java", "tests/**/*", "test/**/*", "__tests__/**/*"]
            seen = set()
            for pat in test_globs:
                for tf in ws.glob(pat):
                    rel = str(tf.relative_to(ws))
                    if any(part in _qa_exclude for part in tf.relative_to(ws).parts):
                        continue
                    if tf.is_file() and tf.suffix in (".py", ".ts", ".js", ".swift", ".kt", ".java") and str(tf) not in seen:
                        seen.add(str(tf))
                        rel = str(tf.relative_to(ws))
                        ttype = "unit"
                        lower = rel.lower()
                        if "e2e" in lower or "integration" in lower or "journey" in lower:
                            ttype = "e2e"
                        elif "smoke" in lower:
                            ttype = "smoke"
                        elif "ui" in lower or "ihm" in lower or "browser" in lower or "spec" in lower:
                            ttype = "e2e-ihm"
                        qa_test_files.append({"path": rel, "type": ttype})
            qa_test_files = sorted(qa_test_files, key=lambda x: x["type"])[:30]

        qa_coverage = {"test_count": len(qa_test_files), "code_count": 0, "ratio": 0, "coverage_pct": None}
        if ws_path and Path(ws_path).exists():
            ws = Path(ws_path)
            code_exts = {".py", ".ts", ".js", ".swift", ".kt", ".java", ".rs"}
            code_count = 0
            for ext in code_exts:
                for cf in ws.rglob(f"*{ext}"):
                    if any(part in _qa_exclude for part in cf.relative_to(ws).parts):
                        continue
                    name = cf.name.lower()
                    if not any(t in name for t in ("test_", "_test.", ".test.", ".spec.", "test")):
                        code_count += 1
            qa_coverage["code_count"] = code_count
            qa_coverage["ratio"] = round(len(qa_test_files) / max(code_count, 1) * 100)
            for cov_file in ["coverage/coverage-summary.json", "htmlcov/status.json", ".coverage", "coverage.xml", "lcov.info"]:
                cp = ws / cov_file
                if cp.exists():
                    try:
                        import json as _jcov
                        if cov_file.endswith(".json"):
                            with open(cp) as _cf:
                                cov_data = _jcov.load(_cf)
                            if "total" in cov_data:
                                qa_coverage["coverage_pct"] = cov_data["total"].get("lines", {}).get("pct")
                                break
                    except Exception:
                        pass

        qa_phase_results = []
        if wf:
            for wp in wf.phases:
                pk = wp.name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
                if "qa" in pk or "test" in pk:
                    pmsgs = phase_messages.get(wp.id, [])
                    for m in pmsgs:
                        content = m.get("content", "")
                        if not content:
                            continue
                        passes = len(re.findall(r'(?:✅|PASS|passed|réussi|OK)', content, re.IGNORECASE))
                        fails = len(re.findall(r'(?:❌|FAIL|failed|échoué|ERROR|KO)', content, re.IGNORECASE))
                        if passes or fails:
                            agent = m.get("from_agent", "unknown")
                            qa_phase_results.append({
                                "phase": wp.name,
                                "agent": agent,
                                "passes": passes,
                                "fails": fails,
                                "excerpt": content[:300],
                            })

        return {
            "agent_scores": agent_scores,
            "qa_pass_rate": qa_pass_rate,
            "qa_total_accepted": qa_total_accepted,
            "qa_total_rejected": qa_total_rejected,
            "qa_total_iterations": qa_total_iterations,
            "qa_test_files": qa_test_files,
            "qa_phase_results": qa_phase_results,
            "qa_coverage": qa_coverage,
        }

    def _load_architecture_data(self, mission, phase_messages, wf):
        archi_content = ""
        archi_updated = ""
        archi_decisions = []
        archi_stack = []
        ws_path = mission.workspace_path or ""
        if ws_path and Path(ws_path).exists():
            ws = Path(ws_path)
            for archi_name in ("Architecture.md", "ARCHITECTURE.md", "architecture.md", "docs/architecture.md"):
                archi_file = ws / archi_name
                if archi_file.exists():
                    try:
                        archi_content = archi_file.read_text()[:8000]
                        mtime = archi_file.stat().st_mtime
                        archi_updated = datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
                    except Exception:
                        pass
                    break

        if wf:
            for wp in wf.phases:
                pmsgs = phase_messages.get(wp.id, [])
                for m in pmsgs:
                    agent = m.get("from_agent", "")
                    content = m.get("content", "")
                    if not content:
                        continue
                    is_archi_agent = any(k in agent for k in ("architecte", "archi", "lead_dev", "sre"))
                    if is_archi_agent and len(content) > 50:
                        for tech in re.findall(r'(?:Swift(?:UI)?|Kotlin|React|Vue|Svelte|FastAPI|Django|Node\.js|PostgreSQL|Redis|Docker|Nginx|Playwright|TypeScript|Python|Rust|Go|GraphQL|gRPC|REST|WebSocket|SSE)', content):
                            if tech not in archi_stack:
                                archi_stack.append(tech)
                        if any(kw in content.lower() for kw in ("architecture", "pattern", "design", "stack", "layer", "module", "service", "composant", "structure", "choix")):
                            archi_decisions.append({"phase": wp.name, "text": content[:400]})
        archi_decisions = archi_decisions[:10]
        archi_stack = archi_stack[:15]

        return {"content": archi_content, "updated": archi_updated, "decisions": archi_decisions, "stack": archi_stack}

    def _load_wiki_data(self, mission, lessons, get_memory_manager):
        wiki_pages = []
        wiki_memories = []
        ws_path = mission.workspace_path or ""
        if ws_path and Path(ws_path).exists():
            ws = Path(ws_path)
            doc_patterns = [
                ("README.md", "README"), ("SPECS.md", "Specifications"),
                ("DesignSystem.md", "Design System"), ("API.md", "API"),
                ("CHANGELOG.md", "Changelog"), ("docs/README.md", "Documentation"),
            ]
            for fname, title in doc_patterns:
                fpath = ws / fname
                if fpath.exists():
                    try:
                        content = fpath.read_text()[:5000]
                        if len(content.strip()) > 20:
                            mtime = fpath.stat().st_mtime
                            updated = datetime.fromtimestamp(mtime).strftime("%d/%m %H:%M")
                            wiki_pages.append({"title": title, "content": content, "updated": updated})
                    except Exception:
                        pass

        try:
            mem = get_memory_manager()
            if mission.project_id:
                entries = mem.project_search(mission.project_id, "", limit=20)
                for e in entries:
                    if hasattr(e, "value") and e.value:
                        wiki_memories.append({"category": getattr(e, "category", "") or "general", "value": e.value[:200]})
        except Exception:
            pass
        for lesson in lessons[:5]:
            wiki_memories.append({"category": "lesson", "value": lesson[:200] if isinstance(lesson, str) else str(lesson)[:200]})
        wiki_memories = wiki_memories[:20]
        return wiki_pages, wiki_memories

    def _build_tab_profile(self, mission, agent_map):
        wf_id = mission.workflow_id or ""
        support_tickets = []
        try:
            from ..db.migrations import get_db
            _tdb = get_db()
            _ticket_rows = _tdb.execute(
                "SELECT * FROM support_tickets WHERE mission_id=? ORDER BY "
                "CASE severity WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 WHEN 'P3' THEN 3 ELSE 4 END, created_at DESC",
                (self.mission_id,)).fetchall()
            support_tickets = [dict(r) for r in _ticket_rows]
            _tdb.close()
        except Exception:
            pass

        if wf_id == "security-hacking":
            tab_profile = [
                {"id": "phases", "label": "Phases", "icon": "list"},
                {"id": "vulns", "label": "Vulnerabilites", "icon": "alert-triangle",
                 "agent_id": "threat-analyst", "fallback": "pentester-lead"},
                {"id": "remediation", "label": "Remediation", "icon": "tool",
                 "agent_id": "security-dev-lead", "fallback": "lead_dev"},
                {"id": "compliance", "label": "Compliance", "icon": "clipboard",
                 "agent_id": "compliance_officer", "fallback": "ciso"},
                {"id": "ciso", "label": "CISO Dashboard", "icon": "shield",
                 "agent_id": "ciso", "fallback": "pentester-lead"},
                {"id": "wiki", "label": "Rapport", "icon": "book-open",
                 "agent_id": "tech_writer", "fallback": "pentester-lead"},
            ]
        elif wf_id == "rse-compliance":
            tab_profile = [
                {"id": "phases", "label": "Phases", "icon": "list"},
                {"id": "rgpd", "label": "RGPD", "icon": "lock",
                 "agent_id": "rse-dpo", "fallback": "rse-manager"},
                {"id": "green-it", "label": "Green IT", "icon": "cpu",
                 "agent_id": "rse-nr", "fallback": "rse-manager"},
                {"id": "a11y", "label": "Accessibilite", "icon": "eye",
                 "agent_id": "rse-a11y", "fallback": "rse-manager"},
                {"id": "ethique", "label": "Ethique IA", "icon": "zap",
                 "agent_id": "rse-ethique-ia", "fallback": "rse-manager"},
                {"id": "wiki", "label": "Synthese", "icon": "book-open",
                 "agent_id": "rse-manager", "fallback": "tech_writer"},
            ]
        elif wf_id in ("tma-maintenance", "dsi-platform-tma"):
            tab_profile = [
                {"id": "phases", "label": "Phases", "icon": "list"},
                {"id": "tickets", "label": "Tickets", "icon": "inbox",
                 "agent_id": "responsable_tma", "fallback": "plat-tma-lead"},
                {"id": "diagnostic", "label": "Diagnostic", "icon": "search",
                 "agent_id": "dev_tma", "fallback": "plat-tma-dev-back"},
                {"id": "correctifs", "label": "Correctifs", "icon": "git-commit",
                 "agent_id": "lead_dev", "fallback": "dev_tma"},
                {"id": "sla", "label": "SLA", "icon": "clock",
                 "agent_id": "chef_projet", "fallback": "responsable_tma"},
                {"id": "historique", "label": "Historique", "icon": "archive",
                 "agent_id": "responsable_tma", "fallback": "plat-tma-lead"},
            ]
        else:
            tab_profile = [
                {"id": "phases", "label": "Phases", "icon": "list"},
                {"id": "dev", "label": "Dev", "icon": "git-branch",
                 "agent_id": "lead_dev", "fallback": "dev_backend"},
                {"id": "po", "label": "PO", "icon": "clipboard",
                 "agent_id": "product_owner", "fallback": "chef_projet"},
                {"id": "qa", "label": "QA", "icon": "check",
                 "agent_id": "qa_lead", "fallback": "test_manager"},
                {"id": "archi", "label": "Archi", "icon": "layers",
                 "agent_id": "architecte", "fallback": "lead_dev"},
                {"id": "wiki", "label": "Wiki", "icon": "book-open",
                 "agent_id": "tech_writer", "fallback": "lead_dev"},
                {"id": "projet", "label": "Projet", "icon": "code"},
            ]

        for tp in tab_profile:
            aid = tp.get("agent_id", "")
            ag = agent_map.get(aid) or agent_map.get(tp.get("fallback", "")) or {}
            tp["agent"] = ag

        return tab_profile, support_tickets
