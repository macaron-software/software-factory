"""
SSH + Docker Deploy Driver.

Deploys to any remote host via SSH + Docker.
Covers: OVH VPS, DigitalOcean Droplets, Hetzner, Azure VMs, bare metal.

Config keys:
  host         Remote hostname or IP
  port         SSH port (default: 22)
  user         SSH username (default: root)
  key_path     Path to private SSH key (~/.ssh/id_rsa if omitted)
  remote_dir   Remote working directory (default: /opt/macaron-apps)
  container_port  Internal container port to expose (default: 3000)
"""
# Ref: feat-tool-builder

from __future__ import annotations

import logging
import os
import subprocess
import tarfile
import tempfile

from .base import DeployResult, DeployTarget

logger = logging.getLogger(__name__)


def _ssh_cmd(host: str, user: str, port: int, key_path: str | None, command: str) -> tuple[int, str, str]:
    """Run command on remote host via SSH. Returns (returncode, stdout, stderr)."""
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes",
           "-p", str(port), f"{user}@{host}"]
    if key_path:
        cmd += ["-i", os.path.expanduser(key_path)]
    cmd.append(command)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout, r.stderr


def _scp(local_path: str, host: str, user: str, port: int, key_path: str | None, remote_path: str) -> tuple[int, str]:
    """Copy file to remote host via scp."""
    cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-P", str(port)]
    if key_path:
        cmd += ["-i", os.path.expanduser(key_path)]
    cmd += [local_path, f"{user}@{host}:{remote_path}"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return r.returncode, r.stderr


class SshDockerTarget(DeployTarget):
    driver = "ssh_docker"
    label = "SSH + Docker (VPS / VM)"
    config_schema = [
        {"key": "host", "label": "Host / IP", "type": "text", "required": True},
        {"key": "port", "label": "SSH Port", "type": "number", "default": 22},
        {"key": "user", "label": "SSH User", "type": "text", "default": "root"},
        {"key": "key_path", "label": "Private Key Path", "type": "text", "placeholder": "~/.ssh/id_rsa"},
        {"key": "remote_dir", "label": "Remote Directory", "type": "text", "default": "/opt/macaron-apps"},
        {"key": "container_port", "label": "Container Port", "type": "number", "default": 3000},
        {"key": "host_port", "label": "Host Port (0 = auto)", "type": "number", "default": 0},
    ]

    @property
    def _host(self) -> str:
        return self.config.get("host", "")

    @property
    def _port(self) -> int:
        return int(self.config.get("port", 22))

    @property
    def _user(self) -> str:
        return self.config.get("user", "root")

    @property
    def _key(self) -> str | None:
        return self.config.get("key_path") or None

    @property
    def _remote_dir(self) -> str:
        return self.config.get("remote_dir", "/opt/macaron-apps")

    def _run(self, cmd: str) -> tuple[int, str, str]:
        return _ssh_cmd(self._host, self._user, self._port, self._key, cmd)

    async def deploy(self, workspace: str, mission_id: str, env: str = "staging", **kwargs) -> DeployResult:
        if not self._host:
            return DeployResult(ok=False, message="SSH host not configured")
        if not os.path.isdir(workspace):
            return DeployResult(ok=False, message=f"Workspace not found: {workspace}")

        container_name = f"macaron-app-{mission_id[:12]}"
        app_dir = f"{self._remote_dir}/{mission_id[:12]}"
        container_port = int(self.config.get("container_port", 3000))
        host_port = int(self.config.get("host_port", 0)) or container_port + 10000

        # Create remote directory
        rc, out, err = self._run(f"mkdir -p {app_dir}")
        if rc != 0:
            return DeployResult(ok=False, message=f"Cannot create remote dir: {err}")

        # Pack workspace as tar and copy
        with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            with tarfile.open(tmp_path, "w:gz") as tar:
                tar.add(workspace, arcname=".")
            rc, err = _scp(tmp_path, self._host, self._user, self._port, self._key, f"{app_dir}/workspace.tar.gz")
            if rc != 0:
                return DeployResult(ok=False, message=f"SCP failed: {err}")
        finally:
            os.unlink(tmp_path)

        # Extract + build + run
        script = f"""
set -e
cd {app_dir}
tar -xzf workspace.tar.gz
docker rm -f {container_name} 2>/dev/null || true
docker build -t {container_name} .
docker run -d --name {container_name} \\
    -p {host_port}:{container_port} \\
    --memory 256m --restart unless-stopped \\
    {container_name}
"""
        rc, out, err = self._run(script.replace("\n", " && ").replace("set -e && ", "set -e; "))
        if rc != 0:
            return DeployResult(ok=False, message=f"Remote deploy failed:\n{err[-1000:]}")

        url = f"http://{self._host}:{host_port}"
        return DeployResult(ok=True, url=url, container=container_name, port=host_port,
                            message=f"Deployed to {self._host}")

    async def stop(self, mission_id: str) -> DeployResult:
        container_name = f"macaron-app-{mission_id[:12]}"
        rc, out, err = self._run(f"docker rm -f {container_name}")
        return DeployResult(ok=rc == 0, message=out.strip() or err.strip())

    async def status(self, mission_id: str) -> DeployResult:
        container_name = f"macaron-app-{mission_id[:12]}"
        rc, out, err = self._run(
            f"docker inspect --format '{{{{.State.Status}}}}' {container_name} 2>/dev/null || echo 'not found'"
        )
        state = out.strip()
        return DeployResult(ok=state == "running", container=container_name, message=state)

    async def logs(self, mission_id: str, lines: int = 50) -> str:
        container_name = f"macaron-app-{mission_id[:12]}"
        rc, out, err = self._run(f"docker logs --tail {lines} {container_name}")
        return out + err

    async def test_connection(self) -> tuple[bool, str]:
        if not self._host:
            return False, "Host not configured"
        rc, out, err = self._run("docker info > /dev/null && echo 'ok'")
        if rc == 0:
            return True, f"SSH OK, Docker running on {self._host}"
        # Try SSH without docker
        rc2, out2, err2 = self._run("echo 'ssh-ok'")
        if rc2 == 0:
            return False, f"SSH OK but Docker not available: {err}"
        return False, f"SSH failed to {self._host}:{self._port}: {err2}"
