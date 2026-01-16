#!/usr/bin/env python3
"""
Chaos Monkey - Injection de pannes pour tests de résilience
==========================================================

Types de chaos:
1. network  - Latence, packet loss, coupure réseau
2. db       - Kill connexions, slow queries, lock tables
3. service  - Kill containers, restart services

Usage:
    ppz chaos network --latency=200ms --duration=60
    ppz chaos db --kill-connections --duration=30
    ppz chaos service --target=frankenphp --action=restart

Safety:
    - JAMAIS sur prod sans --force explicite
    - Toujours avec duration limitée
    - Recovery automatique après chaos
"""

import asyncio
import subprocess
import sys
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
import json

RLM_DIR = Path(__file__).parent
POPINZ_ROOT = Path("/Users/sylvain/_POPINZ/popinz-dev")

# Environment configs
ENVIRONMENTS = {
    "dev": {
        "container": "popinz-dev",
        "db_container": "popinz-dev",
        "db_name": "ppz_test",
        "ssh_host": None,  # Local
        "safe": True,
    },
    "staging": {
        "container": "staging-popinz",
        "db_container": None,  # Direct PostgreSQL
        "db_name": "ppz_staging_test",
        "ssh_host": "ovh-ab-testing",
        "safe": True,
    },
    "prod": {
        "container": "prod-green-popinz",
        "db_container": None,
        "db_name": "ppz_prod",
        "ssh_host": "ovh-ab-testing",
        "safe": False,  # Requires --force
    }
}


@dataclass
class ChaosResult:
    """Result of a chaos injection"""
    chaos_type: str  # network, db, service
    env: str
    target: str
    action: str
    started_at: str
    completed_at: str
    duration_ms: int
    passed: bool  # System recovered properly
    recovery_time_ms: int = 0
    impact: Dict = None
    errors: List[str] = None

    def __post_init__(self):
        if self.impact is None:
            self.impact = {}
        if self.errors is None:
            self.errors = []


def log(msg: str, level: str = "INFO"):
    """Log with timestamp"""
    ts = datetime.now().strftime("%H:%M:%S")
    emoji = {
        "INFO": "🐒",
        "CHAOS": "💥",
        "WARN": "⚠️",
        "ERROR": "❌",
        "OK": "✅",
        "RECOVER": "🔄"
    }.get(level, "")
    print(f"[{ts}] [CHAOS] [{level}] {emoji} {msg}", flush=True)


async def run_cmd(cmd: List[str], timeout: int = 60) -> tuple:
    """Run command with timeout"""
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(),
            timeout=timeout
        )
        return proc.returncode, stdout.decode(), stderr.decode()
    except asyncio.TimeoutError:
        proc.kill()
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


async def run_ssh_cmd(host: str, cmd: str, timeout: int = 60) -> tuple:
    """Run command via SSH"""
    return await run_cmd(["ssh", host, cmd], timeout=timeout)


class ChaosMonkey:
    """Chaos Monkey for resilience testing"""

    def __init__(self, env: str = "dev", force: bool = False):
        self.env = env
        self.env_config = ENVIRONMENTS.get(env, ENVIRONMENTS["dev"])
        self.force = force
        self.results_dir = RLM_DIR / "chaos_results"
        self.results_dir.mkdir(exist_ok=True)

        # Safety check
        if not self.env_config.get("safe", False) and not force:
            raise ValueError(f"Chaos on {env} requires --force flag")

    async def network(self, latency_ms: int = 200, packet_loss_pct: float = 0,
                     duration_seconds: int = 60, target: str = "eth0") -> ChaosResult:
        """
        Network chaos: inject latency, packet loss, or connection drops.

        Uses tc (traffic control) on Linux or pfctl on macOS.
        """
        log(f"NETWORK chaos: latency={latency_ms}ms, loss={packet_loss_pct}%, duration={duration_seconds}s", "CHAOS")
        start_time = time.time()
        started_at = datetime.now().isoformat()

        result = ChaosResult(
            chaos_type="network",
            env=self.env,
            target=target,
            action=f"latency={latency_ms}ms,loss={packet_loss_pct}%",
            started_at=started_at,
            completed_at="",
            duration_ms=0,
            passed=False
        )

        container = self.env_config.get("container")
        ssh_host = self.env_config.get("ssh_host")

        try:
            # Apply network chaos
            if ssh_host:
                # Remote: use tc inside container
                tc_cmd = f"tc qdisc add dev {target} root netem delay {latency_ms}ms"
                if packet_loss_pct > 0:
                    tc_cmd += f" loss {packet_loss_pct}%"

                cmd = f"sudo docker exec {container} {tc_cmd}"
                code, out, err = await run_ssh_cmd(ssh_host, cmd)
            else:
                # Local: tc in container
                if container:
                    tc_cmd = f"tc qdisc add dev {target} root netem delay {latency_ms}ms"
                    if packet_loss_pct > 0:
                        tc_cmd += f" loss {packet_loss_pct}%"

                    code, out, err = await run_cmd([
                        "docker", "exec", container,
                        "sh", "-c", tc_cmd
                    ])
                else:
                    # macOS local: use pfctl (limited)
                    log("macOS detected - using dnctl for network delay", "WARN")
                    result.errors.append("macOS network chaos limited - use Docker container")
                    code = 0

            if code != 0 and "File exists" not in err:
                result.errors.append(f"Failed to apply chaos: {err}")
                return result

            log(f"Chaos active for {duration_seconds}s...", "CHAOS")
            result.impact["chaos_applied"] = True

            # Let chaos run
            await asyncio.sleep(duration_seconds)

            # Remove chaos (recovery)
            log("Removing chaos, starting recovery...", "RECOVER")
            recovery_start = time.time()

            if ssh_host:
                cmd = f"sudo docker exec {container} tc qdisc del dev {target} root 2>/dev/null || true"
                await run_ssh_cmd(ssh_host, cmd)
            elif container:
                await run_cmd([
                    "docker", "exec", container,
                    "sh", "-c", f"tc qdisc del dev {target} root 2>/dev/null || true"
                ])

            # Verify recovery by hitting health endpoint
            await asyncio.sleep(2)  # Brief pause

            if ssh_host:
                health_cmd = f"curl -sf http://localhost/health || curl -sf http://localhost:80/health"
                code, _, _ = await run_ssh_cmd(ssh_host, f"sudo docker exec {container} {health_cmd}")
            elif container:
                code, _, _ = await run_cmd([
                    "docker", "exec", container,
                    "curl", "-sf", "http://localhost/health"
                ])
            else:
                code = 0

            result.recovery_time_ms = int((time.time() - recovery_start) * 1000)
            result.passed = code == 0
            result.impact["recovery_verified"] = result.passed

        except Exception as e:
            result.errors.append(str(e))
            # Always try to clean up
            try:
                if ssh_host:
                    await run_ssh_cmd(ssh_host, f"sudo docker exec {container} tc qdisc del dev {target} root 2>/dev/null || true")
                elif container:
                    await run_cmd(["docker", "exec", container, "sh", "-c", f"tc qdisc del dev {target} root 2>/dev/null || true"])
            except:
                pass

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        status = "RECOVERED" if result.passed else "FAILED"
        log(f"Network chaos {status} (recovery: {result.recovery_time_ms}ms)", "OK" if result.passed else "ERROR")

        self._save_result(result)
        return result

    async def db(self, kill_connections: bool = False, slow_queries: bool = False,
                lock_tables: List[str] = None, duration_seconds: int = 30) -> ChaosResult:
        """
        Database chaos: kill connections, inject slow queries, lock tables.
        """
        actions = []
        if kill_connections:
            actions.append("kill_connections")
        if slow_queries:
            actions.append("slow_queries")
        if lock_tables:
            actions.append(f"lock:{','.join(lock_tables)}")

        action_str = ",".join(actions) if actions else "none"
        log(f"DB chaos: {action_str}, duration={duration_seconds}s", "CHAOS")

        start_time = time.time()
        started_at = datetime.now().isoformat()

        result = ChaosResult(
            chaos_type="db",
            env=self.env,
            target="postgresql",
            action=action_str,
            started_at=started_at,
            completed_at="",
            duration_ms=0,
            passed=False
        )

        container = self.env_config.get("container")
        db_container = self.env_config.get("db_container") or container
        db_name = self.env_config.get("db_name")
        ssh_host = self.env_config.get("ssh_host")

        try:
            killed_count = 0

            # Kill existing connections
            if kill_connections:
                kill_sql = f"""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE datname = '{db_name}'
                  AND pid <> pg_backend_pid()
                  AND state = 'active';
                """

                if ssh_host:
                    cmd = f'sudo docker exec {db_container} psql -U postgres -d {db_name} -c "{kill_sql}"'
                    code, out, err = await run_ssh_cmd(ssh_host, cmd)
                elif db_container:
                    code, out, err = await run_cmd([
                        "docker", "exec", db_container,
                        "psql", "-U", "postgres", "-d", db_name, "-c", kill_sql
                    ])
                else:
                    code, out, err = await run_cmd([
                        "psql", "-U", "postgres", "-d", db_name, "-c", kill_sql
                    ])

                # Count killed connections
                if "t" in out:
                    killed_count = out.count("t")
                result.impact["connections_killed"] = killed_count
                log(f"Killed {killed_count} connections", "CHAOS")

            # Slow queries (add artificial delay)
            if slow_queries:
                # Create a slow function
                slow_func_sql = """
                CREATE OR REPLACE FUNCTION chaos_slow() RETURNS void AS $$
                BEGIN
                    PERFORM pg_sleep(0.5);
                END;
                $$ LANGUAGE plpgsql;
                """

                if ssh_host:
                    cmd = f'sudo docker exec {db_container} psql -U postgres -d {db_name} -c "{slow_func_sql}"'
                    await run_ssh_cmd(ssh_host, cmd)
                elif db_container:
                    await run_cmd([
                        "docker", "exec", db_container,
                        "psql", "-U", "postgres", "-d", db_name, "-c", slow_func_sql
                    ])

                result.impact["slow_function_created"] = True
                log("Slow function installed", "CHAOS")

            # Lock tables
            if lock_tables:
                for table in lock_tables:
                    lock_sql = f"BEGIN; LOCK TABLE {table} IN ACCESS EXCLUSIVE MODE;"
                    # This would block other queries

                    if ssh_host:
                        # Start lock in background
                        bg_cmd = f'sudo docker exec -d {db_container} psql -U postgres -d {db_name} -c "{lock_sql}; SELECT pg_sleep({duration_seconds}); COMMIT;"'
                        await run_ssh_cmd(ssh_host, bg_cmd)
                    elif db_container:
                        # Run in background
                        await run_cmd([
                            "docker", "exec", "-d", db_container,
                            "psql", "-U", "postgres", "-d", db_name,
                            "-c", f"{lock_sql}; SELECT pg_sleep({duration_seconds}); COMMIT;"
                        ])

                result.impact["tables_locked"] = lock_tables
                log(f"Tables locked: {lock_tables}", "CHAOS")

            # Wait for chaos duration
            log(f"Chaos active for {duration_seconds}s...", "CHAOS")
            await asyncio.sleep(duration_seconds)

            # Recovery: drop slow function
            if slow_queries:
                drop_sql = "DROP FUNCTION IF EXISTS chaos_slow();"
                if ssh_host:
                    await run_ssh_cmd(ssh_host, f'sudo docker exec {db_container} psql -U postgres -d {db_name} -c "{drop_sql}"')
                elif db_container:
                    await run_cmd([
                        "docker", "exec", db_container,
                        "psql", "-U", "postgres", "-d", db_name, "-c", drop_sql
                    ])

            # Verify recovery
            recovery_start = time.time()

            verify_sql = "SELECT 1;"
            if ssh_host:
                code, _, _ = await run_ssh_cmd(ssh_host, f'sudo docker exec {db_container} psql -U postgres -d {db_name} -c "{verify_sql}"')
            elif db_container:
                code, _, _ = await run_cmd([
                    "docker", "exec", db_container,
                    "psql", "-U", "postgres", "-d", db_name, "-c", verify_sql
                ])
            else:
                code, _, _ = await run_cmd(["psql", "-U", "postgres", "-d", db_name, "-c", verify_sql])

            result.recovery_time_ms = int((time.time() - recovery_start) * 1000)
            result.passed = code == 0

        except Exception as e:
            result.errors.append(str(e))

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        status = "RECOVERED" if result.passed else "FAILED"
        log(f"DB chaos {status} (recovery: {result.recovery_time_ms}ms)", "OK" if result.passed else "ERROR")

        self._save_result(result)
        return result

    async def service(self, target: str = "frankenphp", action: str = "restart",
                     duration_seconds: int = 30) -> ChaosResult:
        """
        Service chaos: restart, stop, or kill services/containers.

        Targets:
        - frankenphp: PHP service
        - grpc: Rust gRPC service
        - redis: Redis cache
        - gateway: Rust gateway
        """
        log(f"SERVICE chaos: target={target}, action={action}", "CHAOS")
        start_time = time.time()
        started_at = datetime.now().isoformat()

        result = ChaosResult(
            chaos_type="service",
            env=self.env,
            target=target,
            action=action,
            started_at=started_at,
            completed_at="",
            duration_ms=0,
            passed=False
        )

        container = self.env_config.get("container")
        ssh_host = self.env_config.get("ssh_host")

        try:
            # Map targets to supervisor service names
            service_map = {
                "frankenphp": "frankenphp",
                "grpc": "grpc",
                "redis": "redis",
                "gateway": "gateway",
                "postgresql": "postgresql",
            }

            supervisor_service = service_map.get(target, target)

            if action == "restart":
                # Restart service via supervisor
                if ssh_host:
                    cmd = f"sudo docker exec {container} supervisorctl restart {supervisor_service}"
                    code, out, err = await run_ssh_cmd(ssh_host, cmd)
                elif container:
                    code, out, err = await run_cmd([
                        "docker", "exec", container,
                        "supervisorctl", "restart", supervisor_service
                    ])
                else:
                    code, out, err = await run_cmd(["supervisorctl", "restart", supervisor_service])

                result.impact["action"] = "restart"
                result.impact["output"] = out.strip()

            elif action == "stop":
                # Stop service
                if ssh_host:
                    cmd = f"sudo docker exec {container} supervisorctl stop {supervisor_service}"
                    code, _, _ = await run_ssh_cmd(ssh_host, cmd)
                elif container:
                    code, _, _ = await run_cmd([
                        "docker", "exec", container,
                        "supervisorctl", "stop", supervisor_service
                    ])

                result.impact["stopped"] = True
                log(f"Service {target} stopped, waiting {duration_seconds}s...", "CHAOS")

                # Wait for chaos duration
                await asyncio.sleep(duration_seconds)

                # Restart service
                log("Restarting service...", "RECOVER")
                if ssh_host:
                    await run_ssh_cmd(ssh_host, f"sudo docker exec {container} supervisorctl start {supervisor_service}")
                elif container:
                    await run_cmd([
                        "docker", "exec", container,
                        "supervisorctl", "start", supervisor_service
                    ])

            elif action == "kill":
                # Kill the process (more aggressive)
                if ssh_host:
                    # Find and kill process
                    kill_cmd = f"sudo docker exec {container} pkill -9 -f {target}"
                    await run_ssh_cmd(ssh_host, kill_cmd)
                elif container:
                    await run_cmd([
                        "docker", "exec", container,
                        "pkill", "-9", "-f", target
                    ])

                result.impact["killed"] = True
                log(f"Process {target} killed, supervisor should restart it...", "CHAOS")

            # Verify recovery
            await asyncio.sleep(3)  # Give time for restart
            recovery_start = time.time()

            if ssh_host:
                code, status_out, _ = await run_ssh_cmd(ssh_host, f"sudo docker exec {container} supervisorctl status {supervisor_service}")
            elif container:
                code, status_out, _ = await run_cmd([
                    "docker", "exec", container,
                    "supervisorctl", "status", supervisor_service
                ])
            else:
                code, status_out, _ = 0, "RUNNING", ""

            result.passed = "RUNNING" in status_out
            result.recovery_time_ms = int((time.time() - recovery_start) * 1000)
            result.impact["final_status"] = status_out.strip()

        except Exception as e:
            result.errors.append(str(e))

        result.duration_ms = int((time.time() - start_time) * 1000)
        result.completed_at = datetime.now().isoformat()

        status = "RECOVERED" if result.passed else "FAILED"
        log(f"Service chaos {status} (recovery: {result.recovery_time_ms}ms)", "OK" if result.passed else "ERROR")

        self._save_result(result)
        return result

    async def random(self, duration_seconds: int = 60) -> List[ChaosResult]:
        """
        Random chaos: randomly apply different chaos types.
        Good for discovering unknown failure modes.
        """
        log(f"RANDOM chaos: duration={duration_seconds}s", "CHAOS")
        results = []

        chaos_options = [
            ("network", {"latency_ms": random.randint(100, 500), "duration_seconds": 15}),
            ("db", {"kill_connections": True, "duration_seconds": 10}),
            ("service", {"target": random.choice(["frankenphp", "redis"]), "action": "restart"}),
        ]

        start_time = time.time()
        while time.time() - start_time < duration_seconds:
            chaos_type, kwargs = random.choice(chaos_options)
            log(f"Random chaos: {chaos_type} with {kwargs}", "CHAOS")

            if chaos_type == "network":
                result = await self.network(**kwargs)
            elif chaos_type == "db":
                result = await self.db(**kwargs)
            elif chaos_type == "service":
                result = await self.service(**kwargs)

            results.append(result)

            # Brief pause between chaos events
            await asyncio.sleep(5)

        return results

    def _save_result(self, result: ChaosResult, task_id: str = None):
        """Save result to file and optionally to task store"""
        filename = f"{result.chaos_type}_{self.env}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.results_dir / filename
        with open(filepath, 'w') as f:
            json.dump(asdict(result), f, indent=2)

        # Save to task store
        if task_id:
            try:
                from task_store import TaskStore
                store = TaskStore()
                store.record_chaos_result(
                    task_id=task_id,
                    chaos_type=result.chaos_type,
                    target=result.target,
                    duration_ms=result.duration_ms,
                    passed=result.passed,
                    recovery_time_ms=result.recovery_time_ms,
                    impact=result.impact
                )
            except ImportError:
                pass


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Chaos Monkey - Resilience testing")
    parser.add_argument("chaos_type", choices=["network", "db", "service", "random"],
                       help="Type of chaos to inject")
    parser.add_argument("--env", default="dev", choices=["dev", "staging", "prod"])
    parser.add_argument("--force", action="store_true", help="Force chaos on prod")

    # Network options
    parser.add_argument("--latency", type=int, default=200, help="Latency in ms")
    parser.add_argument("--packet-loss", type=float, default=0, help="Packet loss %")

    # DB options
    parser.add_argument("--kill-connections", action="store_true")
    parser.add_argument("--slow-queries", action="store_true")
    parser.add_argument("--lock-tables", type=str, nargs="*")

    # Service options
    parser.add_argument("--target", type=str, default="frankenphp")
    parser.add_argument("--action", choices=["restart", "stop", "kill"], default="restart")

    # Common
    parser.add_argument("--duration", type=int, default=30, help="Duration in seconds")
    parser.add_argument("--task", type=str, help="Task ID")

    args = parser.parse_args()

    try:
        monkey = ChaosMonkey(env=args.env, force=args.force)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.chaos_type == "network":
        result = await monkey.network(
            latency_ms=args.latency,
            packet_loss_pct=args.packet_loss,
            duration_seconds=args.duration
        )
    elif args.chaos_type == "db":
        result = await monkey.db(
            kill_connections=args.kill_connections,
            slow_queries=args.slow_queries,
            lock_tables=args.lock_tables,
            duration_seconds=args.duration
        )
    elif args.chaos_type == "service":
        result = await monkey.service(
            target=args.target,
            action=args.action,
            duration_seconds=args.duration
        )
    elif args.chaos_type == "random":
        results = await monkey.random(duration_seconds=args.duration)
        passed = all(r.passed for r in results)
        sys.exit(0 if passed else 1)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
