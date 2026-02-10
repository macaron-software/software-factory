#!/usr/bin/env python3
"""
Session Keep-Alive Daemon — prevents bank sessions from expiring
by doing a full Page.reload() every 90s on each bank tab.

Usage:
    python3 scrapers/session_keepalive.py          # foreground
    python3 scrapers/session_keepalive.py --daemon  # background

Kill:
    kill $(cat /tmp/session-keepalive.pid)
"""
import asyncio
import json
import os
import sys
import signal
import urllib.request
from datetime import datetime

CDP_URL = "http://localhost:18800"
INTERVAL = 240  # 4 minutes between checks
LOG_FILE = "/tmp/session-keepalive.log"
PID_FILE = "/tmp/session-keepalive.pid"

BANK_KEYS = ["credit-agricole", "bourso", "interactive", "traderepublic"]

# URL patterns that indicate a logged-out session
LOGOUT_PATTERNS = {
    "interactive":      ["AmAuthentication", "sso/Login", "login"],
    "traderepublic":    ["/login"],
    "credit-agricole":  ["particulier.html", "acceder-a-mes-comptes"],
    "bourso":           ["connexion", "saisie-mot-de-pas"],
}


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def detect_bank(url: str) -> str | None:
    for key in BANK_KEYS:
        if key in url:
            return key
    return None


def is_logged_out(bank: str, url: str) -> bool:
    """Check if the URL indicates the bank session has expired."""
    patterns = LOGOUT_PATTERNS.get(bank, [])
    return any(p in url for p in patterns)


async def reload_tab(ws_url: str, bank: str) -> str:
    """Full Page.reload on a tab. Returns status string."""
    import websockets
    try:
        async with websockets.connect(ws_url, open_timeout=5, close_timeout=3) as ws:
            await ws.send(json.dumps({
                "id": 1, "method": "Page.reload",
                "params": {"ignoreCache": False}
            }))
            resp = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            if "error" in resp:
                return f"❌ {resp['error'].get('message', '?')}"
            return "✅ reloaded"
    except asyncio.TimeoutError:
        return "⏱ timeout"
    except Exception as e:
        return f"❌ {type(e).__name__}"


API_PORT = 8000
WEB_PORT = 3000
FINARY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def check_restart_servers():
    """Check API and frontend, restart if down."""
    import subprocess

    # Check API
    try:
        urllib.request.urlopen(f"http://localhost:{API_PORT}/api/v1/status", timeout=5)
    except Exception:
        log(f"⚠ API on :{API_PORT} is DOWN — restarting...")
        subprocess.Popen(
            ["python3", os.path.join(FINARY_DIR, "backend", "api_server.py")],
            env={**os.environ, "PYTHONPATH": FINARY_DIR},
            stdout=open("/tmp/finary-api.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log("  → API restarted")

    # Check Frontend
    try:
        urllib.request.urlopen(f"http://localhost:{WEB_PORT}/", timeout=5)
    except Exception:
        log(f"⚠ Frontend on :{WEB_PORT} is DOWN — restarting...")
        subprocess.Popen(
            ["npx", "next", "start", "-p", str(WEB_PORT)],
            cwd=os.path.join(FINARY_DIR, "frontend", "web"),
            env={**os.environ, "PORT": str(WEB_PORT)},
            stdout=open("/tmp/finary-web.log", "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        log("  → Frontend restarted")


async def keepalive_loop():
    log(f"Session keepalive started — reload every {INTERVAL}s + logout detection + server watchdog")
    relogin_notified = set()  # avoid spamming notifications

    while True:
        try:
            raw = urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=5).read()
            pages = json.loads(raw)
        except Exception as e:
            log(f"CDP unreachable: {e}")
            await asyncio.sleep(INTERVAL)
            continue

        results = []
        logged_out_banks = []

        for p in pages:
            url = p.get("url", "")
            bank = detect_bank(url)
            if not bank:
                continue
            if p.get("type", "page") != "page":
                continue
            if "googletagmanager" in url or "sw.js" in url:
                continue
            ws_url = p.get("webSocketDebuggerUrl", "")
            if not ws_url:
                continue

            short_url = url.split("//", 1)[-1][:50]

            if is_logged_out(bank, url):
                results.append(f"{bank:15} ⚠️  LOGGED OUT ({short_url})")
                logged_out_banks.append(bank)
            else:
                status = await reload_tab(ws_url, bank)
                results.append(f"{bank:15} {status} ({short_url})")

        if results:
            log(" | ".join(results))
        else:
            log("No bank tabs found")

        # Notify about logged-out banks (once per bank)
        new_logouts = [b for b in logged_out_banks if b not in relogin_notified]
        if new_logouts:
            names = ", ".join(new_logouts)
            log(f"🔐 Sessions expired: {names} — run: python3 scrapers/daily_sync.py")
            try:
                import subprocess
                subprocess.run([
                    "osascript", "-e",
                    f'display notification "Sessions expirées: {names}" with title "Finary — Re-login nécessaire"'
                ], timeout=5)
            except Exception:
                pass
            relogin_notified.update(new_logouts)

        # Reset notification when banks come back online
        for bank in list(relogin_notified):
            if bank not in logged_out_banks:
                relogin_notified.discard(bank)

        # Watchdog: restart API/Frontend if crashed
        check_restart_servers()

        await asyncio.sleep(INTERVAL)


def daemonize():
    """Fork to background."""
    if os.path.exists(PID_FILE):
        try:
            old_pid = int(open(PID_FILE).read().strip())
            os.kill(old_pid, signal.SIGTERM)
            log(f"Killed old daemon (PID {old_pid})")
        except (ProcessLookupError, ValueError):
            pass

    pid = os.fork()
    if pid > 0:
        print(f"Session keepalive daemon started (PID {pid})")
        print(f"  Log: {LOG_FILE}")
        print(f"  PID: {PID_FILE}")
        print(f"  Kill: kill $(cat {PID_FILE})")
        sys.exit(0)

    os.setsid()
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))

    sys.stdout = open(LOG_FILE, "a", buffering=1)
    sys.stderr = sys.stdout


def main():
    if "--daemon" in sys.argv:
        daemonize()
    try:
        asyncio.run(keepalive_loop())
    except KeyboardInterrupt:
        log("Stopped")


if __name__ == "__main__":
    main()
