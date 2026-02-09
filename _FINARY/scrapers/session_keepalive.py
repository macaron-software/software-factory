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
INTERVAL = 90  # seconds between reloads
LOG_FILE = "/tmp/session-keepalive.log"
PID_FILE = "/tmp/session-keepalive.pid"

BANK_KEYS = ["credit-agricole", "bourso", "interactive", "traderepublic"]


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def detect_bank(url: str) -> str | None:
    for key in BANK_KEYS:
        if key in url:
            return key
    return None


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


async def keepalive_loop():
    log(f"Session keepalive started — Page.reload every {INTERVAL}s")
    while True:
        try:
            raw = urllib.request.urlopen(f"{CDP_URL}/json/list", timeout=5).read()
            pages = json.loads(raw)
        except Exception as e:
            log(f"CDP unreachable: {e}")
            await asyncio.sleep(INTERVAL)
            continue

        results = []
        seen_banks = set()
        for p in pages:
            url = p.get("url", "")
            bank = detect_bank(url)
            if not bank or bank in seen_banks:
                continue
            seen_banks.add(bank)
            ws_url = p.get("webSocketDebuggerUrl", "")
            if not ws_url:
                continue
            status = await reload_tab(ws_url, bank)
            results.append(f"{bank:15} {status}")

        if results:
            log(" | ".join(results))
        else:
            log("No bank tabs found")

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
