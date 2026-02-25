"""Internal helpers for mission routes — no route handlers here."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import struct
import subprocess
import uuid
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)

async def _auto_retrospective(
    mission, session_id: str, phase_summaries: list, push_sse
):
    """Auto-generate retrospective when epic completes, store lessons in global memory."""
    import json as _json

    from ....llm.client import LLMMessage, get_llm_client
    from ....memory.manager import get_memory_manager
    from ....sessions.store import get_session_store

    ss = get_session_store()
    msgs = ss.get_messages(session_id, limit=500)
    ctx_parts = [f"Epic: {mission.brief[:200]}"]
    for ps in phase_summaries[-8:]:
        ctx_parts.append(ps[:300] if isinstance(ps, str) else str(ps)[:300])
    for m in msgs[-30:]:
        agent = (
            m.get("from_agent", "")
            if isinstance(m, dict)
            else getattr(m, "from_agent", "")
        )
        content = (
            m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        )
        if content:
            ctx_parts.append(f"{agent}: {content[:150]}")

    context = "\n".join(ctx_parts)[:6000]

    prompt = f"""Analyse cette epic terminée et génère une rétrospective.

Contexte:
{context}

Produis un JSON:
{{
  "successes": ["Ce qui a bien fonctionné (3-5 items)"],
  "failures": ["Ce qui a échoué ou peut être amélioré (2-4 items)"],
  "lessons": ["Leçons techniques concrètes et actionnables (3-5 items)"],
  "improvements": ["Actions d'amélioration pour les prochaines epics (2-4 items)"]
}}

Sois CONCRET, TECHNIQUE et ACTIONNABLE. Réponds UNIQUEMENT avec le JSON."""

    client = get_llm_client()
    try:
        resp = await client.chat(
            messages=[LLMMessage(role="user", content=prompt)],
            system_prompt="Coach Agile expert en rétrospectives SAFe. Analyse factuelle.",
            temperature=0.4,
            max_tokens=1500,
        )
        raw = resp.content.strip()
        if "```json" in raw:
            raw = raw.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw:
            raw = raw.split("```", 1)[1].split("```", 1)[0].strip()
        retro = _json.loads(raw)
    except Exception:
        retro = {
            "successes": ["Epic completed"],
            "lessons": ["Auto-retrospective needs LLM availability"],
            "failures": [],
            "improvements": [],
        }

    # Store lessons + improvements in global memory
    mem = get_memory_manager()
    for lesson in retro.get("lessons", []):
        mem.global_store(
            key=f"lesson:epic:{mission.id}",
            value=lesson,
            category="lesson",
            project_id=mission.project_id,
            confidence=0.7,
        )
    for imp in retro.get("improvements", []):
        mem.global_store(
            key=f"improvement:epic:{mission.id}",
            value=imp,
            category="improvement",
            project_id=mission.project_id,
            confidence=0.8,
        )

    # Push retrospective as SSE message
    retro_text = "## Rétrospective automatique\n\n"
    if retro.get("successes"):
        retro_text += (
            "**Réussites:**\n"
            + "\n".join(f"- {s}" for s in retro["successes"])
            + "\n\n"
        )
    if retro.get("lessons"):
        retro_text += (
            "**Leçons:**\n" + "\n".join(f"- {l}" for l in retro["lessons"]) + "\n\n"
        )
    if retro.get("improvements"):
        retro_text += "**Améliorations:**\n" + "\n".join(
            f"- {i}" for i in retro["improvements"]
        )

    await push_sse(
        session_id,
        {
            "type": "message",
            "from_agent": "scrum_master",
            "from_name": "Retrospective",
            "from_role": "Scrum Master",
            "content": retro_text,
            "msg_type": "text",
        },
    )




async def _run_post_phase_hooks(
    phase_id: str, phase_name: str, mission, session_id: str, push_sse
) -> dict:
    """Run real CI/CD actions after phase completion based on phase type.
    Returns dict with build_ok, test_ok, deploy_ok booleans for gate decisions."""
    import subprocess
    from pathlib import Path

    result = {"build_ok": True, "test_ok": True, "deploy_ok": True}
    workspace = mission.workspace_path
    if not workspace or not Path(workspace).is_dir():
        return result

    phase_key = phase_name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")

    # Auto-commit after EVERY phase — agents never call git_commit reliably
    try:
        git_add = subprocess.run(
            ["git", "add", "-A"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if status.stdout.strip():
            file_count = status.stdout.strip().count("\n") + 1
            commit_msg = f"chore({phase_key}): {phase_name} — {file_count} files"
            subprocess.run(
                ["git", "commit", "-m", commit_msg],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "CI/CD",
                    "from_role": "Pipeline",
                    "content": f"Auto-commit: {file_count} fichiers ({phase_name})",
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
    except Exception as e:
        logger.warning("Auto-commit failed for phase %s: %s", phase_id, e)

    # After EVERY phase: update Architecture.md + docs via LLM (architect + tech writer)
    await _update_docs_post_phase(phase_id, phase_name, mission, session_id, push_sse)

    # After ideation/architecture/dev: extract features for PO kanban
    if any(
        k in phase_key for k in ("ideation", "architecture", "sprint", "dev", "setup")
    ):
        try:
            await _extract_features_from_phase(
                mission_id=mission.id,
                session_id=session_id,
                phase_id=phase_id,
                phase_name=phase_name,
                summary="",
                pre_msg_count=0,
            )
        except Exception as e:
            logger.warning("Feature extraction skipped: %s", e)

    # After dev sprint: auto screenshots for HTML files
    if "dev" in phase_key or "sprint" in phase_key:
        ws = Path(workspace)
        html_files = (
            list(ws.glob("*.html"))
            + list(ws.glob("public/*.html"))
            + list(ws.glob("src/*.html"))
            + list(ws.glob("client/*.html"))
        )
        if html_files:
            screenshots_dir = ws / "screenshots"
            screenshots_dir.mkdir(exist_ok=True)
            shot_paths = []
            for hf in html_files[:5]:
                fname = f"{hf.stem}.png"
                shot_script = f"""
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{"width": 1280, "height": 720}})
        await page.goto("file://{hf}", wait_until="load", timeout=10000)
        await page.screenshot(path="{screenshots_dir / fname}", full_page=True)
        await browser.close()
asyncio.run(main())
"""
                try:
                    r = subprocess.run(
                        ["python3", "-c", shot_script],
                        capture_output=True,
                        text=True,
                        cwd=workspace,
                        timeout=30,
                    )
                    if r.returncode == 0 and (screenshots_dir / fname).exists():
                        shot_paths.append(f"screenshots/{fname}")
                    else:
                        logger.warning(
                            "Sprint screenshot failed for %s: %s",
                            hf.name,
                            r.stderr[:200] if r.stderr else "unknown",
                        )
                except Exception as e:
                    logger.warning("Sprint screenshot error for %s: %s", hf.name, e)

            if shot_paths:
                shot_content = "Screenshots automatiques du workspace :\n" + "\n".join(
                    f"[SCREENSHOT:{p}]" for p in shot_paths
                )
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "CI/CD",
                        "from_role": "Pipeline",
                        "content": shot_content,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )

    # After CI/CD or TDD Sprint phase: run build if package.json or Cargo.toml exists
    if any(
        k in phase_key for k in ("cicd", "pipeline", "sprint", "dev", "tdd", "quality")
    ):
        ws = Path(workspace)

        # Detect project roots (support subdirectories: frontend/, backend/, etc.)
        def _find_project_file(name: str) -> Path | None:
            if (ws / name).exists():
                return ws
            for sub in ("frontend", "client", "web", "app", "backend", "server", "api"):
                if (ws / sub / name).exists():
                    return ws / sub
            return None

        npm_root = _find_project_file("package.json")
        cargo_root = _find_project_file("Cargo.toml")

        try:
            # Rust/Cargo project support
            if cargo_root:
                cargo_cwd = str(cargo_root)
                cargo_check = subprocess.run(
                    ["cargo", "check"],
                    cwd=cargo_cwd,
                    capture_output=True,
                    text=True,
                    timeout=180,
                )
                cargo_msg = (
                    "cargo check réussi"
                    if cargo_check.returncode == 0
                    else f"cargo check échoué: {cargo_check.stderr[-300:]}"
                )
                if cargo_check.returncode != 0:
                    result["build_ok"] = False
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "CI/CD",
                        "from_role": "Pipeline",
                        "content": cargo_msg,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )
                # Run cargo test
                if cargo_check.returncode == 0:
                    cargo_test = subprocess.run(
                        ["cargo", "test", "--no-fail-fast"],
                        cwd=cargo_cwd,
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    test_msg = (
                        f"cargo test réussi: {cargo_test.stdout[-200:]}"
                        if cargo_test.returncode == 0
                        else f"cargo test échoué: {cargo_test.stdout[-300:]}"
                    )
                    if cargo_test.returncode != 0:
                        result["test_ok"] = False
                    await push_sse(
                        session_id,
                        {
                            "type": "message",
                            "from_agent": "system",
                            "from_name": "CI/CD",
                            "from_role": "Pipeline",
                            "content": test_msg,
                            "phase_id": phase_id,
                            "msg_type": "text",
                        },
                    )

            # Node.js project support
            if npm_root and (npm_root / "package.json").exists():
                npm_cwd = str(npm_root)
                npm_r = subprocess.run(
                    ["npm", "install"],
                    cwd=npm_cwd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                build_msg = (
                    "npm install réussi"
                    if npm_r.returncode == 0
                    else f"npm install échoué: {npm_r.stderr[:200]}"
                )
                if npm_r.returncode != 0:
                    result["build_ok"] = False
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "CI/CD",
                        "from_role": "Pipeline",
                        "content": build_msg,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )
                # Run build script if exists
                import json as _json

                try:
                    pkg = _json.loads((npm_root / "package.json").read_text())
                    if "build" in (pkg.get("scripts") or {}):
                        build_r = subprocess.run(
                            ["npm", "run", "build"],
                            cwd=npm_cwd,
                            capture_output=True,
                            text=True,
                            timeout=120,
                        )
                        build_status = (
                            "réussi"
                            if build_r.returncode == 0
                            else f"échoué: {build_r.stderr[:200]}"
                        )
                        if build_r.returncode != 0:
                            result["build_ok"] = False
                        await push_sse(
                            session_id,
                            {
                                "type": "message",
                                "from_agent": "system",
                                "from_name": "CI/CD",
                                "from_role": "Pipeline",
                                "content": f"npm run build {build_status}",
                                "phase_id": phase_id,
                                "msg_type": "text",
                            },
                        )
                    if "test" in (pkg.get("scripts") or {}):
                        test_r = subprocess.run(
                            ["npm", "test"],
                            cwd=npm_cwd,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            env={**dict(subprocess.os.environ), "CI": "true"},
                        )
                        test_status = (
                            "réussi"
                            if test_r.returncode == 0
                            else f"échoué: {test_r.stderr[:200]}"
                        )
                        if test_r.returncode != 0:
                            result["test_ok"] = False
                        await push_sse(
                            session_id,
                            {
                                "type": "message",
                                "from_agent": "system",
                                "from_name": "CI/CD",
                                "from_role": "Pipeline",
                                "content": f"npm test {test_status}",
                                "phase_id": phase_id,
                                "msg_type": "text",
                            },
                        )
                except Exception:
                    pass
            # Python project support: requirements.txt + pytest
            elif (ws / "requirements.txt").exists():
                result_pip = subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                pip_msg = (
                    "pip install réussi"
                    if result_pip.returncode == 0
                    else f"pip install échoué: {result_pip.stderr[:200]}"
                )
                if result_pip.returncode != 0:
                    result["build_ok"] = False
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "CI/CD",
                        "from_role": "Pipeline",
                        "content": pip_msg,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )
                # Run pytest if test files exist
                test_files = list(ws.glob("test_*.py")) + list(ws.glob("tests/*.py"))
                if test_files:
                    pytest_result = subprocess.run(
                        ["python3", "-m", "pytest", "-v", "--tb=short"],
                        cwd=workspace,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        env={**dict(subprocess.os.environ), "CI": "true"},
                    )
                    test_status = (
                        "réussi"
                        if pytest_result.returncode == 0
                        else f"échoué: {pytest_result.stdout[-300:]}"
                    )
                    if pytest_result.returncode != 0:
                        result["test_ok"] = False
                    await push_sse(
                        session_id,
                        {
                            "type": "message",
                            "from_agent": "system",
                            "from_name": "CI/CD",
                            "from_role": "Pipeline",
                            "content": f"pytest {test_status}",
                            "phase_id": phase_id,
                            "msg_type": "text",
                        },
                    )
        except Exception as e:
            logger.error("Post-phase build failed: %s", e)

        # After sprint: start server, take screenshots, stop server
        ws = Path(workspace)
        npm_root_srv = _find_project_file("package.json")
        if npm_root_srv and (npm_root_srv / "package.json").exists():
            try:
                import json as _json2

                pkg2 = _json2.loads((npm_root_srv / "package.json").read_text())
                scripts = pkg2.get("scripts") or {}
                start_cmd = None
                srv_cwd = str(npm_root_srv)
                if "start" in scripts:
                    start_cmd = "npm start"
                elif "dev" in scripts:
                    start_cmd = "npm run dev"
                elif (
                    (npm_root_srv / "src" / "server.ts").exists()
                    or (npm_root_srv / "src" / "server.js").exists()
                    or (npm_root_srv / "server.js").exists()
                ):
                    main = pkg2.get("main", "")
                    if main:
                        start_cmd = f"node {main}"

                if start_cmd:
                    screenshots_dir = ws / "screenshots"
                    screenshots_dir.mkdir(exist_ok=True)
                    # Start server in background
                    import signal

                    server_env = {
                        **dict(subprocess.os.environ),
                        "PORT": "9050",
                        "NODE_ENV": "production",
                    }
                    server_proc = subprocess.Popen(
                        start_cmd,
                        shell=True,
                        cwd=srv_cwd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        env=server_env,
                        preexec_fn=subprocess.os.setsid,
                    )
                    import time as _time

                    _time.sleep(4)  # Wait for server to start
                    # Check if server is up
                    health = subprocess.run(
                        [
                            "curl",
                            "-s",
                            "-o",
                            "/dev/null",
                            "-w",
                            "%{http_code}",
                            "http://127.0.0.1:9050/",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    http_code = health.stdout.strip()
                    if http_code and http_code != "000":
                        # Discover routes from HTML files in public/
                        pages_to_shot = [("/", "homepage")]
                        seen = {"/"}
                        for html in sorted(ws.glob("public/*.html")):
                            route = f"/{html.name}"
                            if route not in seen and html.name != "index.html":
                                pages_to_shot.append((route, html.stem))
                                seen.add(route)
                        # Common routes fallback
                        for r, n in [
                            ("/login", "login"),
                            ("/stations", "stations"),
                            ("/booking", "booking"),
                            ("/dashboard", "dashboard"),
                        ]:
                            if r not in seen and (ws / "public" / f"{n}.html").exists():
                                pages_to_shot.append((r, n))
                                seen.add(r)
                        shot_paths_srv = []
                        for url_path, shot_name in pages_to_shot:
                            shot_script = f"""
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{"width": 1280, "height": 720}})
        await page.goto("http://127.0.0.1:9050{url_path}", wait_until="networkidle", timeout=15000)
        await page.screenshot(path="{screenshots_dir}/{shot_name}.png", full_page=True)
        await browser.close()
asyncio.run(main())
"""
                            try:
                                r = subprocess.run(
                                    ["python3", "-c", shot_script],
                                    capture_output=True,
                                    text=True,
                                    timeout=30,
                                )
                                if (
                                    r.returncode == 0
                                    and (screenshots_dir / f"{shot_name}.png").exists()
                                ):
                                    shot_paths_srv.append(
                                        f"screenshots/{shot_name}.png"
                                    )
                            except Exception:
                                pass

                        if shot_paths_srv:
                            shot_msg = (
                                f"Screenshots du serveur (HTTP {http_code}) :\n"
                                + "\n".join(f"[SCREENSHOT:{p}]" for p in shot_paths_srv)
                            )
                            await push_sse(
                                session_id,
                                {
                                    "type": "message",
                                    "from_agent": "system",
                                    "from_name": "CI/CD",
                                    "from_role": "Pipeline",
                                    "content": shot_msg,
                                    "phase_id": phase_id,
                                    "msg_type": "text",
                                },
                            )
                        else:
                            await push_sse(
                                session_id,
                                {
                                    "type": "message",
                                    "from_agent": "system",
                                    "from_name": "CI/CD",
                                    "from_role": "Pipeline",
                                    "content": f"Serveur démarré (HTTP {http_code}) mais screenshots échoués",
                                    "phase_id": phase_id,
                                    "msg_type": "text",
                                },
                            )
                    # Kill server
                    try:
                        subprocess.os.killpg(
                            subprocess.os.getpgid(server_proc.pid), signal.SIGTERM
                        )
                    except Exception:
                        try:
                            server_proc.kill()
                        except Exception:
                            pass
            except Exception as e:
                logger.warning("Post-sprint server screenshot failed: %s", e)
    if "deploy" in phase_key or "quality" in phase_key:
        ws = Path(workspace)
        # Docker build + run if Dockerfile exists
        if (ws / "Dockerfile").exists():
            container_name = f"mission-{mission.id}"
            try:
                # Build Docker image
                build_result = subprocess.run(
                    ["docker", "build", "-t", container_name, "."],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if build_result.returncode == 0:
                    await push_sse(
                        session_id,
                        {
                            "type": "message",
                            "from_agent": "system",
                            "from_name": "CI/CD",
                            "from_role": "Pipeline",
                            "content": f"Docker image {container_name} construite avec succès",
                            "phase_id": phase_id,
                            "msg_type": "text",
                        },
                    )
                    # Stop existing container if any
                    subprocess.run(
                        ["docker", "rm", "-f", container_name],
                        capture_output=True,
                        timeout=10,
                    )
                    # Find free port
                    import socket

                    port = 9100
                    for p in range(9100, 9200):
                        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                            if s.connect_ex(("127.0.0.1", p)) != 0:
                                port = p
                                break
                    # Detect container port from Dockerfile EXPOSE or default 3000
                    container_port = 3000
                    try:
                        df_text = (ws / "Dockerfile").read_text()
                        import re as _re

                        expose_match = _re.search(r"EXPOSE\s+(\d+)", df_text)
                        if expose_match:
                            container_port = int(expose_match.group(1))
                    except Exception:
                        pass
                    # Run container
                    run_result = subprocess.run(
                        [
                            "docker",
                            "run",
                            "-d",
                            "--name",
                            container_name,
                            "-p",
                            f"{port}:{container_port}",
                            "--restart",
                            "unless-stopped",
                            container_name,
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    if run_result.returncode == 0:
                        import time

                        time.sleep(3)  # Wait for container to start
                        # Health check
                        health = subprocess.run(
                            [
                                "curl",
                                "-s",
                                "-o",
                                "/dev/null",
                                "-w",
                                "%{http_code}",
                                f"http://127.0.0.1:{port}/",
                            ],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        status_code = health.stdout.strip()
                        deploy_msg = f"Container {container_name} déployé sur port {port} — HTTP {status_code}"
                        await push_sse(
                            session_id,
                            {
                                "type": "message",
                                "from_agent": "system",
                                "from_name": "CI/CD",
                                "from_role": "Pipeline",
                                "content": deploy_msg,
                                "phase_id": phase_id,
                                "msg_type": "text",
                            },
                        )
                        # Take multi-page screenshots of deployed app
                        screenshots_dir = ws / "screenshots"
                        screenshots_dir.mkdir(exist_ok=True)
                        deploy_pages = [("/", "deployed")]
                        for html in sorted(ws.glob("public/*.html")):
                            if html.name != "index.html":
                                deploy_pages.append(
                                    (f"/{html.name}", f"deployed-{html.stem}")
                                )
                        deploy_shots = []
                        for url_path, shot_name in deploy_pages[:8]:
                            shot_script = f"""
import asyncio
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={{"width": 1280, "height": 720}})
        await page.goto("http://127.0.0.1:{port}{url_path}", wait_until="networkidle", timeout=15000)
        await page.screenshot(path="{screenshots_dir}/{shot_name}.png", full_page=True)
        await browser.close()
asyncio.run(main())
"""
                            try:
                                shot_result = subprocess.run(
                                    ["python3", "-c", shot_script],
                                    capture_output=True,
                                    text=True,
                                    cwd=workspace,
                                    timeout=30,
                                )
                                if (
                                    shot_result.returncode == 0
                                    and (screenshots_dir / f"{shot_name}.png").exists()
                                ):
                                    deploy_shots.append(f"screenshots/{shot_name}.png")
                            except Exception:
                                pass
                        if deploy_shots:
                            shot_content = (
                                f"Screenshots Docker deploy (HTTP {status_code}) :\n"
                            )
                            shot_content += "\n".join(
                                f"[SCREENSHOT:{s}]" for s in deploy_shots
                            )
                            await push_sse(
                                session_id,
                                {
                                    "type": "message",
                                    "from_agent": "system",
                                    "from_name": "CI/CD",
                                    "from_role": "Pipeline",
                                    "content": shot_content,
                                    "phase_id": phase_id,
                                    "msg_type": "text",
                                },
                            )
                    else:
                        result["deploy_ok"] = False
                        await push_sse(
                            session_id,
                            {
                                "type": "message",
                                "from_agent": "system",
                                "from_name": "CI/CD",
                                "from_role": "Pipeline",
                                "content": f"Docker run échoué: {run_result.stderr[:200]}",
                                "phase_id": phase_id,
                                "msg_type": "text",
                            },
                        )
                else:
                    result["deploy_ok"] = False
                    await push_sse(
                        session_id,
                        {
                            "type": "message",
                            "from_agent": "system",
                            "from_name": "CI/CD",
                            "from_role": "Pipeline",
                            "content": f"Docker build échoué: {build_result.stderr[:200]}",
                            "phase_id": phase_id,
                            "msg_type": "text",
                        },
                    )
            except Exception as e:
                logger.warning("Docker deploy failed for %s: %s", mission.id, e)
        ws = Path(workspace)
        try:
            files = list(ws.rglob("*"))
            real_files = [
                f.relative_to(ws) for f in files if f.is_file() and ".git" not in str(f)
            ]
            git_log = subprocess.run(
                ["git", "log", "--oneline", "-10"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            summary = f"Workspace: {len(real_files)} fichiers\n"
            if real_files:
                summary += (
                    "```\n"
                    + "\n".join(str(f) for f in sorted(real_files)[:20])
                    + "\n```\n"
                )
            if git_log.stdout:
                summary += f"\nGit log:\n```\n{git_log.stdout.strip()}\n```"
            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "CI/CD",
                    "from_role": "Pipeline",
                    "content": summary,
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
        except Exception as e:
            logger.error("Post-phase deploy summary failed: %s", e)

    # After QA phases: auto-build + screenshot pipeline (deterministic, no LLM)
    if "qa" in phase_key or "test" in phase_key:
        ws = Path(workspace)
        try:
            platform_type = _detect_project_platform(
                str(ws), brief=mission.brief if hasattr(mission, "brief") else ""
            )
            screenshots = await _auto_qa_screenshots(ws, platform_type)
            if screenshots:
                shot_content = f"QA Screenshots ({platform_type}) — {len(screenshots)} captures :\n"
                shot_content += "\n".join(f"[SCREENSHOT:{s}]" for s in screenshots)
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "QA Pipeline",
                        "from_role": "Automated QA",
                        "content": shot_content,
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )
        except Exception as e:
            logger.error("Post-phase QA screenshots failed: %s", e)

        # Run real Playwright E2E test files if any exist
        try:
            e2e_results = await _run_real_e2e_tests(
                ws, session_id, phase_id, push_sse, mission
            )
        except Exception as e:
            logger.error("Post-phase E2E tests failed: %s", e)

    # Confluence sync — auto-sync after every phase
    try:
        from ....confluence.sync import get_sync_engine

        engine = get_sync_engine()
        if engine.client.health_check():
            results = engine.sync_mission(
                mission.id if hasattr(mission, "id") else str(mission)
            )
            synced = [t for t, r in results.items() if r.get("status") == "ok"]
            if synced:
                await push_sse(
                    session_id,
                    {
                        "type": "message",
                        "from_agent": "system",
                        "from_name": "Confluence",
                        "from_role": "Sync",
                        "content": f"Sync Confluence: {', '.join(synced)} ({len(synced)} pages)",
                        "phase_id": phase_id,
                        "msg_type": "text",
                    },
                )
    except FileNotFoundError:
        pass  # No PAT configured — skip
    except Exception as e:
        logger.warning("Confluence sync failed: %s", e)

    return result




async def _update_docs_post_phase(
    phase_id: str, phase_name: str, mission, session_id: str, push_sse
):
    """Call LLM to update Architecture.md and README.md after each phase."""
    import subprocess
    from pathlib import Path

    workspace = mission.workspace_path
    if not workspace or not Path(workspace).is_dir():
        return

    ws = Path(workspace)

    # Gather context: list of files + phase summary from messages
    try:
        file_list = subprocess.run(
            [
                "find",
                ".",
                "-type",
                "f",
                "-not",
                "-path",
                "./.git/*",
                "-not",
                "-name",
                "*.bak",
            ],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
    except Exception:
        file_list = ""

    # Read existing docs for incremental update
    existing_archi = ""
    archi_path = ws / "Architecture.md"
    if archi_path.exists():
        try:
            existing_archi = archi_path.read_text()[:3000]
        except Exception:
            pass

    existing_readme = ""
    readme_path = ws / "README.md"
    if readme_path.exists():
        try:
            existing_readme = readme_path.read_text()[:2000]
        except Exception:
            pass

    # Read key source files for context (first 200 lines of main files)
    code_context = ""
    code_files = (
        list(ws.glob("**/*.swift"))[:3]
        + list(ws.glob("**/*.ts"))[:3]
        + list(ws.glob("**/*.py"))[:3]
        + list(ws.glob("**/*.svelte"))[:3]
    )
    for cf in code_files[:4]:
        try:
            content = cf.read_text()[:1500]
            code_context += f"\n--- {cf.relative_to(ws)} ---\n{content}\n"
        except Exception:
            pass

    if not file_list and not code_context:
        return

    from ....llm.client import LLMMessage, get_llm_client

    client = get_llm_client()

    # 1. Architecture update (architect agent)
    try:
        archi_prompt = f"""Tu es l'architecte logiciel. Apres la phase "{phase_name}", mets a jour Architecture.md.

Fichiers du projet:
{file_list[:2000]}

Code source principal:
{code_context[:3000]}

Architecture existante:
{existing_archi[:2000] if existing_archi else "(aucune)"}

Genere un Architecture.md complet et a jour avec:
- Vue d'ensemble du projet
- Stack technique (langages, frameworks, outils)
- Structure des dossiers/modules
- Patterns utilises (MVC, MVVM, etc.)
- Diagramme ASCII des composants principaux
- Decisions architecturales prises

Reponds UNIQUEMENT avec le contenu Markdown du fichier."""

        resp = await asyncio.wait_for(
            client.chat(
                messages=[LLMMessage(role="user", content=archi_prompt)],
                system_prompt="Architecte logiciel senior. Documentation technique concise et precise.",
                temperature=0.3,
                max_tokens=2000,
            ),
            timeout=60,
        )
        archi_text = resp.content.strip()
        # Strip markdown fences if present
        if archi_text.startswith("```"):
            archi_text = (
                archi_text.split("\n", 1)[1] if "\n" in archi_text else archi_text
            )
        if archi_text.endswith("```"):
            archi_text = archi_text.rsplit("```", 1)[0]

        if len(archi_text) > 100:
            archi_path.write_text(archi_text)
            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "architecte",
                    "from_name": "Architecte",
                    "from_role": "Architecture",
                    "content": f"Architecture.md mis a jour ({len(archi_text)} chars)",
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
    except Exception as e:
        logger.warning("Architecture update failed: %s", e)

    # 2. README update (tech writer agent)
    try:
        readme_prompt = f"""Tu es le tech writer. Apres la phase "{phase_name}", mets a jour README.md.

Fichiers du projet:
{file_list[:1500]}

README existant:
{existing_readme[:1500] if existing_readme else "(aucun)"}

Genere un README.md a jour avec:
- Titre et description du projet
- Prerequis / Installation
- Lancement (commande build et run)
- Structure du projet
- Technologies utilisees
- Statut actuel

Reponds UNIQUEMENT avec le contenu Markdown du fichier."""

        resp = await asyncio.wait_for(
            client.chat(
                messages=[LLMMessage(role="user", content=readme_prompt)],
                system_prompt="Technical writer. Documentation claire et actionnable.",
                temperature=0.3,
                max_tokens=1500,
            ),
            timeout=60,
        )
        readme_text = resp.content.strip()
        if readme_text.startswith("```"):
            readme_text = (
                readme_text.split("\n", 1)[1] if "\n" in readme_text else readme_text
            )
        if readme_text.endswith("```"):
            readme_text = readme_text.rsplit("```", 1)[0]

        if len(readme_text) > 80:
            readme_path.write_text(readme_text)
            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "tech_writer",
                    "from_name": "Tech Writer",
                    "from_role": "Documentation",
                    "content": f"README.md mis a jour ({len(readme_text)} chars)",
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
    except Exception as e:
        logger.warning("README update failed: %s", e)

    # Auto-commit docs update
    try:
        subprocess.run(
            ["git", "add", "Architecture.md", "README.md"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=workspace,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if status.stdout.strip():
            subprocess.run(
                [
                    "git",
                    "commit",
                    "-m",
                    f"docs({phase_name.lower().replace(' ', '-')}): update Architecture.md + README.md",
                ],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
    except Exception:
        pass




async def _run_real_e2e_tests(
    ws: Path, session_id: str, phase_id: str, push_sse, mission
) -> dict:
    """Run real Playwright/Jest/Vitest E2E test files if they exist in workspace. No LLM."""
    import subprocess

    results = {"ran": False, "passed": 0, "failed": 0, "errors": []}

    # Find E2E test files
    test_patterns = [
        ws / "tests" / "e2e",
        ws / "test" / "e2e",
        ws / "e2e",
        ws / "tests",
        ws / "test",
        ws / "__tests__",
    ]
    test_files = []
    for td in test_patterns:
        if td.exists():
            test_files.extend(td.rglob("*.spec.ts"))
            test_files.extend(td.rglob("*.spec.js"))
            test_files.extend(td.rglob("*.test.ts"))
            test_files.extend(td.rglob("*.test.js"))
            test_files.extend(td.rglob("*.spec.py"))
            test_files.extend(td.rglob("test_*.py"))

    if not test_files:
        return results

    results["ran"] = True
    await push_sse(
        session_id,
        {
            "type": "message",
            "from_agent": "system",
            "from_name": "E2E Pipeline",
            "from_role": "Real Tests",
            "content": f"Running {len(test_files)} E2E test file(s)…",
            "phase_id": phase_id,
            "msg_type": "text",
        },
    )

    # Determine test runner
    has_playwright_config = (ws / "playwright.config.ts").exists() or (
        ws / "playwright.config.js"
    ).exists()
    has_vitest = (ws / "vitest.config.ts").exists() or (
        ws / "vitest.config.js"
    ).exists()
    has_jest = (ws / "jest.config.ts").exists() or (ws / "jest.config.js").exists()
    has_pytest = any(f.suffix == ".py" for f in test_files)

    test_cmds = []
    if has_playwright_config:
        test_cmds.append(("npx playwright test --reporter=list", "Playwright"))
    elif has_vitest:
        test_cmds.append(("npx vitest run --reporter=verbose", "Vitest"))
    elif has_jest:
        test_cmds.append(("npx jest --forceExit --verbose", "Jest"))
    elif has_pytest:
        test_cmds.append(("python3 -m pytest -v", "pytest"))
    else:
        # Fallback: try npx playwright test for .spec.ts files
        ts_tests = [f for f in test_files if f.suffix in (".ts", ".js")]
        py_tests = [f for f in test_files if f.suffix == ".py"]
        if ts_tests:
            test_cmds.append(("npx playwright test --reporter=list", "Playwright"))
        if py_tests:
            test_cmds.append(("python3 -m pytest -v", "pytest"))

    for cmd, runner_name in test_cmds:
        try:
            env = {**__import__("os").environ, "CI": "true", "NODE_ENV": "test"}
            r = subprocess.run(
                cmd,
                shell=True,
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=120,
                env=env,
            )
            output = (r.stdout + "\n" + r.stderr)[-2000:]
            if r.returncode == 0:
                results["passed"] += 1
                status = f"[OK] {runner_name} PASSED"
            else:
                results["failed"] += 1
                results["errors"].append(output[-500:])
                status = f"[FAIL] {runner_name} FAILED (exit {r.returncode})"

            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "E2E Pipeline",
                    "from_role": "Real Tests",
                    "content": f"{status}\n```\n{output[-1500:]}\n```",
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
        except subprocess.TimeoutExpired:
            results["failed"] += 1
            results["errors"].append(f"{runner_name} timed out after 120s")
            await push_sse(
                session_id,
                {
                    "type": "message",
                    "from_agent": "system",
                    "from_name": "E2E Pipeline",
                    "from_role": "Real Tests",
                    "content": f"[FAIL] {runner_name} timed out after 120s",
                    "phase_id": phase_id,
                    "msg_type": "text",
                },
            )
        except Exception as exc:
            results["errors"].append(str(exc)[:200])

    # Create incident if E2E tests failed
    if results["failed"] > 0:
        try:
            from ....missions.feedback import create_platform_incident

            create_platform_incident(
                title=f"E2E tests failed: {results['failed']} runner(s)",
                severity="P3",
                source="e2e_pipeline",
                error_type="test_failure",
                error_detail=f"Mission {mission.id}: {results['failed']} test runner(s) failed. "
                f"Errors: {'; '.join(results['errors'][:3])}",
                mission_id=mission.id if hasattr(mission, "id") else "",
                project_id=mission.project_id if hasattr(mission, "project_id") else "",
            )
        except Exception:
            pass

    return results
    """Deterministic screenshot pipeline — build, run, capture. No LLM."""
    screenshots_dir = ws / "screenshots"
    screenshots_dir.mkdir(exist_ok=True)

    if platform_type == "macos-native":
        results = await _qa_screenshots_macos(ws, screenshots_dir)
    elif platform_type == "ios-native":
        results = await _qa_screenshots_ios(ws, screenshots_dir)
    elif platform_type in ("web-docker", "web-node", "web-static"):
        results = await _qa_screenshots_web(ws, screenshots_dir, platform_type)
    else:
        return []

    # Filter out tiny/empty screenshots
    return [r for r in results if (ws / r).exists() and (ws / r).stat().st_size > 1000]



async def _qa_screenshots_macos(ws: Path, shots_dir: Path) -> list[str]:
    """Build Swift app → launch → AppleScript navigation → multi-step screenshots."""
    import asyncio as _aio
    import subprocess

    results = []

    # 1. Ensure Package.swift exists
    pkg = ws / "Package.swift"
    if not pkg.exists() and (ws / "Sources").exists():
        app_name = "App"
        for sf in (ws / "Sources").rglob("*App.swift"):
            app_name = sf.stem.replace("App", "") or "App"
            break

        # Detect duplicate filenames and .bak files to exclude
        from collections import Counter

        swift_files = list((ws / "Sources").rglob("*.swift"))
        name_counts = Counter(f.name for f in swift_files)
        excludes = []
        seen_names = set()
        for sf in sorted(swift_files, key=lambda f: len(str(f))):
            rel = str(sf.relative_to(ws / "Sources"))
            if sf.suffix == ".bak" or rel.endswith(".bak"):
                continue
            if sf.name in seen_names and name_counts[sf.name] > 1:
                excludes.append(f'"{rel}"')
            seen_names.add(sf.name)

        # Also exclude .bak files
        for sf in (ws / "Sources").rglob("*.bak"):
            excludes.append(f'"{str(sf.relative_to(ws / "Sources"))}"')

        exclude_clause = ""
        if excludes:
            exclude_clause = f",\n            exclude: [{', '.join(excludes)}]"

        pkg.write_text(
            f"// swift-tools-version:5.9\n"
            f"import PackageDescription\n\n"
            f"let package = Package(\n"
            f'    name: "{app_name}",\n'
            f"    platforms: [.macOS(.v14)],\n"
            f"    targets: [\n"
            f"        .executableTarget(\n"
            f'            name: "{app_name}",\n'
            f'            path: "Sources"{exclude_clause}\n'
            f"        ),\n"
            f"    ]\n"
            f")\n"
        )
        logger.info(
            "Auto-generated Package.swift for %s (excluding %d files)",
            app_name,
            len(excludes),
        )

    # 2. Build
    build_result = subprocess.run(
        ["xcrun", "swift", "build"],
        cwd=str(ws),
        capture_output=True,
        text=True,
        timeout=120,
    )
    build_log = (build_result.stdout + "\n" + build_result.stderr)[-3000:]
    (shots_dir / "build_log.txt").write_text(build_log)

    if build_result.returncode != 0:
        _write_status_png(
            shots_dir / "01_build_failed.png",
            "BUILD FAILED [X]",
            build_log[-1200:],
            bg_color=(40, 10, 10),
        )
        results.append("screenshots/01_build_failed.png")
        return results

    _write_status_png(
        shots_dir / "01_build_success.png",
        "BUILD SUCCESS [OK]",
        build_log[-400:],
        bg_color=(10, 40, 10),
    )
    results.append("screenshots/01_build_success.png")

    # 3. Find the built binary
    binary = None
    for d in [ws / ".build" / "debug", ws / ".build" / "release"]:
        if d.exists():
            for f in d.iterdir():
                if (
                    f.is_file()
                    and f.stat().st_mode & 0o111
                    and not f.suffix
                    and f.name != "ModuleCache"
                ):
                    binary = f
                    break
            if binary:
                break

    if not binary:
        _write_status_png(
            shots_dir / "02_no_binary.png",
            "NO EXECUTABLE",
            "Build produced no runnable binary.",
            bg_color=(40, 30, 10),
        )
        results.append("screenshots/02_no_binary.png")
        return results

    # 4. Discover views/screens from source code for journey steps
    views = _discover_macos_views(ws)

    # 5. Launch app + multi-step screenshots via AppleScript
    proc = None
    try:
        proc = subprocess.Popen(
            [str(binary)],
            cwd=str(ws),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        await _aio.sleep(3)

        app_name = binary.name

        # Step 1: Initial launch
        _capture_app_screenshot(app_name, shots_dir / "02_launch.png")
        if (shots_dir / "02_launch.png").exists():
            results.append("screenshots/02_launch.png")

        # Step 2: Interact with each discovered view/tab via keyboard/menu
        step = 3
        for view in views[:8]:
            await _aio.sleep(1)
            # Try navigating via menu or keyboard shortcut
            _applescript_navigate(app_name, view)
            await _aio.sleep(1.5)
            fname = f"{step:02d}_{view['id']}.png"
            _capture_app_screenshot(app_name, shots_dir / fname)
            if (shots_dir / fname).exists():
                results.append(f"screenshots/{fname}")
            step += 1

        # Step N: Final state
        await _aio.sleep(1)
        _capture_app_screenshot(app_name, shots_dir / f"{step:02d}_final_state.png")
        if (shots_dir / f"{step:02d}_final_state.png").exists():
            results.append(f"screenshots/{step:02d}_final_state.png")

    except Exception as e:
        _write_status_png(
            shots_dir / "02_launch_error.png",
            "LAUNCH FAILED",
            str(e)[:500],
            bg_color=(40, 10, 10),
        )
        results.append("screenshots/02_launch_error.png")
    finally:
        if proc:
            try:
                import os

                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
    return results




def _discover_macos_views(ws: Path) -> list[dict]:
    """Scan Swift sources to discover views/screens for screenshot journey."""
    views = []
    seen = set()
    for sf in sorted(ws.rglob("*.swift")):
        try:
            code = sf.read_text(errors="ignore")
        except Exception:
            continue
        name = sf.stem
        # Detect SwiftUI views
        if ": View" in code and "var body" in code and name not in seen:
            view_type = "tab"
            if "TabView" in code:
                view_type = "tabview"
            elif "NavigationView" in code or "NavigationStack" in code:
                view_type = "navigation"
            elif "Sheet" in code or ".sheet" in code:
                view_type = "sheet"
            elif "Menu" in code or "MenuBar" in code:
                view_type = "menu"
            # Extract keyboard shortcut if any
            shortcut = None
            import re

            ks = re.search(r'\.keyboardShortcut\("(\w)"', code)
            if ks:
                shortcut = ks.group(1)
            views.append(
                {
                    "id": name.lower(),
                    "name": name,
                    "type": view_type,
                    "shortcut": shortcut,
                }
            )
            seen.add(name)
    return views




def _capture_app_screenshot(app_name: str, output_path: Path):
    """Capture app window screenshot via screencapture -l (window ID)."""
    import subprocess

    try:
        # Get window ID via AppleScript
        script = (
            'tell application "System Events"\n'
            f'  set appProc to first process whose name contains "{app_name}"\n'
            "  set wID to id of first window of appProc\n"
            "  return wID\n"
            "end tell"
        )
        r = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0 and r.stdout.strip():
            subprocess.run(
                ["screencapture", "-l", r.stdout.strip(), str(output_path)],
                timeout=10,
                capture_output=True,
            )
        else:
            # Fallback: full screen
            subprocess.run(
                ["screencapture", "-x", str(output_path)],
                timeout=10,
                capture_output=True,
            )
    except Exception:
        import subprocess as _sp

        _sp.run(
            ["screencapture", "-x", str(output_path)], timeout=10, capture_output=True
        )




def _applescript_navigate(app_name: str, view: dict):
    """Navigate to a view via AppleScript (keyboard shortcuts, menu clicks, tabs)."""
    import subprocess

    try:
        if view.get("shortcut"):
            # Use keyboard shortcut
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  keystroke "{view["shortcut"]}" using command down\n'
                f"end tell"
            )
        elif view["type"] == "menu":
            # Click menu bar icon
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  click menu bar item 1 of menu bar 2 of process "{app_name}"\n'
                f"end tell"
            )
        elif view["type"] == "tab" or view["type"] == "tabview":
            # Try Tab key navigation
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f"  keystroke tab\n"
                f"end tell"
            )
        elif view["type"] == "sheet":
            # Try Cmd+N for new item (common pattern)
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f'  keystroke "n" using command down\n'
                f"end tell"
            )
        elif view["type"] == "navigation":
            # Try arrow keys to navigate list
            script = (
                f'tell application "{app_name}" to activate\n'
                f'tell application "System Events"\n'
                f"  key code 125\n"
                f"end tell"
            )
        else:
            return
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=5)
    except Exception:
        pass




async def _qa_screenshots_ios(ws: Path, shots_dir: Path) -> list[str]:
    """Build iOS app for simulator, boot sim, screenshot."""
    import asyncio as _aio
    import subprocess

    results = []
    has_xcproj = any(ws.glob("*.xcodeproj")) or any(ws.glob("*.xcworkspace"))

    if has_xcproj:
        build_result = subprocess.run(
            [
                "xcodebuild",
                "-scheme",
                "App",
                "-sdk",
                "iphonesimulator",
                "-destination",
                "platform=iOS Simulator,name=iPhone 16",
                "-derivedDataPath",
                str(ws / ".build"),
                "build",
            ],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=180,
        )
    else:
        build_result = subprocess.run(
            ["xcrun", "swift", "build"],
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=120,
        )

    build_log = (build_result.stdout + "\n" + build_result.stderr)[-2000:]
    if build_result.returncode != 0:
        _write_status_png(
            shots_dir / "01_ios_build_failed.png",
            "iOS BUILD FAILED [X]",
            build_log[-1000:],
            bg_color=(40, 10, 10),
        )
        results.append("screenshots/01_ios_build_failed.png")
        return results

    _write_status_png(
        shots_dir / "01_ios_build_success.png",
        "iOS BUILD [OK]",
        build_log[-400:],
        bg_color=(10, 40, 10),
    )
    results.append("screenshots/01_ios_build_success.png")

    # Boot simulator + screenshot
    try:
        subprocess.run(
            ["xcrun", "simctl", "boot", "iPhone 16"], capture_output=True, timeout=30
        )
        await _aio.sleep(3)
        subprocess.run(
            [
                "xcrun",
                "simctl",
                "io",
                "booted",
                "screenshot",
                str(shots_dir / "02_simulator.png"),
            ],
            capture_output=True,
            timeout=15,
        )
        if (shots_dir / "02_simulator.png").exists():
            results.append("screenshots/02_simulator.png")
    except Exception as e:
        logger.error("iOS simulator screenshot failed: %s", e)
    return results




async def _qa_screenshots_web(
    ws: Path, shots_dir: Path, platform_type: str
) -> list[str]:
    """Start web server → Playwright multi-step journey screenshots (routes + interactions + RBAC)."""
    import asyncio as _aio
    import subprocess

    results = []
    proc = None
    port = 18234

    try:
        # Start server
        if platform_type == "web-docker":
            r = subprocess.run(
                ["docker", "build", "-t", "qa-screenshot-app", "."],
                cwd=str(ws),
                capture_output=True,
                text=True,
                timeout=180,
            )
            if r.returncode == 0:
                proc = subprocess.Popen(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--name",
                        "qa-screenshot-app",
                        "-p",
                        f"{port}:8080",
                        "qa-screenshot-app",
                    ],
                    cwd=str(ws),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True,
                )
            else:
                build_log = (r.stdout + "\n" + r.stderr)[-1200:]
                _write_status_png(
                    shots_dir / "01_docker_build_failed.png",
                    "DOCKER BUILD FAILED [X]",
                    build_log,
                    bg_color=(40, 10, 10),
                )
                results.append("screenshots/01_docker_build_failed.png")
                return results
        elif platform_type == "web-node":
            subprocess.run(
                ["npm", "install"], cwd=str(ws), capture_output=True, timeout=60
            )
            proc = subprocess.Popen(
                ["npm", "start"],
                cwd=str(ws),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env={**__import__("os").environ, "PORT": str(port)},
            )
        elif platform_type == "web-static":
            proc = subprocess.Popen(
                ["python3", "-m", "http.server", str(port)],
                cwd=str(ws),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

        if proc:
            await _aio.sleep(4)

            # Discover routes from codebase
            routes = _discover_web_routes(ws)
            # Discover auth/RBAC users if any
            users = _discover_web_users(ws)

            # Generate Python Playwright journey script
            journey_script = _build_playwright_journey_py(
                port, routes, users, str(shots_dir)
            )

            r = subprocess.run(
                ["python3", "-c", journey_script],
                capture_output=True,
                text=True,
                timeout=90,
                cwd=str(ws),
            )

            # Collect all generated screenshots
            if shots_dir.exists():
                for png in sorted(shots_dir.glob("*.png")):
                    if png.stat().st_size > 1000:
                        results.append(f"screenshots/{png.name}")

            # If no screenshots, write error
            if not results:
                err = (r.stderr or r.stdout or "No output")[-800:]
                _write_status_png(
                    shots_dir / "01_playwright_error.png",
                    "PLAYWRIGHT FAILED",
                    err,
                    bg_color=(40, 10, 10),
                )
                results.append("screenshots/01_playwright_error.png")

    except Exception as e:
        logger.error("Web screenshot pipeline failed: %s", e)
        _write_status_png(
            shots_dir / "01_web_error.png",
            "WEB PIPELINE FAILED",
            str(e)[:500],
            bg_color=(40, 10, 10),
        )
        results.append("screenshots/01_web_error.png")
    finally:
        if proc:
            try:
                import os

                os.killpg(os.getpgid(proc.pid), 9)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            if platform_type == "web-docker":
                subprocess.run(
                    ["docker", "rm", "-f", "qa-screenshot-app"],
                    capture_output=True,
                    timeout=10,
                )
    return results




def _discover_web_routes(ws: Path) -> list[dict]:
    """Scan codebase to find web routes for screenshot journey."""
    import re

    routes = [{"path": "/", "label": "homepage", "actions": []}]
    seen = {"/"}

    # SvelteKit / Next.js file-based routes
    for routes_dir in [ws / "src" / "routes", ws / "app", ws / "pages"]:
        if routes_dir.exists():
            for f in sorted(routes_dir.rglob("*.{svelte,tsx,jsx,vue}")):
                rel = str(f.parent.relative_to(routes_dir)).replace("\\", "/")
                if rel == ".":
                    continue
                route = "/" + rel.replace("(", "").replace(")", "").replace(
                    "[", ":"
                ).replace("]", "")
                if (
                    route not in seen
                    and "+page" in f.name
                    or "index" in f.name
                    or "page" in f.name
                ):
                    label = rel.strip("/").replace("/", "_").replace("-", "_")
                    routes.append({"path": route, "label": label, "actions": []})
                    seen.add(route)

    # Express / FastAPI route decorators
    for ext in ("*.py", "*.ts", "*.js"):
        for f in ws.rglob(ext):
            if "node_modules" in str(f) or ".build" in str(f):
                continue
            try:
                code = f.read_text(errors="ignore")[:5000]
            except Exception:
                continue
            # Python: @app.get("/path") or @router.get("/path")
            for m in re.finditer(r'@(?:app|router)\.\w+\(["\'](/[^"\']*)["\']', code):
                path = m.group(1)
                if path not in seen and not re.search(r":\w+|{\w+}", path):
                    routes.append(
                        {
                            "path": path,
                            "label": path.strip("/").replace("/", "_") or "root",
                            "actions": [],
                        }
                    )
                    seen.add(path)
            # Express: app.get('/path', ...)
            for m in re.finditer(
                r"(?:app|router)\.(?:get|post|use)\(['\"](/[^'\"]*)['\"]", code
            ):
                path = m.group(1)
                if path not in seen and not re.search(r":\w+", path):
                    routes.append(
                        {
                            "path": path,
                            "label": path.strip("/").replace("/", "_") or "root",
                            "actions": [],
                        }
                    )
                    seen.add(path)

    # HTML files as fallback
    for hf in sorted(ws.rglob("*.html"))[:10]:
        if "node_modules" in str(hf) or ".build" in str(hf):
            continue
        rel = str(hf.relative_to(ws))
        path = f"/{rel}"
        if path not in seen:
            routes.append(
                {
                    "path": path,
                    "label": rel.replace("/", "_").replace(".html", ""),
                    "actions": [],
                }
            )
            seen.add(path)

    # Discover forms/buttons for interaction steps
    for route in routes[:10]:
        _enrich_route_actions(ws, route)

    return routes[:15]




def _enrich_route_actions(ws: Path, route: dict):
    """Detect interactive elements (forms, buttons, modals) in route files."""
    import re

    actions = []
    # Search for form elements, buttons, links in HTML/template files
    for ext in ("*.html", "*.svelte", "*.tsx", "*.jsx", "*.vue"):
        for f in ws.rglob(ext):
            if "node_modules" in str(f):
                continue
            try:
                code = f.read_text(errors="ignore")[:8000]
            except Exception:
                continue
            if route["path"] != "/" and route["label"] not in str(f).lower():
                continue
            # Forms
            if "<form" in code:
                actions.append({"type": "form", "selector": "form"})
            # Login patterns
            if 'type="password"' in code or 'type="email"' in code:
                actions.append({"type": "login", "selector": "form"})
            # Buttons with text
            for m in re.finditer(r"<button[^>]*>([^<]+)</button>", code):
                btn_text = m.group(1).strip()
                if len(btn_text) < 30:
                    actions.append(
                        {"type": "click", "selector": f"button:has-text('{btn_text}')"}
                    )
            # Navigation links
            for m in re.finditer(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>', code
            ):
                href, text = m.group(1), m.group(2).strip()
                if href.startswith("/") and len(text) < 30:
                    actions.append({"type": "navigate", "href": href, "text": text})
            break  # Only check first matching file
    route["actions"] = actions[:5]




def _discover_web_users(ws: Path) -> list[dict]:
    """Scan codebase for auth/RBAC test users (env, fixtures, seed)."""
    import re

    users = []
    # Check for seed/fixture files
    for pattern in ("*seed*", "*fixture*", "*mock*", ".env*", "*test*"):
        for f in ws.glob(pattern):
            try:
                code = f.read_text(errors="ignore")[:3000]
            except Exception:
                continue
            # Look for user/password patterns
            for m in re.finditer(
                r'(?:email|user(?:name)?)\s*[:=]\s*["\']([^"\']+)["\']', code, re.I
            ):
                email = m.group(1)
                pw_match = re.search(
                    r'(?:password|pass|pwd)\s*[:=]\s*["\']([^"\']+)["\']',
                    code[m.start() : m.start() + 200],
                    re.I,
                )
                if pw_match:
                    role = "user"
                    if "admin" in email.lower():
                        role = "admin"
                    elif "manager" in email.lower() or "lead" in email.lower():
                        role = "manager"
                    users.append(
                        {"email": email, "password": pw_match.group(1), "role": role}
                    )
    # Deduplicate
    seen = set()
    unique = []
    for u in users:
        if u["email"] not in seen:
            unique.append(u)
            seen.add(u["email"])
    return unique[:4]




def _build_playwright_journey(
    port: int, routes: list, users: list, shots_dir: str
) -> str:
    """Generate a Playwright script that screenshots each route + interactions + RBAC."""
    base = f"http://localhost:{port}"

    # Build journey steps
    steps_js = ""
    step_num = 1

    # Per-user journeys (RBAC)
    if users:
        for user in users[:3]:
            role = user["role"]
            steps_js += f"""
    // --- RBAC Journey: {role} ({user["email"]}) ---
    console.log('Journey: {role}');
    await page.goto('{base}/', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_00_before_login.png', fullPage: true }});
"""
            step_num += 1
            # Try login
            steps_js += f"""
    // Login attempt
    try {{
        const loginForm = await page.$('form');
        if (loginForm) {{
            const emailInput = await page.$('input[type="email"], input[name="email"], input[name="username"]');
            const pwInput = await page.$('input[type="password"]');
            if (emailInput && pwInput) {{
                await emailInput.fill('{user["email"]}');
                await pwInput.fill('{user["password"]}');
                await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_01_login_filled.png', fullPage: true }});
                await loginForm.$('button[type="submit"], button').then(b => b && b.click()).catch(() => {{}});
                await page.waitForTimeout(2000);
                await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_02_after_login.png', fullPage: true }});
            }}
        }}
    }} catch(e) {{ console.log('Login skip:', e.message); }}
"""
            step_num += 2
            # Visit each route as this user
            for route in routes[:5]:
                steps_js += f"""
    await page.goto('{base}{route["path"]}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{role}_{route["label"]}.png', fullPage: true }});
"""
                step_num += 1
            # Clear session
            steps_js += """
    await context.clearCookies();
"""
    else:
        # No RBAC — anonymous journey through all routes
        for route in routes[:10]:
            label = route["label"]
            steps_js += f"""
    // Route: {route["path"]}
    await page.goto('{base}{route["path"]}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}.png', fullPage: true }});
"""
            step_num += 1

            # Interactions on this page
            for action in route.get("actions", [])[:3]:
                if action["type"] == "click":
                    steps_js += f"""
    try {{
        const btn = await page.$('{action["selector"]}');
        if (btn) {{
            await btn.click();
            await page.waitForTimeout(1000);
            await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}_click.png', fullPage: true }});
        }}
    }} catch(e) {{}}
"""
                    step_num += 1
                elif action["type"] == "navigate":
                    steps_js += f"""
    await page.goto('{base}{action.get("href", "/")}', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_{label}_nav_{action.get("text", "link")[:10]}.png', fullPage: true }});
"""
                    step_num += 1

    # Viewport variants (mobile + desktop)
    steps_js += f"""
    // Mobile viewport
    await page.setViewportSize({{ width: 375, height: 812 }});
    await page.goto('{base}/', {{ waitUntil: 'networkidle', timeout: 10000 }}).catch(() => {{}});
    await page.screenshot({{ path: '{shots_dir}/{step_num:02d}_mobile_home.png', fullPage: true }});
"""
    step_num += 1

    script = f"""
const {{ chromium }} = require('playwright');
(async () => {{
    const browser = await chromium.launch();
    const context = await browser.newContext({{ viewport: {{ width: 1280, height: 720 }} }});
    const page = await context.newPage();
    const errors = [];
    page.on('console', msg => {{ if (msg.type() === 'error') errors.push(msg.text()); }});

    try {{
{steps_js}
    }} catch(e) {{
        console.error('Journey error:', e.message);
    }}

    // Console errors summary
    if (errors.length > 0) {{
        const fs = require('fs');
        fs.writeFileSync('{shots_dir}/console_errors.txt', errors.join('\\n'));
    }}

    await browser.close();
}})();
"""
    return script




def _build_playwright_journey_py(
    port: int, routes: list, users: list, shots_dir: str
) -> str:
    """Generate a Python Playwright script that screenshots each route."""
    base = f"http://localhost:{port}"

    steps = ""
    step_num = 1

    if users:
        for user in users[:3]:
            role = user["role"]
            steps += f"""
        # RBAC Journey: {role}
        await page.goto("{base}/", wait_until="networkidle", timeout=10000)
        await page.screenshot(path="{shots_dir}/{step_num:02d}_{role}_before_login.png", full_page=True)
"""
            step_num += 1
            for route in routes[:5]:
                steps += f"""
        try:
            await page.goto("{base}{route["path"]}", wait_until="networkidle", timeout=10000)
            await page.screenshot(path="{shots_dir}/{step_num:02d}_{role}_{route["label"]}.png", full_page=True)
        except Exception:
            pass
"""
                step_num += 1
            steps += "        await context.clear_cookies()\n"
    else:
        for route in routes[:10]:
            label = route["label"]
            steps += f"""
        try:
            await page.goto("{base}{route["path"]}", wait_until="networkidle", timeout=10000)
            await page.screenshot(path="{shots_dir}/{step_num:02d}_{label}.png", full_page=True)
        except Exception:
            pass
"""
            step_num += 1

    # Mobile viewport
    steps += f"""
        await page.set_viewport_size({{"width": 375, "height": 812}})
        await page.goto("{base}/", wait_until="networkidle", timeout=10000)
        await page.screenshot(path="{shots_dir}/{step_num:02d}_mobile_home.png", full_page=True)
"""

    script = f"""
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context(viewport={{"width": 1280, "height": 720}})
        page = await context.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        try:
{steps}
        except Exception as e:
            print(f"Journey error: {{e}}")
        if errors:
            with open("{shots_dir}/console_errors.txt", "w") as f:
                f.write("\\n".join(str(e) for e in errors))
        await browser.close()

asyncio.run(main())
"""
    return script




def _write_status_png(
    path: Path,
    title: str,
    body: str,
    bg_color: tuple = (26, 17, 40),
    width: int = 800,
    height: int = 400,
):
    """Generate a status PNG with readable text using Pillow."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        lines = body.split("\n")
        line_h = 16
        pad = 20
        title_h = 36
        img_w = max(width, 600)
        img_h = max(height, len(lines) * line_h + pad * 2 + title_h + 20)

        img = Image.new("RGB", (img_w, img_h), bg_color)
        draw = ImageDraw.Draw(img)

        # Title bar
        draw.rectangle([0, 0, img_w, title_h], fill=(37, 26, 53))
        draw.line([0, title_h, img_w, title_h], fill=(168, 85, 247), width=2)

        # Use default font (monospace-like)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 13)
            title_font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 15)
        except Exception:
            font = ImageFont.load_default()
            title_font = font

        # Title text
        draw.text((pad, 8), title, fill=(255, 255, 255), font=title_font)

        # Body text
        y = title_h + pad
        for line in lines:
            # Truncate long lines
            if len(line) > 100:
                line = line[:97] + "..."
            color = (200, 200, 200)
            if "error" in line.lower() or "failed" in line.lower():
                color = (255, 100, 100)
            elif "warning" in line.lower():
                color = (255, 200, 80)
            elif "success" in line.lower() or "[OK]" in line:
                color = (100, 255, 100)
            draw.text((pad, y), line, fill=color, font=font)
            y += line_h
            if y > img_h - pad:
                draw.text((pad, y), "... (truncated)", fill=(150, 150, 150), font=font)
                break

        img.save(str(path), "PNG")
    except ImportError:
        # Fallback: minimal PNG without text
        import struct
        import zlib

        img_w, img_h = 400, 100
        raw = b""
        for y in range(img_h):
            raw += b"\x00" + bytes(bg_color) * img_w

        def _ch(ct, d):
            c = ct + d
            return (
                struct.pack(">I", len(d))
                + c
                + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", img_w, img_h, 8, 2, 0, 0, 0)
        with open(str(path), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n")
            f.write(_ch(b"IHDR", ihdr))
            f.write(_ch(b"IDAT", zlib.compress(raw)))
            f.write(_ch(b"IEND", b""))

    # Also write readable text
    path.with_suffix(".txt").write_text(f"=== {title} ===\n\n{body}")




def _detect_project_platform(workspace_path: str, brief: str = "") -> str:
    """Detect project platform from brief first, then workspace files.

    Returns one of: macos-native, ios-native, android-native, web-docker, web-node, web-static, unknown
    """
    # --- Priority 1: Check brief/mission text for explicit stack ---
    if brief:
        bl = brief.lower()
        # Explicit web indicators override file detection
        web_kw = (
            "react",
            "vue",
            "svelte",
            "angular",
            "next.js",
            "nextjs",
            "nuxt",
            "vite",
            "node.js",
            "nodejs",
            "express",
            "fastapi",
            "django",
            "flask",
            "typescript",
            "html",
            "css",
            "tailwind",
            "web app",
            "webapp",
            "site web",
            "website",
            "clone",
            "saas",
            "dashboard",
            "figma",
            "frontend",
            "full-stack",
            "fullstack",
        )
        if any(kw in bl for kw in web_kw):
            return "web-node"
        ios_kw = (
            "ios",
            "iphone",
            "ipad",
            "swiftui",
            "uikit",
            "swift app",
            "apple",
            "xcode",
        )
        if any(kw in bl for kw in ios_kw):
            return "ios-native"
        macos_kw = ("macos", "mac app", "appkit", "cocoa")
        if any(kw in bl for kw in macos_kw):
            return "macos-native"
        android_kw = ("android", "kotlin", "jetpack", "gradle")
        if any(kw in bl for kw in android_kw):
            return "android-native"

    # --- Priority 2: Check .stack file (written by ideation/architecture phase) ---
    if workspace_path:
        ws = Path(workspace_path)
        stack_file = ws / ".stack"
        if stack_file.exists():
            try:
                stack = stack_file.read_text().strip().lower()
                if stack in (
                    "web-node",
                    "web-docker",
                    "web-static",
                    "ios-native",
                    "macos-native",
                    "android-native",
                ):
                    return stack
            except Exception:
                pass

    # --- Priority 3: Fallback to file detection ---
    if not workspace_path:
        return "unknown"
    ws = Path(workspace_path)
    if not ws.exists():
        return "unknown"

    has_swift = (ws / "Package.swift").exists() or (ws / "Sources").exists()
    has_xcode = (
        any(ws.glob("*.xcodeproj"))
        or any(ws.glob("*.xcworkspace"))
        or (ws / "project.yml").exists()
    )
    has_kotlin = (ws / "build.gradle").exists() or (ws / "build.gradle.kts").exists()
    has_android = (
        (ws / "app" / "build.gradle").exists()
        or (ws / "app" / "build.gradle.kts").exists()
        or (ws / "AndroidManifest.xml").exists()
    )
    has_node = (ws / "package.json").exists()
    has_docker = (ws / "Dockerfile").exists() or (ws / "docker-compose.yml").exists()

    # Web indicators take priority over Swift (prevents accidental Swift bias)
    if has_node:
        return "web-node"

    if has_docker:
        return "web-docker"

    if (ws / "index.html").exists():
        return "web-static"

    # Swift/Xcode detection only if NO web indicators
    if has_swift or has_xcode:
        is_ios = False
        for f in [ws / "Package.swift", ws / "project.yml"]:
            if f.exists():
                try:
                    text = f.read_text()[:3000].lower()
                    if "ios" in text or "uikit" in text or "iphone" in text:
                        is_ios = True
                except Exception:
                    pass
        if not is_ios:
            for src in (
                list((ws / "Sources").rglob("*.swift"))[:20]
                if (ws / "Sources").exists()
                else []
            ):
                try:
                    txt = src.read_text()[:500].lower()
                    if "uiapplication" in txt or "uiscene" in txt or "uidevice" in txt:
                        is_ios = True
                        break
                except Exception:
                    pass
        return "ios-native" if is_ios else "macos-native"

    if has_android or (has_kotlin and not has_node):
        return "android-native"

    return "unknown"


# Platform-specific QA/deploy/CI prompts


_PLATFORM_QA = {
    "macos-native": {
        "qa-campaign": (
            "TYPE: Application macOS native (Swift/SwiftUI)\n"
            "OUTILS QA ADAPTÉS — PAS de Playwright, PAS de Docker :\n"
            "1. list_files + code_read pour comprendre la structure\n"
            "2. Créez tests/PLAN.md (code_write) — plan de test macOS natif\n"
            "3. Build: build command='swift build'\n"
            "4. Tests unitaires: build command='swift test'\n"
            "5. Bootez simulateur: build command='open -a Simulator'\n"
            "6. SCREENSHOTS par parcours utilisateur (simulator_screenshot) :\n"
            "   - simulator_screenshot filename='01_launch.png'\n"
            "   - simulator_screenshot filename='02_main_view.png'\n"
            "   - simulator_screenshot filename='03_feature_1.png'\n"
            "   - simulator_screenshot filename='04_feature_2.png'\n"
            "   - simulator_screenshot filename='05_settings.png'\n"
            "7. Documentez bugs dans tests/BUGS.md, commitez\n"
            "IMPORTANT: Chaque parcours DOIT avoir un screenshot réel."
        ),
        "qa-execution": (
            "TYPE: Application macOS native (Swift/SwiftUI)\n"
            "1. build command='swift test'\n"
            "2. build command='open -a Simulator'\n"
            "3. SCREENSHOTS: simulator_screenshot pour chaque écran\n"
            "4. tests/REPORT.md avec résultats + screenshots\n"
            "PAS de Playwright. PAS de Docker."
        ),
        "deploy-prod": (
            "TYPE: Application macOS native — PAS de Docker/Azure\n"
            "1. build command='swift build -c release'\n"
            "2. Créez .app bundle ou archive\n"
            "3. simulator_screenshot filename='release_final.png'\n"
            "4. Documentez installation dans INSTALL.md\n"
            "Distribution: TestFlight, .dmg, ou Mac App Store."
        ),
        "cicd": (
            "TYPE: Application macOS native\n"
            "1. Créez .github/workflows/ci.yml avec xcodebuild ou swift build\n"
            "2. Créez scripts/build.sh + scripts/test.sh\n"
            "3. build command='swift build && swift test'\n"
            "4. git_commit\n"
            "PAS de Dockerfile. PAS de docker-compose."
        ),
    },
    "ios-native": {
        "qa-campaign": (
            "TYPE: Application iOS native (Swift/SwiftUI/UIKit)\n"
            "OUTILS QA iOS — simulateur iPhone :\n"
            "1. list_files + code_read\n"
            "2. Créez tests/PLAN.md (code_write)\n"
            "3. Build: build command='xcodebuild -scheme App -sdk iphonesimulator -destination \"platform=iOS Simulator,name=iPhone 16\" build'\n"
            "4. Tests: build command='xcodebuild test -scheme App -sdk iphonesimulator -destination \"platform=iOS Simulator,name=iPhone 16\"'\n"
            "5. SCREENSHOTS par parcours (simulator_screenshot) :\n"
            "   - simulator_screenshot filename='01_splash.png'\n"
            "   - simulator_screenshot filename='02_onboarding.png'\n"
            "   - simulator_screenshot filename='03_main_screen.png'\n"
            "   - simulator_screenshot filename='04_detail.png'\n"
            "   - simulator_screenshot filename='05_profile.png'\n"
            "6. Documentez bugs dans tests/BUGS.md\n"
            "IMPORTANT: Screenshots RÉELS du simulateur iPhone."
        ),
        "qa-execution": (
            "TYPE: Application iOS native\n"
            "1. build command='xcodebuild test -scheme App -sdk iphonesimulator'\n"
            "2. simulator_screenshot pour chaque écran\n"
            "3. tests/REPORT.md\n"
            "PAS de Playwright. PAS de Docker."
        ),
        "deploy-prod": (
            "TYPE: Application iOS — TestFlight ou App Store\n"
            "1. build command='xcodebuild archive -scheme App'\n"
            "2. Export IPA pour TestFlight\n"
            "3. simulator_screenshot filename='release_final.png'\n"
            "Distribution: TestFlight → App Store Connect."
        ),
        "cicd": (
            "TYPE: Application iOS native\n"
            "1. .github/workflows/ci.yml avec xcodebuild + simulateur\n"
            "2. Fastlane si disponible\n"
            "3. build + test command\n"
            "PAS de Docker."
        ),
    },
    "android-native": {
        "qa-campaign": (
            "TYPE: Application Android native (Kotlin/Java)\n"
            "OUTILS QA Android — émulateur :\n"
            "1. list_files + code_read\n"
            "2. Créez tests/PLAN.md (code_write)\n"
            "3. Build: build command='./gradlew assembleDebug'\n"
            "4. Tests: build command='./gradlew testDebugUnitTest'\n"
            "5. Tests instrumentés: build command='./gradlew connectedAndroidTest'\n"
            "6. SCREENSHOTS: build command='adb exec-out screencap -p > screenshots/NOM.png'\n"
            "7. Documentez bugs dans tests/BUGS.md\n"
            "IMPORTANT: Lancez l'émulateur et prenez des screenshots réels."
        ),
        "qa-execution": (
            "TYPE: Application Android native\n"
            "1. build command='./gradlew testDebugUnitTest'\n"
            "2. build command='./gradlew connectedAndroidTest'\n"
            "3. Screenshots via adb\n"
            "4. tests/REPORT.md\n"
            "PAS de Playwright."
        ),
        "deploy-prod": (
            "TYPE: Application Android — Play Store\n"
            "1. build command='./gradlew assembleRelease'\n"
            "2. Signer l'APK/AAB\n"
            "3. Screenshot final\n"
            "Distribution: Google Play Console."
        ),
        "cicd": (
            "TYPE: Application Android native\n"
            "1. .github/workflows/ci.yml avec Gradle + JDK\n"
            "2. Android SDK setup\n"
            "3. ./gradlew build + test\n"
            "PAS de Docker pour le build."
        ),
    },
}

# Web fallback (docker / node / static)


_WEB_QA = {
    "qa-campaign": (
        "TYPE: Application web\n"
        "1. list_files + code_read\n"
        "2. Créez tests/PLAN.md (code_write)\n"
        "3. Tests E2E Playwright :\n"
        "   - tests/e2e/smoke.spec.ts (HTTP 200, 0 erreurs console)\n"
        "   - tests/e2e/journey.spec.ts (parcours complets)\n"
        "4. Lancez: playwright_test spec=tests/e2e/smoke.spec.ts\n"
        "5. SCREENSHOTS par page/parcours :\n"
        "   - screenshot url=http://localhost:3000 filename='01_home.png'\n"
        "   - screenshot url=http://localhost:3000/dashboard filename='02_dashboard.png'\n"
        "   UN SCREENSHOT PAR PAGE\n"
        "6. tests/BUGS.md + git_commit\n"
        "IMPORTANT: Screenshots réels, pas simulés."
    ),
    "qa-execution": (
        "TYPE: Application web\n"
        "1. playwright_test spec=tests/e2e/smoke.spec.ts\n"
        "2. screenshot par page\n"
        "3. tests/REPORT.md"
    ),
    "deploy-prod": (
        "TYPE: Application web\n"
        "DEPLOIEMENT REEL — Utilisez docker_deploy pour builder+run le container:\n"
        "1. docker_deploy cwd=WORKSPACE_PATH mission_id=MISSION_ID\n"
        "   → Auto-genere Dockerfile si absent, installe deps, build image, run container\n"
        "   → Retourne l'URL live du container\n"
        "2. docker_status mission_id=MISSION_ID pour verifier le container\n"
        "3. screenshot url=URL_RETOURNEE filename='deploy_final.png'\n"
        "4. Si health check echoue: docker_status pour les logs, corrigez, recommencez\n"
        "IMPORTANT: PAS de discussion sur le deploiement. EXECUTEZ docker_deploy."
    ),
    "cicd": (
        "TYPE: Application web\n"
        "1. Dockerfile + docker-compose.yml\n"
        "2. .github/workflows/ci.yml\n"
        "3. scripts/build.sh + test.sh\n"
        "4. build + verify"
    ),
}




async def _extract_features_from_phase(
    mission_id: str,
    session_id: str,
    phase_id: str,
    phase_name: str,
    summary: str,
    pre_msg_count: int,
):
    """Extract features/user stories from phase output and insert into features table."""
    import uuid

    try:
        from ....db.migrations import get_db
        from ....llm.client import LLMMessage, get_llm_client
        from ....sessions.store import get_session_store

        ss = get_session_store()
        msgs = ss.get_messages(session_id, limit=1000)
        phase_msgs = msgs[pre_msg_count:]
        transcript_parts = []
        for m in phase_msgs:
            txt = (getattr(m, "content", "") or "").strip()
            if txt and len(txt) > 30:
                name = getattr(m, "from_name", "") or getattr(m, "from_agent", "") or ""
                transcript_parts.append(f"{name}: {txt[:600]}")
        if not transcript_parts and not summary:
            return
        transcript = "\n".join(transcript_parts[-20:])

        llm = get_llm_client()
        resp = await asyncio.wait_for(
            llm.chat(
                [
                    LLMMessage(
                        role="user",
                        content=(
                            "Extract actionable features/user stories from this phase output. "
                            "Return a JSON array of objects with keys: name (short title), description, priority (1-5, 1=highest), story_points (1,2,3,5,8,13). "
                            "If no features found, return []. Only valid JSON, no markdown.\n\n"
                            f"Phase: {phase_name}\nSummary: {summary}\n\nTranscript:\n{transcript[:3000]}"
                        ),
                    )
                ],
                max_tokens=500,
                temperature=0.2,
            ),
            timeout=30,
        )

        import json as _json

        raw = (resp.content or "").strip()
        # Strip markdown fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        features = _json.loads(raw)
        if not isinstance(features, list):
            return

        db = get_db()
        inserted = []
        for feat in features[:15]:
            if not isinstance(feat, dict) or not feat.get("name"):
                continue
            fid = str(uuid.uuid4())[:8]
            db.execute(
                "INSERT OR IGNORE INTO features (id, epic_id, name, description, priority, status, story_points) VALUES (?,?,?,?,?,?,?)",
                (
                    fid,
                    mission_id,
                    feat["name"][:120],
                    feat.get("description", "")[:500],
                    feat.get("priority", 5),
                    "backlog",
                    feat.get("story_points", 3),
                ),
            )
            inserted.append(
                {
                    "id": fid,
                    "name": feat["name"][:120],
                    "priority": feat.get("priority", 5),
                    "story_points": feat.get("story_points", 3),
                    "status": "backlog",
                }
            )
        db.commit()

        if inserted:
            await _push_sse(
                session_id,
                {
                    "type": "backlog_update",
                    "mission_id": mission_id,
                    "phase_id": phase_id,
                    "features": inserted,
                },
            )
    except Exception:
        pass




def _build_phase_prompt(
    phase_name: str,
    pattern: str,
    brief: str,
    idx: int,
    total: int,
    prev_context: str = "",
    workspace_path: str = "",
) -> str:
    """Build a contextual task prompt for each lifecycle phase."""
    platform = _detect_project_platform(workspace_path, brief=brief)

    # Get platform-specific QA/deploy/cicd prompts
    platform_prompts = _PLATFORM_QA.get(platform, {})

    def _qa(key: str) -> str:
        base = platform_prompts.get(key, _WEB_QA.get(key, ""))
        return f"{key.replace('-', ' ').title()} pour «{brief}».\n{base}\nIMPORTANT: Commandes réelles, pas de simulation."

    platform_label = {
        "macos-native": "macOS native (Swift/SwiftUI)",
        "ios-native": "iOS native (Swift/SwiftUI/UIKit)",
        "android-native": "Android native (Kotlin/Java)",
        "web-docker": "web (Docker)",
        "web-node": "web (Node.js)",
        "web-static": "web statique",
    }.get(platform, "")

    prompts = {
        "ideation": (
            f"Nous démarrons l'idéation pour le projet : «{brief}».\n"
            "Chaque expert doit donner son avis selon sa spécialité :\n"
            "- Business Analyst : besoin métier, personas, pain points\n"
            "- UX Designer : parcours utilisateur, wireframes, ergonomie\n"
            "- Architecte : faisabilité technique, stack recommandée\n"
            "- Product Manager : valeur business, ROI, priorisation\n"
            "Débattez et convergez vers une vision produit cohérente."
        ),
        "strategic-committee": (
            f"Comité stratégique GO/NOGO pour le projet : «{brief}».\n"
            "Analysez selon vos rôles respectifs :\n"
            "- CPO : alignement vision produit, roadmap\n"
            "- CTO : risques techniques, capacité équipe\n"
            "- Portfolio Manager : WSJF score, priorisation portefeuille\n"
            "- Lean Portfolio Manager : budget, ROI, lean metrics\n"
            "- DSI : alignement stratégique SI, gouvernance\n"
            "Donnez votre avis : GO, NOGO, ou PIVOT avec justification."
        ),
        "project-setup": (
            f"Constitution du projet «{brief}».\n"
            "- Scrum Master : cérémonie, cadence sprints, outils\n"
            "- RH : staffing, compétences requises, planning\n"
            "- Lead Dev : stack technique, repo, CI/CD setup\n"
            "- Product Owner : backlog initial, user stories prioritisées\n"
            "Définissez l'organisation projet complète."
        ),
        "architecture": (
            f"Design architecture pour «{brief}».\n"
            + (f"PLATEFORME CIBLE: {platform_label}\n" if platform_label else "")
            + "- Architecte : patterns, layers, composants, API design\n"
            "- UX Designer : maquettes, design system, composants UI\n"
            "- Expert Sécurité : threat model, auth, OWASP\n"
            "- DevOps : infra, CI/CD, monitoring, environnements\n"
            "- Lead Dev : revue technique, standards code\n"
            "Produisez le dossier d'architecture consolidé."
        ),
        "dev-sprint": (
            f"Sprint de développement TDD pour «{brief}».\n"
            + (f"PLATEFORME: {platform_label}\n" if platform_label else "")
            + (
                f"/!\\ STACK OBLIGATOIRE: {platform_label}. NE PAS utiliser une autre technologie.\n"
                f"{'Utilisez HTML/CSS/JS ou TypeScript/Node.js. NE PAS écrire de Swift.' if platform in ('web-node', 'web-docker', 'web-static') else ''}\n"
                f"{'Utilisez Swift/SwiftUI. NE PAS écrire de TypeScript.' if platform in ('ios-native', 'macos-native') else ''}\n"
                f"{'Utilisez Kotlin/Java. NE PAS écrire de Swift.' if platform == 'android-native' else ''}\n"
                if platform_label
                else ""
            )
            + "VOUS DEVEZ UTILISER VOS OUTILS pour écrire du VRAI code dans le workspace.\n\n"
            "WORKFLOW OBLIGATOIRE:\n"
            "1. LIRE LE WORKSPACE: list_files + code_read sur les fichiers existants\n"
            "2. ECRIRE LE CODE avec code_write:\n"
            "   - Créer les fichiers source (HTML, CSS, JS, package.json si Node.js)\n"
            "   - Créer au moins un fichier de test\n"
            "   - Minimum 5 fichiers source pour une application fonctionnelle\n"
            "3. BUILDER avec l'outil build:\n"
            "   - Appeler build(command='npm install && npm run build', cwd=WORKSPACE)\n"
            "   - Ou build(command='npx tsc --noEmit', cwd=WORKSPACE) pour TypeScript\n"
            "   - Pour du HTML/JS simple: build(command='node -e \"console.log(1)\"', cwd=WORKSPACE)\n"
            "4. TESTER avec l'outil test:\n"
            "   - Appeler test(command='npm test', cwd=WORKSPACE)\n"
            "   - Ou test(command='node tests/run.js', cwd=WORKSPACE)\n"
            "5. COMMITTER avec git_commit: message descriptif\n\n"
            "REGLES STRICTES:\n"
            "- Chaque dev DOIT appeler code_write au minimum 3 fois\n"
            "- Au moins UN appel à build() ou test() est OBLIGATOIRE\n"
            "- NE DISCUTEZ PAS du code. ECRIVEZ-LE avec code_write.\n"
            "- Pas de placeholder, pas de TODO, pas de mock — du vrai code fonctionnel\n"
            "- Créez un package.json si c'est un projet Node.js"
        ),
        "cicd": _qa("cicd"),
        "qa-campaign": _qa("qa-campaign"),
        "qa-execution": _qa("qa-execution"),
        "deploy-prod": _qa("deploy-prod"),
        "tma-routing": (
            f"Routage incidents TMA pour «{brief}».\n"
            "- Support N1 : classification, triage incident\n"
            "- Support N2 : diagnostic technique\n"
            "- QA : reproduction, test regression\n"
            "- Lead Dev : évaluation impact, assignation\n"
            "Classifiez et routez l'incident."
        ),
        "tma-fix": (
            f"Correctif TMA (TDD) pour «{brief}».\n"
            "UTILISEZ VOS OUTILS — methode TDD obligatoire :\n"
            "1. Lisez le code concerne avec code_read\n"
            "2. RED: Ecrivez le test de non-regression qui reproduit le bug (code_write)\n"
            "3. Lancez le test — il DOIT echouer (confirmant le bug)\n"
            "4. GREEN: Corrigez le code avec code_edit (fix minimal)\n"
            "5. Lancez le test — il DOIT passer\n"
            "6. Lancez TOUS les tests pour verifier zero regression\n"
            "7. Commitez avec git_commit (message: fix + test ajouté)"
        ),
    }
    # Match by phase key first, then by alias mappings, then by index
    phase_key = phase_name.lower().replace(" ", "-").replace("é", "e").replace("è", "e")
    # Alias map for workflow phase names → prompt keys
    _KEY_ALIASES = {
        "feature-design": "architecture",
        "tdd-sprint": "dev-sprint",
        "adversarial-review": "qa-campaign",
        "tests-e2e": "qa-execution",
        "deploy-feature": "deploy-prod",
        "feature-e2e": "qa-execution",
    }
    resolved_key = _KEY_ALIASES.get(phase_key, phase_key)
    if resolved_key in prompts:
        prompt = prompts[resolved_key]
    elif idx < len(prompts):
        ordered_keys = list(prompts.keys())
        prompt = prompts[ordered_keys[idx]]
    else:
        prompt = (
            f"Phase {idx + 1}/{total} : {phase_name} (pattern: {pattern}) pour le projet «{brief}».\n"
            "Chaque agent contribue selon son rôle. Produisez un livrable concret."
        )

    # Inject previous phase context
    if prev_context:
        prompt += (
            "\n\n--- Contexte des phases précédentes ---\n"
            f"{prev_context}\n"
            "Utilisez ce contexte. Lisez le workspace avec list_files et code_read pour voir le travail déjà fait."
        )

    # Inject workspace path so agents know where to work
    if workspace_path:
        prompt += f"\n\nWORKSPACE: {workspace_path}\nUtilisez ce chemin pour cwd dans vos outils (code_write, build, docker_deploy, etc.)."

    return prompt


# ── Feedback Loop API ──────────────────────────────────────────────



