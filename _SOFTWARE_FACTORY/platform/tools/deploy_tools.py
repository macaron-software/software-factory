"""
Deploy Tools - Docker build, transfer, and deploy to Azure VM.
================================================================
"""

from __future__ import annotations

import subprocess
import logging
from ..models import AgentInstance
from .registry import BaseTool

logger = logging.getLogger(__name__)

VM_HOST = "vm-macaron"  # SSH config alias


class DockerBuildTool(BaseTool):
    name = "docker_build"
    description = "Build a Docker image from a project directory containing a Dockerfile."
    category = "deploy"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        cwd = params.get("cwd", ".")
        image_name = params.get("image_name", "macaron-app")
        try:
            r = subprocess.run(
                ["docker", "build", "-t", image_name, "."],
                cwd=cwd, capture_output=True, text=True, timeout=600,
            )
            if r.returncode == 0:
                return f"[OK] Docker image '{image_name}' built successfully\n{r.stdout[-1000:]}"
            return f"[FAIL] Docker build failed (exit {r.returncode})\n{r.stderr[-2000:]}"
        except subprocess.TimeoutExpired:
            return "[FAIL] Docker build timed out (600s)"
        except Exception as e:
            return f"Error: {e}"


class DockerDeployTool(BaseTool):
    name = "deploy_azure"
    description = (
        "Deploy a Docker image to the Azure VM (4.233.64.30). "
        "Saves the image as tarball, transfers via SCP, loads and runs on the VM. "
        "Provide image_name (from docker_build) and container_port (the port the app listens on)."
    )
    category = "deploy"
    requires_approval = True

    async def execute(self, params: dict, agent: AgentInstance = None) -> str:
        image_name = params.get("image_name", "macaron-app")
        container_port = params.get("container_port", 8080)
        host_port = params.get("host_port", 0)

        if not host_port:
            import hashlib
            host_port = 8100 + int(hashlib.md5(image_name.encode()).hexdigest()[:4], 16) % 100

        tar_path = f"/tmp/{image_name}.tar"
        steps = []

        try:
            # Step 1: Save image
            r = subprocess.run(
                ["docker", "save", "-o", tar_path, image_name],
                capture_output=True, text=True, timeout=180,
            )
            if r.returncode != 0:
                return f"[FAIL] docker save failed: {r.stderr[-500:]}"
            steps.append("Image saved to tarball")

            # Step 2: Transfer to VM
            r = subprocess.run(
                ["scp", "-o", "StrictHostKeyChecking=no", tar_path, f"{VM_HOST}:/tmp/{image_name}.tar"],
                capture_output=True, text=True, timeout=300,
            )
            if r.returncode != 0:
                return f"[FAIL] SCP transfer failed: {r.stderr[-500:]}"
            steps.append("Image transferred to VM")

            # Step 3: Load + Run on VM
            remote_cmd = (
                f"sudo docker load -i /tmp/{image_name}.tar && "
                f"sudo docker stop {image_name} 2>/dev/null; "
                f"sudo docker rm {image_name} 2>/dev/null; "
                f"sudo docker run -d --name {image_name} --restart unless-stopped "
                f"-p {host_port}:{container_port} {image_name} && "
                f"echo DEPLOY_OK"
            )
            r = subprocess.run(
                ["ssh", VM_HOST, remote_cmd],
                capture_output=True, text=True, timeout=120,
            )
            if "DEPLOY_OK" not in r.stdout:
                return f"[FAIL] Remote deploy failed:\n{r.stderr[-500:]}\n{r.stdout[-500:]}"
            steps.append(f"Container running on VM port {host_port}")

            # Step 4: Health check
            import time
            time.sleep(3)
            r = subprocess.run(
                ["ssh", VM_HOST, f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{host_port}/"],
                capture_output=True, text=True, timeout=15,
            )
            http_code = r.stdout.strip().replace("'", "")
            steps.append(f"Health check: HTTP {http_code}")

            # Cleanup
            try:
                import os
                os.unlink(tar_path)
                subprocess.run(
                    ["ssh", VM_HOST, f"rm -f /tmp/{image_name}.tar"],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass

            url = f"http://4.233.64.30:{host_port}"
            return (
                f"[OK] DEPLOYED SUCCESSFULLY\n"
                f"URL: {url}\n"
                f"Container: {image_name} on port {host_port}\n"
                f"Steps: {' → '.join(steps)}"
            )

        except subprocess.TimeoutExpired:
            return "[FAIL] Deploy timed out"
        except Exception as e:
            return f"Error: {e}"


def register_deploy_tools(registry):
    """Register all deploy tools."""
    registry.register(DockerBuildTool())
    registry.register(DockerDeployTool())
