"""Docker brick — container management via docker CLI."""

from __future__ import annotations

import asyncio
import logging
import os

from . import BrickDef, BrickRegistry, ToolDef

logger = logging.getLogger(__name__)


async def _run_docker(args: str) -> str:
    cmd = f"docker {args}"
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.DEVNULL,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        if proc.returncode != 0:
            return f"Error: {(stderr or b'').decode('utf-8', errors='replace')}"
        return (stdout or b"").decode("utf-8", errors="replace")
    except asyncio.TimeoutError:
        return "Error: docker command timed out after 60s"
    except Exception as e:
        return f"Error: {e}"


async def build_image(args: dict, ctx=None) -> str:
    path = args.get("path", ".")
    tag = args.get("tag", "latest")
    dockerfile = args.get("dockerfile", "")
    cmd = f"build -t {tag} {path}"
    if dockerfile:
        cmd += f" -f {dockerfile}"
    return await _run_docker(cmd)


async def list_containers(args: dict, ctx=None) -> str:
    all_flag = "--all" if args.get("all", False) else ""
    return await _run_docker(f"ps {all_flag} --format 'table {{{{.ID}}}}\\t{{{{.Image}}}}\\t{{{{.Status}}}}\\t{{{{.Names}}}}'")


async def container_logs(args: dict, ctx=None) -> str:
    container = args.get("container", "")
    tail = args.get("tail", 50)
    return await _run_docker(f"logs --tail {tail} {container}")


async def run_container(args: dict, ctx=None) -> str:
    image = args.get("image", "")
    name = args.get("name", "")
    ports = args.get("ports", "")
    detach = args.get("detach", True)
    cmd = f"run {'--detach' if detach else ''}"
    if name:
        cmd += f" --name {name}"
    if ports:
        cmd += f" -p {ports}"
    cmd += f" {image}"
    return await _run_docker(cmd)


async def stop_container(args: dict, ctx=None) -> str:
    container = args.get("container", "")
    return await _run_docker(f"stop {container}")


BRICK = BrickDef(
    id="docker",
    name="Docker",
    description="Docker container management: build, run, logs, stop",
    tools=[
        ToolDef(name="docker_build", description="Build a Docker image",
                parameters={"path": "str", "tag": "str", "dockerfile": "str (optional)"},
                execute=build_image, category="docker"),
        ToolDef(name="docker_ps", description="List running containers",
                parameters={"all": "bool"},
                execute=list_containers, category="docker"),
        ToolDef(name="docker_logs", description="Get container logs",
                parameters={"container": "str", "tail": "int"},
                execute=container_logs, category="docker"),
        ToolDef(name="docker_run", description="Run a container",
                parameters={"image": "str", "name": "str", "ports": "str", "detach": "bool"},
                execute=run_container, category="docker"),
        ToolDef(name="docker_stop", description="Stop a container",
                parameters={"container": "str"},
                execute=stop_container, category="docker"),
    ],
    roles=["devops", "sre", "cto"],
    requires_env=[],  # Docker socket availability checked at runtime
)


def register(registry: BrickRegistry) -> None:
    registry.register(BRICK)
