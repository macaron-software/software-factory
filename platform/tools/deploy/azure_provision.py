"""
Azure VM Provisioner for Deploy Targets.

Uses Azure REST API (no SDK, only httpx) to:
  1. Ensure resource group exists
  2. Create public IP + VNet/subnet + NIC
  3. Create Ubuntu 22.04 VM with auto-generated SSH key pair
  4. Wait for VM to be ready
  5. Bootstrap Docker via SSH
  6. Return VM IP + private key for the deploy target config

Auth: service principal (client_id + client_secret + tenant_id)
      OR a bearer token directly.

VM defaults: Standard_B2s, francecentral, Ubuntu 22.04 LTS
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator

import httpx

logger = logging.getLogger(__name__)

_AZ_API = "https://management.azure.com"
_AZ_LOGIN = "https://login.microsoftonline.com"
_VM_SIZE = "Standard_B2s"
_LOCATION = "francecentral"
_RG_DEFAULT = "macaron-sandbox-rg"
_VM_NAME = "macaron-sandbox"
_OS_DISK_SIZE = 32  # GB


# ─── Result types ─────────────────────────────────────────────────────────────

@dataclass
class ProvisionStep:
    step: str
    message: str
    done: bool = False
    error: bool = False


@dataclass
class ProvisionResult:
    ok: bool
    host: str = ""
    user: str = "azureuser"
    private_key: str = ""
    message: str = ""
    steps: list[ProvisionStep] = field(default_factory=list)


# ─── Azure REST helpers ────────────────────────────────────────────────────────

async def _get_token(client: httpx.AsyncClient, tenant_id: str, client_id: str, client_secret: str) -> str:
    """Obtain Azure bearer token via service principal."""
    resp = await client.post(
        f"{_AZ_LOGIN}/{tenant_id}/oauth2/token",
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": _AZ_API,
        },
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def _put(client: httpx.AsyncClient, token: str, url: str, body: dict, timeout: int = 120) -> dict:
    resp = await client.put(url, headers=_headers(token), json=body, timeout=timeout)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"PUT {url} → {resp.status_code}: {resp.text[:500]}")
    return resp.json()


async def _get(client: httpx.AsyncClient, token: str, url: str) -> dict:
    resp = await client.get(url, headers=_headers(token), timeout=30)
    resp.raise_for_status()
    return resp.json()


async def _wait_for_operation(client: httpx.AsyncClient, token: str, op_url: str, timeout: int = 300) -> None:
    """Poll Azure async operation until succeeded or failed."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = await client.get(op_url, headers=_headers(token), timeout=30)
        data = resp.json()
        status = data.get("status", "Running")
        if status == "Succeeded":
            return
        if status in ("Failed", "Canceled"):
            err = data.get("error", {}).get("message", "Unknown error")
            raise RuntimeError(f"Azure operation {status}: {err}")
        await asyncio.sleep(5)
    raise TimeoutError(f"Azure operation did not complete within {timeout}s")


# ─── SSH key generation ────────────────────────────────────────────────────────

def _generate_ssh_keypair() -> tuple[str, str]:
    """Generate RSA key pair. Returns (private_key_pem, public_key_openssh)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, "key")
        subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "4096", "-N", "", "-f", key_path, "-C", "macaron-sandbox"],
            check=True, capture_output=True,
        )
        with open(key_path) as f:
            private_key = f.read()
        with open(key_path + ".pub") as f:
            public_key = f.read().strip()
    return private_key, public_key


# ─── SSH bootstrap ─────────────────────────────────────────────────────────────

def _ssh_bootstrap(host: str, user: str, private_key_pem: str) -> tuple[bool, str]:
    """Install Docker on remote host via SSH. Returns (ok, message)."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as kf:
        kf.write(private_key_pem)
        key_path = kf.name
    os.chmod(key_path, 0o600)

    docker_install_script = """
set -e
# Wait for cloud-init to finish
timeout 120 bash -c 'until [ -f /var/lib/cloud/instance/boot-finished ]; do sleep 3; done' 2>/dev/null || true
# Install Docker
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y -qq docker-ce docker-ce-cli containerd.io
systemctl enable --now docker
usermod -aG docker $USER
echo "Docker installed: $(docker --version)"
"""
    try:
        cmd = [
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10",
            "-o", "ServerAliveInterval=10", "-i", key_path,
            f"{user}@{host}", "sudo bash -s",
        ]
        result = subprocess.run(
            cmd, input=docker_install_script, capture_output=True, text=True, timeout=300,
        )
        return result.returncode == 0, result.stdout[-500:] + result.stderr[-300:]
    finally:
        os.unlink(key_path)


# ─── Main provisioner ─────────────────────────────────────────────────────────

async def provision_azure_vm(
    subscription_id: str,
    tenant_id: str,
    client_id: str,
    client_secret: str,
    resource_group: str = _RG_DEFAULT,
    location: str = _LOCATION,
    vm_name: str = _VM_NAME,
    progress_cb=None,
) -> ProvisionResult:
    """
    Full Azure VM provisioning flow.

    progress_cb: async callable(ProvisionStep) for streaming progress
    """
    steps = []

    async def step(name: str, msg: str, done: bool = False, error: bool = False) -> ProvisionStep:
        s = ProvisionStep(step=name, message=msg, done=done, error=error)
        steps.append(s)
        if progress_cb:
            await progress_cb(s)
        logger.info("[%s] %s", name, msg)
        return s

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            # 1. Auth
            await step("auth", "Obtaining Azure token…")
            token = await _get_token(client, tenant_id, client_id, client_secret)
            await step("auth", "Token OK", done=True)

            sub_url = f"{_AZ_API}/subscriptions/{subscription_id}"

            # 2. Resource Group
            await step("rg", f"Creating resource group '{resource_group}'…")
            rg_url = f"{sub_url}/resourceGroups/{resource_group}?api-version=2021-04-01"
            await _put(client, token, rg_url, {"location": location})
            await step("rg", f"Resource group '{resource_group}' ready", done=True)

            # 3. Public IP
            await step("ip", "Creating public IP…")
            ip_name = f"{vm_name}-ip"
            ip_url = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/publicIPAddresses/{ip_name}?api-version=2021-02-01"
            ip_body = {
                "location": location,
                "properties": {"publicIPAllocationMethod": "Static", "publicIPAddressVersion": "IPv4"},
                "sku": {"name": "Standard"},
            }
            resp = await _put(client, token, ip_url, ip_body)
            op_url = resp.get("properties", {}).get("provisioningState")
            await step("ip", "Waiting for public IP…")
            # Poll until IP is assigned
            deadline = time.monotonic() + 120
            public_ip = ""
            while time.monotonic() < deadline and not public_ip:
                ip_data = await _get(client, token, ip_url)
                public_ip = ip_data.get("properties", {}).get("ipAddress", "")
                if not public_ip:
                    await asyncio.sleep(5)
            await step("ip", f"Public IP: {public_ip or 'pending'}", done=True)

            # 4. VNet + Subnet
            await step("vnet", "Creating VNet/subnet…")
            vnet_name = f"{vm_name}-vnet"
            vnet_url = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}?api-version=2021-02-01"
            vnet_body = {
                "location": location,
                "properties": {
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                    "subnets": [{"name": "default", "properties": {"addressPrefix": "10.0.0.0/24"}}],
                },
            }
            vnet_resp = await _put(client, token, vnet_url, vnet_body, timeout=180)
            # Get subnet ID
            subnet_id = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/virtualNetworks/{vnet_name}/subnets/default"
            await step("vnet", "VNet ready", done=True)

            # 5. NSG (allow SSH + ports 9100-9199)
            await step("nsg", "Creating NSG (SSH + deploy ports)…")
            nsg_name = f"{vm_name}-nsg"
            nsg_url = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkSecurityGroups/{nsg_name}?api-version=2021-02-01"
            nsg_body = {
                "location": location,
                "properties": {
                    "securityRules": [
                        {
                            "name": "AllowSSH",
                            "properties": {
                                "priority": 1000, "protocol": "Tcp", "access": "Allow",
                                "direction": "Inbound", "sourceAddressPrefix": "*",
                                "sourcePortRange": "*", "destinationAddressPrefix": "*",
                                "destinationPortRange": "22",
                            },
                        },
                        {
                            "name": "AllowAppPorts",
                            "properties": {
                                "priority": 1100, "protocol": "Tcp", "access": "Allow",
                                "direction": "Inbound", "sourceAddressPrefix": "*",
                                "sourcePortRange": "*", "destinationAddressPrefix": "*",
                                "destinationPortRange": "9100-9199",
                            },
                        },
                    ]
                },
            }
            await _put(client, token, nsg_url, nsg_body, timeout=120)
            nsg_id = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkSecurityGroups/{nsg_name}"
            await step("nsg", "NSG ready", done=True)

            # 6. NIC
            await step("nic", "Creating network interface…")
            nic_name = f"{vm_name}-nic"
            ip_id = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/publicIPAddresses/{ip_name}"
            nic_url = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkInterfaces/{nic_name}?api-version=2021-02-01"
            nic_body = {
                "location": location,
                "properties": {
                    "networkSecurityGroup": {"id": nsg_id},
                    "ipConfigurations": [{
                        "name": "ipconfig1",
                        "properties": {
                            "privateIPAllocationMethod": "Dynamic",
                            "subnet": {"id": subnet_id},
                            "publicIPAddress": {"id": ip_id},
                        },
                    }],
                },
            }
            nic_resp = await _put(client, token, nic_url, nic_body, timeout=120)
            nic_id = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Network/networkInterfaces/{nic_name}"
            await step("nic", "NIC ready", done=True)

            # 7. Generate SSH key pair
            await step("ssh_key", "Generating SSH key pair…")
            private_key, public_key = _generate_ssh_keypair()
            await step("ssh_key", "SSH key pair generated", done=True)

            # 8. Create VM
            await step("vm", f"Creating VM '{vm_name}' ({_VM_SIZE})…")
            vm_url = f"{sub_url}/resourceGroups/{resource_group}/providers/Microsoft.Compute/virtualMachines/{vm_name}?api-version=2021-07-01"
            vm_body = {
                "location": location,
                "properties": {
                    "hardwareProfile": {"vmSize": _VM_SIZE},
                    "storageProfile": {
                        "imageReference": {
                            "publisher": "Canonical",
                            "offer": "0001-com-ubuntu-server-jammy",
                            "sku": "22_04-lts-gen2",
                            "version": "latest",
                        },
                        "osDisk": {
                            "createOption": "FromImage",
                            "diskSizeGB": _OS_DISK_SIZE,
                            "managedDisk": {"storageAccountType": "StandardSSD_LRS"},
                        },
                    },
                    "osProfile": {
                        "computerName": vm_name,
                        "adminUsername": "azureuser",
                        "linuxConfiguration": {
                            "disablePasswordAuthentication": True,
                            "ssh": {
                                "publicKeys": [{
                                    "path": "/home/azureuser/.ssh/authorized_keys",
                                    "keyData": public_key,
                                }]
                            },
                        },
                    },
                    "networkProfile": {
                        "networkInterfaces": [{"id": nic_id}]
                    },
                },
            }
            vm_resp = await _put(client, token, vm_url, vm_body, timeout=300)
            # Wait for VM
            await step("vm", "Waiting for VM to be running…")
            deadline = time.monotonic() + 300
            while time.monotonic() < deadline:
                vm_data = await _get(client, token, vm_url)
                pstate = vm_data.get("properties", {}).get("provisioningState", "")
                if pstate == "Succeeded":
                    break
                if pstate == "Failed":
                    raise RuntimeError("VM provisioning failed")
                await asyncio.sleep(8)

            # Get final public IP
            if not public_ip:
                ip_data = await _get(client, token, ip_url)
                public_ip = ip_data.get("properties", {}).get("ipAddress", "")
            await step("vm", f"VM running at {public_ip}", done=True)

            # 9. SSH Bootstrap (Docker install)
            await step("docker", f"Installing Docker on {public_ip}…")
            await asyncio.sleep(15)  # Wait for SSH daemon
            ok, msg = await asyncio.get_event_loop().run_in_executor(
                None, _ssh_bootstrap, public_ip, "azureuser", private_key
            )
            if not ok:
                await step("docker", f"Docker install warning: {msg[:200]}", done=True)
            else:
                await step("docker", "Docker installed", done=True)

            await step("done", f"VM ready: {public_ip}", done=True)
            return ProvisionResult(
                ok=True,
                host=public_ip,
                user="azureuser",
                private_key=private_key,
                message=f"VM {vm_name} provisioned at {public_ip}",
                steps=steps,
            )

    except Exception as e:
        err_msg = str(e)
        logger.error("Azure provisioning failed: %s", err_msg)
        await step("error", err_msg, error=True)
        return ProvisionResult(ok=False, message=err_msg, steps=steps)
