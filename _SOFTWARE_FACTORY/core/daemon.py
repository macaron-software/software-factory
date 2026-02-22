#!/usr/bin/env python3
"""
Daemon utilities for Macaron Agent Platform
=====================================
Provides daemonization for Wiggum TDD and Deploy pools.

Features:
- Double-fork for proper daemonization
- PID file management
- Signal handlers for graceful shutdown
- Log file rotation
- Status checking

Usage:
    from core.daemon import Daemon

    class MyWorker(Daemon):
        def run(self):
            while self.running:
                # do work
                pass

    worker = MyWorker(name="wiggum-tdd", project="ppz")
    worker.start()  # Daemonize and run
    worker.stop()   # Send SIGTERM
    worker.restart()
    worker.status()
"""

import os
from typing import Set

# Global registry of child process groups to kill on shutdown
# Workers register their PIDs here, daemon kills them on SIGTERM
_child_pgroups: Set[int] = set()


def register_child_pgroup(pid: int):
    """Register a child process group PID for cleanup on shutdown."""
    _child_pgroups.add(pid)


def unregister_child_pgroup(pid: int):
    """Unregister a child process group PID after it exits."""
    _child_pgroups.discard(pid)


def kill_all_child_pgroups():
    """Kill all registered child process groups."""
    import signal
    for pid in list(_child_pgroups):
        try:
            os.killpg(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass
    _child_pgroups.clear()

import sys
import time
import signal
import atexit
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable
import logging
from logging.handlers import RotatingFileHandler


class Daemon:
    """
    Base daemon class with proper Unix daemonization.

    Subclass and override run() to implement your daemon logic.
    """

    # Class-level paths
    BASE_DIR = Path(__file__).parent.parent
    PID_DIR = Path("/tmp/factory")
    LOG_DIR = BASE_DIR / "data" / "logs"

    def __init__(
        self,
        name: str,
        project: str = None,
        log_level: int = logging.INFO,
    ):
        """
        Initialize daemon.

        Args:
            name: Daemon name (e.g., "wiggum-tdd", "wiggum-deploy")
            project: Project name for isolation
            log_level: Logging level
        """
        self.name = name
        self.project = project or "default"
        self.daemon_name = f"{name}-{self.project}"

        # Ensure directories exist
        self.PID_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)

        # Paths
        self.pidfile = self.PID_DIR / f"{self.daemon_name}.pid"
        self.logfile = self.LOG_DIR / f"{self.daemon_name}.log"

        # State
        self.running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Setup logging
        self.logger = self._setup_logging(log_level)

    def _setup_logging(self, level: int) -> logging.Logger:
        """Setup rotating file logger"""
        logger = logging.getLogger(self.daemon_name)
        logger.setLevel(level)

        # Remove existing handlers
        logger.handlers = []

        # Rotating file handler (10MB, 5 backups)
        handler = RotatingFileHandler(
            self.logfile,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    def log(self, msg: str, level: str = "INFO"):
        """Log message"""
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] [{self.daemon_name}] [{level}] {msg}", flush=True)

        if level == "ERROR":
            self.logger.error(msg)
        elif level == "WARN":
            self.logger.warning(msg)
        elif level == "DEBUG":
            self.logger.debug(msg)
        else:
            self.logger.info(msg)

    def daemonize(self):
        """
        Double-fork to daemonize the process.

        This is the standard Unix daemonization pattern:
        1. Fork #1: Parent exits, child continues
        2. setsid(): Create new session, become session leader
        3. Fork #2: Exit session leader, grandchild can't acquire terminal
        4. Redirect stdin/stdout/stderr to /dev/null
        5. Write PID file
        """
        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Parent exits
                sys.exit(0)
        except OSError as e:
            self.logger.error(f"Fork #1 failed: {e}")
            sys.exit(1)

        # Decouple from parent environment
        os.chdir("/")
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                # First child exits
                sys.exit(0)
        except OSError as e:
            self.logger.error(f"Fork #2 failed: {e}")
            sys.exit(1)

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect to /dev/null
        with open("/dev/null", "r") as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())
        with open(str(self.logfile), "a+") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())

        # Write PID file
        atexit.register(self._cleanup)
        pid = str(os.getpid())
        self.pidfile.write_text(pid + "\n")

        self.logger.info(f"Daemon started with PID {pid}")

    def _cleanup(self):
        """Cleanup PID file on exit"""
        if self.pidfile.exists():
            self.pidfile.unlink()

    def _get_pid(self) -> Optional[int]:
        """Get PID from pidfile"""
        try:
            if self.pidfile.exists():
                return int(self.pidfile.read_text().strip())
        except (ValueError, FileNotFoundError):
            pass
        return None

    def _is_running(self, pid: int = None) -> bool:
        """Check if process is running"""
        pid = pid or self._get_pid()
        if pid is None:
            return False
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def start(self, foreground: bool = False):
        """
        Start the daemon.

        Args:
            foreground: Run in foreground (don't daemonize)
        """
        # Check if already running
        pid = self._get_pid()
        if pid and self._is_running(pid):
            print(f"{self.daemon_name} is already running (PID: {pid})")
            sys.exit(1)

        # Clean up stale PID file
        if self.pidfile.exists():
            self.pidfile.unlink()

        if foreground:
            # Run in foreground (for debugging)
            print(f"Starting {self.daemon_name} in foreground...")
            self.pidfile.write_text(str(os.getpid()) + "\n")
            atexit.register(self._cleanup)
            self._setup_signals()
            self._run_loop()
        else:
            # Daemonize
            print(f"Starting {self.daemon_name} daemon...")
            self.daemonize()
            self._setup_signals()
            self._run_loop()

    def stop(self, timeout: int = 30):
        """
        Stop the daemon gracefully.

        Args:
            timeout: Seconds to wait for graceful shutdown
        """
        pid = self._get_pid()
        if not pid:
            print(f"{self.daemon_name} is not running (no PID file)")
            return

        if not self._is_running(pid):
            print(f"{self.daemon_name} is not running (stale PID file)")
            self.pidfile.unlink()
            return

        print(f"Stopping {self.daemon_name} (PID: {pid})...")

        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            print(f"Error sending SIGTERM: {e}")
            return

        # Wait for process to exit
        for _ in range(timeout):
            if not self._is_running(pid):
                print(f"{self.daemon_name} stopped")
                return
            time.sleep(1)

        # Force kill if still running
        print(f"Forcing kill of {self.daemon_name}...")
        try:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)
            if self.pidfile.exists():
                self.pidfile.unlink()
            print(f"{self.daemon_name} killed")
        except OSError as e:
            print(f"Error killing process: {e}")

    def restart(self):
        """Restart the daemon"""
        self.stop()
        time.sleep(2)
        self.start()

    def status(self) -> dict:
        """
        Get daemon status.

        Returns:
            Status dict with running state, PID, uptime, etc.
        """
        pid = self._get_pid()
        running = pid and self._is_running(pid)

        status = {
            "name": self.daemon_name,
            "project": self.project,
            "running": running,
            "pid": pid if running else None,
            "pidfile": str(self.pidfile),
            "logfile": str(self.logfile),
        }

        if running and pid:
            # Get process info
            try:
                import subprocess

                result = subprocess.run(
                    ["ps", "-p", str(pid), "-o", "etime="],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    status["uptime"] = result.stdout.strip()
            except Exception:
                pass

        return status

    def _setup_signals(self):
        """Setup signal handlers for graceful shutdown"""

        def handle_signal(signum, frame):
            self.logger.info(f"Received signal {signum}, shutting down...")
            self.running = False
            # Kill all registered child process groups (opencode workers)
            self.logger.info(f"Killing {len(_child_pgroups)} child process groups...")
            kill_all_child_pgroups()
            if self._loop:
                self._loop.stop()

        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

    def _run_loop(self):
        """Run the async event loop"""
        self.running = True
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self.run())
        except Exception as e:
            self.logger.error(f"Daemon error: {e}")
        finally:
            self._loop.close()
            self.running = False
            self.logger.info("Daemon stopped")

    async def run(self):
        """
        Main daemon loop - override in subclass.

        This method should contain your daemon logic.
        Check self.running periodically and exit when False.
        """
        raise NotImplementedError("Subclass must implement run()")


# ============================================================================
# DAEMON MANAGER
# ============================================================================

class DaemonManager:
    """
    Manages multiple daemons for the Macaron Agent Platform.

    Provides unified interface to start/stop/status all daemons.
    """

    def __init__(self, project: str = None):
        self.project = project or "default"

    def list_daemons(self) -> list:
        """List all registered daemon PIDs for this project"""
        pid_dir = Daemon.PID_DIR
        daemons = []

        if not pid_dir.exists():
            return daemons

        for pidfile in pid_dir.glob(f"*-{self.project}.pid"):
            daemon_name = pidfile.stem.rsplit(f"-{self.project}", 1)[0]
            pid = None
            running = False

            try:
                pid = int(pidfile.read_text().strip())
                running = self._is_running(pid)
            except (ValueError, FileNotFoundError):
                pass

            daemons.append({
                "name": daemon_name,
                "pid": pid,
                "running": running,
                "pidfile": str(pidfile),
            })

        return daemons

    def _is_running(self, pid: int) -> bool:
        """Check if PID is running"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def status_all(self) -> dict:
        """Get status of all daemons"""
        daemons = self.list_daemons()
        return {
            "project": self.project,
            "daemons": daemons,
            "total": len(daemons),
            "running": sum(1 for d in daemons if d["running"]),
        }

    def stop_all(self, timeout: int = 30):
        """Stop all daemons for this project"""
        for daemon in self.list_daemons():
            if daemon["running"] and daemon["pid"]:
                print(f"Stopping {daemon['name']}...")
                try:
                    os.kill(daemon["pid"], signal.SIGTERM)
                except OSError:
                    pass

        # Wait for all to stop
        for _ in range(timeout):
            running = [d for d in self.list_daemons() if d["running"]]
            if not running:
                print("All daemons stopped")
                return
            time.sleep(1)

        # Force kill remaining
        for daemon in self.list_daemons():
            if daemon["running"] and daemon["pid"]:
                print(f"Force killing {daemon['name']}...")
                try:
                    os.kill(daemon["pid"], signal.SIGKILL)
                except OSError:
                    pass


# ============================================================================
# WATCHDOG - Auto-restart dead daemons + alerting
# ============================================================================

class DaemonWatchdog:
    """
    Watchdog that monitors all factory daemons.

    - Checks PID files every interval
    - Detects daemons that died unexpectedly (PID file exists, process dead)
    - Restarts them automatically
    - Logs CRITICAL alerts
    - Writes alerts to file for external monitoring
    """

    PID_DIR = Daemon.PID_DIR
    LOG_DIR = Daemon.LOG_DIR
    ALERT_FILE = Daemon.BASE_DIR / "data" / "alerts.jsonl"

    # Map daemon names to their restart commands
    RESTART_COMMANDS = {
        "cycle": "factory {project} cycle start",
        "wiggum-tdd": "factory {project} wiggum start",
        "wiggum-deploy": "factory {project} deploy start --batch",
    }

    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.logger = logging.getLogger("watchdog")
        self.logger.setLevel(logging.INFO)
        if not self.logger.handlers:
            handler = RotatingFileHandler(
                self.LOG_DIR / "watchdog.log",
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
            )
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s] [WATCHDOG] [%(levelname)s] %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            ))
            self.logger.addHandler(handler)
        self._restart_counts = {}  # daemon_name -> count (prevent restart loops)
        self._restart_cooldown = {}  # daemon_name -> last_restart_time

    def _is_running(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _alert(self, daemon_name: str, message: str, level: str = "CRITICAL"):
        """Log alert and write to alerts file."""
        self.logger.critical(f"[{daemon_name}] {message}")

        # Write structured alert
        import json
        alert = {
            "timestamp": datetime.now().isoformat(),
            "daemon": daemon_name,
            "level": level,
            "message": message,
        }
        try:
            self.ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ALERT_FILE, "a") as f:
                f.write(json.dumps(alert) + "\n")
        except Exception as e:
            self.logger.error(f"Failed to write alert: {e}")

    def _should_restart(self, daemon_name: str) -> bool:
        """Check cooldown and max restart count to prevent restart loops."""
        now = datetime.now()

        # Max 3 restarts per daemon per hour
        count = self._restart_counts.get(daemon_name, 0)
        if count >= 3:
            last = self._restart_cooldown.get(daemon_name)
            if last and (now - last).total_seconds() < 3600:
                self._alert(daemon_name,
                    f"RESTART LOOP DETECTED: {count} restarts in 1h. Manual intervention required.",
                    level="EMERGENCY")
                return False
            # Reset after cooldown
            self._restart_counts[daemon_name] = 0

        return True

    def _restart_daemon(self, daemon_name: str, project: str):
        """Restart a dead daemon."""
        import subprocess

        if not self._should_restart(daemon_name):
            return False

        # Find the daemon type from the name
        daemon_type = None
        for dtype in self.RESTART_COMMANDS:
            if daemon_name.startswith(dtype):
                daemon_type = dtype
                break

        if not daemon_type:
            self._alert(daemon_name, f"Unknown daemon type, cannot restart: {daemon_name}")
            return False

        cmd = self.RESTART_COMMANDS[daemon_type].format(project=project)
        self._alert(daemon_name, f"RESTARTING: {cmd}")

        try:
            # Clean stale PID file first
            pidfile = self.PID_DIR / f"{daemon_name}.pid"
            if pidfile.exists():
                pidfile.unlink()

            result = subprocess.run(
                cmd.split(),
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Daemon.BASE_DIR),
            )

            if result.returncode == 0:
                self._alert(daemon_name, f"RESTARTED OK: {cmd}", level="WARNING")
                self._restart_counts[daemon_name] = self._restart_counts.get(daemon_name, 0) + 1
                self._restart_cooldown[daemon_name] = datetime.now()
                return True
            else:
                self._alert(daemon_name, f"RESTART FAILED (exit {result.returncode}): {result.stderr[:200]}")
                return False
        except Exception as e:
            self._alert(daemon_name, f"RESTART ERROR: {e}")
            return False

    def check_all(self) -> list:
        """
        Check all daemons, restart dead ones.

        Returns list of actions taken.
        """
        actions = []

        if not self.PID_DIR.exists():
            return actions

        for pidfile in self.PID_DIR.glob("*.pid"):
            daemon_name = pidfile.stem
            try:
                pid = int(pidfile.read_text().strip())
            except (ValueError, FileNotFoundError):
                continue

            if not self._is_running(pid):
                # Extract project from daemon name (e.g., "cycle-veligo" -> "veligo")
                parts = daemon_name.rsplit("-", 1)
                project = parts[-1] if len(parts) > 1 else "unknown"

                self._alert(daemon_name,
                    f"DAEMON DEAD: PID {pid} not running. PID file exists = unexpected crash.")

                restarted = self._restart_daemon(daemon_name, project)
                actions.append({
                    "daemon": daemon_name,
                    "pid": pid,
                    "action": "restarted" if restarted else "restart_failed",
                    "project": project,
                })

        return actions

    def run_once(self) -> list:
        """Single watchdog check. Returns actions taken."""
        self.logger.info("Watchdog check started")
        actions = self.check_all()
        if actions:
            self.logger.warning(f"Watchdog actions: {len(actions)} daemons handled")
        else:
            self.logger.info("All daemons healthy")
        return actions

    async def run_loop(self):
        """Continuous watchdog loop."""
        self.logger.info(f"Watchdog started (interval={self.check_interval}s)")
        while True:
            try:
                self.check_all()
            except Exception as e:
                self.logger.error(f"Watchdog error: {e}")
            await asyncio.sleep(self.check_interval)


# ============================================================================
# CLI HELPERS
# ============================================================================

def print_daemon_status(status: dict):
    """Pretty print daemon status"""
    if status.get("running"):
        icon = "🟢"
        state = "RUNNING"
    else:
        icon = "🔴"
        state = "STOPPED"

    print(f"{icon} {status['name']}: {state}")
    if status.get("pid"):
        print(f"   PID: {status['pid']}")
    if status.get("uptime"):
        print(f"   Uptime: {status['uptime']}")
    print(f"   Log: {status['logfile']}")


def print_all_status(manager_status: dict):
    """Pretty print all daemons status"""
    print(f"\n{'=' * 50}")
    print(f"Macaron Agent Platform Daemons - {manager_status['project']}")
    print(f"{'=' * 50}")

    if not manager_status["daemons"]:
        print("No daemons registered")
        return

    for d in manager_status["daemons"]:
        icon = "🟢" if d["running"] else "🔴"
        state = "RUNNING" if d["running"] else "STOPPED"
        pid_str = f"PID {d['pid']}" if d["pid"] else "no PID"
        print(f"{icon} {d['name']}: {state} ({pid_str})")

    print(f"\nTotal: {manager_status['running']}/{manager_status['total']} running")


# ============================================================================
# ORPHAN CLEANUP WATCHDOG
# ============================================================================

async def orphan_cleanup_watchdog(
    interval: int = 300,
    min_age: int = 600,
    log_fn: Optional[Callable[[str, str], None]] = None,
):
    """
    Periodic cleanup of orphaned opencode processes.

    Scans for opencode processes with parent=1 (reparented to init) and kills
    them if older than min_age seconds. This prevents memory leaks from stuck
    processes that escape the normal killpg() cleanup during fallback.

    Args:
        interval: Seconds between cleanup runs (default 5 minutes)
        min_age: Minimum age in seconds before killing orphan (default 10 minutes)
        log_fn: Optional log function(msg, level)
    """
    import asyncio
    import signal

    def log(msg: str, level: str = "INFO"):
        if log_fn:
            log_fn(msg, level)

    log("[WATCHDOG] Orphan cleanup started (interval={}s, min_age={}s)".format(interval, min_age), "INFO")

    while True:
        await asyncio.sleep(interval)

        try:
            # Find opencode processes with parent info
            proc = await asyncio.create_subprocess_shell(
                "ps -eo pid,ppid,etime,command | grep 'opencode run' | grep -v grep",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            stdout, _ = await proc.communicate()

            orphans = []
            for line in stdout.decode().strip().split('\n'):
                if not line:
                    continue

                parts = line.split(None, 3)
                if len(parts) < 3:
                    continue

                pid, ppid = int(parts[0]), int(parts[1])
                etime = parts[2]

                if ppid == 1:  # Orphan (reparented to init)
                    # Parse etime: "03:55:31" or "1-03:55:31" or "31" (seconds only)
                    try:
                        if '-' in etime:  # days-HH:MM:SS
                            days, hms = etime.split('-')
                            h, m, s = hms.split(':')
                            age_sec = int(days) * 86400 + int(h) * 3600 + int(m) * 60 + int(s)
                        elif etime.count(':') == 2:  # HH:MM:SS
                            h, m, s = etime.split(':')
                            age_sec = int(h) * 3600 + int(m) * 60 + int(s)
                        elif etime.count(':') == 1:  # MM:SS
                            m, s = etime.split(':')
                            age_sec = int(m) * 60 + int(s)
                        else:  # seconds only
                            age_sec = int(etime)
                    except (ValueError, AttributeError):
                        continue

                    # Kill if older than min_age
                    if age_sec > min_age:
                        orphans.append((pid, age_sec))

            if orphans:
                log(f"[WATCHDOG] Found {len(orphans)} orphan opencode processes", "WARN")
                for pid, age in orphans:
                    try:
                        os.kill(pid, signal.SIGKILL)
                        log(f"[WATCHDOG] Killed orphan PID {pid} (age {age}s)", "INFO")
                    except ProcessLookupError:
                        pass  # Already dead
                    except Exception as e:
                        log(f"[WATCHDOG] Failed to kill orphan PID {pid}: {e}", "ERROR")

        except Exception as e:
            log(f"[WATCHDOG] Cleanup error: {e}", "ERROR")


def start_watchdog_daemon(interval: int = 300, min_age: int = 600):
    """
    Start orphan cleanup watchdog as background task.

    Call this once at Factory startup (e.g., in cycle_worker or daemon manager).
    """
    from core.log import get_logger
    logger = get_logger("watchdog")

    def log_fn(msg: str, level: str):
        getattr(logger, level.lower(), logger.info)(msg)

    # Run watchdog in event loop
    loop = asyncio.get_event_loop()
    loop.create_task(orphan_cleanup_watchdog(interval, min_age, log_fn))
